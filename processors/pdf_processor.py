"""
PDF Processor - AI image processing
"""

import json
import asyncio
from typing import List, Dict, Optional
from pathlib import Path
from PIL import Image
from pdf2image import convert_from_path
from google import genai
from config import config
from utils.api_rotator import GeminiAPIRotator
from prompts import get_extraction_prompt, get_generation_prompt

class PDFProcessor:
    def __init__(self, api_rotator: GeminiAPIRotator):
        self.api_rotator = api_rotator
    
    @staticmethod
    async def pdf_to_images(pdf_path: Path, page_range: Optional[tuple] = None) -> List[Image.Image]:
        """Convert PDF to images"""
        if page_range:
            return convert_from_path(
                pdf_path,
                first_page=page_range[0],
                last_page=page_range[1],
                dpi=300
            )
        return convert_from_path(pdf_path, dpi=300)
    
    async def process_single_image(self, image: Image.Image, image_idx: int, mode: str, retry_count: int = 3) -> Optional[tuple]:
        """Process single image with AI"""
        for attempt in range(retry_count):
            try:
                api_key = self.api_rotator.get_next_key()
                client = genai.Client(api_key=api_key)
                
                prompt = get_extraction_prompt() if mode == "extraction" else get_generation_prompt()
                response = client.models.generate_content(
                    model=config.GEMINI_MODEL,
                    contents=[prompt, image]
                )
                
                text = response.text.strip()
                
                # Clean JSON
                if text.startswith("```json"):
                    text = text[7:]
                if text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                
                questions = json.loads(text.strip())
                return (image_idx, questions)
                
            except Exception as e:
                print(f"⚠️ Image {image_idx} attempt {attempt + 1} failed: {e}")
                if attempt == retry_count - 1:
                    return (image_idx, None)
                await asyncio.sleep(1)
        
        return (image_idx, None)
    
    async def process_images_parallel(self, images: List[Image.Image], mode: str, progress_callback=None) -> List[Dict]:
        """Process images in parallel with progress"""
        all_questions = []
        total = len(images)
        
        for batch_start in range(0, total, config.MAX_CONCURRENT_IMAGES):
            batch_end = min(batch_start + config.MAX_CONCURRENT_IMAGES, total)
            batch = images[batch_start:batch_end]
            
            # Process batch
            tasks = [
                self.process_single_image(img, batch_start + i + 1, mode)
                for i, img in enumerate(batch)
            ]
            results = await asyncio.gather(*tasks)
            
            # Collect results and update progress
            for idx, questions in results:
                if progress_callback:
                    await progress_callback(idx, total)
                if questions:
                    all_questions.extend(questions)
            
            # Small delay between batches
            if batch_end < total:
                await asyncio.sleep(0.1)
        
        return all_questions
