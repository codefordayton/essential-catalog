#!/usr/bin/env python3
"""Process a single new artist from their Wix website URL.

Fetches the artist page, extracts metadata, generates a summary via Claude
if one doesn't already exist, and renders Instagram and Facebook social images.

Usage:
    python process_artist_url.py <artist-page-url>

Example:
    python process_artist_url.py https://www.essentialartistsdayton.org/artist/jane-doe
"""
import html as html_module
import json
import re
import sys
import os

import requests

from generate_summaries import build_prompt, call_claude, CLAUDE_DEFAULT_MODEL
from lib.text import load_summaries
from social.social import render_social_image, PLATFORMS, safe_name, OUTPUT_DIR

SUMMARIES_PATH = 'text/artist_summaries.json'
BASE_SITE_URL = 'https://www.essentialartistsdayton.org'


def fetch_page(url):
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text


def extract_meta(html, prop):
    """Extract og: meta tag content, trying both attribute orderings."""
    patterns = [
        rf'<meta\s+property="{re.escape(prop)}"\s+content="([^"]*)"',
        rf'<meta\s+content="([^"]*)"\s+property="{re.escape(prop)}"',
        rf'<meta\s+name="{re.escape(prop)}"\s+content="([^"]*)"',
        rf'<meta\s+content="([^"]*)"\s+name="{re.escape(prop)}"',
    ]
    for pattern in patterns:
        m = re.search(pattern, html)
        if m:
            return m.group(1)
    return None


WIX_MEDIA_BASE = 'https://static.wixstatic.com/media/'


def extract_gallery_image(page_html):
    """Extract the first artwork image URL from the Wix slideshow gallery.

    Parses the data-image-info JSON on the first wow-image element inside
    the slide-show-gallery-items container and builds a full CDN URL from
    the uri field.
    """
    m = re.search(
        r'data-testid="slide-show-gallery-items".*?data-image-info="([^"]+)"',
        page_html,
        re.DOTALL,
    )
    if not m:
        return None
    try:
        info = json.loads(html_module.unescape(m.group(1)))
        uri = info.get('imageData', {}).get('uri')
        if uri:
            return WIX_MEDIA_BASE + uri
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


def extract_page_text(page_html):
    """Extract visible bio/statement text from Wix rich-text elements."""
    # Wix renders body text in richTextElement containers
    chunks = re.findall(
        r'data-testid="richTextElement"[^>]*>(.*?)</[^>]+>',
        page_html,
        re.DOTALL,
    )
    if not chunks:
        return None
    # Strip inner tags and collapse whitespace
    texts = []
    for chunk in chunks:
        plain = re.sub(r'<[^>]+>', ' ', chunk)
        plain = re.sub(r'\s+', ' ', plain).strip()
        if len(plain) > 40:  # skip navigation snippets
            texts.append(plain)
    return '\n\n'.join(texts) if texts else None


def scrape_artist(url):
    """Fetch artist page and extract name, gallery image, and bio text."""
    print(f"Fetching {url}...")
    page_html = fetch_page(url)

    raw_name = extract_meta(page_html, 'og:title') or ''
    # og:title is "Artist Name | Essential Artists" — keep only the name part
    name = raw_name.split(' | ')[0].strip()

    return {
        'name': name,
        'image_url': extract_gallery_image(page_html),
        'text': extract_page_text(page_html) or extract_meta(page_html, 'og:description') or '',
        'url_slug': url.replace(BASE_SITE_URL, ''),
    }


def generate_summary(artist_name, text):
    """Generate summaries via the shared generate_summaries prompt and Claude."""
    prompt = build_prompt(artist_name, text)
    return call_claude(prompt, CLAUDE_DEFAULT_MODEL)


def process_artist_url(url):
    data = scrape_artist(url)

    if not data['name']:
        print("Error: could not extract artist name from page meta tags.")
        sys.exit(1)
    artist_name = data['name']
    print(f"Artist: {artist_name}")

    if not data['image_url']:
        print("Error: could not find gallery image in page (data-testid=\"slide-show-gallery-items\" not found or has no data-image-info).")
        sys.exit(1)

    # Load or generate summary
    summaries = load_summaries()
    artist_summary = summaries.get(artist_name, {})
    if isinstance(artist_summary, str):
        artist_summary = {'short': artist_summary, 'medium': artist_summary}

    if not artist_summary.get('short') and not artist_summary.get('medium'):
        if data['text']:
            print("Generating summary via Claude...")
            artist_summary = generate_summary(artist_name, data['text'])
            summaries[artist_name] = {**summaries.get(artist_name, {}), **artist_summary}
            with open(SUMMARIES_PATH, 'w') as f:
                json.dump(summaries, f, indent=2)
            print(f"Summary saved (short={len(artist_summary['short'])}ch, medium={len(artist_summary['medium'])}ch)")
        else:
            print("Warning: no bio text found — images will have no summary text.")
            artist_summary = {'short': '', 'medium': ''}
    else:
        print("Using existing summary from artist_summaries.json")

    # Download artwork
    print("Downloading artwork image...")
    resp = requests.get(data['image_url'], timeout=30)
    resp.raise_for_status()
    artwork_bytes = resp.content

    # Generate social images
    dirname = safe_name(artist_name)
    out_dir = os.path.join(OUTPUT_DIR, dirname)

    for platform, (width, height, summary_key) in PLATFORMS.items():
        summary = artist_summary.get(summary_key, '')
        out_path = os.path.join(out_dir, f'{platform}.png')
        print(f"Generating {platform} ({width}×{height})...")
        render_social_image(artwork_bytes, artist_name, summary, (width, height), out_path, data['url_slug'])

    print(f"\nDone! Images saved to {out_dir}/")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python process_artist_url.py <artist-page-url>")
        print("Example:")
        print("  python process_artist_url.py https://www.essentialartistsdayton.org/artist/jane-doe")
        sys.exit(1)

    process_artist_url(sys.argv[1])
