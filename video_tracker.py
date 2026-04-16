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
    "San Antonio Spurs": "UCEZHE-0CoHqeL1LGFa2EmQw",
    "Killswitch": "UCbwGkD8-Fbxun7zgzfC5kjg",
    "The Late Run": "UCcZ6iVdTPU5g4pN3MaIbruw",
    "Michael Easter": "UC-3foA4PyACqvubjyrlzIcg",
    "Anik & Florian": "UCDqSRXkx0E58VdH__Y8expQ",
    "No Such Thing": "UCFRiYABu5iXlkEF5ZCZd6wQ"
}

# --- Helper: Script directory for reliable pathing ---
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
# TOKEN_DIR should be relative to SCRIPT_DIR if it's not an absolute path.
# If TOKEN_DIR is just "tokens", it implies "tokens" subdirectory next to the script.
TOKEN_DIR = os.path.join(SCRIPT_DIR, "tokens") # Ensure TOKEN_DIR is robust

def load_token(channel_id):
    # token_path = os.path.join(TOKEN_DIR, f"token_{channel_id}.pickle") # TOKEN_DIR is now set above
    # The above line is fine, this is just to show the SCRIPT_DIR based path construction
    token_filename = f"token_{channel_id}.pickle"
    token_path = os.path.join(TOKEN_DIR, token_filename)

    if not os.path.exists(token_path):
        print(f"⚠️ No token found for {channel_id} at path {token_path}")
        return None
    with open(token_path, "rb") as token_file:
        return pickle.load(token_file)


def fetch_channel_videos(creds, channel_id, lookback_days=None, page_size=10, max_total_videos=1000, api_key=None):
    """
    Fetches videos for a channel.
    If lookback_days is None, attempts to fetch all videos (up to max_total_videos).
    If lookback_days is an int, fetches videos published in the last N days.
    Uses pagination to retrieve videos.
    """
    try:
        if creds:
            youtube = build("youtube", "v3", credentials=creds)
        else:
            youtube = build("youtube", "v3", developerKey=api_key)

        # Use playlistItems.list for all channels (1 unit/call vs 100 for search.list)
        uploads_playlist_id = channel_id.replace("UC", "UU", 1)
        print(f"  Using playlistItems.list (uploads playlist: {uploads_playlist_id})")

        all_videos = []
        next_page_token = None
        videos_fetched_count = 0

        while True:
            if videos_fetched_count >= max_total_videos:
                print(f"    Reached max_total_videos limit of {max_total_videos}. Stopping video fetch for this channel.")
                break

            actual_page_size = min(page_size, max_total_videos - videos_fetched_count)
            if actual_page_size <= 0: break

            playlist_request = youtube.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=uploads_playlist_id,
                maxResults=actual_page_size,
                pageToken=next_page_token
            )
            playlist_response = playlist_request.execute()

            for item in playlist_response.get("items", []):
                video_id = item.get("contentDetails", {}).get("videoId")
                published_at = item.get("contentDetails", {}).get("videoPublishedAt")
                title = item.get("snippet", {}).get("title")

                if video_id and published_at and title and item.get("snippet", {}).get("thumbnails"):
                    should_add = True
                    if lookback_days is not None and lookback_days > 0:
                        video_published_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=lookback_days)
                        if video_published_dt < cutoff_dt:
                            should_add = False

                    if should_add:
                        all_videos.append({
                            "videoId": video_id,
                            "title": title,
                            "publishedAt": published_at
                        })
                        videos_fetched_count += 1

            next_page_token = playlist_response.get("nextPageToken")
            print(f"    Fetched page: {videos_fetched_count} videos so far for channel {channel_id}.")

            if not next_page_token:
                print(f"    No more pages to fetch for channel {channel_id}.")
                break

        print(f"  Total videos retrieved for channel {channel_id}: {len(all_videos)}")
        return all_videos
        
    except Exception as e:
        if "quota" in str(e).lower() or ("HttpError 403" in str(e) and "quota" in str(e).lower()):
            print(f"🟡 YouTube API quota likely exceeded for channel {channel_id} while fetching videos: {str(e)}")
            return None # Indicate quota issue
        else:
            print(f"❌ Error fetching videos for channel {channel_id}: {str(e)}")
            return [] # Return empty list on other errors

