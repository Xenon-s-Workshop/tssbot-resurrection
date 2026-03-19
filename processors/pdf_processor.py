"""
PDF/Image → Questions processor via Gemini AI.
"""

import json
import asyncio
import logging
from typing import List, Dict, Optional
from pathlib import Path
from PIL import Image
from pdf2image import convert_from_path
from google import genai
from config import config
from utils.api_rotator import GeminiAPIRotator
from prompts import get_extraction_prompt, get_generation_prompt

logger = logging.getLogger(__name__)


class PDFProcessor:
    def __init__(self, api_rotator: GeminiAPIRotator):
        self.api_rotator = api_rotator

    # ── PDF → images ─────────────────────────────────────────────────────────

    @staticmethod
    async def pdf_to_images(pdf_path: Path, page_range: Optional[tuple] = None) -> List[Image.Image]:
        try:
            kwargs = {"dpi": 300}
            if page_range:
                kwargs["first_page"], kwargs["last_page"] = page_range
            images = convert_from_path(pdf_path, **kwargs)
            logger.info(f"PDF converted: {len(images)} page(s)")
            return images
        except Exception as e:
            raise Exception(f"Error converting PDF to images: {e}")

    # ── Single image → questions ──────────────────────────────────────────────

    async def process_single_image(
        self, image: Image.Image, image_idx: int, mode: str, retry_count: int = 3
    ) -> tuple:
        prompt = get_extraction_prompt() if mode == "extraction" else get_generation_prompt()

        for attempt in range(retry_count):
            try:
                api_key = self.api_rotator.get_next_key()
                client = genai.Client(api_key=api_key)
                logger.info(f"Processing image {image_idx} (attempt {attempt+1}, mode={mode})")

                response = client.models.generate_content(
                    model=config.GEMINI_MODEL,
                    contents=[prompt, image],
                )
                text = response.text.strip()

                # Strip markdown fences if present
                for fence in ("```json", "```"):
                    if text.startswith(fence):
                        text = text[len(fence):]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

                questions = json.loads(text)
                if not isinstance(questions, list):
                    raise ValueError("Expected JSON array")

                logger.info(f"Image {image_idx}: extracted {len(questions)} question(s)")
                return (image_idx, questions)

            except Exception as e:
                logger.warning(f"Image {image_idx} attempt {attempt+1} failed: {e}")
                if attempt < retry_count - 1:
                    await asyncio.sleep(1 + attempt)

        logger.error(f"Image {image_idx}: all attempts failed")
        return (image_idx, None)

    # ── Batch parallel processing ─────────────────────────────────────────────

    async def process_images_parallel(
        self,
        images: List[Image.Image],
        mode: str,
        progress_callback=None,
    ) -> List[Dict]:
        all_questions: List[Dict] = []
        total = len(images)

        for batch_start in range(0, total, config.MAX_CONCURRENT_IMAGES):
            batch_end = min(batch_start + config.MAX_CONCURRENT_IMAGES, total)
            batch = images[batch_start:batch_end]

            tasks = [
                self.process_single_image(img, batch_start + i + 1, mode)
                for i, img in enumerate(batch)
            ]
            results = await asyncio.gather(*tasks)

            for idx, questions in results:
                if progress_callback:
                    await progress_callback(idx, total)
                if questions:
                    all_questions.extend(questions)

            if batch_end < total:
                await asyncio.sleep(0.2)

        logger.info(f"Total questions extracted: {len(all_questions)}")
        return all_questions
