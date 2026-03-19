"""Image Processing Utilities"""
from PIL import Image

class ImageProcessor:
    @staticmethod
    async def load_image(path):
        """Load image from path"""
        try:
            return Image.open(path)
        except Exception as e:
            print(f"❌ Image load error: {e}")
            raise
