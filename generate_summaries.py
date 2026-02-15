import json
import anthropic


def generate_summaries(text_file_path, output_file_path):
    """
    Generate concise summaries from artist texts using Claude and save to file.

    Requires ANTHROPIC_API_KEY environment variable.
    """
    client = anthropic.Anthropic()

    summaries = {}
    current_artist = None
    current_type = None
    current_text = []

    # First, collect all texts for each artist
    artist_texts = {}

    with open(text_file_path, 'r') as f:
        for line in f:
            line = line.rstrip()
            if line.startswith('=== ') and line.endswith(' ==='):
                # Save previous entry if exists
                if current_artist and current_type:
                    if current_artist not in artist_texts:
                        artist_texts[current_artist] = {}
                    artist_texts[current_artist][current_type] = '\n'.join(current_text)

                # Parse new header
                header = line[4:-4]  # Remove '=== ' and ' ==='
                if ' Bio' in header:
                    current_artist = header[:-4].strip()
                    current_type = 'bio'
                elif ' Statement' in header:
                    current_artist = header[:-10].strip()
                    current_type = 'statement'
                current_text = []
            elif line:
                current_text.append(line)

    # Handle final entry
    if current_artist and current_type:
        if current_artist not in artist_texts:
            artist_texts[current_artist] = {}
        artist_texts[current_artist][current_type] = '\n'.join(current_text)

    # Summary lengths for different social media formats
    length_configs = {
        "short": "STRICT LIMIT: 1-2 sentences, maximum 120 characters total. This is for a small banner.",
        "medium": "STRICT LIMIT: 2-3 sentences, maximum 220 characters total. This is for a square post.",
        "long": "STRICT LIMIT: 2-4 sentences, maximum 350 characters total. This is for a tall story.",
    }

    # Now generate summaries for each artist
    for artist, texts in artist_texts.items():
        combined_text = ""
        if 'bio' in texts:
            combined_text += texts['bio'] + "\n\n"
        if 'statement' in texts:
            combined_text += texts['statement']

        if combined_text:
            # Generate all three lengths in a single API call for efficiency
            prompt = f"""Write three summaries of this artist for social media posts. Each summary should be compelling and focus on their unique artistic perspective and style.

Rules:
- Do NOT start with "Meet" or "Discover"
- Describe the artist and their work directly
- Use the artist's full name in each summary
- Count characters carefully and stay within limits

Length requirements:
- short: {length_configs['short']}
- medium: {length_configs['medium']}
- long: {length_configs['long']}

Artist text:
{combined_text}

Respond in this exact JSON format (no markdown, no code fences):
{{"short": "...", "medium": "...", "long": "..."}}"""

            try:
                response = client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=512,
                    messages=[
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": "{"},
                    ],
                )
                result = "{" + response.content[0].text.strip()
                # Strip anything after the closing brace
                brace_end = result.rfind('}')
                if brace_end != -1:
                    result = result[:brace_end + 1]
                artist_summaries = json.loads(result)
                summaries[artist] = artist_summaries
                print(f"Generated summaries for {artist} "
                      f"(short={len(artist_summaries['short'])}ch, "
                      f"medium={len(artist_summaries['medium'])}ch, "
                      f"long={len(artist_summaries['long'])}ch)")
            except Exception as e:
                print(f"Error generating summaries for {artist}: {str(e)}")
                summaries[artist] = {"short": "", "medium": "", "long": ""}

    # Save summaries to file
    with open(output_file_path, 'w') as f:
        json.dump(summaries, f, indent=2)

    print(f"\nSummaries saved to {output_file_path}")


if __name__ == "__main__":
    generate_summaries('text/all_texts.txt', 'text/artist_summaries.json')