def fetch_video_details(creds, video_ids, api_key=None):
    """Get detailed video information, handling batching for large lists of IDs."""
    try:
        if not video_ids:
            return []

        if creds:
            youtube = build("youtube", "v3", credentials=creds)
        else:
            youtube = build("youtube", "v3", developerKey=api_key)
        all_video_items = []
        
        # The YouTube API v3 videos().list endpoint can take max 50 IDs at a time.
        chunk_size = 50 
        
        for i in range(0, len(video_ids), chunk_size):
            video_ids_chunk = video_ids[i:i + chunk_size]
            print(f"    Fetching details for video ID chunk: {i//chunk_size + 1} (IDs {i+1} to {min(i+chunk_size, len(video_ids))})") # Added print
            
            try:
                request = youtube.videos().list(
                    part="statistics,snippet,contentDetails",
                    id=",".join(video_ids_chunk)
                )
                response = request.execute()
                all_video_items.extend(response.get("items", []))
            except Exception as chunk_e:
                # Handle error for a specific chunk, e.g., log it and continue if appropriate
                # This allows the process to continue with other chunks if one fails.
                print(f"    ❌ Error fetching details for chunk of video IDs (starting with {video_ids_chunk[0]}...): {chunk_e}")
                # Optionally, re-raise if any chunk failure should stop the whole process:
                # raise chunk_e 
                # For now, we'll let it try other chunks. If quota is hit, outer handler will catch it.

        return all_video_items
        
    except Exception as e:
        # This will catch broader errors, like quota exceeded before or during chunk processing
        if "quota" in str(e).lower() or ("HttpError 403" in str(e) and "quota" in str(e).lower()):
            # If it's a quota error, it likely applies to the whole operation now, so return None
            print(f"🟡 YouTube API quota likely exceeded while fetching video details: {str(e)}")
            return None 
        else:
            print(f"❌ General error in fetch_video_details for IDs starting with {video_ids[0] if video_ids else 'N/A'}: {str(e)}")
            return [] # Return empty on other general errors

def parse_duration(duration):
    try:
        td = isodate.parse_duration(duration)
        return td.total_seconds(), round(td.total_seconds() / 60, 2)
    except:
        return 0, 0

def get_video_format_details(video_id, thumbnails, duration_seconds):
    """
    Determines if a video is likely a Short based on aspect ratio and duration,
    with a primary check using the /shorts/ URL endpoint.
    Returns the format_type_string: "Short" or "Long Form".
    video_id: The YouTube video ID.
    thumbnails: The video's thumbnail data from the API (used as a fallback).
    duration_seconds: The video's duration in seconds (used as a fallback).
    """
    # Primary Method: Check /shorts/ URL redirect behavior
    try:
        shorts_url = f"https://www.youtube.com/shorts/{video_id}"
        # We only need the headers, and we don't want to follow redirects automatically for this check
        response = requests.head(shorts_url, allow_redirects=False, timeout=5) # 5 second timeout
        
        # If it's a Short, the /shorts/ URL should return a 200 OK (or similar success) and not redirect significantly.
        # If it's not a Short, accessing the /shorts/ URL often results in a redirect (e.g., 302, 303, 307) to the /watch?v= URL.
        if response.status_code >= 200 and response.status_code < 300:
            # Check if it tries to redirect to a /watch?v= url, which would mean it's NOT a short despite a 200-ish code
            # Some actual shorts might also have a location header but it points to itself or similar /shorts/ url.
            # A more robust check might be needed if this isn't perfect.
            # For now, if it's 200-299 on /shorts/ and doesn't heavily redirect, assume it's a Short.
            # Location header might point to the same /shorts/ URL or a slightly canonicalized version.
            # If it redirects to a /watch? url, then it's definitely not a short.
            if 'location' in response.headers and '/watch?v=' in response.headers['location']:
                # print(f"  DEBUG Format: {video_id} - /shorts/ URL redirected to /watch. Not a Short.")
                pass # Fallback to secondary method
            else:
                # print(f"  DEBUG Format: {video_id} - /shorts/ URL returned {response.status_code}. Detected as Short.")
                return "Short"
        # If it redirects (3xx status codes like 301, 302, 303, 307, 308) it might be a non-short or youtube is just canonicalizing the URL
        # A 303 specifically to the /watch?v= is a strong indicator it's NOT a short.
        elif response.status_code in [301, 302, 303, 307, 308] and 'location' in response.headers and f"/watch?v={video_id}" in response.headers['location']:
            # print(f"  DEBUG Format: {video_id} - /shorts/ URL redirected ({response.status_code}) to /watch. Not a Short.")
            pass # Fallback to secondary method
        # Other status codes or conditions might mean it's not a short or the check isn't conclusive, so we fallback.

    except requests.exceptions.Timeout:
        print(f"  ⚠️ Timeout checking /shorts/ URL for {video_id}. Falling back to secondary format detection.")
    except requests.exceptions.RequestException as e:
        print(f"  ⚠️ Error checking /shorts/ URL for {video_id}: {e}. Falling back to secondary format detection.")

    # Secondary Method (Fallback): Aspect ratio and duration (original method)
    # print(f"  DEBUG Format: {video_id} - Using fallback aspect/duration check.")
    is_vertical_or_square = False
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
        "Notion-Version": "2026-03-11",
        "Content-Type": "application/json"
    }
    try:
        duration_secs, duration_mins = parse_duration(video["contentDetails"]["duration"])
        format_type = get_video_format_details(video['id'], video["snippet"]["thumbnails"], duration_secs)

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
                "Thumbnail": {"files": [{"name": f"{video['id']}.jpg", "external": {"url": f"https://i.ytimg.com/vi/{video['id']}/hqdefault.jpg"}}]},
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
        "Notion-Version": "2026-03-11",
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

