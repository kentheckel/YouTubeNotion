"""
Fetches daily view totals for all network channels and writes to public/daily-views.json.

Usage:
  python daily_views.py              # Fetch last 7 days (daily mode)
  python daily_views.py --backfill   # Fetch all available history back to 2022-01-01
"""

import os
import sys
import json
import pickle
from datetime import datetime, timedelta

import requests
from googleapiclient.discovery import build

# --- CONFIGURATION ---
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

CHANNELS = {
    "All The Smoke": "UC2ozVs4pg2K3uFLw6-0ayCQ",
    "KG Certified": "UCa9W_cPwwbDlwBwHOd1YWoQ",
    "Morning Kombat": "UC9Qy3sHrr5wil-rkYcmcNcw",
    "All The Smoke Fight": "UCFPoJNd0d4k1H9A6UOlikcg",
    "Ring Champs": "UCBX_Qx_Hx5QTuEL72YVyn_A",
    "San Antonio Spurs": "UCEZHE-0CoHqeL1LGFa2EmQw",
    "Killswitch": "UCbwGkD8-Fbxun7zgzfC5kjg",
    "The Late Run": "UCcZ6iVdTPU5g4pN3MaIbruw",
    "Michael Easter": "UC-3foA4PyACqvubjyrlzIcg",
    "Anik & Florian": "UCDqSRXkx0E58VdH__Y8expQ",
    "No Such Thing": "UCFRiYABu5iXlkEF5ZCZd6wQ",
}

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "public", "daily-views.json")
BACKFILL_START = "2022-01-01"


def load_existing_data():
    """Load existing daily-views.json if it exists."""
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r") as f:
            return json.load(f)
    return {"last_updated": None, "channels": {}, "daily": {}}


def load_token(channel_id):
    """Load OAuth credentials for a channel, return None if unavailable."""
    token_path = os.path.join(SCRIPT_DIR, "tokens", f"token_{channel_id}.pickle")
    try:
        with open(token_path, "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        return None


def fetch_daily_views(creds, channel_id, start_date, end_date):
    """
    Fetch daily views from YouTube Analytics API.
    Returns dict of {date_str: view_count}.
    Processes in 180-day chunks to stay within API limits.
    """
    daily = {}
    chunk_start = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    youtube_analytics = build("youtubeAnalytics", "v2", credentials=creds)

    while chunk_start < end_dt:
        chunk_end = min(chunk_start + timedelta(days=180), end_dt)
        try:
            response = youtube_analytics.reports().query(
                ids=f"channel=={channel_id}",
                startDate=chunk_start.strftime("%Y-%m-%d"),
                endDate=chunk_end.strftime("%Y-%m-%d"),
                metrics="views",
                dimensions="day",
                sort="day",
            ).execute()

            for row in response.get("rows", []):
                daily[row[0]] = row[1]

        except Exception as e:
            print(f"  Warning: Analytics API error for chunk {chunk_start.date()}–{chunk_end.date()}: {e}")

        chunk_start = chunk_end + timedelta(days=1)

    return daily


def get_channel_total_views(channel_id):
    """Get lifetime total views from YouTube Data API (no OAuth needed)."""
    if not YOUTUBE_API_KEY:
        return 0
    url = "https://www.googleapis.com/youtube/v3/channels"
    params = {"part": "statistics", "id": channel_id, "key": YOUTUBE_API_KEY}
    try:
        res = requests.get(url, params=params).json()
        return int(res["items"][0]["statistics"]["viewCount"])
    except (KeyError, IndexError, requests.RequestException):
        return 0


def main():
    backfill = "--backfill" in sys.argv
    data = load_existing_data()
    today = datetime.utcnow().date()

    if backfill:
        start_date = BACKFILL_START
        print(f"Backfill mode: fetching from {start_date} to {today}")
    else:
        start_date = (today - timedelta(days=7)).isoformat()
        print(f"Daily mode: fetching from {start_date} to {today}")

    end_date = today.isoformat()

    for channel_name, channel_id in CHANNELS.items():
        print(f"\n--- {channel_name} ---")

        # Always update lifetime total views
        total_views = get_channel_total_views(channel_id)
        data["channels"][channel_name] = {
            "channel_id": channel_id,
            "total_views": total_views,
        }

        # Fetch daily views if we have a token
        creds = load_token(channel_id)
        if creds is None:
            print(f"  No OAuth token — skipping daily analytics (lifetime total: {total_views:,})")
            continue

        daily_views = fetch_daily_views(creds, channel_id, start_date, end_date)
        print(f"  Fetched {len(daily_views)} days of data")

        # Merge into existing data
        for date_str, views in daily_views.items():
            if date_str not in data["daily"]:
                data["daily"][date_str] = {}
            data["daily"][date_str][channel_name] = views

    # Compute daily network totals
    for date_str in data["daily"]:
        channel_views = data["daily"][date_str]
        # Don't overwrite channel entries — just ensure _total is current
        channel_views["_total"] = sum(v for k, v in channel_views.items() if k != "_total")

    # Sort daily entries by date
    data["daily"] = dict(sorted(data["daily"].items()))

    # Summary stats
    data["last_updated"] = today.isoformat()
    data["network_total_views"] = sum(
        ch.get("total_views", 0) for ch in data["channels"].values()
    )

    # Date range info
    all_dates = list(data["daily"].keys())
    if all_dates:
        data["earliest_date"] = all_dates[0]
        data["latest_date"] = all_dates[-1]

    # Write output
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nWrote {OUTPUT_PATH}")
    print(f"  Dates covered: {len(all_dates)}")
    print(f"  Network lifetime views: {data['network_total_views']:,}")
    print(f"  Channels: {len(data['channels'])}")


if __name__ == "__main__":
    main()
