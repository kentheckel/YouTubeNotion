"""One-shot dedup for the ASFC YouTube video tracker Notion database.

For each (Channel Name, Video ID) group with multiple pages, keeps the earliest-created
page and archives the rest. Run with --dry-run first to preview.

Usage:
    python dedup_notion_videos.py --dry-run
    python dedup_notion_videos.py
"""
import argparse
import os
import sys
import time
from collections import defaultdict

import requests
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
VIDEO_DB_ID = os.getenv("NOTION_VIDEO_DB_ID")
NOTION_VERSION = "2026-03-11"

if not NOTION_TOKEN or not VIDEO_DB_ID:
    sys.exit("NOTION_TOKEN and NOTION_VIDEO_DB_ID must be set in env.")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}


def get_data_source_id():
    r = requests.get(f"https://api.notion.com/v1/databases/{VIDEO_DB_ID}", headers=HEADERS)
    r.raise_for_status()
    data_sources = r.json().get("data_sources") or []
    if not data_sources:
        sys.exit(f"No data sources on database {VIDEO_DB_ID}")
    return data_sources[0]["id"]


def fetch_all_pages(data_source_id):
    url = f"https://api.notion.com/v1/data_sources/{data_source_id}/query"
    pages = []
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        r = requests.post(url, headers=HEADERS, json=body)
        r.raise_for_status()
        data = r.json()
        pages.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
        print(f"  Fetched {len(pages)} pages so far...")
    return pages


def extract_rich_text(prop):
    if not prop:
        return ""
    items = prop.get("rich_text") or []
    return "".join(item.get("plain_text", "") for item in items).strip()


def archive_page(page_id):
    r = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=HEADERS,
        json={"archived": True},
    )
    if r.status_code != 200:
        print(f"  ❌ Failed to archive {page_id}: {r.status_code} {r.text}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--channel", help="Only dedup this channel name")
    args = parser.parse_args()

    data_source_id = get_data_source_id()
    print(f"Data source: {data_source_id}")
    print("Fetching all pages...")
    pages = fetch_all_pages(data_source_id)
    print(f"Total pages: {len(pages)}\n")

    groups = defaultdict(list)
    for page in pages:
        props = page.get("properties", {})
        video_id = extract_rich_text(props.get("Video ID"))
        channel_name = extract_rich_text(props.get("Channel Name"))
        if not video_id:
            continue
        if args.channel and channel_name != args.channel:
            continue
        groups[(channel_name, video_id)].append(
            {"id": page["id"], "created": page.get("created_time", "")}
        )

    to_archive = []
    for (channel, vid), rows in groups.items():
        if len(rows) <= 1:
            continue
        rows.sort(key=lambda r: r["created"])
        keep = rows[0]
        dups = rows[1:]
        to_archive.extend((channel, vid, keep["id"], d["id"]) for d in dups)

    by_channel = defaultdict(int)
    for channel, _, _, _ in to_archive:
        by_channel[channel] += 1
    print("Duplicates to archive by channel:")
    for ch, n in sorted(by_channel.items(), key=lambda x: -x[1]):
        print(f"  {ch}: {n}")
    print(f"TOTAL: {len(to_archive)}\n")

    if args.dry_run:
        print("Dry run — no changes made.")
        return

    if not to_archive:
        print("Nothing to do.")
        return

    confirm = input(f"Archive {len(to_archive)} duplicate pages? [y/N] ")
    if confirm.lower() != "y":
        print("Aborted.")
        return

    archived = 0
    for i, (channel, vid, keep_id, dup_id) in enumerate(to_archive, 1):
        if archive_page(dup_id):
            archived += 1
        if i % 50 == 0:
            print(f"  Archived {archived}/{i}...")
        time.sleep(0.34)  # ~3 req/s, Notion rate limit
    print(f"\n✅ Archived {archived}/{len(to_archive)} duplicate pages.")


if __name__ == "__main__":
    main()
