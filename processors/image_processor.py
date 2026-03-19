import logging
from pathlib import Path
from PIL import Image

logger = logging.getLogger(__name__)


class ImageProcessor:
    @staticmethod
    async def load_image(path: Path) -> Image.Image:
        try:
            return Image.open(path).convert("RGB")
        except Exception as e:
            logger.error(f"Failed to load image {path}: {e}")
            raise
