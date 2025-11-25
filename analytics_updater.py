import os
import requests
from googleapiclient.discovery import build # We'll need this later
import pickle
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
VIDEO_DB_ID = os.getenv("NOTION_VIDEO_DB_ID") # This is your VIDEO database

# --- Define TOKEN_DIR relative to this script's location ---
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
TOKEN_DIR = os.path.join(SCRIPT_DIR, "tokens")
# --- End TOKEN_DIR definition ---

# Channel map (can be useful, or we can just rely on Channel ID from Notion)
CHANNELS = {
    "All The Smoke": "UC2ozVs4pg2K3uFLw6-0ayCQ",
    "KG Certified": "UCa9W_cPwwbDlwBwHOd1YWoQ",
    "Morning Kombat": "UC9Qy3sHrr5wil-rkYcmcNcw",
    "All The Smoke Fight": "UCFPoJNd0d4k1H9A6UOlikcg",
    "Ring Champs": "UCBX_Qx_Hx5QTuEL72YVyn_A",
    "San Antonio Spurs": "UCEZHE-0CoHqeL1LGFa2EmQw"
}

def load_token(channel_id):
    """Loads a token for a given channel_id."""
    # Normalize the channel_id to ensure it's clean (remove any extra whitespace)
    if channel_id:
        channel_id = channel_id.strip().replace('\n', '').replace('\r', '').replace('\t', '')
    
    # --- BEGIN DEBUG PRINTS ---
    print(f"  DEBUG load_token: Received channel_id: '{channel_id}'")
    print(f"  DEBUG load_token: Channel ID length: {len(channel_id) if channel_id else 0}")
    token_filename = f"token_{channel_id}.pickle"
    print(f"  DEBUG load_token: Constructed token_filename: '{token_filename}'")
    # Get absolute path for TOKEN_DIR for clarity in debugging
    # abs_token_dir = os.path.abspath(TOKEN_DIR) # TOKEN_DIR is now already absolute or reliably relative
    token_path = os.path.join(TOKEN_DIR, token_filename) # Use the new TOKEN_DIR
    print(f"  DEBUG load_token: Checking absolute token_path: '{token_path}'")
    print(f"  DEBUG load_token: Script SCRIPT_DIR: '{SCRIPT_DIR}'") # Print SCRIPT_DIR for checking
    print(f"  DEBUG load_token: Script CWD: '{os.getcwd()}'")
    # --- END DEBUG PRINTS ---

    if not os.path.exists(token_path):
        print(f"⚠️ No token found for channel_id '{channel_id}' at {token_path}")
        # List available tokens to help debug
        if os.path.exists(TOKEN_DIR):
            available_tokens = [f for f in os.listdir(TOKEN_DIR) if f.startswith('token_') and f.endswith('.pickle')]
            print(f"  Available tokens in {TOKEN_DIR}: {available_tokens}")
        return None
    try:
        with open(token_path, "rb") as token_file:
            creds = pickle.load(token_file)
            print(f"  ✅ Token loaded successfully for channel_id '{channel_id}'")
            return creds
    except Exception as e:
        print(f"❌ Error loading token for channel_id '{channel_id}': {e}")
        import traceback
        traceback.print_exc()
        return None

def get_videos_from_notion():
    """Fetches all video entries from the Notion database."""
    if not VIDEO_DB_ID or not NOTION_TOKEN:
        print("❌ Notion DB ID or Token not configured. Cannot fetch videos.")
        return []

    url = f"https://api.notion.com/v1/databases/{VIDEO_DB_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    all_videos = []
    has_more = True
    start_cursor = None

    print("⬇️ Fetching videos from Notion...")
    while has_more:
        payload = {}
        if start_cursor:
            payload["start_cursor"] = start_cursor
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status() # Raise an exception for HTTP errors
            data = response.json()
            
            for page in data.get("results", []):
                video_id_prop = page.get("properties", {}).get("Video ID", {}).get("rich_text", [])
                channel_id_prop = page.get("properties", {}).get("Channel ID", {}).get("rich_text", [])
                title_prop = page.get("properties", {}).get("Video Title", {}).get("title", [])
                date_published_prop = page.get("properties", {}).get("Date Published", {}).get("date", {})

                video_id = video_id_prop[0]["plain_text"] if video_id_prop else None
                # Strip whitespace from channel_id read from Notion and normalize it
                # Handle potential whitespace, newlines, or other formatting issues
                channel_id_text = channel_id_prop[0]["plain_text"] if channel_id_prop and channel_id_prop[0].get("plain_text") else None
                # Strip all whitespace (spaces, tabs, newlines) and ensure it's a clean channel ID
                channel_id = channel_id_text.strip().replace('\n', '').replace('\r', '').replace('\t', '') if channel_id_text else None
                
                title = title_prop[0]["plain_text"] if title_prop else "Unknown Title"
                # Get the start date from the date object, it's in ISO format
                published_at_iso = date_published_prop.get("start") if date_published_prop else None

                if video_id: # Only process if we have a YouTube Video ID
                    all_videos.append({
                        "notion_page_id": page["id"],
                        "video_id": video_id,
                        "channel_id": channel_id, # This is crucial
                        "title": title,
                        "published_at_iso": published_at_iso # Store the publish date
                    })
            
            start_cursor = data.get("next_cursor")
            has_more = bool(start_cursor)
            if has_more:
                print(f"   Fetched {len(data.get('results', []))} videos, more available...")
        except requests.exceptions.RequestException as e:
            print(f"❌ HTTP Error querying Notion: {e} - {response.text if 'response' in locals() else 'No response details'}")
            return [] # Stop if there's an error
        except Exception as e:
            print(f"❌ Exception querying Notion: {e}")
            return [] # Stop if there's an error
            
    print(f"✅ Found {len(all_videos)} videos in Notion database.")
    return all_videos

