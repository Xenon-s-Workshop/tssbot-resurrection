"""
Poll Collector - Complete Implementation
Supports CSV collection, merging, JSON export, and progress tracking
"""

import os
import re
import csv
import json
import tempfile
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from config import config

def escape_markdown(text: str) -> str:
    """Escape characters for MarkdownV2"""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

class PollCollector:
    def __init__(self):
        self.application = None
        self.user_states: Dict[int, Dict] = {}
        self.MAX_POLLS = 200
        self.MAX_CSV_SIZE = 10 * 1024 * 1024  # 10MB
        self.MAX_CSV_ROWS = 500
        self.PROCESS_DELAY = 2  # Delay before processing pending polls
        print("✅ Poll Collector initialized")
    
    def set_application(self, app):
        """Set application reference"""
        self.application = app
        print("✅ Application reference set for poll collector")
    
    # ==================== COLLECTION MANAGEMENT ====================
    
    def start_collection(self, user_id: int, filename: str):
        """Start poll collection session"""
        self.user_states[user_id] = {
            'is_collecting': True,
            'polls': [],
            'filename': filename,
            'start_time': datetime.now(),
            'last_progress_message_id': None,
            'pending_polls': [],
            'processing_task': None,
            'chat_id': None,
        }
        print(f"✅ Poll collection started for user {user_id} → {filename}")
    
    def is_collecting(self, user_id: int) -> bool:
        """Check if user is collecting polls"""
        return user_id in self.user_states and self.user_states[user_id].get('is_collecting', False)
    
    def get_poll_count(self, user_id: int) -> int:
        """Get number of collected polls"""
        if user_id in self.user_states:
            return len(self.user_states[user_id]['polls'])
        return 0
    
    def get_filename(self, user_id: int) -> str:
        """Get collection filename"""
        if user_id in self.user_states:
            return self.user_states[user_id]['filename']
        return "polls.csv"
    
    def get_duration(self, start_time: datetime) -> str:
        """Calculate duration"""
        duration = datetime.now() - start_time
        minutes = int(duration.total_seconds() / 60)
        seconds = int(duration.total_seconds() % 60)
        return f"{minutes}m {seconds}s"
    
    def create_progress_bar(self, current: int, total: int, length: int = 10) -> str:
        """Create progress bar"""
        filled = int((current / total) * length)
        bar = "█" * filled + "░" * (length - filled)
        percentage = int((current / total) * 100)
        return f"[{bar}] {percentage}%"
    
    # ==================== POLL PROCESSING ====================
    
    def add_poll(self, user_id: int, poll_data: dict):
        """Add poll to pending queue"""
        if user_id not in self.user_states:
            return
        
        user_state = self.user_states[user_id]
        user_state['pending_polls'].append(poll_data)
        
        # Cancel existing processing task
        if user_state.get('processing_task') and not user_state['processing_task'].done():
            user_state['processing_task'].cancel()
        
        # Schedule new processing task
        user_state['processing_task'] = asyncio.create_task(
            self._process_pending_polls_delayed(user_id)
        )
    
    async def _process_pending_polls_delayed(self, user_id: int):
        """Process pending polls after delay"""
        try:
            await asyncio.sleep(self.PROCESS_DELAY)
            
            if user_id not in self.user_states:
                return
            
            user_state = self.user_states[user_id]
            pending = user_state['pending_polls']
            
            if not pending:
                return
            
            # Process all pending polls
            for poll_data in pending:
                if len(user_state['polls']) >= self.MAX_POLLS:
                    print(f"⚠️ Max polls reached for user {user_id}")
                    break
                
                user_state['polls'].append(poll_data)
            
            # Clear pending
            user_state['pending_polls'] = []
            
            # Update progress message
            await self._update_progress_message(user_id)
            
        except asyncio.CancelledError:
            print(f"🛑 Processing cancelled for user {user_id}")
        except Exception as e:
            print(f"❌ Error processing polls for user {user_id}: {e}")
    
    async def _update_progress_message(self, user_id: int):
        """Update or send progress message"""
        if user_id not in self.user_states:
            return
        
        user_state = self.user_states[user_id]
        chat_id = user_state.get('chat_id')
        
        if not chat_id or not self.application:
            return
        
        polls_count = len(user_state['polls'])
        progress_bar = self.create_progress_bar(polls_count, self.MAX_POLLS)
        
        message_text = (
            f"📊 **Poll Collection Progress**\n\n"
            f"📁 **File:** `{user_state['filename']}`\n"
            f"📈 **Collected:** {polls_count}/{self.MAX_POLLS}\n"
            f"{progress_bar}\n"
            f"⏱️ **Duration:** {self.get_duration(user_state['start_time'])}\n\n"
            f"Commands: /done | /status | /cancel"
        )
        
        try:
            last_msg_id = user_state.get('last_progress_message_id')
            
            if last_msg_id:
                # Try to edit existing message
                try:
                    await self.application.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=last_msg_id,
                        text=message_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    # If edit fails, send new message
                    msg = await self.application.bot.send_message(
                        chat_id=chat_id,
                        text=message_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    user_state['last_progress_message_id'] = msg.message_id
            else:
                # Send new message
                msg = await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=message_text,
                    parse_mode=ParseMode.MARKDOWN
                )
                user_state['last_progress_message_id'] = msg.message_id
                
        except Exception as e:
            print(f"⚠️ Error updating progress message: {e}")
    
    async def cleanup_progress_message(self, chat_id: int, user_state: dict, context: ContextTypes.DEFAULT_TYPE):
        """Delete progress message"""
        last_msg_id = user_state.get('last_progress_message_id')
        if last_msg_id:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=last_msg_id)
            except:
                pass
    
    # ==================== CSV GENERATION ====================
    
    async def generate_csv(self, polls: List[dict], output_path: str):
        """Generate CSV file from polls"""
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'questions', 'option1', 'option2', 'option3', 'option4', 'option5',
                'answer', 'explanation', 'type', 'section'
            ])
            writer.writeheader()
            
            for poll in polls:
                options = poll.get('options', [])
                correct_idx = poll.get('correct_option_id', 0)
                
                row = {
                    'questions': poll.get('question', ''),
                    'option1': options[0] if len(options) > 0 else '',
                    'option2': options[1] if len(options) > 1 else '',
                    'option3': options[2] if len(options) > 2 else '',
                    'option4': options[3] if len(options) > 3 else '',
                    'option5': options[4] if len(options) > 4 else '',
                    'answer': str(correct_idx + 1),
                    'explanation': poll.get('explanation', ''),
                    'type': '1',
                    'section': '1'
                }
                writer.writerow(row)
        
        print(f"✅ CSV generated: {output_path} ({len(polls)} polls)")
    
    async def generate_json(self, polls: List[dict], output_path: str):
        """Generate JSON file from polls"""
        json_data = []
        
        for poll in polls:
            options = poll.get('options', [])
            correct_idx = poll.get('correct_option_id', 0)
            correct_letter = chr(65 + correct_idx) if correct_idx < 26 else 'A'
            
            options_dict = {}
            for i, opt in enumerate(options[:10]):
                letter = chr(65 + i)
                options_dict[letter] = opt
            
            json_data.append({
                'question': poll.get('question', ''),
                'options': options_dict,
                'correct_answer': correct_letter,
                'explanation': poll.get('explanation', '')
            })
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ JSON generated: {output_path} ({len(polls)} polls)")
    
    def export_csv(self, user_id: int) -> tuple:
        """Export polls to CSV (synchronous wrapper)"""
        if user_id not in self.user_states:
            raise ValueError("No active session")
        
        polls = self.user_states[user_id]['polls']
        
        if not polls:
            raise ValueError("No polls to export")
        
        # Create temp CSV
        temp_path = config.OUTPUT_DIR / f"polls_{user_id}.csv"
        
        # Write CSV synchronously
        with open(temp_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'questions', 'option1', 'option2', 'option3', 'option4', 'option5',
                'answer', 'explanation', 'type', 'section'
            ])
            writer.writeheader()
            
            for poll in polls:
                options = poll.get('options', [])
                correct_idx = poll.get('correct_option_id', 0)
                
                row = {
                    'questions': poll.get('question', ''),
                    'option1': options[0] if len(options) > 0 else '',
                    'option2': options[1] if len(options) > 1 else '',
                    'option3': options[2] if len(options) > 2 else '',
                    'option4': options[3] if len(options) > 3 else '',
                    'option5': options[4] if len(options) > 4 else '',
                    'answer': str(correct_idx + 1),
                    'explanation': poll.get('explanation', ''),
                    'type': '1',
                    'section': '1'
                }
                writer.writerow(row)
        
        return temp_path, len(polls)
    
    def stop_collection(self, user_id: int):
        """Stop collection and cleanup"""
        if user_id in self.user_states:
            user_state = self.user_states[user_id]
            
            # Cancel processing task
            if user_state.get('processing_task') and not user_state['processing_task'].done():
                user_state['processing_task'].cancel()
            
            user_state['is_collecting'] = False
            del self.user_states[user_id]
            print(f"🛑 Poll collection stopped for user {user_id}")
    
    # ==================== MERGE FUNCTIONALITY ====================
    
    def start_merge_session(self, user_id: int, filename: Optional[str] = None):
        """Start file merge session"""
        if user_id not in self.user_states:
            self.user_states[user_id] = {}
        
        self.user_states[user_id].update({
            'is_merging': True,
            'merge_files': [],
            'merge_mode': None,  # 'csv' or 'json'
            'merge_filename': filename
        })
        print(f"✅ Merge session started for user {user_id}")
    
    def is_merging(self, user_id: int) -> bool:
        """Check if user is in merge mode"""
        return user_id in self.user_states and self.user_states[user_id].get('is_merging', False)
    
    def add_merge_file(self, user_id: int, file_path: str, file_type: str):
        """Add file to merge queue"""
        if user_id not in self.user_states:
            return False
        
        user_state = self.user_states[user_id]
        
        # Check if mixing file types
        if user_state['merge_mode'] and user_state['merge_mode'] != file_type:
            return False
        
        user_state['merge_mode'] = file_type
        user_state['merge_files'].append(file_path)
        print(f"📁 File added to merge queue: {file_path}")
        return True
    
    def get_merge_file_count(self, user_id: int) -> int:
        """Get number of files in merge queue"""
        if user_id in self.user_states:
            return len(self.user_states[user_id].get('merge_files', []))
        return 0
    
    async def perform_merge(self, user_id: int) -> tuple:
        """Merge files and return output path"""
        if user_id not in self.user_states:
            raise ValueError("No merge session")
        
        user_state = self.user_states[user_id]
        merge_files = user_state.get('merge_files', [])
        merge_mode = user_state.get('merge_mode')
        
        if not merge_files:
            raise ValueError("No files to merge")
        
        output_filename = user_state.get('merge_filename')
        
        if merge_mode == 'csv':
            if not output_filename:
                output_filename = "merged.csv"
            elif not output_filename.endswith('.csv'):
                output_filename += ".csv"
            
            output_path = config.OUTPUT_DIR / output_filename
            
            # Merge CSV files
            with open(output_path, 'w', newline='', encoding='utf-8') as outfile:
                # Read header from first file
                with open(merge_files[0], 'r', encoding='utf-8-sig') as f:
                    header = f.readline()
                    outfile.write(header)
                    for line in f:
                        outfile.write(line)
                
                # Append remaining files (skip headers)
                for file_path in merge_files[1:]:
                    with open(file_path, 'r', encoding='utf-8-sig') as f:
                        f.readline()  # Skip header
                        for line in f:
                            outfile.write(line)
            
            return output_path, len(merge_files)
        
        elif merge_mode == 'json':
            if not output_filename:
                output_filename = "merged.json"
            elif not output_filename.endswith('.json'):
                output_filename += ".json"
            
            output_path = config.OUTPUT_DIR / output_filename
            
            # Merge JSON files
            combined_json = []
            for file_path in merge_files:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        combined_json.extend(data)
                    else:
                        combined_json.append(data)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(combined_json, f, ensure_ascii=False, indent=2)
            
            return output_path, len(merge_files)
        
        else:
            raise ValueError("Unknown merge mode")
    
    def cleanup_merge_session(self, user_id: int):
        """Cleanup merge session"""
        if user_id not in self.user_states:
            return
        
        user_state = self.user_states[user_id]
        
        # Delete temporary files
        for file_path in user_state.get('merge_files', []):
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass
        
        # Clear merge state
        if 'is_merging' in user_state:
            del self.user_states[user_id]
        
        print(f"🧹 Merge session cleaned up for user {user_id}")
    
    # ==================== UTILITY METHODS ====================
    
    def parse_filename(self, command_text: str) -> str:
        """Parse filename from command text"""
        match = re.search(r'-n\s+"([^"]+)"', command_text)
        if match:
            filename = match.group(1).strip()
            if not filename.endswith('.csv'):
                filename += '.csv'
            # Remove invalid characters
            filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
            return filename
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"polls_{timestamp}.csv"
    
    def set_chat_id(self, user_id: int, chat_id: int):
        """Set chat ID for progress updates"""
        if user_id in self.user_states:
            self.user_states[user_id]['chat_id'] = chat_id

# Global instance
poll_collector = PollCollector()
