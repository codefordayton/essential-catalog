import os
import uuid
from io import BytesIO

import requests
from flask import Flask, jsonify, render_template, request, send_file

from process_artist_url import scrape_artist, generate_summary
from social.social import PLATFORMS, render_social_image
from lib.text import load_summaries

app = Flask(__name__)

# In-memory store: session_id -> {platform: bytes}
_image_store = {}
_MAX_SESSIONS = 50


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/extract', methods=['POST'])
def extract():
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'Please enter a URL.'}), 400

    try:
        artist_data = scrape_artist(url)
    except requests.RequestException as e:
        return jsonify({'error': f'Could not load that page: {e}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    if not artist_data.get('name'):
        return jsonify({'error': 'Could not find artist name on that page.'}), 400
    if not artist_data.get('image_url'):
        return jsonify({'error': 'Could not find artwork image on that page.'}), 400

    name = artist_data['name']
    summary_short = ''
    summary_medium = ''
    summary_note = ''

    # Check existing summaries file first (fast, no API call)
    existing = load_summaries().get(name, {})
    if isinstance(existing, str):
        existing = {'short': existing, 'medium': existing}

    if existing.get('short') or existing.get('medium'):
        summary_short = existing.get('short', '')
        summary_medium = existing.get('medium', summary_short)
    elif artist_data.get('text'):
        try:
            result = generate_summary(name, artist_data['text'])
            summary_short = result.get('short', '')
            summary_medium = result.get('medium', summary_short)
        except Exception as e:
            summary_note = 'Could not auto-generate a description — please write your own below.'

    return jsonify({
        'name': name,
        'image_url': artist_data['image_url'],
        'url_slug': artist_data['url_slug'],
        'summary_short': summary_short,
        'summary_medium': summary_medium,
        'summary_note': summary_note,
    })


@app.route('/api/generate', methods=['POST'])
def generate():
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    image_url = data.get('image_url', '').strip()
    url_slug = data.get('url_slug', '')
    summary_short = data.get('summary_short', '')
    summary_medium = data.get('summary_medium', '')

    if not name or not image_url:
        return jsonify({'error': 'Missing name or image URL.'}), 400

    # Map each platform to its summary length key
    summaries = {'instagram': summary_medium, 'facebook': summary_short}

    try:
        resp = requests.get(image_url, timeout=30)
        resp.raise_for_status()
        artwork_bytes = resp.content
    except requests.RequestException as e:
        return jsonify({'error': f'Could not download artwork image: {e}'}), 400

    session_id = str(uuid.uuid4())
    images = {}
    for platform, (width, height, _) in PLATFORMS.items():
        img_bytes = render_social_image(
            artwork_bytes, name, summaries[platform], (width, height), artist_url=url_slug
        )
        images[platform] = img_bytes

    _image_store[session_id] = images

    # Evict oldest session when over limit
    if len(_image_store) > _MAX_SESSIONS:
        del _image_store[next(iter(_image_store))]

    return jsonify({'session_id': session_id})


@app.route('/image/<session_id>/<platform>')
def get_image(session_id, platform):
    images = _image_store.get(session_id)
    if not images or platform not in images:
        return 'Not found', 404
    return send_file(BytesIO(images[platform]), mimetype='image/png')


if __name__ == '__main__':
    app.run(debug=True)
