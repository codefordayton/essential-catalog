# Essential Artists Dayton — Catalog Tools

Python tools for generating a PDF art catalog and social media images from the Essential Artists Dayton Wix CMS.

## What's here

| Script / App | Purpose |
|---|---|
| `main.py` | Generate the PDF catalog (`ArtistCatalog.pdf`) |
| `extract_text.py` | Pull artist bios and statements out of `Artists.csv` into text files |
| `generate_summaries.py` | Use Claude (or a local Ollama model) to write short social media summaries |
| `social/social.py` | Render Instagram and Facebook images for all artists (or one by name) |
| `process_artist_url.py` | Generate images for a single artist directly from their website URL |
| `app.py` | Web app — artists self-serve their own social images |

## Setup

Requires Python 3.11 and a virtual environment:

```bash
python3.11 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

Set your Anthropic API key (required for summary generation):

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## Web app

The simplest way for artists to generate their own images. Run locally:

```bash
source env/bin/activate
python app.py
```

Then open [http://localhost:5000](http://localhost:5000). Enter an artist page URL (e.g. `https://www.essentialartistsdayton.org/artist/amy-kollar-anderson`), review and edit the description, and download Instagram and Facebook images.

For production deployment see [Deployment](#deployment) below.

## Batch workflow (new artist cohort)

Run these steps after exporting a fresh `Artists.csv` from Wix CMS:

```bash
source env/bin/activate

# 1. Extract bios and statements from CSV into text files
python extract_text.py

# 2. Generate AI summaries for any artists that don't have one yet
python generate_summaries.py

# 3a. Generate social images for all artists
python social/social.py

# 3b. Or generate for a single artist
python social/social.py "Artist Name"
```

Social images are written to `social/output/<Artist_Name>/instagram.png` and `facebook.png`.

## PDF catalog

```bash
source env/bin/activate
python main.py
```

Outputs `ArtistCatalog.pdf`.

## Single-artist URL workflow

Process one new artist directly from their website without a CSV export:

```bash
source env/bin/activate
python process_artist_url.py https://www.essentialartistsdayton.org/artist/artist-slug
```

## Summary generation options

`generate_summaries.py` is incremental — it skips artists that already have summaries.

```bash
# Use Claude (default)
python generate_summaries.py

# Use a local Ollama model
python generate_summaries.py --provider ollama
python generate_summaries.py --provider ollama --model llama3.2
```

## Deployment

The web app (`app.py`) is configured for [Render](https://render.com) via `Procfile`.

1. Push this repo to GitHub.
2. Create a new **Web Service** on Render pointed at the repo.
3. Set the environment variable `ANTHROPIC_API_KEY` in Render's dashboard.
4. Render will run `gunicorn app:app` automatically.

The app checks `text/artist_summaries.json` for existing summaries before calling the Claude API, so artists who've already been processed get instant results.

## Project structure

```
lib/
  artists.py      CSV parsing and image URL extraction
  images.py       Image download, caching, EXIF rotation
  text.py         Bio/statement loading, summary loading
  wix.py          Wix image URL → CDN URL
social/
  social.py       Social image renderer
  output/         Generated images (gitignored)
templates/
  index.html      Web app UI
text/
  bios/           Per-artist bio text files
  statements/     Per-artist statement text files
  all_texts.txt   Combined text file for summary generation
  artist_summaries.json  AI-generated summaries (short / medium / long)
image_cache/      Downloaded image cache (gitignored)
```
