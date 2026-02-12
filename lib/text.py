import json
import os


def extract_text_from_nodes(nodes):
    """Recursively extract text from Wix rich-text JSON nodes."""
    text_parts = []
    for node in nodes:
        if 'nodes' in node:
            text_parts.extend(extract_text_from_nodes(node['nodes']))
        if 'textData' in node and 'text' in node['textData']:
            text = node['textData']['text'].strip()
            if text:
                text_parts.append(text)
    return text_parts


def extract_bio_text(bio_json_str):
    """Extract plain text from a Bio JSON string."""
    try:
        bio_data = json.loads(bio_json_str)
        if 'nodes' in bio_data:
            return ' '.join(extract_text_from_nodes(bio_data['nodes']))
        return ""
    except Exception as e:
        print(f"Error parsing bio: {e}")
        return ""


def load_artist_text(artist_name, texts_file='text/all_texts.txt'):
    """Load artist's bio and statement from the combined text file."""
    artist_name = artist_name.strip().replace('"', '')
    texts = {'bio': '', 'statement': ''}

    if not os.path.exists(texts_file):
        return texts

    current_artist = None
    current_type = None
    current_text = []

    with open(texts_file, 'r') as f:
        for line in f:
            line = line.rstrip()
            if line.startswith('=== ') and line.endswith(' ==='):
                if current_artist and current_type and current_artist == artist_name:
                    texts[current_type] = '\n'.join(current_text)

                header = line[4:-4]
                if ' Bio' in header:
                    current_artist = header[:-4].strip()
                    current_type = 'bio'
                elif ' Statement' in header:
                    current_artist = header[:-10].strip()
                    current_type = 'statement'
                current_text = []
            elif line:
                current_text.append(line)

        if current_artist and current_type and current_artist == artist_name:
            texts[current_type] = '\n'.join(current_text)

    return texts


def load_summaries(file_path='text/artist_summaries.json'):
    """Load artist summaries from JSON file."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading summaries: {str(e)}")
        return {}
