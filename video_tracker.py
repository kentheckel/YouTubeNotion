import os
import requests
from googleapiclient.discovery import build
import pickle
from datetime import datetime, timedelta, timezone
import isodate
import json
import sys

# --- Load .env file ---
from dotenv import load_dotenv
load_dotenv() # Loads variables from .env into environment
# --- End Load .env file ---

# Load environment variables
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
VIDEO_DB_ID = os.getenv("NOTION_VIDEO_DB_ID")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

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
        today = datetime.now(timezone.utc)
        start_datetime = today - timedelta(days=days) # Calculate the datetime object
        start = start_datetime.strftime('%Y-%m-%dT%H:%M:%SZ') # Format as YYYY-MM-DDTHH:MM:SSZ
        
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
        if "quota" in str(e).lower() or ("HttpError 403" in str(e) and "quota" in str(e).lower()):
            print(f"🟡 YouTube API quota likely exceeded for channel {channel_id} while fetching recent videos: {str(e)}")
            return None
        else:
            print(f"❌ Error fetching videos for channel {channel_id}: {str(e)}")
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
        if "quota" in str(e).lower() or ("HttpError 403" in str(e) and "quota" in str(e).lower()):
            print(f"🟡 YouTube API quota likely exceeded while fetching details for videos {','.join(video_ids)}: {str(e)}")
            return None
        else:
            print(f"❌ Error fetching video details for videos {','.join(video_ids)}: {str(e)}")
            return []

def parse_duration(duration):
    try:
        td = isodate.parse_duration(duration)
        return td.total_seconds(), round(td.total_seconds() / 60, 2)
    except:
        return 0, 0

def get_video_format_details(thumbnails, duration_seconds):
    """
    Determines if a video is likely a Short based on aspect ratio and duration.
    Returns the format_type_string: "Short" or "Long Form".
    """
    is_vertical_or_square = False
    # Ensure thumbnails and high quality thumbnail data exist before accessing
    if isinstance(thumbnails, dict):
        high_thumb = thumbnails.get("high", {})
        if isinstance(high_thumb, dict):
            height = high_thumb.get("height", 0)
            width = high_thumb.get("width", 0)

            if height > 0 and width > 0: # Ensure we have valid dimensions
                if height > width: # Vertical
                    is_vertical_or_square = True
                elif height == width: # Square
                    is_vertical_or_square = True
    
    # YouTube defines Shorts as up to 60 seconds.
    # Using <= 61 seconds for a little leniency.
    is_short_duration = duration_seconds <= 61 

    if is_vertical_or_square and is_short_duration:
        return "Short" 
    return "Long Form"

def is_vertical(thumbnails):
    high = thumbnails.get("high", {})
    return high.get("height", 0) > high.get("width", 0)

def create_notion_video_row(video, channel_name, channel_id):
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    try:
        duration_secs, duration_mins = parse_duration(video["contentDetails"]["duration"])
        format_type = get_video_format_details(video["snippet"]["thumbnails"], duration_secs)

        payload = {
            "parent": {"database_id": VIDEO_DB_ID},
            "properties": {
                "Video Title": {"title": [{"text": {"content": video["snippet"]["title"]}}]},
                "Channel Name": {"rich_text": [{"text": {"content": channel_name}}]},
                "URL": {"url": f"https://www.youtube.com/watch?v={video['id']}"},
                "Date Published": {"date": {"start": video["snippet"]["publishedAt"]}},
                "Views": {"number": int(video["statistics"].get("viewCount", 0))},
                # Subs Gained via videos().list is generally not available or accurate for individual videos.
                # It often returns 0 or is missing. True subscriber impact is better tracked at the channel level.
                "Subs Gained": {"number": int(video["statistics"].get("subscriberGained", 0))}, # Typically 0 from this API endpoint
                "Revenue": {"number": 0},  # Placeholder; requires YouTube Analytics API & monetary scope
                "Avg View %": {"number": 0},  # Placeholder; requires YouTube Analytics API
                "Duration (Mins)": {"number": duration_mins}, # Renamed from Avg View Min
                "Format": {"select": {"name": format_type}},
                "Thumbnail": {"url": f"https://i.ytimg.com/vi/{video['id']}/hqdefault.jpg"},
                "Video ID": {"rich_text": [{"text": {"content": video["id"]}}]},
                "Channel ID": {"rich_text": [{"text": {"content": channel_id}}]}
            }
        }

        res = requests.post(url, headers=headers, json=payload)
        if res.status_code != 200:
            print(f"❌ Failed to create row for {video['snippet']['title']}: {res.status_code} | {res.text}")
        else:
            print(f"✅ Added video to Notion: {video['snippet']['title']}")
    except Exception as e:
        print(f"❌ Error creating Notion row for {video.get('id', 'unknown')}: {str(e)}")

