import os
import hashlib
import requests
from io import BytesIO
from PIL import Image as PILImage, ImageDraw, ExifTags


def get_cached_image(url, cache_dir="image_cache"):
    """Get image from cache if it exists, otherwise download and cache it.

    Args:
        url: URL of the image
        cache_dir: Directory to store cached images

    Returns:
        bytes: Image data, or None on failure.
    """
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    filename = hashlib.md5(url.encode()).hexdigest() + ".jpeg"
    cache_path = os.path.join(cache_dir, filename)

    if os.path.exists(cache_path):
        with open(cache_path, 'rb') as f:
            return f.read()

    try:
        response = requests.get(url)
        response.raise_for_status()
        with open(cache_path, 'wb') as f:
            f.write(response.content)
        return response.content
    except Exception as e:
        print(f"Error downloading image from {url}: {str(e)}")
        return None


def get_cached_image_with_rotation(url):
    """Get image data from cache and correct EXIF rotation."""
    image_data = get_cached_image(url)
    if not image_data:
        return None

    img = PILImage.open(BytesIO(image_data))

    try:
        for orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation] == 'Orientation':
                break

        exif = img._getexif()
        if exif is not None:
            orientation = exif.get(orientation)
            if orientation == 3:
                img = img.rotate(180, expand=True)
            elif orientation == 6:
                img = img.rotate(270, expand=True)
            elif orientation == 8:
                img = img.rotate(90, expand=True)
    except (AttributeError, KeyError, IndexError, TypeError):
        pass

    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format=img.format if img.format else 'JPEG')
    img_byte_arr.seek(0)
    return img_byte_arr.getvalue()


def round_corners(image_bytes, radius=30):
    """Round the corners of an image with higher internal resolution for better quality."""
    im = PILImage.open(BytesIO(image_bytes))

    if im.mode != 'RGB':
        im = im.convert('RGB')

    internal_size = 288  # 144 * 2
    final_size = 144

    original_width, original_height = im.size
    ratio = max(internal_size / original_width, internal_size / original_height)
    new_width = int(original_width * ratio)
    new_height = int(original_height * ratio)

    im = im.resize((new_width, new_height), PILImage.Resampling.LANCZOS)

    left = (new_width - internal_size) // 2
    top = (new_height - internal_size) // 2
    im = im.crop((left, top, left + internal_size, top + internal_size))

    mask = PILImage.new('L', (internal_size, internal_size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (internal_size, internal_size)], radius=radius * 2, fill=255)

    output = PILImage.new('RGBA', (internal_size, internal_size), (0, 0, 0, 0))
    output.paste(im, mask=mask)

    output = output.resize((final_size, final_size), PILImage.Resampling.LANCZOS)

    img_byte_arr = BytesIO()
    output.save(img_byte_arr, format='PNG', quality=95)
    img_byte_arr.seek(0)
    return img_byte_arr.getvalue()
