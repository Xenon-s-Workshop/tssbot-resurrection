"""
PDF Processor - WITH USER ERROR REPORTING
Processes PDFs and images with Gemini AI
Sends detailed error messages to users in Telegram
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
        context=None
    ) -> List[Dict]:
        """
        Process multiple images in parallel
        NOW WITH: User error reporting
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
            
            # Process with Gemini - WITH ERROR REPORTING
            questions = await self.process_image_with_gemini(
                image_data, 
                mode,
                user_id=user_id,
                context=context
            )
            
            all_questions.extend(questions)
        
        return all_questions
    
    async def process_image_with_gemini(
        self, 
        image_data: bytes, 
        mode: str, 
        user_id: int = None, 
        context = None
    ) -> List[Dict]:
        """Process image with Gemini AI - with user error reporting"""
        import json
        import re
        from google.genai import types
        
        async def send_error(msg: str):
            """Send error message to user if context available"""
            if context and user_id:
                try:
                    await context.bot.send_message(user_id, msg, parse_mode='Markdown')
                except:
                    pass
            logger.error(msg)
        
        try:
            # Get prompt
            if mode == 'extraction':
                from prompts.extraction_prompt import get_extraction_prompt
                prompt = get_extraction_prompt()
            else:
                from prompts.generation_prompt import get_generation_prompt
                prompt = get_generation_prompt()
            
            # Get current client from rotator
            client = self.api_rotator.get_client()
            
            # Send status to user
            if context and user_id:
                try:
                    await context.bot.send_message(
                        user_id,
                        f"🤖 Calling Gemini API...\n"
                        f"Model: `{config.GEMINI_MODEL}`\n"
                        f"Mode: {mode}",
                        parse_mode='Markdown'
                    )
                except:
                    pass
            
            # Prepare image part
            image_part = types.Part.from_bytes(
                data=image_data,
                mime_type="image/jpeg"
            )
            
            # Make API call with timeout
            try:
                response = client.models.generate_content(
                    model=config.GEMINI_MODEL,
                    contents=[prompt, image_part],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=8000
                    )
                )
            except Exception as api_error:
                error_str = str(api_error)
                
                # Check for specific errors
                if "404" in error_str or "not found" in error_str.lower():
                    await send_error(
                        f"❌ **Invalid Model Name**\n\n"
                        f"Model `{config.GEMINI_MODEL}` doesn't exist!\n\n"
                        f"✅ Valid models:\n"
                        f"• `gemini-2.5-flash`\n"
                        f"• `gemini-2.5-flash-lite`\n"
                        f"• `gemini-2.5-pro`\n\n"
                        f"Update your config.py"
                    )
                elif "403" in error_str or "permission" in error_str.lower():
                    await send_error(
                        f"❌ **API Key Permission Denied**\n\n"
                        f"Your API key doesn't have permission.\n\n"
                        f"Check your key at:\n"
                        f"https://aistudio.google.com/apikey"
                    )
                elif "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
                    await send_error(
                        f"❌ **Rate Limit Hit**\n\n"
                        f"Free tier limits:\n"
                        f"• 10 requests/min\n"
                        f"• 250 requests/day\n\n"
                        f"⏰ Wait a minute and try again."
                    )
                elif "invalid" in error_str.lower() and "key" in error_str.lower():
                    await send_error(
                        f"❌ **Invalid API Key**\n\n"
                        f"Your API key is invalid or expired.\n\n"
                        f"Get new keys at:\n"
                        f"https://aistudio.google.com/apikey"
                    )
                else:
                    await send_error(
                        f"❌ **Gemini API Error**\n\n"
                        f"```\n{error_str[:300]}\n```"
                    )
                
                # Rotate key
                self.api_rotator.mark_failure()
                return []
            
            # Check response
            if not response or not response.text:
                await send_error(
                    f"❌ **Empty Response from Gemini**\n\n"
                    f"The AI returned no text.\n"
                    f"Try a clearer image."
                )
                return []
            
            # Send success status
            if context and user_id:
                try:
                    await context.bot.send_message(
                        user_id,
                        f"✅ Got response from Gemini\n"
                        f"📄 Length: {len(response.text)} chars\n"
                        f"🔍 Parsing questions...",
                        parse_mode='Markdown'
                    )
                except:
                    pass
            
            # Parse JSON response
            text = response.text.strip()
            
            # Remove markdown code blocks if present
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            
            # Try to find JSON array in response
            json_match = re.search(r'\[.*\]', text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                try:
                    questions = json.loads(json_str)
                    
                    if not questions:
                        await send_error(
                            f"❌ **No Questions in Response**\n\n"
                            f"Gemini responded but found 0 questions.\n"
                            f"Try a clearer image with visible text."
                        )
                        return []
                    
                    # Send success
                    if context and user_id:
                        try:
                            await context.bot.send_message(
                                user_id,
                                f"✅ **Found {len(questions)} questions!**",
                                parse_mode='Markdown'
                            )
                        except:
                            pass
                    
                    return questions
                
                except json.JSONDecodeError as e:
                    await send_error(
                        f"❌ **JSON Parse Error**\n\n"
                        f"Gemini returned invalid JSON.\n\n"
                        f"Error: `{str(e)[:100]}`"
                    )
                    return []
            else:
                # No JSON found in response
                await send_error(
                    f"❌ **No JSON Array Found**\n\n"
                    f"Gemini response format invalid.\n\n"
                    f"First 300 chars:\n"
                    f"```\n{text[:300]}\n```"
                )
                return []
        
        except Exception as e:
            await send_error(
                f"❌ **Unexpected Error**\n\n"
                f"```\n{str(e)[:300]}\n```"
            )
            logger.error(f"PDF processing error: {e}", exc_info=True)
            return []
