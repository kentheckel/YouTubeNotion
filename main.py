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

    try:
        stats = res["items"][0]["statistics"]
        return {
            "subs": int(stats["subscriberCount"]),
            "views": int(stats["viewCount"]),
            "videos": int(stats["videoCount"])
        }
    except (KeyError, IndexError):
        print(f"⚠️ Failed to get stats for {channel_id}: {res}")
        return {"subs": 0, "views": 0, "videos": 0}


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
        title_prop = props.get("Channel Name", {}).get("title", [])
        date_object = props.get("Date", {}).get("date")
        icon_files = props.get("Channel Icon", {}).get("files", [])
        icon_url = icon_files[0]["file"]["url"] if icon_files else ""

        title = title_prop[0]["text"]["content"] if title_prop else ""
        date = date_object.get("start") if date_object else ""

        if title == channel_name and date == date_str:
            return page["id"], icon_url

    return None, ""




def upsert_notion_row(channel, stats, analytics, yearly, date_str):
    page_id, icon_url = find_existing_row(channel, date_str)

    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    properties = {
        "Channel Name": {"title": [{"text": {"content": channel}}]},
        "Date": {"date": {"start": date_str}},
        "Subscribers": {"number": stats["subs"]},
        "Total Views": {"number": stats["views"]},
        "Total Videos": {"number": stats["videos"]},
        "Views (28 Days)": {"number": analytics["views_28"]},
        "Subs (28 Days)": {"number": analytics["subs_28"]},
        "Uploads (28 Days)": {"number": analytics["uploads_28"]},
        "Views (Prev 28 Days)": {"number": analytics["views_prev_28"]},
        "Subs (Prev 28 Days)": {"number": analytics["subs_prev_28"]},
        "Uploads (Prev 28 Days)": {"number": analytics["uploads_prev_28"]},
        "Views (365 Days)": {"number": analytics["views_365"]},
        "Subs (365 Days)": {"number": analytics["subs_365"]},
        "Views (2022)": {"number": yearly["views_2022"]},
        "Subs (2022)": {"number": yearly["subs_2022"]},
        "Views (2023)": {"number": yearly["views_2023"]},
        "Subs (2023)": {"number": yearly["subs_2023"]},
        "Views (2024)": {"number": yearly["views_2024"]},
        "Subs (2024)": {"number": yearly["subs_2024"]}
    }

    payload = {"properties": properties}

    if page_id:
        url = f"https://api.notion.com/v1/pages/{page_id}"
        res = requests.patch(url, headers=headers, json=payload)
        print(f"🔴 Notion PATCH response for {channel}: {res.status_code} | {res.text}")
    else:
        url = "https://api.notion.com/v1/pages"
        payload["parent"] = {"database_id": NOTION_DATABASE_ID}
        res = requests.post(url, headers=headers, json=payload)
        print(f"🟡 Notion POST response for {channel}: {res.status_code} | {res.text}")


def fetch_analytics_for_range(creds, channel_id, start_date, end_date):
    youtube_analytics = build("youtubeAnalytics", "v2", credentials=creds)
    response = youtube_analytics.reports().query(
        ids=f"channel=={channel_id}",
        startDate=start_date,
        endDate=end_date,
        metrics="views,subscribersGained,subscribersLost",
        dimensions="day",
        sort="day"
    ).execute()

    rows = response.get("rows", [])
    views = sum(row[1] for row in rows) if rows else 0
    subs = sum(row[2] - row[3] for row in rows) if rows else 0
    return views, subs

