"""
Script to test YouTube 16:9 1280x720 thumbnail generation using Pillow, including OCR text overlay.
"""
from PIL import Image, ImageFilter, ImageDraw, ImageFont
from pathlib import Path
import platform
import asyncio
from modules.win_ocr import _recognize_text_async

def make_youtube_thumbnail(input_path, output_path):
    print(f"Processing {input_path} -> {output_path}")
    target_w, target_h = 1280, 720
    
    with Image.open(input_path) as img:
        img = img.convert("RGB")
        
        # Extract Text
        ocr_text = ""
        try:
            print("Reading text via Windows OCR...")
            raw_text = asyncio.run(_recognize_text_async(input_path))
            if raw_text:
                ocr_text = " ".join(raw_text.split())
                print(f"-> Extracted: {ocr_text}")
        except Exception as e:
            print(f"OCR failed: {e}")
            
    # Load Template
    og_template = Path("D:/project/douyin搬运/dist/og.jpg")
    if og_template.exists():
        bg_img = Image.open(og_template).convert('RGB')
    else:
        print(f"Template {og_template} not found! Falling back to black canvas.")
        bg_img = Image.new('RGB', (1280, 720), (0, 0, 0))
        
    target_w, target_h = bg_img.size
        
    # 3. Draw OCR Text Overlay
    if ocr_text:
        draw = ImageDraw.Draw(bg_img)
        font_path = ""
        if platform.system() == "Windows":
            font_path = "C:\\Windows\\Fonts\\simkai.ttf"
            if not Path(font_path).exists():
                font_path = "C:\\Windows\\Fonts\\msyhbd.ttc"
                
        if font_path:
            font = ImageFont.truetype(font_path, 80)
        else:
            font = ImageFont.load_default()
            
        max_len = 16
        lines = [ocr_text[i:i+max_len] for i in range(0, len(ocr_text), max_len)][:2]
        
        start_y = (target_h - (len(lines) * 100)) / 2
        
        for idx, line in enumerate(lines):
            # Left alignment, starting around 10%~15% from the left edge
            text_x = 180 
            text_y = start_y + (idx * 100)
            
            draw.text((text_x + 4, text_y + 4), line, font=font, fill=(0,0,0))
            draw.text((text_x, text_y), line, font=font, fill=(255, 235, 59))
        print("Painted text onto template successfully.")
        
    bg_img.save(output_path, "JPEG", quality=95)
    print("Success!")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:
        make_youtube_thumbnail(sys.argv[1], sys.argv[2])
    else:
        root = Path(__file__).parent
        img_found = False
        for f in (root / "dist" / "DouyinSync" / "downloads").rglob("*.jpg"):
            if "3x4" not in f.name and "4x3" not in f.name and "yt" not in f.name:
                make_youtube_thumbnail(str(f), str(root / "dist" / "og.jpg"))
                img_found = True
                break
        if not img_found:
            print("No test images found in downloads to test.")
