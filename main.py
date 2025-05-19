import requests
from datetime import datetime, timedelta
import pytz
import os

from googleapiclient.discovery import build
import pickle

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
    try:
        token_path = f"tokens/token_{channel_id}.pickle"
        with open(token_path, "rb") as token_file:
            creds = pickle.load(token_file)
    except FileNotFoundError:
        print(f"⚠️ No token found for {channel_id}")
        return {"views_28": 0, "subs_28": 0, "uploads_28": 0}

    youtube_analytics = build("youtubeAnalytics", "v2", credentials=creds)

    try:
        response = youtube_analytics.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=end_date,
            metrics="views,subscribersGained,subscribersLost,estimatedMinutesWatched,comments,likes,dislikes,averageViewDuration",
            dimensions="day",
            filters="",
            sort="day"
        ).execute()

        rows = response.get("rows", [])
        views = sum(row[1] for row in rows) if rows else 0
        subs = sum(row[2] - row[3] for row in rows) if rows else 0
        upload_count = get_uploads_in_range(channel_id, start_date, end_date, creds)

        return {
            "views_28": views,
            "subs_28": subs,
            "uploads_28": upload_count
        }

    except Exception as e:
        print(f"⚠️ Failed to get analytics for {channel_id}: {e}")
        return {"views_28": 0, "subs_28": 0, "uploads_28": 0}

def get_uploads_in_range(channel_id, start_date, end_date, creds):
    youtube = build("youtube", "v3", credentials=creds)
    upload_count = 0
    next_page_token = None

    while True:
        response = youtube.search().list(
            part="snippet",
            channelId=channel_id,
            maxResults=50,
            order="date",
            publishedAfter=start_date + "T00:00:00Z",
            publishedBefore=end_date + "T23:59:59Z",
            type="video",
            pageToken=next_page_token
        ).execute()

        upload_count += len(response.get("items", []))
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return upload_count

def find_existing_row(channel_name, date_str):
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers).json()
    pages = response.get("results", [])

    for page in pages:
        props = page["properties"]
        title = props.get("Channel Name", {}).get("title", [])
        date = props.get("Date", {}).get("date", {}).get("start", "")
        if title and title[0]["text"]["content"] == channel_name and date == date_str:
            return page["id"]

    return None

def upsert_notion_row(channel, stats, analytics, date_str):
    page_id = find_existing_row(channel, date_str)
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    payload = {
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

    if page_id:
        url = f"https://api.notion.com/v1/pages/{page_id}"
        res = requests.patch(url, headers=headers, json=payload)
        print(f"✅ Updated existing row for {channel}: {res.status_code}")
    else:
        url = "https://api.notion.com/v1/pages"
        payload["parent"] = {"database_id": NOTION_DATABASE_ID}
        res = requests.post(url, headers=headers, json=payload)
        print(f"✅ Created new row for {channel}: {res.status_code}")

# --- MAIN ---
today = datetime.now(pytz.timezone("US/Eastern")).strftime("%Y-%m-%d")
start_28_days = (datetime.now() - timedelta(days=28)).strftime("%Y-%m-%d")

for channel_name, channel_id in CHANNELS.items():
    stats = get_channel_stats(channel_id)
    analytics = get_analytics(channel_id, start_28_days, today)
    upsert_notion_row(channel_name, stats, analytics, today)

    # Debug output per channel
    print(f"Processing: {channel_name}")
    print(f"Stats: {stats}")
    print(f"Analytics: {analytics}")

print("✅ Finished processing all channels.")
