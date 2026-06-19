from pathlib import Path
from typing import AsyncIterator

import pandas as pd


async def convert(path: Path) -> AsyncIterator[dict]:
    suffix = path.suffix.lower()

    if suffix == ".csv":
        async for chunk in convert_csv(path):
            yield chunk
        return

    async for chunk in convert_excel(path):
        yield chunk


async def convert_csv(path: Path) -> AsyncIterator[dict]:
    df = None
    last_error = None

    # Try a few common encodings before giving up — CSVs from Excel exports
    # are often not UTF-8.
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            df = pd.read_csv(path, encoding=encoding)
            break
        except Exception as e:
            last_error = e
            continue

    if df is None:
        yield {
            "section": "Error",
            "markdown": f"> **Could not parse this CSV file.**\n>\n> `{last_error}`\n",
            "progress": 1.0,
        }
        return

    yield {
        "section": path.stem,
        "markdown": df_to_markdown(df, path.stem),
        "progress": 1.0,
    }


async def convert_excel(path: Path) -> AsyncIterator[dict]:
    try:
        xls = pd.ExcelFile(path)
    except Exception as e:
        yield {
            "section": "Error",
            "markdown": f"> **Could not open this Excel file** — it may be corrupt, password-protected, or an unsupported format.\n>\n> `{e}`\n",
            "progress": 1.0,
        }
        return

    sheet_names = xls.sheet_names
    if not sheet_names:
        yield {
            "section": "Error",
            "markdown": "> This workbook has no sheets.\n",
            "progress": 1.0,
        }
        return

    total = len(sheet_names)

    for i, name in enumerate(sheet_names):
        try:
            df = xls.parse(name)
            md = df_to_markdown(df, name)
        except Exception as e:
            md = f"## {name}\n\n> **Could not read this sheet.**\n>\n> `{e}`\n"

        yield {
            "section": name,
            "markdown": md,
            "progress": (i + 1) / total,
        }


def df_to_markdown(df: pd.DataFrame, title: str) -> str:
    if df.empty:
        return f"## {title}\n\n_(empty sheet)_\n"
    try:
        # to_markdown can fail on exotic dtypes; stringify everything as a
        # safe fallback rather than crashing the whole sheet.
        return f"## {title}\n\n" + df.to_markdown(index=False) + "\n"
    except Exception:
        df = df.astype(str)
        return f"## {title}\n\n" + df.to_markdown(index=False) + "\n"