def is_video_in_notion(video_id):
    """Checks if a video with the given video_id already exists in the Notion database."""
    if not VIDEO_DB_ID or not NOTION_TOKEN:
        print("❌ Notion DB ID or Token not configured. Cannot check for existing videos.")
        return False # Or raise an error

    url = f"https://api.notion.com/v1/databases/{VIDEO_DB_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    payload = {
        "filter": {
            "property": "Video ID", # Assumes you have a text property named 'Video ID'
            "rich_text": {
                "equals": video_id
            }
        }
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            return len(data.get("results", [])) > 0
        else:
            print(f"❌ Error querying Notion to check for video {video_id}: {response.status_code} - {response.text}")
            return False # Default to false on error to avoid blocking new entries, but log it
    except Exception as e:
        print(f"❌ Exception querying Notion for video {video_id}: {str(e)}")
        return False

def run_video_tracker():
    print(f"🚀 Starting video tracker at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    # print("⚙️ Focusing only on adding new videos to save API quota") # Commenting out, it's implied
    
    videos_added_total = 0
    missing_tokens_channels = []
    quota_issues_channels = []
    
    for channel_name, channel_id in CHANNELS.items():
        print(f"\n📊 Processing channel: {channel_name} ({channel_id})")
        
        creds = load_token(channel_id)
        if not creds:
            missing_tokens_channels.append(channel_name)
            continue

        try:
            recent_videos_response = fetch_recent_videos(creds, channel_id, days=1, max_results=5)
            
            if recent_videos_response is None: # Check for quota issue from fetch_recent_videos
                quota_issues_channels.append(channel_name)
                print(f"🟡 Skipping {channel_name} due to YouTube API quota issue during recent video fetch.")
                continue
            if not recent_videos_response: # Empty list, no recent videos
                print(f"ℹ️ No new videos found for {channel_name} in the last day.")
                continue
                
            print(f"🔍 Found {len(recent_videos_response)} potentially new videos for {channel_name}.")
            
            video_ids_to_fetch_details = []
            for video_summary in recent_videos_response:
                if not is_video_in_notion(video_summary["videoId"]):
                    video_ids_to_fetch_details.append(video_summary["videoId"])
                else:
                    print(f"⏭️ Video '{video_summary['title']}' ({video_summary['videoId']}) already in Notion. Skipping detail fetch.")
            
            if not video_ids_to_fetch_details:
                print(f"ℹ️ All potentially new videos for {channel_name} are already in Notion or no new videos to process.")
                continue

            print(f"⬇️ Fetching details for {len(video_ids_to_fetch_details)} new videos for {channel_name}...")
            video_details_list = fetch_video_details(creds, video_ids_to_fetch_details)

            if video_details_list is None: # Check for quota issue from fetch_video_details
                quota_issues_channels.append(channel_name)
                print(f"🟡 Skipping detail fetch for {channel_name} due to YouTube API quota issue.")
                continue
            
            if not video_details_list: # Empty list from details fetch
                print(f"ℹ️ No details retrieved for new videos from {channel_name} (possibly an error or no videos found).")
                continue

            print(f"➕ Adding {len(video_details_list)} new videos from {channel_name} to Notion...")
            videos_added_channel = 0
            for video_detail in video_details_list:
                # Final check before adding, though fetch_video_details should only return new ones
                if not is_video_in_notion(video_detail["id"]):
                    create_notion_video_row(video_detail, channel_name, channel_id)
                    videos_added_channel += 1
                else:
                    # This case should be rare if the logic above works correctly
                    print(f"⏭️ Video '{video_detail['snippet']['title']}' ({video_detail['id']}) found in Notion just before adding. Skipping.")
            
            if videos_added_channel > 0:
                print(f"✅ Successfully added {videos_added_channel} videos from {channel_name} to Notion.")
            videos_added_total += videos_added_channel
                
        except Exception as e:
            # General catch-all for unexpected errors per channel
            print(f"❌ An unexpected error occurred while processing {channel_name}: {str(e)}")
            # Optionally, add to a list of channels with errors if needed
    
    print(f"\n--- Video Tracker Summary ---")
    print(f"✅ Total new videos added to Notion: {videos_added_total}")
    if missing_tokens_channels:
        print(f"⚠️ Missing tokens for: {', '.join(missing_tokens_channels)}")
    if quota_issues_channels:
        # Remove duplicates from quota_issues_channels before printing
        unique_quota_issues = sorted(list(set(quota_issues_channels)))
        print(f"🟡 YouTube API quota issues encountered for: {', '.join(unique_quota_issues)}")
    print(f"🏁 Video tracker finished at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    run_video_tracker()