def get_advanced_analytics(channel_id):
    try:
        token_path = f"tokens/token_{channel_id}.pickle"
        with open(token_path, "rb") as token_file:
            creds = pickle.load(token_file)
    except FileNotFoundError:
        print(f"⚠️ No token found for {channel_id}")
        return {
            "views_28": 0, "subs_28": 0,
            "views_prev_28": 0, "subs_prev_28": 0,
            "uploads_28": 0, "uploads_prev_28": 0,
            "views_365": 0, "subs_365": 0
        }

    today = datetime.utcnow().date()
    start_28 = (today - timedelta(days=28)).isoformat()
    start_prev_28 = (today - timedelta(days=56)).isoformat()
    end_prev_28 = (today - timedelta(days=29)).isoformat()
    start_365 = (today - timedelta(days=365)).isoformat()
    today_str = today.isoformat()

    try:
        views_28, subs_28 = fetch_analytics_for_range(creds, channel_id, start_28, today_str)
        views_prev_28, subs_prev_28 = fetch_analytics_for_range(creds, channel_id, start_prev_28, end_prev_28)

        uploads_28 = get_uploads_in_range(channel_id, start_28, today_str, creds)
        uploads_prev_28 = get_uploads_in_range(channel_id, start_prev_28, end_prev_28, creds)

        views_365, subs_365 = fetch_analytics_for_range(creds, channel_id, start_365, today_str)

        return {
            "views_28": views_28,
            "subs_28": subs_28,
            "uploads_28": uploads_28,
            "views_prev_28": views_prev_28,
            "subs_prev_28": subs_prev_28,
            "uploads_prev_28": uploads_prev_28,
            "views_365": views_365,
            "subs_365": subs_365
        }

    except Exception as e:
        print(f"⚠️ Analytics fetch failed for {channel_id}: {e}")
        return {
            "views_28": 0, "subs_28": 0,
            "uploads_28": 0,
            "views_prev_28": 0, "subs_prev_28": 0,
            "uploads_prev_28": 0,
            "views_365": 0, "subs_365": 0
        }

def get_yearly_analytics(channel_id):
    try:
        token_path = f"tokens/token_{channel_id}.pickle"
        with open(token_path, "rb") as token_file:
            creds = pickle.load(token_file)
    except FileNotFoundError:
        print(f"⚠️ No token found for {channel_id}")
        return {
            "views_2022": 0, "subs_2022": 0,
            "views_2023": 0, "subs_2023": 0,
            "views_2024": 0, "subs_2024": 0
        }

    def fetch_for_year(year):
        start = f"{year}-01-01"
        end = f"{year}-12-31"
        return fetch_analytics_for_range(creds, channel_id, start, end)

    try:
        views_2022, subs_2022 = fetch_for_year(2022)
        views_2023, subs_2023 = fetch_for_year(2023)
        views_2024, subs_2024 = fetch_for_year(2024)

        return {
            "views_2022": views_2022,
            "subs_2022": subs_2022,
            "views_2023": views_2023,
            "subs_2023": subs_2023,
            "views_2024": views_2024,
            "subs_2024": subs_2024
        }

    except Exception as e:
        print(f"⚠️ Failed yearly analytics for {channel_id}: {e}")
        return {
            "views_2022": 0, "subs_2022": 0,
            "views_2023": 0, "subs_2023": 0,
            "views_2024": 0, "subs_2024": 0
        }

# --- MAIN ---
if __name__ == "__main__":
    today = datetime.now(pytz.timezone("US/Eastern")).strftime("%Y-%m-%d")
    start_28_days = (datetime.now() - timedelta(days=28)).strftime("%Y-%m-%d")

    for channel_name, channel_id in CHANNELS.items():
        stats = get_channel_stats(channel_id)
        analytics = get_advanced_analytics(channel_id)
        yearly_analytics = get_yearly_analytics(channel_id)
        upsert_notion_row(channel_name, stats, analytics, yearly_analytics, today)

        # Debug output per channel
        print(f"Processing: {channel_name}")
        print(f"Stats: {stats}")
        print(f"Analytics (28-day & previous): {analytics}")
        print(f"Yearly Analytics: {yearly_analytics}")

    print("✅ Finished processing all channels.")

import json

# Final export list
export_data = []

for channel_name, channel_id in CHANNELS.items():
    stats = get_channel_stats(channel_id)
    analytics = get_advanced_analytics(channel_id)
    yearly_analytics = get_yearly_analytics(channel_id)
    page_id, icon_url = find_existing_row(channel_name, today)

    # Add all values into exportable JSON
    export_data.append({
        "name": channel_name,
        "icon": icon_url,
        "views_28": analytics["views_28"],
        "views_prev_28": analytics["views_prev_28"],
        "subs_28": analytics["subs_28"],
        "subs_prev_28": analytics["subs_prev_28"],
        "uploads_28": analytics["uploads_28"],
        "uploads_prev_28": analytics["uploads_prev_28"]
    })

# Write data.json for widget
os.makedirs("public", exist_ok=True)
with open("public/data.json", "w") as f:
    json.dump(export_data, f, indent=2)

