# TSS Telegram Bot - Complete Fixed Version

Production-ready quiz generation and management bot with ALL fixes applied.

## ✅ All Issues Fixed

### 1. Enhanced START & HELP Commands
- Clear explanations of bot features
- Step-by-step workflow guide
- Quick action buttons

### 2. CSV Export - FIXED
- Proper validation before writing
- Fixed empty fields issue
- Complete question/option/answer/explanation columns
- Logging on parse failures

### 3. Quiz Posting Flow - REDESIGNED
- Step 1: Header message (with Skip button)
- Step 2: Destination selection
- UI removed after selection (prevents duplicate clicks)
- Step 3: Sequential posting with progress bar
- Retry system (2 retries, shows failure reason)
- Proper session management

### 4. KeyError: 'quiz_marker' - FIXED
- Default values in database.py
- Safe access with .get()
- Settings always initialized

### 5. Settings System - COMPLETE
- Quiz Marker (customizable via UI)
- Explanation Tag (customizable via UI)
- PDF Mode (mode1/mode2 selection)
- All settings persist per user

### 6. /collectpolls - FIXED
- Proper poll collection
- Data storage
- Export functionality

### 7. PDF System - TWO MODES

**Mode 1: Answer Key at End (ReportLab)**
- Questions with options only
- Answer section at end
- 6-7 questions per A4 page

**Mode 2: Inline Answers (WeasyPrint)**
- Each question includes answer
- Explanation shown immediately
- Clean, readable layout

**Bengali Font Support:**
- ReportLab: TTFont registration
- WeasyPrint: Noto Sans Bengali via CSS
- UTF-8 encoding throughout

### 8. UX Improvements
- Descriptive progress messages
- Progress bars for long operations
- Clear error messages
- Status updates at every step

### 9. Error Handling
- Global error handler
- Proper logging
- User-friendly error messages
- Automatic retry on failures

### 10. Code Quality
- Modular structure
- No hardcoding
- Safe dictionary access
- Clean naming
- Maintainable design

## Quick Start

1. **Set Environment Variables:**
```bash
export TELEGRAM_BOT_TOKEN="your_token"
export GEMINI_API_KEYS="key1,key2,key3"
export MONGODB_URI="mongodb://localhost:27017/"
export SUDO_USER_IDS="123456789"
export AUTH_ENABLED="true"
```

2. **Install Dependencies:**
```bash
pip install -r requirements.txt

# For WeasyPrint (Ubuntu/Debian):
sudo apt-get install -y python3-cffi python3-brotli \
  libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
  libgdk-pixbuf2.0-0 libffi-dev shared-mime-info
```

3. **Run Bot:**
```bash
python main.py
```

## Features

- 📤 Extract quizzes from PDFs/images
- ✨ AI-powered question generation
- 📊 Export to CSV, JSON, PDF
- 📢 Post quizzes to channels/groups
- 🎯 Live quiz sessions
- 📈 Poll collection
- 🔄 Automatic API key rotation
- 📋 Task queue management
- ⚙️ Customizable settings

## Commands

### User Commands
- `/start` - Welcome and quick guide
- `/help` - Complete documentation
- `/settings` - Manage preferences
- `/info` - Your stats
- `/queue` - Check processing queue
- `/cancel` - Cancel current task
- `/collectpolls` - Collect poll results
- `/livequiz` - Start live quiz session

### Admin Commands
- `/authorize <user_id>` - Authorize user
- `/revoke <user_id>` - Revoke user
- `/users` - List authorized users

## Usage Workflow

1. **Generate Quizzes**
   - Send PDF or images
   - Choose extraction or generation mode
   - Wait for processing

2. **Get Files**
   - Receive CSV, JSON, PDF files
   - Review and edit if needed

3. **Post Quizzes**
   - Click "Post Quiz" button
   - Optionally send header message
   - Select destination channel/group
   - Watch progress bar
   - Get score counter (?/total)

## PDF Modes

**Mode 1 - Answer Key at End:**
Perfect for practice tests where students answer first, then check answers.

**Mode 2 - Inline Answers:**
Perfect for study materials where immediate feedback is desired.

Change mode in `/settings` → PDF Mode

## Support

For issues or feature requests, contact admin.

## License

Proprietary - All Rights Reserved
