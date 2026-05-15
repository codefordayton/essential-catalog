import os
import re
import sys
from colorsys import rgb_to_hsv, hsv_to_rgb
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from lib.artists import parse_csv_to_dict, sort_artists_by_lastname, extract_image_sources, NAME_COLUMN
from lib.images import get_cached_image_with_rotation
from lib.text import load_summaries

# Platform sizes and summary length keys: (width, height, summary_key)
PLATFORMS = {
    'instagram': (1080, 1080, 'medium'),
    'facebook': (1200, 630, 'short'),
}

FONT_BOLD = 'Raleway-Bold.ttf'
FONT_REGULAR = 'Raleway-VariableFont_wght.ttf'
OUTPUT_DIR = 'social/output'
BASE_URL = 'https://www.essentialartistsdayton.org'


def get_dominant_color(img):
    """Extract dominant non-gray color from image and boost its saturation."""
    small = img.copy()
    small.thumbnail((50, 50))
    small = small.convert('RGB')
    pixels = list(small.getdata())

    # Filter out near-gray pixels (low saturation)
    colorful = []
    for r, g, b in pixels:
        h, s, v = rgb_to_hsv(r / 255, g / 255, b / 255)
        if s > 0.15 and v > 0.1:
            colorful.append((r, g, b))

    if not colorful:
        # Fallback: use average color
        colorful = pixels

    # Find most common color by bucketing
    buckets = {}
    for r, g, b in colorful:
        key = (r // 32, g // 32, b // 32)
        buckets.setdefault(key, []).append((r, g, b))

    largest_bucket = max(buckets.values(), key=len)
    avg_r = sum(c[0] for c in largest_bucket) // len(largest_bucket)
    avg_g = sum(c[1] for c in largest_bucket) // len(largest_bucket)
    avg_b = sum(c[2] for c in largest_bucket) // len(largest_bucket)

    # Boost saturation
    h, s, v = rgb_to_hsv(avg_r / 255, avg_g / 255, avg_b / 255)
    s = min(1.0, s * 1.6 + 0.2)
    v = min(1.0, max(0.5, v))
    r, g, b = hsv_to_rgb(h, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


def wrap_text(text, font, max_width):
    """Word-wrap text to fit within max_width pixels. Returns list of lines."""
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = font.getbbox(test_line)
        if bbox[2] - bbox[0] <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]

    if current_line:
        lines.append(' '.join(current_line))
    return lines


def truncate_to_sentences(text, font, max_width, max_lines):
    """Truncate text at a sentence or clause boundary that fits within the given lines."""
    # First try splitting at sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    fitted = ''
    for sentence in sentences:
        candidate = (fitted + ' ' + sentence).strip() if fitted else sentence
        lines = wrap_text(candidate, font, max_width)
        if len(lines) <= max_lines:
            fitted = candidate
        else:
            break

    # If the fitted text works, use it
    if fitted and len(wrap_text(fitted, font, max_width)) <= max_lines:
        return fitted

    # Fallback: trim at clause boundaries (commas) within the first sentence
    clauses = sentences[0].split(', ') if sentences else [text]
    fitted = ''
    for i, clause in enumerate(clauses):
        sep = ', ' if fitted else ''
        candidate = fitted + sep + clause
        # Add period if we might stop here
        test_candidate = candidate.rstrip('.') + '.'
        lines = wrap_text(test_candidate, font, max_width)
        if len(lines) <= max_lines:
            fitted = candidate
        else:
            break

    if fitted:
        return fitted.rstrip('.') + '.'
    return text


def render_social_image(artwork_bytes, artist_name, summary, size, output_path=None, artist_url=''):
    """Render a social media image for one artist at the given size."""
    width, height = size

    # Open artwork and scale/crop to fill canvas
    artwork = Image.open(BytesIO(artwork_bytes)).convert('RGB')
    art_w, art_h = artwork.size
    scale = max(width / art_w, height / art_h)
    new_w = int(art_w * scale)
    new_h = int(art_h * scale)
    artwork = artwork.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    artwork = artwork.crop((left, top, left + width, top + height))

    canvas = artwork.copy()

    # Gradient overlay from bottom
    gradient = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw_grad = ImageDraw.Draw(gradient)
    gradient_height = int(height * 0.5)
    for y in range(gradient_height):
        alpha = int(180 * (y / gradient_height))
        draw_grad.line(
            [(0, height - gradient_height + y), (width, height - gradient_height + y)],
            fill=(0, 0, 0, alpha),
        )
    canvas = canvas.convert('RGBA')
    canvas = Image.alpha_composite(canvas, gradient)

    # Get accent color from artwork
    accent = get_dominant_color(artwork)

    # Determine frame area based on aspect ratio
    margin = int(width * 0.05)
    if width > height:
        # Facebook landscape
        frame_top = int(height * 0.42)
    else:
        # Instagram square
        frame_top = int(height * 0.68)

    frame_bottom = height - margin
    frame_left = margin
    frame_right = width - margin
    frame_radius = 24

    # Draw semi-transparent rounded rectangle frame
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    draw_overlay.rounded_rectangle(
        [(frame_left, frame_top), (frame_right, frame_bottom)],
        radius=frame_radius,
        fill=(*accent, 190),
    )
    canvas = Image.alpha_composite(canvas, overlay)

    # Text rendering
    draw = ImageDraw.Draw(canvas)
    text_left = frame_left + int(margin * 0.8)
    text_right = frame_right - int(margin * 0.8)
    text_max_width = text_right - text_left
    shadow_offset = max(1, int(width * 0.002))

    def draw_text_with_shadow(xy, text, font, fill):
        """Draw text with a subtle dark shadow for readability."""
        x, y = xy
        draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=(0, 0, 0, 100))
        draw.text((x, y), text, font=font, fill=fill)

    name_size = max(24, int(width * 0.042))
    summary_size = max(14, int(width * 0.022))

    font_name = ImageFont.truetype(FONT_BOLD, name_size)
    font_summary = ImageFont.truetype(FONT_BOLD, summary_size)

    # Artist name
    name_y = frame_top + int(margin * 0.6)
    draw_text_with_shadow((text_left, name_y), artist_name, font=font_name, fill=(255, 255, 255))

    # Summary text
    name_bbox = font_name.getbbox(artist_name)
    summary_y = name_y + (name_bbox[3] - name_bbox[1]) + int(margin * 0.6)

    # URL line
    url_size = max(14, int(width * 0.022))
    font_url = ImageFont.truetype(FONT_BOLD, url_size)
    url_line_height = int(url_size * 1.4)
    url_text = BASE_URL + artist_url if artist_url else ''

    if summary:
        line_height = int(summary_size * 1.4)
        # Reserve space for URL line at the bottom
        url_space = (url_line_height + int(margin * 0.3)) if url_text else 0
        available_height = frame_bottom - summary_y - int(margin * 0.4) - url_space
        max_lines = max(1, available_height // line_height)

        lines = wrap_text(summary, font_summary, text_max_width)
        lines = lines[:max_lines]

        for line in lines:
            draw_text_with_shadow((text_left, summary_y), line, font=font_summary, fill=(255, 255, 255, 230))
            summary_y += line_height

    # Draw artist URL
    if url_text:
        url_y = frame_bottom - int(margin * 0.4) - url_line_height
        draw_text_with_shadow((text_left, url_y), url_text, font=font_url, fill=(255, 255, 255, 200))

    # Save to path or return bytes
    if output_path is not None:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        canvas.convert('RGB').save(output_path, 'PNG')
    else:
        buf = BytesIO()
        canvas.convert('RGB').save(buf, 'PNG')
        buf.seek(0)
        return buf.read()


def safe_name(name):
    """Convert artist name to filesystem-safe directory name."""
    return re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')


def generate_all(csv_path='Artists.csv', single_artist=None):
    """Generate social media images for all (or one) artist."""
    data = parse_csv_to_dict(csv_path)
    if not data:
        print("Failed to load CSV data.")
        return

    data = sort_artists_by_lastname(data)
    image_sources = extract_image_sources(data)
    summaries = load_summaries()

    for row in data:
        artist_name = row.get(NAME_COLUMN, '').strip().replace('"', '')
        if not artist_name:
            continue
        if single_artist and artist_name != single_artist:
            continue

        if artist_name not in image_sources or not image_sources[artist_name]:
            print(f"Skipping {artist_name}: no artwork images")
            continue

        artwork_url = image_sources[artist_name][0]
        artwork_bytes = get_cached_image_with_rotation(artwork_url)
        if not artwork_bytes:
            print(f"Skipping {artist_name}: failed to download artwork")
            continue

        artist_summaries = summaries.get(artist_name, '')
        # Support both old format (plain string) and new format (dict with short/medium/long)
        if isinstance(artist_summaries, str):
            artist_summaries = {'short': artist_summaries, 'medium': artist_summaries, 'long': artist_summaries}
        artist_url = row.get('Artists (Item)', '')
        dirname = safe_name(artist_name)
        out_dir = os.path.join(OUTPUT_DIR, dirname)

        for platform, (width, height, summary_key) in PLATFORMS.items():
            summary = artist_summaries.get(summary_key, '')
            out_path = os.path.join(out_dir, f'{platform}.png')
            print(f"Generating {platform} for {artist_name}...")
            render_social_image(artwork_bytes, artist_name, summary, (width, height), out_path, artist_url)

        print(f"Done: {artist_name} -> {out_dir}/")

    if single_artist:
        print(f"\nFinished generating images for {single_artist}")
    else:
        print(f"\nFinished generating all social media images in {OUTPUT_DIR}/")


if __name__ == '__main__':
    single = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else None
    generate_all(single_artist=single)
