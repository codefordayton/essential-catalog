# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python application that generates a professional PDF art catalog (and eventually social media images) from Wix CMS CSV exports. It processes artist entries with photos, bios, artwork images, and social links.

## Running the Scripts

All scripts use a local virtual environment (`env/`) with Python 3.11:

```bash
source env/bin/activate

# Generate the PDF catalog (main workflow)
python main.py

# Extract artist bios/statements from CSV into text files
python extract_text.py

# Generate AI summaries (requires local Ollama server on port 11434, uses llama3.1)
python generate_summaries.py
```

Install dependencies: `pip install -r requirements.txt`

There are no tests, linting, or build tools configured.

## Architecture

### Shared library (`lib/`)

Reusable modules used by both the PDF catalog and future social media image generator:

- **`lib/artists.py`** — CSV parsing (`parse_csv_to_dict`), sorting, artwork/photo URL extraction. Exports `NAME_COLUMN` constant for the BOM-prefixed Wix CSV name field (`'\ufeff"Name"'`).
- **`lib/images.py`** — Image download with MD5-based caching (`image_cache/`), EXIF rotation correction, rounded corner processing.
- **`lib/text.py`** — Extracts plain text from Wix rich-text JSON nodes, loads artist bios/statements from text files, loads AI-generated summaries.
- **`lib/wix.py`** — Transforms `wix:image://` URLs into static CDN URLs (`static.wixstatic.com`).

### Pipeline scripts

1. **`extract_text.py`** — Parses `Artists.csv`, extracts JSON-encoded bios/statements into `text/bios/`, `text/statements/`, and a combined `text/all_texts.txt`.

2. **`generate_summaries.py`** — Reads the combined text file, sends each artist's text to a local Ollama API, outputs `text/artist_summaries.json`. Only needs to be run once or when artist data changes.

3. **`main.py`** — PDF-specific code only. Reads `Artists.csv` via `lib/`, generates `ArtistCatalog.pdf`. Key components:
   - `NumberedCanvas` class: custom ReportLab canvas that applies `background.jpg` and page footers
   - `scale_image`: scales ReportLab `Image` objects (PDF-specific, not reusable for Pillow)
   - `create_toc`: table of contents with photo grid and hyperlinked page references
   - `create_catalog`: artist profiles laid out 2 per page with photos, bios, artwork thumbnails

## Key Data Formats

- **`Artists.csv`**: Wix CMS export. Several columns contain JSON strings (bio, artist statement, sample pieces, artist photos, social links) that must be parsed with `json.loads()`. The first column name is BOM-prefixed — use `NAME_COLUMN` from `lib/artists.py`.
- **Image URLs**: Wix `wix:image://v1/` URLs transformed to static CDN URLs via `lib/wix.py`.
- **Fonts**: Custom Raleway fonts (`.ttf` files in project root).

## Dependencies

Defined in `requirements.txt`: `reportlab`, `pillow`, `requests`.