def run_video_tracker(bulk_mode=False, lookback_days_if_not_bulk=7):
    """
    Main function to track videos.
    bulk_mode: If True, attempts to fetch all videos for all channels.
    lookback_days_if_not_bulk: If bulk_mode is False, how many recent days to check.
    """
    print(f"🚀 Starting video tracker at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if bulk_mode:
        print("⚙️ Running in BULK IMPORT mode - attempting to fetch all videos.")
    else:
        print(f"⚙️ Running in RECENT VIDEOS mode - fetching videos from last {lookback_days_if_not_bulk} days.")

    videos_added_total = 0
    missing_tokens_channels = []
    quota_issues_channels = []
    
    for channel_name, channel_id in CHANNELS.items():
        print(f"\n📊 Processing channel: {channel_name} ({channel_id})")
        
        creds = load_token(channel_id)
        use_api_key = False
        if not creds:
            if YOUTUBE_API_KEY:
                print(f"  ℹ️ No OAuth token for {channel_name}, using public API key for video discovery.")
                use_api_key = True
            else:
                missing_tokens_channels.append(channel_name)
                continue

        try:
            videos_from_channel_response = []
            fetch_key = YOUTUBE_API_KEY if use_api_key else None
            if bulk_mode:
                videos_from_channel_response = fetch_channel_videos(creds, channel_id, lookback_days=None, page_size=50, max_total_videos=2500, api_key=fetch_key)
            else:
                videos_from_channel_response = fetch_channel_videos(creds, channel_id, lookback_days=lookback_days_if_not_bulk, page_size=10, max_total_videos=50, api_key=fetch_key)
            
            if videos_from_channel_response is None: # Check for quota issue
                quota_issues_channels.append(channel_name)
                print(f"🟡 Skipping {channel_name} due to YouTube API quota issue during video fetch.")
                continue
            if not videos_from_channel_response: # Empty list, no videos found matching criteria
                if bulk_mode:
                    print(f"ℹ️ No videos found for {channel_name}.")
                else:
                    print(f"ℹ️ No new videos found for {channel_name} in the last {lookback_days_if_not_bulk} days.")
                continue
                
            print(f"🔍 Found {len(videos_from_channel_response)} videos for {channel_name} based on current mode.")
            
            video_ids_to_fetch_details = []
            for video_summary in videos_from_channel_response:
                if not is_video_in_notion(video_summary["videoId"]):
                    video_ids_to_fetch_details.append(video_summary["videoId"])
                else:
                    print(f"⏭️ Video '{video_summary['title']}' ({video_summary['videoId']}) already in Notion. Skipping detail fetch.")
            
            if not video_ids_to_fetch_details:
                print(f"ℹ️ All potentially new videos for {channel_name} are already in Notion or no new videos to process.")
                continue

            print(f"⬇️ Fetching details for {len(video_ids_to_fetch_details)} new videos for {channel_name}...")
            video_details_list = fetch_video_details(creds, video_ids_to_fetch_details, api_key=fetch_key)

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
    import sys
    bulk_mode = "--bulk" in sys.argv
    DAYS_TO_CHECK_FOR_RECENT = 3  # Covers weekend gaps and timezone edge cases

    if bulk_mode:
        print("🌟 BULK IMPORT MODE (--bulk flag). Fetching all videos for all channels. 🌟")
        run_video_tracker(bulk_mode=True)
    else:
        print(f"ℹ️ Daily mode: checking last {DAYS_TO_CHECK_FOR_RECENT} days. Use --bulk for full historical import.")
        run_video_tracker(bulk_mode=False, lookback_days_if_not_bulk=DAYS_TO_CHECK_FOR_RECENT)
