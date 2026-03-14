"""
PDF Processor - WITH AUTO KEY ROTATION & SINGLE MESSAGE EDITING
Processes PDFs and images with Gemini AI
Automatically rotates API keys on rate limits
"""

import asyncio
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
                images = convert_from_path(
                    pdf_path,
                    first_page=first_page,
                    last_page=last_page,
                    dpi=200
                )
            else:
                images = convert_from_path(pdf_path, dpi=200)
            
            logger.info(f"✅ Converted PDF to {len(images)} images")
            return images
        except Exception as e:
            logger.error(f"❌ PDF conversion error: {e}")
            raise
    
    async def process_images_parallel(
        self, 
        images: List, 
        mode: str, 
        progress_callback=None, 
        user_id: int = None, 
        context=None,
        progress_msg=None  # ← NEW: Message to edit
    ) -> List[Dict]:
        """
        Process multiple images in parallel
        Edits SINGLE message for all progress updates
        Auto-rotates API keys on rate limit
        """
        all_questions = []
        total = len(images)
        
        for idx, image in enumerate(images, 1):
            # Call progress callback
            if progress_callback:
                await progress_callback(idx, total)
            
            # Convert image to bytes
            from io import BytesIO
            buffer = BytesIO()
            image.save(buffer, format='JPEG')
            image_data = buffer.getvalue()
            
            # Process with Gemini - WITH SINGLE MESSAGE EDITING
            questions = await self.process_image_with_gemini(
                image_data, 
                mode,
                user_id=user_id,
                context=context,
                progress_msg=progress_msg,  # ← Pass message
                image_num=idx,
                total_images=total
            )
            
            all_questions.extend(questions)
        
        return all_questions
    
    async def process_image_with_gemini(
        self, 
        image_data: bytes, 
        mode: str, 
        user_id: int = None, 
        context = None,
        progress_msg = None,  # ← NEW: Single message to edit
        image_num: int = 1,
        total_images: int = 1
    ) -> List[Dict]:
        """
        Process image with Gemini AI
        EDITS SINGLE MESSAGE for all updates
        AUTO-ROTATES API key on rate limit
        """
        import json
        import re
        from google.genai import types
        
        async def update_status(msg: str):
            """Update status in single message"""
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
            
            # Update status
            await update_status(
                f"🤖 *Processing Image {image_num}/{total_images}*\n\n"
                f"📡 Calling Gemini API...\n"
                f"Model: `{config.GEMINI_MODEL}`\n"
                f"Mode: {mode}"
            )
            
            # Prepare image part
            image_part = types.Part.from_bytes(
                data=image_data,
                mime_type="image/jpeg"
            )
            
            # ===== TRY WITH AUTO KEY ROTATION =====
            max_retries = len(config.GEMINI_API_KEYS)  # Try all keys
            
            for attempt in range(max_retries):
                try:
                    # Get current client
                    client = self.api_rotator.get_client()
                    
                    # Make API call
                    response = client.models.generate_content(
                        model=config.GEMINI_MODEL,
                        contents=[prompt, image_part],
                        config=types.GenerateContentConfig(
                            temperature=0.1,
                            max_output_tokens=8000
                        )
                    )
                    
                    # Success! Break retry loop
                    break
                    
                except Exception as api_error:
                    error_str = str(api_error)
                    
                    # Check for rate limit
                    if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
                        # Auto-rotate to next key
                        self.api_rotator.mark_failure()
                        
                        if attempt < max_retries - 1:
                            await update_status(
                                f"⚠️ *Rate Limit Hit*\n\n"
                                f"🔄 Rotating to next API key...\n"
                                f"Attempt {attempt + 1}/{max_retries}"
                            )
                            await asyncio.sleep(2)  # Brief pause
                            continue  # Try next key
                        else:
                            await update_status(
                                f"❌ *All API Keys Rate Limited*\n\n"
                                f"Free tier limits:\n"
                                f"• 10 requests/min\n"
                                f"• 250 requests/day\n\n"
                                f"⏰ Wait a minute and try again."
                            )
                            return []
                    
                    # Other errors
                    elif "404" in error_str or "not found" in error_str.lower():
                        await update_status(
                            f"❌ *Invalid Model Name*\n\n"
                            f"Model `{config.GEMINI_MODEL}` doesn't exist!\n\n"
                            f"✅ Valid models:\n"
                            f"• `gemini-2.5-flash`\n"
                            f"• `gemini-2.5-flash-lite`\n"
                            f"• `gemini-2.5-pro`"
                        )
                        return []
                    
                    elif "403" in error_str or "permission" in error_str.lower():
                        await update_status(
                            f"❌ *API Key Permission Denied*\n\n"
                            f"Your API key doesn't have permission.\n\n"
                            f"Check your key at:\n"
                            f"https://aistudio.google.com/apikey"
                        )
                        return []
                    
                    elif "invalid" in error_str.lower() and "key" in error_str.lower():
                        await update_status(
                            f"❌ *Invalid API Key*\n\n"
                            f"Your API key is invalid or expired.\n\n"
                            f"Get new keys at:\n"
                            f"https://aistudio.google.com/apikey"
                        )
                        return []
                    
                    else:
                        await update_status(
                            f"❌ *Gemini API Error*\n\n"
                            f"```\n{error_str[:300]}\n```"
                        )
                        return []
            
            # Check response
            if not response or not response.text:
                await update_status(
                    f"❌ *Empty Response from Gemini*\n\n"
                    f"The AI returned no text.\n"
                    f"Try a clearer image."
                )
                return []
            
            # Update status
            await update_status(
                f"✅ *Image {image_num}/{total_images} Processed*\n\n"
                f"📄 Response: {len(response.text)} chars\n"
                f"🔍 Parsing questions..."
            )
            
            # Parse JSON response
            text = response.text.strip()
            
            # Remove markdown code blocks
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            
            # Try to find JSON array
            json_match = re.search(r'\[.*\]', text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                try:
                    questions = json.loads(json_str)
                    
                    if not questions:
                        await update_status(
                            f"⚠️ *Image {image_num}/{total_images}*\n\n"
                            f"No questions found in this image."
                        )
                        return []
                    
                    # Success message
                    await update_status(
                        f"✅ *Image {image_num}/{total_images}*\n\n"
                        f"Found {len(questions)} questions!"
                    )
                    
                    return questions
                
                except json.JSONDecodeError as e:
                    await update_status(
                        f"❌ *JSON Parse Error*\n\n"
                        f"Image {image_num}/{total_images}\n"
                        f"Error: `{str(e)[:100]}`"
                    )
                    return []
            else:
                await update_status(
                    f"❌ *No JSON Found*\n\n"
                    f"Image {image_num}/{total_images}\n"
                    f"First 300 chars:\n"
                    f"```\n{text[:300]}\n```"
                )
                return []
        
        except Exception as e:
            await update_status(
                f"❌ *Unexpected Error*\n\n"
                f"Image {image_num}/{total_images}\n"
                f"```\n{str(e)[:300]}\n```"
            )
            logger.error(f"PDF processing error: {e}", exc_info=True)
            return []
