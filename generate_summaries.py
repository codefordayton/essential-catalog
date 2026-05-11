import argparse
import json
import re
import requests
import anthropic

CLAUDE_DEFAULT_MODEL = 'claude-sonnet-4-6'
OLLAMA_DEFAULT_MODEL = 'llama3.1'
OLLAMA_BASE_URL = 'http://localhost:11434'

LENGTH_CONFIGS = {
    "short": "STRICT LIMIT: 1-2 sentences, maximum 120 characters total. This is for a small banner.",
    "medium": "STRICT LIMIT: 2-3 sentences, maximum 220 characters total. This is for a square post.",
    "long": "STRICT LIMIT: 2-4 sentences, maximum 350 characters total. This is for a tall story.",
}


def build_prompt(artist_name, combined_text):
    return f"""Write three summaries of this artist for social media posts. Each summary should be compelling and focus on their unique artistic perspective and style.

Rules:
- Do NOT start with "Meet" or "Discover"
- Describe the artist and their work directly
- The artist's name is: {artist_name} — use this exact name (never substitute a placeholder or different name)
- Count characters carefully and stay within limits

Length requirements:
- short: {LENGTH_CONFIGS['short']}
- medium: {LENGTH_CONFIGS['medium']}
- long: {LENGTH_CONFIGS['long']}

Artist text:
{combined_text}

Respond in this exact JSON format (no markdown, no code fences):
{{"short": "...", "medium": "...", "long": "..."}}"""


def extract_json(text):
    """Extract the first complete JSON object from a response string."""
    start = text.find('{')
    if start == -1:
        raise ValueError("No JSON object found in response")
    end = text.rfind('}')
    if end == -1:
        raise ValueError("No closing brace found in response")
    return json.loads(text[start:end + 1])


def call_claude(prompt, model):
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return extract_json(response.content[0].text)


def call_ollama(prompt, model):
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        },
        timeout=120,
    )
    response.raise_for_status()
    return extract_json(response.json()["message"]["content"])


def parse_artist_texts(text_file_path):
    artist_texts = {}
    current_artist = None
    current_type = None
    current_text = []

    with open(text_file_path, 'r') as f:
        for line in f:
            line = line.rstrip()
            if line.startswith('=== ') and line.endswith(' ==='):
                if current_artist and current_type:
                    artist_texts.setdefault(current_artist, {})[current_type] = '\n'.join(current_text)

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

    if current_artist and current_type:
        artist_texts.setdefault(current_artist, {})[current_type] = '\n'.join(current_text)

    return artist_texts


def generate_summaries(text_file_path, output_file_path, provider='claude', model=None):
    if model is None:
        model = CLAUDE_DEFAULT_MODEL if provider == 'claude' else OLLAMA_DEFAULT_MODEL

    print(f"Provider: {provider}, Model: {model}")

    # Load existing summaries so we don't regenerate
    try:
        with open(output_file_path, 'r') as f:
            summaries = json.load(f)
        print(f"Loaded {len(summaries)} existing summaries from {output_file_path}")
    except (FileNotFoundError, json.JSONDecodeError):
        summaries = {}

    artist_texts = parse_artist_texts(text_file_path)

    for artist, texts in artist_texts.items():
        existing = summaries.get(artist)
        if existing and any(existing.get(k) for k in ('short', 'medium', 'long')):
            print(f"Skipping {artist} (already has summary)")
            continue

        combined_text = ""
        if 'bio' in texts:
            combined_text += texts['bio'] + "\n\n"
        if 'statement' in texts:
            combined_text += texts['statement']

        if not combined_text:
            continue

        prompt = build_prompt(artist, combined_text)

        try:
            if provider == 'claude':
                artist_summaries = call_claude(prompt, model)
            else:
                artist_summaries = call_ollama(prompt, model)

            summaries[artist] = artist_summaries
            print(f"Generated summaries for {artist} "
                  f"(short={len(artist_summaries['short'])}ch, "
                  f"medium={len(artist_summaries['medium'])}ch, "
                  f"long={len(artist_summaries['long'])}ch)")
        except Exception as e:
            print(f"Error generating summaries for {artist}: {str(e)}")
            summaries[artist] = {"short": "", "medium": "", "long": ""}

    with open(output_file_path, 'w') as f:
        json.dump(summaries, f, indent=2)

    print(f"\nSummaries saved to {output_file_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate artist summaries for social media")
    parser.add_argument(
        '--provider',
        choices=['claude', 'ollama'],
        default='claude',
        help='LLM provider to use (default: claude)',
    )
    parser.add_argument(
        '--model',
        default=None,
        help=f'Model name (default: {CLAUDE_DEFAULT_MODEL} for Claude, {OLLAMA_DEFAULT_MODEL} for Ollama)',
    )
    args = parser.parse_args()

    generate_summaries(
        'text/all_texts.txt',
        'text/artist_summaries.json',
        provider=args.provider,
        model=args.model,
    )
