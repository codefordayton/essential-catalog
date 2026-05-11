# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python application that generates a professional PDF art catalog and social media images from Wix CMS CSV exports. It processes artist entries with photos, bios, artwork images, and social links.

## Running the Scripts

All scripts use a local virtual environment (`env/`) with Python 3.11:

```bash
source env/bin/activate

# Generate the PDF catalog (main workflow)
python main.py

# Extract artist bios/statements from CSV into text files
python extract_text.py

# Generate AI summaries (defaults to Claude API; see options below)
python generate_summaries.py

# Generate social media images for all artists
python social/social.py

# Generate social media images for a single artist
python social/social.py "Artist Name"

# Process a single new artist directly from their website URL (no CSV export needed)
python process_artist_url.py https://www.essentialartistsdayton.org/artist/artist-slug
```

`generate_summaries.py` supports two providers:

```bash
# Use Claude (default, requires ANTHROPIC_API_KEY)
python generate_summaries.py --provider claude

# Use a local Ollama model (requires Ollama running on port 11434)
python generate_summaries.py --provider ollama
python generate_summaries.py --provider ollama --model llama3.2
```

The script is incremental — it skips artists that already have non-empty summaries in `text/artist_summaries.json`.

`social/social.py` must be run from the repo root with `PYTHONPATH` set (or use the helper scripts below).

### Social image batch workflow (new artist cohort)

When processing a new batch of artists:

1. Export a fresh `Artists.csv` from Wix CMS containing all artists.
2. Run `python extract_text.py` to update `text/bios/`, `text/statements/`, and `text/all_texts.txt`.
3. Run `python generate_summaries.py` to generate summaries for new artists only.
4. Run social image generation — either `python social/social.py` for all, or use a batch script for a specific cohort (see `generate_april19_social.sh` as a template).

Batch helper scripts (e.g. `generate_april19_social.sh`) must `export PYTHONPATH="$(pwd)"` before calling `social/social.py` so the `lib/` module is importable.

Social images are written to `social/output/<Artist_Name>/` with one PNG per platform (`instagram.png`, `facebook.png`).

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

2. **`generate_summaries.py`** — Reads the combined text file, sends each artist's text to Claude (default) or a local Ollama model, outputs `text/artist_summaries.json`. Incremental — skips artists with existing non-empty summaries. Supports `--provider claude|ollama` and `--model` flags.

3. **`social/social.py`** — Social media image generator. Reads `Artists.csv` and `text/artist_summaries.json`, downloads artwork images, and renders branded images for Instagram (1080×1080) and Facebook (1200×630). Accepts an optional artist name argument to generate for a single artist. Must be run from the repo root with `PYTHONPATH` set.

4. **`process_artist_url.py`** — Single-artist URL workflow. Given a public Wix artist page URL, fetches the page, extracts name/image/description from `og:` meta tags, generates a Claude summary if needed, and renders social images. No CSV export required. Run from repo root: `python process_artist_url.py <url>`.

4. **`main.py`** — PDF-specific code only. Reads `Artists.csv` via `lib/`, generates `ArtistCatalog.pdf`. Key components:
   - `NumberedCanvas` class: custom ReportLab canvas that applies `background.jpg` and page footers
   - `scale_image`: scales ReportLab `Image` objects (PDF-specific, not reusable for Pillow)
   - `create_toc`: table of contents with photo grid and hyperlinked page references
   - `create_catalog`: artist profiles laid out 2 per page with photos, bios, artwork thumbnails

## Key Data Formats

- **`Artists.csv`**: Wix CMS export. Several columns contain JSON strings (bio, artist statement, sample pieces, artist photos, social links) that must be parsed with `json.loads()`. The first column name is BOM-prefixed — use `NAME_COLUMN` from `lib/artists.py`.
- **Image URLs**: Wix `wix:image://v1/` URLs transformed to static CDN URLs via `lib/wix.py`.
- **Fonts**: Custom Raleway fonts (`.ttf` files in project root).

## Dependencies

Defined in `requirements.txt`: `reportlab`, `pillow`, `requests`, `anthropic`.
