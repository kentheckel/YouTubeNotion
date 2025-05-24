import os
import requests
from googleapiclient.discovery import build
import pickle
from datetime import datetime, timedelta
import isodate
import json
import sys

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
    # Commenting out Spurs for now as requested
    # "San Antonio Spurs": "UCEZHE-0CoHqeL1LGFa2EmQw"
}

def load_token(channel_id):
    token_path = os.path.join(TOKEN_DIR, f"token_{channel_id}.pickle")
    if not os.path.exists(token_path):
        print(f"⚠️ No token found for {channel_id}")
        return None
    with open(token_path, "rb") as token_file:
        return pickle.load(token_file)

def fetch_recent_videos(creds, channel_id, days=1, max_results=5):
    """Only fetch videos from the past day to limit API calls"""
    try:
        youtube = build("youtube", "v3", credentials=creds)
        today = datetime.utcnow()
        start = (today - timedelta(days=days)).isoformat("T") + "Z"
        
        videos = []
        request = youtube.search().list(
            part="snippet",
            channelId=channel_id,
            maxResults=max_results,  # Reduced to save quota
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
    except Exception as e:
        if "quota" in str(e).lower():
            print(f"❌ YouTube API quota exceeded: {str(e)}")
            sys.exit(1)  # Exit if quota is exceeded
        else:
            print(f"❌ Error fetching videos: {str(e)}")
            return []

def fetch_video_details(creds, video_ids):
    """Get detailed video information"""
    try:
        if not video_ids:
            return []
            
        youtube = build("youtube", "v3", credentials=creds)
        request = youtube.videos().list(
            part="statistics,snippet,contentDetails",
            id=",".join(video_ids)
        )
        response = request.execute()
        return response.get("items", [])
    except Exception as e:
        if "quota" in str(e).lower():
            print(f"❌ YouTube API quota exceeded: {str(e)}")
            sys.exit(1)  # Exit if quota is exceeded
        else:
            print(f"❌ Error fetching video details: {str(e)}")
            return []

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
    try:
        duration_secs, duration_mins = parse_duration(video["contentDetails"]["duration"])
        vertical = is_vertical(video["snippet"]["thumbnails"])
        format_type = "Short" if vertical else "Long Form"

        payload = {
            "parent": {"database_id": VIDEO_DB_ID},
            "properties": {
                "Video Title": {"title": [{"text": {"content": video["snippet"]["title"]}}]},
                "Channel Name": {"rich_text": [{"text": {"content": channel_name}}]},
                "URL": {"url": f"https://www.youtube.com/watch?v={video['id']}"},
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
        if res.status_code != 200:
            print(f"❌ Failed to create row for {video['snippet']['title']}: {res.status_code} | {res.text}")
        else:
            print(f"✅ Added video: {video['snippet']['title']}")
    except Exception as e:
        print(f"❌ Error creating Notion row for {video.get('id', 'unknown')}: {str(e)}")

def is_video_in_notion(video_id):
    # This function would check if video already exists in Notion
    # For now, just returning False to process all videos
    # In a future update, we could implement a proper check to avoid duplicates
    return False

def run_video_tracker():
    print(f"🚀 Starting focused video tracker at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("⚙️ Focusing only on adding new videos to save API quota")
    
    videos_added = 0
    missing_tokens = []
    
    for channel_name, channel_id in CHANNELS.items():
        print(f"\n📊 Processing channel: {channel_name}")
        
        creds = load_token(channel_id)
        if not creds:
            missing_tokens.append(channel_name)
            continue

        try:
            # Fetch only very recent videos (1 day) with a small limit
            recent_videos = fetch_recent_videos(creds, channel_id, days=1, max_results=5)
            if not recent_videos:
                print(f"ℹ️ No recent videos found for {channel_name}")
                continue
                
            print(f"🔍 Found {len(recent_videos)} recent videos")
            
            # Get the video details
            video_ids = [v["videoId"] for v in recent_videos]
            video_details = fetch_video_details(creds, video_ids)

            # Add each video to Notion
            for video in video_details:
                create_notion_video_row(video, channel_name)
                videos_added += 1
                
        except Exception as e:
            print(f"❌ Error processing {channel_name}: {str(e)}")
    
    # Summary
    print(f"\n✅ Video tracker completed - Added {videos_added} videos to Notion")        
    if missing_tokens:
        print(f"\n⚠️ Missing tokens for: {', '.join(missing_tokens)}")

if __name__ == "__main__":
    run_video_tracker()
