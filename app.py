import os
import zipfile
import uuid
import shutil
import math
from flask import Flask, render_template, request, send_file, after_this_request
from werkzeug.utils import secure_filename
from PIL import Image, ImageSequence, ImageChops, ImageStat

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB Limit

# --- IMAGE PROCESSING ENGINE ---

def calculate_psnr(img1, img2):
    try:
        if img1.mode != img2.mode: img2 = img2.convert(img1.mode)
        diff = ImageChops.difference(img1, img2)
        stat = ImageStat.Stat(diff)
        mse = sum(val ** 2 for val in stat.mean) / len(stat.mean)
        if mse == 0: return float('inf')
        return 20 * math.log10(255.0 / math.sqrt(mse))
    except: return 40.0

def optimize_jpeg_iterative(img, output_path, min_psnr=38.5):
    if img.mode in ('RGBA', 'P', 'LA'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3] if len(img.split()) > 3 else None)
        img = background
    else: img = img.convert('RGB')
    
    best_q, low, high = 82, 55, 88
    while low <= high:
        mid = (low + high) // 2
        img.save(output_path, format='JPEG', quality=mid, optimize=True)
        with Image.open(output_path) as tmp:
            if calculate_psnr(img, tmp) >= min_psnr:
                best_q, high = mid, mid - 1
            else: low = mid + 1
    img.save(output_path, format='JPEG', quality=best_q, optimize=True, progressive=True, subsampling="4:2:0")

def optimize_png_hardcore(img, output_path):
    try:
        quantized = img.quantize(colors=256, method=Image.Quantize.MAXCOVERAGE, dither=1)
        quantized.save(output_path, format='PNG', optimize=True, compress_level=9)
    except:
        img.save(output_path, format='PNG', optimize=True, compress_level=9)

def resize_with_lanczos(img, max_w, max_h):
    copy = img.copy()
    copy.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    return copy

# --- WEB ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    files = request.files.getlist('files')
    if not files or files[0].filename == '': return "No files selected", 400

    session_id = str(uuid.uuid4())
    session_dir = os.path.join(UPLOAD_FOLDER, session_id)
    out_dir = os.path.join(session_dir, 'output')
    os.makedirs(out_dir, exist_ok=True)

    resolutions = {'360p': (640, 360), '480p': (854, 480), '540p': (960, 540), '720p': (1280, 720)}

    for file in files:
        fname = secure_filename(file.filename)
        in_path = os.path.join(session_dir, fname)
        file.save(in_path)
        
        base, ext = os.path.splitext(fname)
        ext = ext.lower()

        try:
            with Image.open(in_path) as img:
                for label, (w, h) in resolutions.items():
                    out_fname = f"{base}_{label}{ext}"
                    out_path = os.path.join(out_dir, out_fname)
                    
                    if ext == '.gif' and getattr(img, "is_animated", False):
                        frames = [resize_with_lanczos(f, w, h) for f in ImageSequence.Iterator(img)]
                        frames[0].save(out_path, format='GIF', save_all=True, append_images=frames[1:], optimize=True, duration=img.info.get('duration', 100))
                    else:
                        res = resize_with_lanczos(img, w, h)
                        if ext in ('.jpg', '.jpeg'): optimize_jpeg_iterative(res, out_path)
                        elif ext == '.png': optimize_png_hardcore(res, out_path)
                        elif ext == '.webp': res.save(out_path, format='WEBP', quality=78, method=6)
                        else: res.save(out_path, optimize=True)
        except: continue

    zip_path = os.path.join(UPLOAD_FOLDER, f"images_{session_id}.zip")
    with zipfile.ZipFile(zip_path, 'w') as z:
        for f in os.listdir(out_dir): z.write(os.path.join(out_dir, f), f)
    
    shutil.rmtree(session_dir)

    @after_this_request
    def remove_file(response):
        try: os.remove(zip_path)
        except: pass
        return response

    return send_file(zip_path, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)