def update_video_in_notion(notion_page_id, analytics_data):
    """Updates a video's Notion page with new analytics data."""
    if not NOTION_TOKEN:
        print("❌ Notion Token not configured. Cannot update page.")
        return False

    url = f"https://api.notion.com/v1/pages/{notion_page_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    properties_to_update = {}

    # --- Map YouTube Analytics keys to Notion Property Names and format --- 
    # Ensure these Notion Property Names exactly match your database schema

    if "views" in analytics_data:
        properties_to_update["Views"] = {"number": int(analytics_data["views"]) if analytics_data["views"] is not None else 0}
    
    if "estimatedRevenue" in analytics_data:
        # Ensure revenue is a float, default to 0.0 if None
        properties_to_update["Revenue"] = {"number": float(analytics_data["estimatedRevenue"]) if analytics_data["estimatedRevenue"] is not None else 0.0}

    if "averageViewPercentage" in analytics_data:
        # YouTube provides this as a whole number (e.g., 45.5 for 45.5%). Notion can format it.
        properties_to_update["Avg View %"] = {"number": float(analytics_data["averageViewPercentage"]) if analytics_data["averageViewPercentage"] is not None else 0.0}

    if "subscribersGained" in analytics_data:
        properties_to_update["Subs Gained"] = {"number": int(analytics_data["subscribersGained"]) if analytics_data["subscribersGained"] is not None else 0}

    # --- New Properties You Created ---
    if "estimatedMinutesWatched" in analytics_data:
        properties_to_update["Watch Time (Mins)"] = {"number": int(analytics_data["estimatedMinutesWatched"]) if analytics_data["estimatedMinutesWatched"] is not None else 0}
    
    if "averageViewDuration" in analytics_data: # This is in seconds from YouTube
        properties_to_update["Avg View Duration (Secs)"] = {"number": int(analytics_data["averageViewDuration"]) if analytics_data["averageViewDuration"] is not None else 0}

    if "likes" in analytics_data:
        properties_to_update["Likes"] = {"number": int(analytics_data["likes"]) if analytics_data["likes"] is not None else 0}

    if "comments" in analytics_data:
        properties_to_update["Comments"] = {"number": int(analytics_data["comments"]) if analytics_data["comments"] is not None else 0}

    if "subscribersLost" in analytics_data:
        properties_to_update["Subs Lost"] = {"number": int(analytics_data["subscribersLost"]) if analytics_data["subscribersLost"] is not None else 0}

    if "shares" in analytics_data:
        properties_to_update["Shares"] = {"number": int(analytics_data["shares"]) if analytics_data["shares"] is not None else 0}

    if "impressions" in analytics_data:
        properties_to_update["Impressions"] = {"number": int(analytics_data["impressions"]) if analytics_data["impressions"] is not None else 0}

    if "impressionsClickThroughRate" in analytics_data: # YouTube provides as decimal (e.g., 0.05 for 5%)
        # Notion's "Percent" number format will handle displaying 0.05 as 5%
        properties_to_update["Impressions CTR (%)"] = {"number": float(analytics_data["impressionsClickThroughRate"]) if analytics_data["impressionsClickThroughRate"] is not None else 0.0}
    # --- End Mapping ---

    if not properties_to_update:
        print(f"  ℹ️ No relevant analytics data found in YouTube response to update Notion page {notion_page_id}.")
        return False

    payload = {"properties": properties_to_update}
    video_title_for_log = analytics_data.get("title", notion_page_id) # Use title if available for logging

    try:
        response = requests.patch(url, headers=headers, json=payload)
        response.raise_for_status()
        print(f"  ✅ Notion page for '{video_title_for_log}' ({notion_page_id}) updated successfully with {len(properties_to_update)} new analytics fields.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  ❌ HTTP Error updating Notion page {notion_page_id}: {e} - {response.text}")
        return False
    except Exception as e:
        print(f"  ❌ Exception updating Notion page {notion_page_id}: {e}")
        return False

