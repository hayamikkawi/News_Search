from config import CONFIG
from crawler.pipeline import run_feed_pipeline
from crawler.output import write_jsonl

def main():
    # Use one to have a try
    feed_url = "https://feeds.bbci.co.uk/news/rss.xml"

    # https://www.theguardian.com/uk/rss
    # https://www.theguardian.com/world/rss
    # https://feeds.bbci.co.uk/news/rss.xml
    # https://feeds.bbci.co.uk/news/world/rss.xml

    # feeds = [
    #     "https://feeds.bbci.co.uk/news/rss.xml",
    #     "https://www.theguardian.com/world/rss",
    #     "https://www.ft.com/rss/home",
    # ]
    #
    # for feed_url in feeds:
    #     records = run_feed_pipeline(...)
    #     write_jsonl(...)


    records = run_feed_pipeline(
        feed_url=feed_url,
        user_agent=CONFIG.user_agent,#Crawler identification and ethical compliance
        timeout_seconds=CONFIG.timeout_seconds,
        max_items=CONFIG.max_items_per_feed, # Limits the number of RSS entries processed per feed in a single run.
        sleep_seconds=CONFIG.sleep_seconds, # Defines the fixed delay applied between consecutive HTTP requests, Avoid Blocks.
        jitter_seconds=CONFIG.jitter_seconds,# Adds a random delay (uniformly sampled from [0, jitter_seconds]) on top of sleep_seconds.
        min_text_length=CONFIG.min_text_length #Filters out navigation pages, login pages, error pages, or teaser-only content.
    )

    write_jsonl(CONFIG.output_path, records)

    ok = sum(1 for r in records if r.extracted and r.extracted.get("text_ok"))
    print(f"Done. {ok}/{len(records)} extracted OK. Output: {CONFIG.output_path}")

if __name__ == "__main__":
    main()
