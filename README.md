# 🤖 Telegram Quiz Bot — Fixed & Upgraded

A production-ready Telegram bot that extracts or generates MCQs from PDFs and images using **Gemini AI**, exports them as CSV / JSON / PDF, and posts them as Telegram quiz polls.

---

## ✨ What's Fixed

| Issue | Fix Applied |
|---|---|
| `KeyError: 'quiz_marker'` | All settings access uses `.get()` with defaults; DB back-fills missing keys |
| Empty CSV fields | Full validation per row; skips invalid rows with warnings |
| Missing JSON export | Added alongside CSV |
| Broken PDF | Rebuilt with ReportLab (2 modes) + WeasyPrint fallback |
| Bengali font crash | Noto Sans Bengali auto-downloaded and registered for both engines |
| Post flow chaos | 3-step flow: header → destination → progress bar |
| Duplicate clicks | UI disabled immediately after destination selected |
| `/collectpolls` | Stores poll answers, exports as JSON |
| No global error handler | Added — logs and notifies user |
| Vague UX messages | Live progress bars, descriptive status at every step |

---

## 🚀 Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your tokens
```

### 3. Font (optional — auto-downloads on first run)
Place `NotoSansBengali-Regular.ttf` in the `fonts/` folder, or the bot will download it automatically.

### 4. Run
```bash
python main.py
```

---

## ⚙️ Configuration

All settings are editable via `/settings` in the bot. They persist per user in MongoDB.

| Setting | Default | Description |
|---|---|---|
| `quiz_marker` | `[TSS]` | Prepended to every quiz question |
| `explanation_tag` | `t.me/tss` | Appended to every explanation |
| `pdf_mode` | `inline` | `inline` or `answer_key` |

Global defaults can be set via environment variables:
```
QUIZ_MARKER=[TSS]
EXPLANATION_TAG=t.me/mychannel
```

---

## 📄 PDF Modes

### `inline` (default)
Each question shows:
- Question text
- All options (correct one marked with ✓)
- Explanation inline

### `answer_key`
- Part 1: All questions + options (no answers)
- Part 2: Answer key (`1 → A`, `2 → C`, …) with explanations

---

## 📁 Project Structure

```
tssbot-fixed/
├── main.py                     # Entry point, queue, error handler
├── config.py                   # All configuration
├── database.py                 # MongoDB (users, channels, groups, polls)
├── requirements.txt
├── .env.example
├── bot/
│   ├── handlers.py             # /start /help /settings + file handlers
│   ├── callbacks.py            # All inline keyboard + text state machine
│   └── content_processor.py   # PDF→AI→exports→post pipeline
├── processors/
│   ├── csv_processor.py        # CSV parse + write; JSON write
│   ├── pdf_processor.py        # Gemini image processing
│   ├── pdf_generator.py        # ReportLab + WeasyPrint PDF engines
│   ├── quiz_poster.py          # Telegram poll posting with retry
│   └── image_processor.py     # PIL image loader
├── prompts/
│   ├── extraction_prompt.py
│   └── generation_prompt.py
├── utils/
│   ├── api_rotator.py          # Round-robin Gemini key rotation
│   └── queue_manager.py        # Per-user task queue
└── fonts/
    └── NotoSansBengali-Regular.ttf  # Auto-downloaded on first run
```

---

## 📋 CSV Format (for import)

```
question,option_a,option_b,option_c,option_d,correct_answer,explanation
What is 2+2?,1,2,3,4,D,Simple arithmetic
```

The bot also accepts the **legacy format** (`questions`, `option1–4`, `answer` as number).

---

## 📢 Posting Flow

1. Send PDF/image → choose mode → receive CSV + JSON + PDF
2. Tap **Post Quizzes**
3. **Step 1**: Send a header message (or skip)
4. **Step 2**: Choose a channel or group
5. **Step 3**: Bot posts with a live progress bar

---

## 🔧 Commands

| Command | Description |
|---|---|
| `/start` | Main menu with action buttons |
| `/help` | Full step-by-step guide |
| `/settings` | Configure channels, markers, PDF mode |
| `/info` | Show current chat ID (useful for adding groups) |
| `/queue` | Check your queue position |
| `/cancel` | Cancel current task and reset session |
| `/collectpolls` | View and export collected poll answers |
| `/model` | Show AI model and worker info |