# Placeholder for the YouTube Analytics API fetching function
def fetch_video_analytics_from_youtube(creds, channel_id_for_api_context, video_id_to_filter, start_date_str, end_date_str):
    """Fetches analytics for a specific video using the YouTube Analytics API."""
    # print(f"📈 (Placeholder) Fetching YouTube Analytics for video {video_id} from {start_date_str} to {end_date_str}")
    try:
        youtube_analytics = build('youtubeAnalytics', 'v2', credentials=creds)

        # Define a comprehensive list of metrics we'd like to try and fetch.
        # Not all metrics may be available for all videos/channels or date ranges.
        metrics_list = [
            "views",
            "estimatedMinutesWatched",
            "averageViewDuration",
            "averageViewPercentage",
            "likes",
            "dislikes", # May not be available
            "comments",
            "subscribersGained",
            "subscribersLost",
            "shares",
            # "impressions", # Changed name
            # "impressionsClickThroughRate", # Changed name
            # For basic reports, impressions are often just 'impressions' or 'viewerPercentage' related. 
            # However, for video-specific breakdowns, let's try a more common one if basic 'impressions' fails.
            # The API often uses just 'impressions' for general content reports. 
            # If this specific query doesn't like it, it might be because it's combined with channel-level ID and video filter.
            # Let's try just 'impressions' first as it's most standard. The error indicates 'impressions' was the issue.
            # The error was "Unknown identifier (impressions)". Let's find the correct name or remove it if it blocks others.
            # Consulting common metrics: 'impressions' is standard for video reports.
            # It might be the combination with monetary metrics. Let's simplify.
            "cardImpressions", # Example of specific impressions
            "cardClickRate",   # Example of specific CTR

            # Revenue metrics (require yt-analytics-monetary.readonly scope and monetized content)
            "estimatedRevenue",
            "adImpressions", # More specific ad impressions metric
            "cpm", 
            "rpm"  
        ]
        # Let's simplify the metrics list for now to isolate the "impressions" issue or other problematic ones.
        # Start with a core set that is usually available.
        metrics_list_core = [
            "views", "estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage",
            "likes", "comments", "subscribersGained", "subscribersLost", "shares"
        ]
        metrics_list_revenue = ["estimatedRevenue"] # Keep revenue separate for now if it causes issues
        metrics_list_impressions_specific = ["cardImpressions", "cardClickRate"] # Test these specific ones

        # Let's try with a known good core set first
        metrics_str = ",".join(metrics_list_core)
        
        # If you want to try adding revenue and specific impressions back:
        # metrics_str = ",".join(metrics_list_core + metrics_list_revenue + metrics_list_impressions_specific)
        # Or, one by one.

        print(f" querying YouTube Analytics for video {video_id_to_filter} (Channel Context: {channel_id_for_api_context}) from {start_date_str} to {end_date_str} with metrics: {metrics_str}...")

        response = youtube_analytics.reports().query(
            ids=f'channel=={channel_id_for_api_context}', # Context for the data (which channel owns it)
            startDate=start_date_str,
            endDate=end_date_str,
            metrics=metrics_str,
            dimensions='video', # Results broken down by video
            filters=f'video=={video_id_to_filter}', # Filter to the specific video
            maxResults=1 # We only expect one row for the specified video
            # sort='-views' # Optional: not strictly needed when filtering to one video
        ).execute()

        # print(f"YouTube Analytics API Response for {video_id_to_filter}: {response}") # For debugging

        if response and 'rows' in response and len(response['rows']) > 0:
            # We expect one row since we filtered by video ID and set maxResults=1
            row_data = response['rows'][0]
            column_headers = [header['name'] for header in response['columnHeaders']]
            
            # Create a dictionary of metric_name: value
            analytics_results = {}
            for i, header_name in enumerate(column_headers):
                # The first column header is usually 'video' (the dimension), skip it if we only care about metrics
                if header_name == 'video': 
                    continue 
                analytics_results[header_name] = row_data[i]
            
            print(f"  📊 Analytics fetched for {video_id_to_filter}: {len(analytics_results)} metrics.")
            # print(f"  Analytics data: {analytics_results}") # For debugging
            return analytics_results
        else:
            print(f"  ℹ️ No analytics rows returned from YouTube for video {video_id_to_filter}. The video might be too new, have no data for the period, or there was an issue.")
            return {} # Return empty dict if no data

    except Exception as e:
        if "quota" in str(e).lower() or ("HttpError 403" in str(e) and "quota" in str(e).lower()):
            print(f"  🟡 YouTube API quota likely exceeded while fetching analytics for video {video_id_to_filter}: {e}")
        elif "HttpError 403" in str(e) and "does not have permission" in str(e).lower():
            print(f"  🔴 Permission denied for video {video_id_to_filter}. The token for channel {channel_id_for_api_context} may not have access to this video's analytics or the required scopes (yt-analytics.readonly, yt-analytics-monetary.readonly). Details: {e}")
        elif "HttpError 400" in str(e) and "invalidFilters" in str(e).lower():
            print(f"  ❌ Invalid filter for video {video_id_to_filter}. This video ID might not belong to channel {channel_id_for_api_context} or is incorrect. Details: {e}")
        else:
            print(f"  ❌ Error fetching YouTube Analytics for video {video_id_to_filter}: {e}")
        return None # Indicate an error or significant issue


