import json
import os
import random
from typing import Tuple, cast
from urllib.parse import urlparse

import fasttext
import jsonlines
import requests
import trafilatura
from warcio.archiveiterator import ArchiveIterator

## 1)
# Download a warc.paths.gz from https://data.commoncrawl.org/crawl-data/CC-NEWS/index.html
# Move it to the same directory as this script
# Unzip with `gzip -dk ./warc.paths.gz`

## 2)
# Download the language detection model using
# https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz

## 3)
# Run the script with `python script.py`
# This will create:
#   news.jsonl -- rename it with the month when done
#   processed_warcs.txt -- gets updated automatically
# Note: You can stop the script with `Ctrl+C` and restart it again later safely.

language_detection_model = fasttext.load_model("lid.176.ftz")

warc_base_url = "https://data.commoncrawl.org/"
warc_file_paths = open("warc.paths", "r").readlines()
jsonl_outfile = "news.jsonl"

news_domains_top50 = {
    "bbc.com",
    "bbc.co.uk",
    "nytimes.com",
    "msn.com",
    "cnn.comnews.google.com",
    "theguardian.com",
    "indiatimes.com",
    "foxnews.com",
    "dailymail.co.uk",
    "finance.yahoo.com",
    "people.com",
    "news.yahoo.com",
    "ndtv.com",
    "usatoday.com",
    "hindustantimes.com",
    "news18.com",
    "nypost.com",
    "cnbc.com",
    "forbes.com",
    "apnews.com",
    "indianexpress.com",
    "cbsnews.com",
    "nbcnews.com",
    "washingtonpost.com",
    "wsj.com",
    "reuters.com",
    "news.com.au",
    "thehindu.com",
    "businessinsider.com",
    "buzzfeed.com",
    "abc.net.au",
    "independent.co.uk",
    "telegraph.co.uk",
    "oneindia.com",
    "newsweek.com",
    "abcnews.go.com",
    "indiatoday.in",
    "thesun.co.uk",
    "india.com",
    "cbc.ca",
    "rediff.com",
    "news.sky.com",
    "politico.com",
    "mirror.co.uk",
    "express.co.uk",
    "drudgereport.com",
    "bloomberg.com",
    "thehill.com",
    "rt.com",
}

# Track which WARC files have been processed for resumability
processed_file = "processed_warcs.txt"
if os.path.exists(processed_file):
    with open(processed_file, "r") as f:
        processed_warcs = set(line.strip() for line in f)
else:
    with open(processed_file, "w") as f:
        f.write("")
        processed_warcs = set()

for warc_file_path in warc_file_paths:
    warc_file_path = warc_file_path.strip()
    if not warc_file_path:
        continue
    if warc_file_path in processed_warcs:
        print(f"Skipping already processed: {warc_file_path}")
        continue

    url = warc_base_url + warc_file_path
    print(f"Streaming {url}")

    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()

        record_count = 0
        match_count = 0

        with jsonlines.open(jsonl_outfile, mode="a") as writer:
            for record in ArchiveIterator(response.raw):
                if record.rec_type == "response":
                    record_count += 1
                    if record_count % 1000 == 0:
                        print(
                            f"  [{warc_file_path}] Processed {record_count} records, {match_count} matches"
                        )

                    target_url = record.rec_headers.get_header("WARC-Target-URI")
                    content = record.content_stream().read()

                    domain = urlparse(target_url).netloc.removeprefix("www.")

                    if domain in news_domains_top50:
                        result = trafilatura.extract(content, output_format="json")

                        if result is not None:
                            metadata = json.loads(result)
                            text = metadata.get("text", "")

                            if text:
                                lines = text.splitlines()
                                sample_lines = random.sample(lines, min(5, len(lines)))
                                predictions = [
                                    prediction_with_score := cast(
                                        Tuple[str, float],
                                        language_detection_model.predict(line)[0],
                                    )[0]
                                    for line in sample_lines
                                    if line.strip()
                                ]
                                if all(p == "__label__en" for p in predictions):
                                    writer.write(
                                        {
                                            "url": target_url,
                                            "date": record.rec_headers.get_header(
                                                "WARC-Date"
                                            ),
                                            "text": text,
                                        }
                                    )
                                    match_count += 1

        with open(processed_file, "a") as f:
            f.write(warc_file_path + "\n")
        processed_warcs.add(warc_file_path)
        print(
            f"Finished: {warc_file_path} ({record_count} records, {match_count} matches)"
        )

    except KeyboardInterrupt:
        print(
            f"\nInterrupted during {warc_file_path}. Will retry this file on next run."
        )
        break
    except Exception as e:
        print(f"Error processing {warc_file_path}: {e}")
        continue
