"""PDF Processor with Robust JSON Parsing"""
import asyncio
import json
import re
import logging
from typing import List, Dict
from pdf2image import convert_from_path
from config import config

logger = logging.getLogger(__name__)

class PDFProcessor:
    def __init__(self, api_rotator):
        self.api_rotator = api_rotator
        print("✅ PDF Processor initialized")
    
    @staticmethod
    async def pdf_to_images(pdf_path, page_range=None):
        """Convert PDF to images"""
        try:
            if page_range:
                first_page, last_page = page_range
                images = convert_from_path(pdf_path, first_page=first_page, last_page=last_page, dpi=200)
            else:
                images = convert_from_path(pdf_path, dpi=200)
            
            logger.info(f"✅ Converted PDF: {len(images)} images")
            return images
        except Exception as e:
            logger.error(f"❌ PDF conversion error: {e}")
            raise
    
    async def process_images_parallel(self, images, mode, progress_callback=None, user_id=None, context=None, progress_msg=None):
        """Process images with Gemini"""
        all_questions = []
        total = len(images)
        
        for idx, image in enumerate(images, 1):
            if progress_callback:
                await progress_callback(idx, total)
            
            from io import BytesIO
            buffer = BytesIO()
            image.save(buffer, format='JPEG')
            image_data = buffer.getvalue()
            
            questions = await self.process_image_with_gemini(
                image_data, mode, user_id=user_id, context=context,
                progress_msg=progress_msg, image_num=idx, total_images=total
            )
            
            all_questions.extend(questions)
        
        return all_questions
    
    async def process_image_with_gemini(self, image_data, mode, user_id=None, context=None, progress_msg=None, image_num=1, total_images=1):
        """Process with Gemini - ROBUST JSON PARSING"""
        from google.genai import types
        
        async def update_status(msg: str):
            if progress_msg and context and user_id:
                try:
                    await progress_msg.edit_text(msg, parse_mode='Markdown')
                except:
                    pass
        
        try:
            # Get prompt
            if mode == 'extraction':
                from prompts.extraction_prompt import get_extraction_prompt
                prompt = get_extraction_prompt()
            else:
                from prompts.generation_prompt import get_generation_prompt
                prompt = get_generation_prompt()
            
            await update_status(f"🤖 *Image {image_num}/{total_images}*\nProcessing...")
            
            # Prepare image
            image_part = types.Part.from_bytes(data=image_data, mime_type="image/jpeg")
            
            # Try with API rotation
            max_retries = len(config.GEMINI_API_KEYS)
            
            for attempt in range(max_retries):
                try:
                    client = self.api_rotator.get_client()
                    
                    response = client.models.generate_content(
                        model=config.GEMINI_MODEL,
                        contents=[prompt, image_part],
                        config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=8000)
                    )
                    
                    break
                    
                except Exception as api_error:
                    error_str = str(api_error)
                    
                    if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
                        self.api_rotator.mark_failure()
                        
                        if attempt < max_retries - 1:
                            await update_status(f"⚠️ *Rate Limit*\nRotating API key...\nAttempt {attempt + 1}/{max_retries}")
                            await asyncio.sleep(2)
                            continue
                        else:
                            await update_status("❌ *All Keys Rate Limited*\n\nWait 1 minute")
                            return []
                    else:
                        await update_status(f"❌ API Error:\n`{error_str[:200]}`")
                        return []
            
            if not response or not response.text:
                await update_status("❌ Empty response")
                return []
            
            # ROBUST JSON PARSING
            text = response.text.strip()
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            
            questions = []
            
            # Strategy 1: Find complete JSON array
            json_match = re.search(r'\[.*\]', text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                try:
                    questions = json.loads(json_str)
                except json.JSONDecodeError:
                    # Strategy 2: Fix trailing commas
                    try:
                        fixed = re.sub(r',(\s*[}\]])', r'\1', json_str)
                        questions = json.loads(fixed)
                    except:
                        # Strategy 3: Extract individual objects
                        try:
                            q_pattern = r'\{[^{}]*"question"[^{}]*?"options"[^{}]*?\}'
                            q_objects = re.findall(q_pattern, text, re.DOTALL)
                            for q_str in q_objects:
                                try:
                                    q = json.loads(q_str)
                                    if 'question' in q and 'options' in q:
                                        questions.append(q)
                                except:
                                    continue
                        except:
                            pass
            
            if not questions:
                await update_status(f"❌ *Image {image_num}/{total_images}*\nNo valid questions")
                return []
            
            await update_status(f"✅ *{image_num}/{total_images}*\nFound {len(questions)}Q")
            
            return questions
        
        except Exception as e:
            await update_status(f"❌ Error:\n`{str(e)[:200]}`")
            logger.error(f"Processing error: {e}", exc_info=True)
            return []
