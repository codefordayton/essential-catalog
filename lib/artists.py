import csv
import json

from lib.wix import transform_wix_image_url

# The Wix CSV export prefixes the first column name with a BOM character.
NAME_COLUMN = '\ufeff"Name"'


def parse_csv_to_dict(file_path):
    """Parse a CSV file into a list of dictionaries.

    Args:
        file_path: Path to the CSV file

    Returns:
        list of dicts, one per row, or None on error.
    """
    data = []
    try:
        with open(file_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                data.append(row)
        return data
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found")
        return None
    except Exception as e:
        print(f"Error reading CSV file: {str(e)}")
        return None


def sort_artists_by_lastname(artists_data):
    """Sort artists by last name."""
    return sorted(artists_data, key=lambda x: x['Lastname'])


def extract_image_sources(data):
    """Extract artwork image URLs from the Sample Piece column.

    Returns:
        dict mapping artist names to lists of CDN URLs.
    """
    image_sources = {}
    for row in data:
        name = row.get(NAME_COLUMN, 'Unknown Artist')
        try:
            sample_piece = row.get('Sample Piece', '')
            if not sample_piece:
                print(f"No Sample Piece data for artist: {name}")
                continue

            sample_pieces = json.loads(sample_piece)
            if not isinstance(sample_pieces, list):
                sample_pieces = [sample_pieces]

            sources = [
                item['src'] for item in sample_pieces
                if isinstance(item, dict) and 'src' in item
                and isinstance(item['src'], str)
                and item['src'].startswith('wix:image')
            ]

            output_sources = []
            for source in sources:
                url = transform_wix_image_url(source)
                if url:
                    output_sources.append(url)

            if output_sources:
                image_sources[name] = output_sources
            else:
                print(f"No valid image sources found for artist: {name}")

        except json.JSONDecodeError as e:
            print(f"JSON parsing error for artist {name}: {str(e)}")
        except KeyError as e:
            print(f"Missing key {e} for artist: {name}")
        except Exception as e:
            print(f"Unexpected error processing {name}: {str(e)}")

    return image_sources


def extract_artist_photos(data):
    """Extract artist photo URLs from the Photo column.

    Returns:
        dict mapping artist names to lists of CDN URLs.
    """
    artist_photos = {}
    for row in data:
        name = row.get(NAME_COLUMN, 'Unknown Artist')
        try:
            photo = row.get('Photo', '')
            if not photo or not isinstance(photo, str):
                continue

            url = transform_wix_image_url(photo)
            if url:
                artist_photos[name] = [url]

        except Exception as e:
            print(f"Error processing photo for {name}: {str(e)}")

    return artist_photos
