from pathlib import Path
from typing import AsyncIterator

import pytesseract
from PIL import Image


async def convert(path: Path) -> AsyncIterator[dict]:
    try:
        img = Image.open(path)
        img.load()  # force a decode now so corrupt images fail here, not later
    except Exception as e:
        yield {
            "section": "Error",
            "markdown": f"> **Could not open this image** — it may be corrupt or an unsupported format.\n>\n> `{e}`\n",
            "progress": 1.0,
        }
        return

    try:
        text = pytesseract.image_to_string(img).strip()
        md = text if text else "_(no text detected in image)_"
    except Exception as e:
        md = (
            f"_(OCR failed: Tesseract is not installed or not in PATH — `{e}`)_\n\n"
            "Install it: `brew install tesseract` (macOS), "
            "`apt-get install tesseract-ocr` (Linux), or the Windows installer "
            "from https://github.com/UB-Mannheim/tesseract/wiki"
        )

    yield {
        "section": path.stem,
        "markdown": md + "\n",
        "progress": 1.0,
    }