def run_analytics_updater():
    print(f"🚀 Starting YouTube Analytics Updater at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    videos_in_notion = get_videos_from_notion()
    if not videos_in_notion:
        print("🏁 No videos found in Notion or error fetching. Exiting.")
        return

    updated_count = 0
    skipped_no_channel_id = 0
    skipped_no_token = 0

    for video_data in videos_in_notion:
        print(f"\nProcessing: {video_data['title']} (Video ID: {video_data['video_id']})")
        
        if not video_data["channel_id"]:
            print(f"  🟡 Skipping - Missing Channel ID in Notion for this video.")
            skipped_no_channel_id += 1
            continue

        # Normalize channel_id before using it (in case it wasn't normalized when read from Notion)
        channel_id_normalized = video_data["channel_id"].strip().replace('\n', '').replace('\r', '').replace('\t', '')
        print(f"  Channel ID from Notion: '{video_data['channel_id']}' (normalized: '{channel_id_normalized}')")
        
        creds = load_token(channel_id_normalized)
        if not creds:
            # This message is already printed by load_token
            skipped_no_token +=1
            continue
        
        # Use the normalized channel_id for the API call as well
        video_data["channel_id"] = channel_id_normalized
        
        if not video_data["published_at_iso"]:
            print(f"  🟡 Skipping - Missing Published Date in Notion for video {video_data['video_id']}. Cannot determine analytics start date.")
            continue

        # Use video's publish date as start_date for analytics
        try:
            # Convert ISO publish date to YYYY-MM-DD for API
            # The date from Notion should be like YYYY-MM-DDTHH:MM:SS.sssZ or YYYY-MM-DD
            start_date_dt = datetime.fromisoformat(video_data["published_at_iso"].replace("Z", "+00:00"))
            start_date_str = start_date_dt.strftime('%Y-%m-%d')
        except ValueError:
            # If it's already YYYY-MM-DD from Notion (for an all-day event, less likely for YouTube publish)
            try:
                datetime.strptime(video_data["published_at_iso"], '%Y-%m-%d') # Validate format
                start_date_str = video_data["published_at_iso"]
            except ValueError:
                print(f"  🔴 Skipping - Invalid Published Date format in Notion for video {video_data['video_id']}: {video_data['published_at_iso']}")
                continue

        end_date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        # --- DEBUG: Print date range being used --- 
        print(f"  DEBUG: Raw published_at_iso from Notion: '{video_data['published_at_iso']}'")
        print(f"  DEBUG: Querying analytics from {start_date_str} to {end_date_str}")
        # --- END DEBUG --- 

        # Pass channel_id for API context, then video_id to filter by
        analytics_data = fetch_video_analytics_from_youtube(creds, video_data["channel_id"], video_data["video_id"], start_date_str, end_date_str)

        if analytics_data is None: # Indicates a significant error like quota or permission
            print(f"  Skipping Notion update for {video_data['video_id']} due to YouTube API error.")
            continue # Move to the next video
        
        if analytics_data: # If we got some data (even if it's an empty dict for no rows)
            if update_video_in_notion(video_data["notion_page_id"], analytics_data):
                updated_count +=1
        else:
            print(f"  ℹ️ No analytics data returned from YouTube for video {video_data['video_id']}.")

    print(f"\n--- Analytics Updater Summary ---")
    print(f"✅ Videos updated in Notion: {updated_count}")
    print(f"🟡 Videos skipped (missing Channel ID in Notion): {skipped_no_channel_id}")
    print(f"🟡 Videos skipped (missing auth token): {skipped_no_token}")
    print(f"🏁 Analytics Updater finished at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}")


if __name__ == "__main__":
    run_analytics_updater() 