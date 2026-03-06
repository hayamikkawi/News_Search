CONTENT_HEADLINE_DOMAINS = {
    "www.cbsnews.com",
    "www.indiatoday.in",
    "www.independent.co.uk",
}


import json
import re
import sys
from urllib.parse import urlparse


def url_to_headline(url):
    path = urlparse(url).path
    parts = [s for s in path.split("/") if s]

    # Find the last path segment that isn't purely numeric (e.g. a date like 20260129)
    slug = None
    for part in reversed(parts):
        clean = re.sub(r"\.\w+$", "", part)
        if not re.fullmatch(r"\d+", clean):
            slug = clean
            break

    if not slug:
        return url  # fallback to raw URL if nothing usable found

    slug = re.sub(r"\.\w+$", "", slug)  # strip extension
    slug = re.sub(
        r"-?\d+$", "", slug
    )  # strip any trailing numbers from the slug itself

    words = [w.capitalize() for w in slug.split("-") if w]
    return " ".join(words)


def get_headline(record):
    url = record.get("url", "")
    domain = urlparse(url).netloc.lstrip("www.")

    if domain in CONTENT_HEADLINE_DOMAINS:
        content = record.get("content", "")
        return content.split("\n")[0].strip()
    else:
        return url_to_headline(url)


def jsonl_to_json(input_path, output_path):
    records = []
    with open(input_path, "r") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if line:
                record = json.loads(line)
                record["id"] = i
                record["headline"] = get_headline(record)
                records.append(record)

    with open(output_path, "w") as f:
        json.dump(records, f, indent=2)

    print(f"Converted {len(records)} records to {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python convert.py <input.jsonl> <output.json>")
        sys.exit(1)

    jsonl_to_json(sys.argv[1], sys.argv[2])
