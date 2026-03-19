"""
Download NotoSansBengali-Regular.ttf into the fonts/ directory.
Run once before starting the bot if you want to pre-cache the font:

    python download_font.py

The bot also downloads it automatically on first PDF generation,
but running this script upfront avoids any delay during the first export.
"""

import sys
from pathlib import Path

FONT_URL = (
    "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/"
    "NotoSansBengali/NotoSansBengali-Regular.ttf"
)
DEST = Path("fonts") / "NotoSansBengali-Regular.ttf"


def download():
    try:
        import requests
    except ImportError:
        print("Install requests first:  pip install requests")
        sys.exit(1)

    if DEST.exists():
        print(f"✅ Font already present at {DEST}")
        return

    DEST.parent.mkdir(exist_ok=True)
    print(f"⬇️  Downloading Noto Sans Bengali…")
    r = requests.get(FONT_URL, timeout=60)
    r.raise_for_status()
    DEST.write_bytes(r.content)
    print(f"✅ Saved to {DEST}  ({len(r.content):,} bytes)")


if __name__ == "__main__":
    download()
