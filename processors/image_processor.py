"""
Image Processor - Image loading utilities
"""

from pathlib import Path
from PIL import Image

class ImageProcessor:
    @staticmethod
    def is_image_file(filename: str) -> bool:
        """Check if file is an image"""
        return any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif'])
    
    @staticmethod
    async def load_image(image_path: Path) -> Image.Image:
        """Load image from path"""
        return Image.open(image_path)
