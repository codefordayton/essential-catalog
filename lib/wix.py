WIX_IMAGE_BASE_URL = "https://static.wixstatic.com/media/"


def transform_wix_image_url(wix_url):
    """Transform a wix:image:// URL into a static CDN URL.

    Args:
        wix_url: URL in the format 'wix:image://v1/<hash>/<filename>'

    Returns:
        Full static CDN URL, or None if the input isn't a Wix image URL.
    """
    if not wix_url or not wix_url.startswith('wix:image'):
        return None
    local_path = wix_url.replace('wix:image://v1/', '')
    local_path = local_path[:local_path.rindex('/')]
    return WIX_IMAGE_BASE_URL + local_path
