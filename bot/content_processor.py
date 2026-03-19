"""
Content Processor - FIXED CSV Export
Proper validation and error handling
"""

import json
import asyncio
from typing import List, Dict
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import config
from database import db
from processors.csv_processor import CSVGenerator
from processors.image_processor import ImageProcessor
from processors.quiz_poster import quiz_poster
from processors.pdf_processor import PDFProcessor

class ContentProcessor:
    def __init__(self, bot_handlers):
        self.bot_handlers = bot_handlers

    async def process_content(self, user_id, content_type, content_paths, page_range, mode, context):
        """Process content with descriptive messages"""
        msg = None
        
        try:
            # Convert to images
            if content_type == 'pdf':
                msg = await context.bot.send_message(
                    user_id,
                    f"🔄 **Processing PDF**
"
                    f"Model: `{config.GEMINI_MODEL}`",
                    parse_mode='Markdown'
                )
                
                try:
                    images = await PDFProcessor.pdf_to_images(content_paths[0], page_range)
                except Exception as e:
                    await msg.edit_text(
                        f"❌ **PDF Conversion Failed**

`{str(e)[:150]}`",
                        parse_mode='Markdown'
                    )
                    return
            else:
                msg = await context.bot.send_message(user_id, "🔄 **Processing Images...**")
                images = [await ImageProcessor.load_image(p) for p in content_paths]

            total = len(images)
            
            if total == 0:
                await msg.edit_text("❌ No images found")
                return

            await msg.edit_text(f"✅ {total} images
⚙️ **Processing with AI...**")

            # Progress callback
            async def progress(current, total_pages):
                try:
                    pct = int((current / total_pages) * 100)
                    bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                    await msg.edit_text(
                        f"`[{bar}]` {pct}%
{current}/{total_pages}",
                        parse_mode='Markdown'
                    )
                except:
                    pass

            # Get processor
            processor = self.bot_handlers.get_processor(user_id)
            
            # Process
            try:
                raw_questions = await processor.process_images_parallel(
                    images, mode, progress,
                    user_id=user_id, context=context, progress_msg=msg
                )
            except Exception as e:
                await msg.edit_text(
                    f"❌ **Processing Failed**

`{str(e)[:150]}`",
                    parse_mode='Markdown'
                )
                raise

            if not raw_questions:
                await msg.edit_text("❌ No questions extracted")
                return

            # Normalize
            try:
                questions = self._normalize_questions(raw_questions)
                
                if not questions:
                    await msg.edit_text("❌ No valid questions after normalization")
                    return
            except Exception as e:
                await msg.edit_text(
                    f"❌ **Format Error**

`{str(e)[:150]}`",
                    parse_mode='Markdown'
                )
                return

            # Store
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_id = f"gen_{user_id}_{timestamp}"
            
            self.bot_handlers.user_states[user_id] = {
                'questions': questions,
                'session_id': session_id,
                'source': 'generated'
            }

            await msg.edit_text(
                f"✅ **{len(questions)} Questions**
"
                f"📦 Generating files..."
            )

            # Generate files
            await self.auto_generate_files(user_id, questions, timestamp, context, msg)

            # Cleanup
            for p in content_paths:
                if p.exists():
                    p.unlink(missing_ok=True)

        except Exception as e:
            print(f"❌ Content processing error: {e}")
            import traceback
            traceback.print_exc()
            
            if msg:
                await msg.edit_text(
                    f"❌ **Error**

`{str(e)[:150]}`",
                    parse_mode='Markdown'
                )
            raise

    def _normalize_questions(self, raw_questions: List[Dict]) -> List[Dict]:
        """Normalize question format with validation"""
        normalized = []
        
        for idx, q in enumerate(raw_questions):
            if not isinstance(q, dict):
                print(f"⚠️ Q{idx+1}: Not a dict, skipping")
                continue
            
            # Already normalized
            if 'question_description' in q and isinstance(q.get('options'), list):
                # Validate
                if not q.get('question_description') or len(q.get('options', [])) < 2:
                    print(f"⚠️ Q{idx+1}: Invalid, skipping")
                    continue
                
                normalized.append({
                    'question_description': q.get('question_description', ''),
                    'options': q.get('options', []),
                    'correct_answer_index': q.get('correct_answer_index', 0),
                    'correct_option': q.get('correct_option', 'A'),
                    'explanation': q.get('explanation', '')
                })
                continue
            
            # Dict options format
            if 'question' in q and isinstance(q.get('options'), dict):
                question_text = q.get('question', '')
                opts_dict = q.get('options', {})
                
                options = []
                for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
                    opt = opts_dict.get(letter)
                    if opt:
                        options.append(opt)
                
                if not question_text or len(options) < 2:
                    print(f"⚠️ Q{idx+1}: Invalid options, skipping")
                    continue
                
                correct_letter = q.get('correct_answer', 'A').upper()
                correct_idx = ord(correct_letter) - ord('A')
                
                if correct_idx < 0 or correct_idx >= len(options):
                    correct_idx = 0
                    correct_letter = 'A'
                
                normalized.append({
                    'question_description': question_text,
                    'options': options,
                    'correct_answer_index': correct_idx,
                    'correct_option': correct_letter,
                    'explanation': q.get('explanation', '')
                })
                continue
            
            # List options format
            if 'question' in q and isinstance(q.get('options'), list):
                question_text = q.get('question', '')
                options = q.get('options', [])
                
                if not question_text or len(options) < 2:
                    print(f"⚠️ Q{idx+1}: Invalid, skipping")
                    continue
                
                if 'correct_answer_index' in q:
                    correct_idx = q.get('correct_answer_index', 0)
                elif 'correct_answer' in q:
                    correct_letter = q.get('correct_answer', 'A').upper()
                    correct_idx = ord(correct_letter) - ord('A')
                else:
                    correct_idx = 0
                
                if correct_idx < 0 or correct_idx >= len(options):
                    correct_idx = 0
                
                correct_letter = chr(65 + correct_idx)
                
                normalized.append({
                    'question_description': question_text,
                    'options': options,
                    'correct_answer_index': correct_idx,
                    'correct_option': correct_letter,
                    'explanation': q.get('explanation', '')
                })
                continue
            
            # Unknown format - try to extract
            print(f"⚠️ Q{idx+1}: Unknown format, attempting extraction")
            
            question_text = (
                q.get('question_description') or 
                q.get('question') or 
                q.get('text') or 
                ''
            )
            
            options = q.get('options', [])
            if isinstance(options, dict):
                options = [options.get(letter) for letter in ['A', 'B', 'C', 'D', 'E'] if options.get(letter)]
            
            if not question_text or len(options) < 2:
                print(f"⚠️ Q{idx+1}: Cannot extract, skipping")
                continue
            
            normalized.append({
                'question_description': question_text,
                'options': options,
                'correct_answer_index': 0,
                'correct_option': 'A',
                'explanation': q.get('explanation', '')
            })
        
        print(f"✅ Normalized {len(normalized)}/{len(raw_questions)} questions")
        return normalized

    async def auto_generate_files(self, user_id: int, questions: List, timestamp: str, context, progress_msg):
        """Generate CSV, JSON, PDF - WITH VALIDATION"""
        
        try:
            # CSV with validation
            await progress_msg.edit_text("📦 **Generating CSV...**")
            
            csv_path = config.OUTPUT_DIR / f"questions_{timestamp}.csv"
            
            csv_questions = []
            for idx, q in enumerate(questions, 1):
                try:
                    # Validate before adding
                    question_text = q.get('question_description', '').strip()
                    options = q.get('options', [])
                    
                    if not question_text:
                        print(f"⚠️ CSV Q{idx}: Empty question, skipping")
                        continue
                    
                    if len(options) < 2:
                        print(f"⚠️ CSV Q{idx}: Less than 2 options, skipping")
                        continue
                    
                    csv_q = {
                        'questions': question_text,
                        'option1': options[0] if len(options) > 0 else '',
                        'option2': options[1] if len(options) > 1 else '',
                        'option3': options[2] if len(options) > 2 else '',
                        'option4': options[3] if len(options) > 3 else '',
                        'option5': options[4] if len(options) > 4 else '',
                        'answer': str(q.get('correct_answer_index', 0) + 1),
                        'explanation': q.get('explanation', '').strip(),
                        'type': '1',
                        'section': '1'
                    }
                    csv_questions.append(csv_q)
                    
                except Exception as e:
                    print(f"⚠️ CSV Q{idx} error: {e}")
                    continue
            
            if not csv_questions:
                print("❌ No valid questions for CSV")
                await progress_msg.edit_text("⚠️ **No valid questions for export**")
                return
            
            CSVGenerator.questions_to_csv(csv_questions, csv_path)
            print(f"✅ CSV: {len(csv_questions)} questions")
            
            # JSON
            await progress_msg.edit_text("📦 CSV ✓
📦 **Generating JSON...**")
            
            json_questions = []
            for q in questions:
                json_q = {
                    'question': q.get('question_description', ''),
                    'options': {},
                    'correct_answer': q.get('correct_option', 'A'),
                    'explanation': q.get('explanation', '')
                }
                
                for i, opt in enumerate(q['options']):
                    if opt:
                        json_q['options'][chr(65 + i)] = opt
                
                json_questions.append(json_q)
            
            json_path = config.OUTPUT_DIR / f"questions_{timestamp}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_questions, f, ensure_ascii=False, indent=2)
            
            # PDF
            await progress_msg.edit_text("📦 CSV ✓
📦 JSON ✓
📦 **Generating PDF...**")
            
            from processors.pdf_exporter import pdf_exporter
            
            settings = db.get_user_settings(user_id)
            pdf_mode = settings.get('pdf_mode', 'mode1')
            
            pdf_title = f"Quiz_{timestamp}"
            pdf_path = config.OUTPUT_DIR / f"questions_{timestamp}.pdf"
            
            cleaned = pdf_exporter.cleanup_questions(questions)
            pdf_exporter.generate_beautiful_pdf(cleaned, pdf_path, pdf_title, mode=pdf_mode)
            
            # Send files
            await progress_msg.edit_text("📦 **Sending files...**")
            
            # CSV
            with open(csv_path, 'rb') as f:
                await context.bot.send_document(
                    user_id, f,
                    filename=f"questions_{timestamp}.csv",
                    caption="📊 **CSV File**"
                )
            
            # JSON
            with open(json_path, 'rb') as f:
                await context.bot.send_document(
                    user_id, f,
                    filename=f"questions_{timestamp}.json",
                    caption="📋 **JSON File**"
                )
            
            # PDF with action buttons
            session_id = self.bot_handlers.user_states[user_id]['session_id']
            
            keyboard = [
                [InlineKeyboardButton("📢 Post Quizzes", callback_data=f"post_{session_id}")],
                [InlineKeyboardButton("🎯 Live Quiz", callback_data=f"livequiz_{session_id}")]
            ]
            
            with open(pdf_path, 'rb') as f:
                await context.bot.send_document(
                    user_id, f,
                    filename=f"questions_{timestamp}.pdf",
                    caption=f"📄 **PDF File** • {len(questions)}Q • {pdf_mode}",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            
            # Cleanup
            csv_path.unlink(missing_ok=True)
            json_path.unlink(missing_ok=True)
            pdf_path.unlink(missing_ok=True)
            
            # Delete progress message
            await progress_msg.delete()
            
            print(f"✅ All files generated and sent")
            
        except Exception as e:
            print(f"❌ File generation error: {e}")
            import traceback
            traceback.print_exc()
            
            await progress_msg.edit_text(
                f"⚠️ **File Generation Error**

`{str(e)[:150]}`",
                parse_mode='Markdown'
            )

    async def post_quizzes_to_destination(self, user_id, chat_id, thread_id, context, status_msg, custom_message=None):
        """Post quizzes with progress tracking"""
        if user_id not in self.bot_handlers.user_states:
            await status_msg.edit_text("❌ Session expired")
            return

        questions = self.bot_handlers.user_states[user_id]['questions']
        settings = db.get_user_settings(user_id)

        await status_msg.edit_text(
            f"📢 **Starting...**
{len(questions)} quizzes to post"
        )

        # Pin custom message if provided
        if custom_message:
            try:
                pin_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=custom_message,
                    message_thread_id=thread_id
                )
                try:
                    await context.bot.pin_chat_message(
                        chat_id=chat_id,
                        message_id=pin_msg.message_id,
                        disable_notification=True
                    )
                    print("✅ Header pinned")
                except Exception as e:
                    print(f"⚠️ Pin failed: {e}")
            except Exception as e:
                print(f"⚠️ Header send failed: {e}")

        # Progress callback
        async def progress(current, total, success, failed):
            try:
                pct = int((current / total) * 100)
                bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                await status_msg.edit_text(
                    f"📢 **Posting**

"
                    f"`[{bar}]` {pct}%
"
                    f"{current}/{total}
"
                    f"✅ {success} | ❌ {failed}",
                    parse_mode='Markdown'
                )
            except:
                pass

        # Post quizzes
        result = await quiz_poster.post_quizzes_batch(
            context, chat_id, questions,
            settings.get('quiz_marker', '🎯 Quiz'),
            settings.get('explanation_tag', 'Exp'),
            thread_id, progress, None, user_id=user_id
        )

        # Show results
        result_text = (
            f"✅ **Complete**

"
            f"Total: {result['total']}
"
            f"Success: {result['success']}
"
            f"Failed: {result['failed']}"
        )
        
        if result['failed_questions']:
            result_text += "

**Failed Questions:**
"
            for fq in result['failed_questions'][:5]:
                result_text += f"• Q{fq['number']}: {fq['error'][:30]}...
"
        
        await status_msg.edit_text(result_text, parse_mode='Markdown')

        # Cleanup
        self.bot_handlers.user_states.pop(user_id, None)
