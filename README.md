# DocStream

Real-time document → Markdown converter. Upload a PDF, DOCX, PPTX, XLSX, CSV,
TXT, or image, watch it stream into Markdown section-by-section as it's
converted, edit it live, and download the result.

## File structure

```
docstream/
├── backend/
│   ├── main.py                  # FastAPI app: /upload + /stream (SSE)
│   ├── requirements.txt
│   ├── uploads/                 # temp storage (auto-created, auto-cleaned)
│   └── converters/
│       ├── router.py            # dispatches by file extension, last-resort error net
│       ├── pdf_converter.py     # PyMuPDF text + Tesseract OCR fallback, per page,
│       │                        # carries unfinished paragraphs across page breaks
│       ├── docx_converter.py    # python-docx, preserves headings/lists/tables
│       ├── pptx_converter.py    # python-pptx, per slide, tables + speaker notes
│       ├── sheet_converter.py   # pandas, per sheet -> markdown tables, multi-encoding CSV
│       ├── text_converter.py    # txt/md passthrough, multi-encoding fallback
│       └── image_converter.py   # standalone image OCR
└── frontend/
    └── index.html               # single-page UI: dropzone + live markdown editor/preview
```

## Prerequisites

- Python 3.10+
- **Tesseract OCR** binary installed on the system — only needed for scanned
  PDF pages and standalone images. Regular text-based PDFs, DOCX, PPTX,
  XLSX/CSV, and TXT files work fine without it.

### Installing Tesseract

- **Windows**: download the installer from
  [UB-Mannheim's Tesseract build](https://github.com/UB-Mannheim/tesseract/wiki),
  run it, then add the install folder (default `C:\Program Files\Tesseract-OCR`)
  to your System PATH. Restart your terminal/IDE afterward.
  Verify with `tesseract --version`.

  If you don't want to touch PATH, point `pytesseract` at the binary directly
  by adding this near the top of `pdf_converter.py` and `image_converter.py`:
  ```python
  pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
  ```

- **macOS**: `brew install tesseract`
- **Ubuntu/Debian**: `sudo apt-get install tesseract-ocr`

If Tesseract isn't installed, the app still runs fine — scanned pages and
images will just show an inline note instead of extracted text, rather than
crashing the conversion job.

## Setup

```bash
cd docstream/backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
cd docstream/backend
uvicorn main:app --reload --port 8000
```

Then open **http://localhost:8000** in your browser. The FastAPI app serves
the frontend itself via `StaticFiles`, so don't open `frontend/index.html`
directly or through a separate tool like VS Code's Live Server — the two
won't be talking to the same backend and uploads will silently fail.

## How it works

1. `POST /upload` saves the file, creates a `job_id`, and kicks off conversion
   in a background asyncio task.
2. The client opens `GET /stream/{job_id}` as a Server-Sent Events (SSE)
   connection.
3. Each converter is an async generator that yields one chunk per logical unit
   (PDF page, DOCX section, PPTX slide, spreadsheet sheet) as soon as it's
   ready.
4. Chunks are pushed onto an `asyncio.Queue` and streamed to the browser in
   real time; the frontend appends each chunk to the markdown editor and
   re-renders the live preview.
5. The `/stream` endpoint watches for client disconnects (`request.is_disconnected()`)
   and stops cleanly instead of retrying writes to a closed connection.
6. On completion, the temp upload file is deleted.

## Error handling

Every converter is built to degrade gracefully rather than crash the whole
job:

- A corrupt or password-protected file → a clear inline error block instead
  of an unhandled exception.
- A bad page/slide/sheet/shape inside an otherwise-good file → that one
  piece is skipped with a note; the rest of the document still converts.
- CSV/TXT files in non-UTF-8 encodings (common from Excel exports) → tried
  against several encodings before falling back to a lossy decode.
- Missing Tesseract → OCR-dependent pages/images show an explanatory message
  instead of failing the job.
- Unsupported file extensions → rejected at upload with a clear 400, and the
  router itself also handles it defensively if reached some other way.

If something still slips through, `router.py` has a top-level
try/except that converts any unexpected exception into a visible
`"Error"` chunk in the stream rather than silently dying.

## Known limitations

- **PDF structure detection is heuristic, not a real layout parser.**
  Headings, lists, and clause numbering are reconstructed from line length,
  capitalization, and punctuation patterns — not actual visual layout. This
  works well for many documents but will misfire on complex or unusual
  layouts. For documents where structural accuracy really matters (e.g.
  feeding into a RAG pipeline), consider swapping in
  [Docling](https://github.com/DS4SD/docling) or
  [Marker](https://github.com/VikParuchuri/marker) for layout-aware PDF
  parsing instead of the current PyMuPDF + heuristics approach.
- **Job state is in-memory** (a plain Python dict) — fine for local or
  single-process use. For production with multiple worker processes, swap
  in Redis (pub/sub for streaming, a hash for job status) so streaming works
  across processes.
- **OCR quality depends on Tesseract**, which is mediocre on messy scans,
  handwriting, or low-resolution images. For higher-quality OCR on
  table-heavy or low-quality scans, consider routing those pages to a
  vision-LLM-based OCR call instead.
- **No auth, file size limits, or rate limiting.** Add these before deploying
  publicly, since this accepts arbitrary file uploads.