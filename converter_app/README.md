# Universal File Converter (FastAPI)

A simple web UI and API to convert files between many formats:

- PDF → Images (PNG)
- Image ↔ Image (requires ImageMagick for broad support; Pillow fallback)
- Image → PDF
- Office Docs (DOCX/PPTX/XLSX/ODT) → PDF (LibreOffice headless)
- Markdown/TXT → PDF (Pandoc)
- Video → other formats (ffmpeg)
- Audio → other formats (ffmpeg or pydub fallback)
- CSV/Excel ↔ JSON
- Archive extract/create (7zip or Python stdlib)

## Requirements

System tools (recommended for best coverage):
- poppler-utils (pdftoppm)
- imagemagick
- libreoffice
- pandoc
- ffmpeg
- p7zip-full (optional)

Python dependencies are listed in `converter_app/requirements.txt`.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r converter_app/requirements.txt
uvicorn converter_app.app.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 in your browser.