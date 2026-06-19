from pathlib import Path
from typing import AsyncIterator

from converters import (
    pdf_converter,
    docx_converter,
    pptx_converter,
    sheet_converter,
    text_converter,
    image_converter,
)

CONVERTERS = {
    ".pdf": pdf_converter,
    ".docx": docx_converter,
    ".pptx": pptx_converter,
    ".xlsx": sheet_converter,
    ".xls": sheet_converter,
    ".csv": sheet_converter,
    ".txt": text_converter,
    ".md": text_converter,
    ".png": image_converter,
    ".jpg": image_converter,
    ".jpeg": image_converter,
    ".tiff": image_converter,
    ".bmp": image_converter,
}


async def convert_document(path: Path) -> AsyncIterator[dict]:
    """
    Dispatch to the right converter based on file extension.
    Each converter is an async generator yielding
    {"section": str, "markdown": str, "progress": float}.

    Individual converters already catch their own per-item errors and emit
    an inline error block instead of raising. This is a last-resort safety
    net in case something still escapes that.
    """
    suffix = path.suffix.lower()
    module = CONVERTERS.get(suffix)

    if module is None:
        yield {
            "section": "Error",
            "markdown": f"> **Unsupported file type: `{suffix}`**\n",
            "progress": 1.0,
        }
        return

    try:
        async for chunk in module.convert(path):
            yield chunk
    except Exception as e:
        yield {
            "section": "Error",
            "markdown": f"> **Conversion failed unexpectedly.**\n>\n> `{type(e).__name__}: {e}`\n",
            "progress": 1.0,
        }