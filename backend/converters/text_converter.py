from pathlib import Path
from typing import AsyncIterator


async def convert(path: Path) -> AsyncIterator[dict]:
    text = None
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            text = path.read_text(encoding=encoding)
            break
        except Exception:
            continue

    if text is None:
        # Last resort: decode bytes, dropping anything that can't be read.
        try:
            text = path.read_bytes().decode("utf-8", errors="ignore")
        except Exception as e:
            yield {
                "section": "Error",
                "markdown": f"> **Could not read this file as text.**\n>\n> `{e}`\n",
                "progress": 1.0,
            }
            return

    yield {
        "section": path.stem,
        "markdown": text,
        "progress": 1.0,
    }