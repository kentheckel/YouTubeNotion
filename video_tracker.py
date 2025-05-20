import os
import requests
from googleapiclient.discovery import build
import pickle
from datetime import datetime, timedelta
import isodate

# Load environment variables
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
VIDEO_DB_ID = os.getenv("NOTION_VIDEO_DB_ID")

# Directory with tokens like tokens/token_<channel_id>.pickle
TOKEN_DIR = "tokens"

# Channel map
CHANNELS = {
    "All The Smoke": "UC2ozVs4pg2K3uFLw6-0ayCQ",
    "KG Certified": "UCa9W_cPwwbDlwBwHOd1YWoQ",
    "Morning Kombat": "UC9Qy3sHrr5wil-rkYcmcNcw",
    "All The Smoke Fight": "UCFPoJNd0d4k1H9A6UOlikcg",
    "Ring Champs": "UCBX_Qx_Hx5QTuEL72YVyn_A",
    "Victor Oladipo": "UCf5fcEALUCA53oUW3mc8tiQ",
    "San Antonio Spurs": "UCEZHE-0CoHqeL1LGFa2EmQw"
}

def load_token(channel_id):
    token_path = os.path.join(TOKEN_DIR, f"token_{channel_id}.pickle")
    if not os.path.exists(token_path):
        print(f"⚠️ No token found for {channel_id}")
        return None
    with open(token_path, "rb") as token_file:
        return pickle.load(token_file)

def fetch_recent_videos(creds, channel_id):
    youtube = build("youtube", "v3", credentials=creds)
    today = datetime.utcnow()
    start = (today - timedelta(days=1)).isoformat("T") + "Z"
    
    videos = []
    request = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        maxResults=10,
        publishedAfter=start,
        type="video",
        order="date"
    )
    response = request.execute()
    for item in response.get("items", []):
        videos.append({
            "videoId": item["id"]["videoId"],
            "title": item["snippet"]["title"],
            "publishedAt": item["snippet"]["publishedAt"]
        })
    return videos

def fetch_video_details(creds, video_ids):
    youtube = build("youtube", "v3", credentials=creds)
    request = youtube.videos().list(
        part="statistics,snippet,contentDetails",
        id=",".join(video_ids)
    )
    response = request.execute()
    return response.get("items", [])

def parse_duration(duration):
    try:
        td = isodate.parse_duration(duration)
        return td.total_seconds(), round(td.total_seconds() / 60, 2)
    except:
        return 0, 0

def is_vertical(thumbnails):
    high = thumbnails.get("high", {})
    return high.get("height", 0) > high.get("width", 0)

def create_notion_video_row(video, channel_name):
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    duration_secs, duration_mins = parse_duration(video["contentDetails"]["duration"])
    vertical = is_vertical(video["snippet"]["thumbnails"])
    format_type = "Short" if vertical else "Long Form"

    payload = {
        "parent": {"database_id": VIDEO_DB_ID},
        "properties": {
            "Video Title": {"title": [{"text": {"content": video["snippet"]["title"]}}]},
            "Channel Name": {"rich_text": [{"text": {"content": channel_name}}]},
            "Video URL": {"url": f"https://www.youtube.com/watch?v={video['id']}"},
            "Date Published": {"date": {"start": video["snippet"]["publishedAt"]}},
            "Views": {"number": int(video["statistics"].get("viewCount", 0))},
            "Subs Gained": {"number": int(video["statistics"].get("subscriberGained", 0))},
            "Revenue": {"number": 0},  # Placeholder for now
            "Avg View %": {"number": 0},  # Placeholder for now
            "Avg View Min": {"number": duration_mins},
            "Format": {"select": {"name": format_type}},
            "Thumbnail": {"url": f"https://i.ytimg.com/vi/{video['id']}/hqdefault.jpg"}
        }
    }

    res = requests.post(url, headers=headers, json=payload)
    print(f"📹 Added video: {video['snippet']['title']} ({res.status_code})")

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

def run_video_tracker():
    for channel_name, channel_id in CHANNELS.items():
        creds = load_token(channel_id)
        if not creds:
            continue

        recent_videos = fetch_recent_videos(creds, channel_id)
        if not recent_videos:
            continue

        video_ids = [v["videoId"] for v in recent_videos]
        video_details = fetch_video_details(creds, video_ids)

        for video in video_details:
            create_notion_video_row(video, channel_name)

if __name__ == "__main__":
    run_video_tracker()
