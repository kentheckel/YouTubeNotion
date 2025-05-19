import requests
from datetime import datetime, timedelta
import pytz
import os

# --- CONFIGURATION ---
YOUTUBE_API_KEY = os.environ["YOUTUBE_API_KEY"]
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]


CHANNELS = {
    "All The Smoke": "UC2ozVs4pg2K3uFLw6-0ayCQ",
    "KG Certified": "UCa9W_cPwwbDlwBwHOd1YWoQ",
    "Morning Kombat": "UC9Qy3sHrr5wil-rkYcmcNcw",
    "All The Smoke Fight": "UCFPoJNd0d4k1H9A6UOlikcg",
    "Ring Champs": "UCBX_Qx_Hx5QTuEL72YVyn_A",
    "Victor Oladipo": "UCf5fcEALUCA53oUW3mc8tiQ",
    "San Antonio Spurs": "UCEZHE-0CoHqeL1LGFa2EmQw"
}

# --- HELPERS ---
def get_channel_stats(channel_id):
    url = "https://www.googleapis.com/youtube/v3/channels"
    params = {
        "part": "statistics",
        "id": channel_id,
        "key": YOUTUBE_API_KEY
    }
    res = requests.get(url, params=params).json()
    stats = res["items"][0]["statistics"]
    return {
        "subs": int(stats["subscriberCount"]),
        "views": int(stats["viewCount"]),
        "videos": int(stats["videoCount"])
    }

def get_analytics(channel_id, start_date, end_date):
    # NOTE: This endpoint requires OAuth2, not just an API key.
    # Placeholder data for now.
    return {
        "views_28": 0,
        "subs_28": 0,
        "uploads_28": 0
    }

def get_notion_pages():
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    return requests.post(url, headers=headers).json()

def find_existing_row(channel_name, date_str):
    pages = get_notion_pages().get("results", [])
    for page in pages:
        props = page["properties"]
        title = props.get("Channel Name", {}).get("title", [])
        date = props.get("Date", {}).get("date", {}).get("start", "")
        if title and title[0]["text"]["content"] == channel_name and date.startswith(date_str):
            return page["id"]
    return None

def upsert_notion_row(channel, stats, analytics, date_str):
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Channel Name": {"title": [{"text": {"content": channel}}]},
            "Date": {"date": {"start": date_str}},
            "Subscribers": {"number": stats["subs"]},
            "Total Views": {"number": stats["views"]},
            "Total Videos": {"number": stats["videos"]},
            "Views (28 Days)": {"number": analytics["views_28"]},
            "Subs (28 Days)": {"number": analytics["subs_28"]},
            "Uploads (28 Days)": {"number": analytics["uploads_28"]}
        }
    }

    res = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload)
    print(f"Notion response for {channel}:", res.status_code, res.text)


    if page_id:
        url = f"https://api.notion.com/v1/pages/{page_id}"
        requests.patch(url, headers=headers, json=payload)
    else:
        url = "https://api.notion.com/v1/pages"
        payload["parent"] = {"database_id": NOTION_DATABASE_ID}
        requests.post(url, headers=headers, json=payload)

# --- MAIN ---
today = datetime.now(pytz.timezone("US/Eastern")).strftime("%Y-%m-%d")
start_28_days = (datetime.now() - timedelta(days=28)).strftime("%Y-%m-%d")

for channel_name, channel_id in CHANNELS.items():
    stats = get_channel_stats(channel_id)
    analytics = get_analytics(channel_id, start_28_days, today)
    upsert_notion_row(channel_name, stats, analytics, today)

"✅ Script updated with analytics placeholders. OAuth setup needed for 28-day stats."
print(f"Processing: {channel_name}")
print(f"Stats: {stats}")
print(f"Analytics: {analytics}")
print("✅ Finished processing all channels.")

