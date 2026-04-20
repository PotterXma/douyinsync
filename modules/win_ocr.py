import asyncio
from pathlib import Path
from modules.logger import logger
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.graphics.imaging import BitmapDecoder
from winrt.windows.storage import StorageFile

async def _recognize_text_async(image_path: str) -> str:
    try:
        # Load the image using Windows Storage API
        file = await StorageFile.get_file_from_path_async(str(Path(image_path).resolve()))
        stream = await file.open_async(0) # 0 is FileAccessMode.Read
        
        # Decode the image bitmap
        decoder = await BitmapDecoder.create_async(stream)
        software_bitmap = await decoder.get_software_bitmap_async()
        
        # Create OCR Engine with preferred languages
        engine = OcrEngine.try_create_from_user_profile_languages()
        if not engine:
            return ""
            
        # Run recognition
        result = await engine.recognize_async(software_bitmap)
        return result.text
    except Exception as e:
        logger.warning(f"OCR async recognition error: {e}")
        return ""

def get_text_from_image(image_path: str) -> str:
    """
    Extracts text from an image using native Windows 10/11 OCR.
    Runs synchronously, making it easy to call from standard Python code.
    """
    try:
        # If there's already an event loop running, we use it, otherwise run it
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # In an existing loop, use an event thread
            import threading
            result_container = []
            
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                res = new_loop.run_until_complete(_recognize_text_async(image_path))
                result_container.append(res)
                new_loop.close()
                
            t = threading.Thread(target=run_in_thread)
            t.start()
            t.join()
            return result_container[0] if result_container else ""
        else:
            # Main thread fast path
            return asyncio.run(_recognize_text_async(image_path))
    except Exception as e:
        logger.warning(f"Failed to run Windows Native OCR: {e}")
        return ""
