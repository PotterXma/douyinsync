"""
Test Windows Native OCR
"""
import asyncio
import os
from pathlib import Path
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.graphics.imaging import BitmapDecoder
from winrt.windows.storage import StorageFile

async def recognize_text(image_path: str):
    print(f"Loading {image_path}")
    file = await StorageFile.get_file_from_path_async(str(Path(image_path).resolve()))
    stream = await file.open_async(0) # 0 is FileAccessMode.Read
    
    decoder = await BitmapDecoder.create_async(stream)
    software_bitmap = await decoder.get_software_bitmap_async()
    
    engine = OcrEngine.try_create_from_user_profile_languages()
    if not engine:
        print("Default language OCR engine not found.")
        return ""
        
    result = await engine.recognize_async(software_bitmap)
    print("Recognized Text:")
    print(result.text)
    return result.text

if __name__ == "__main__":
    import sys
    root = Path(__file__).parent
    
    # Try to find an image to test on
    test_img = None
    if len(sys.argv) > 1:
        test_img = sys.argv[1]
    else:
        for f in (root / "dist" / "DouyinSync" / "downloads").rglob("*.jpg"):
            if "3x4" not in f.name and "4x3" not in f.name:
                test_img = str(f)
                break
                
    if test_img:
        asyncio.run(recognize_text(test_img))
    else:
        print("No image found.")
