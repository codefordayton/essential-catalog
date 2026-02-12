import csv
import json
import os

from lib.text import extract_text_from_nodes
from lib.artists import NAME_COLUMN


def save_artist_texts():
    """Extract and save artist bios and statements to text files."""
    os.makedirs('text/bios', exist_ok=True)
    os.makedirs('text/statements', exist_ok=True)

    with open('text/all_texts.txt', 'w') as combined_file:
        with open('Artists.csv', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                artist_name = row[NAME_COLUMN]
                safe_name = "".join(x for x in artist_name if x.isalnum() or x.isspace()).strip()

                # Process Bio
                if row.get('Bio'):
                    try:
                        bio_data = json.loads(row['Bio'])
                        bio_text = ' '.join(extract_text_from_nodes(bio_data['nodes']))

                        with open(f'text/bios/{safe_name}_bio.txt', 'w') as f:
                            f.write(bio_text)

                        combined_file.write(f"=== {artist_name} Bio ===\n")
                        combined_file.write(bio_text)
                        combined_file.write("\n\n")
                    except Exception as e:
                        print(f"Error processing bio for {artist_name}: {e}")

                # Process Artist Statement
                if row.get('Artist Statement'):
                    try:
                        statement = row['Artist Statement']

                        with open(f'text/statements/{safe_name}_statement.txt', 'w') as f:
                            f.write(statement)

                        combined_file.write(f"=== {artist_name} Statement ===\n")
                        combined_file.write(statement)
                        combined_file.write("\n\n")
                    except Exception as e:
                        print(f"Error processing statement for {artist_name}: {e}")

if __name__ == "__main__":
    save_artist_texts()
