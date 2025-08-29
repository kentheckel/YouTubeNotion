#!/usr/bin/env python3
"""
Update only San Antonio Spurs data in data.json
"""

import json
import os
import pickle
from datetime import datetime, timedelta
from googleapiclient.discovery import build

def update_spurs_data():
    """Update San Antonio Spurs analytics data in data.json"""
    
    channel_id = "UCEZHE-0CoHqeL1LGFa2EmQw"
    channel_name = "San Antonio Spurs"
    
    print(f"🏀 Updating {channel_name} data...")
    
    # Load existing data.json
    try:
        with open("public/data.json", "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("❌ data.json not found!")
        return
    
    # Find San Antonio Spurs entry
    spurs_entry = None
    for i, channel in enumerate(data):
        if channel["name"] == channel_name:
            spurs_entry = i
            break
    
    if spurs_entry is None:
        print(f"❌ {channel_name} not found in data.json!")
        return
    
    print(f"✅ Found {channel_name} at index {spurs_entry}")
    
    # Load token
    token_path = f"tokens/token_{channel_id}.pickle"
    if not os.path.exists(token_path):
        print(f"❌ Token not found: {token_path}")
        return
    
    try:
        with open(token_path, "rb") as token_file:
            creds = pickle.load(token_file)
        print("✅ Token loaded successfully")
    except Exception as e:
        print(f"❌ Error loading token: {e}")
        return
    
    # Test the token by getting channel info
    try:
        youtube = build('youtube', 'v3', credentials=creds)
        channel_response = youtube.channels().list(
            part='snippet,statistics',
            id=channel_id
        ).execute()
        
        if not channel_response['items']:
            print("❌ No channel data returned")
            return
            
        channel_info = channel_response['items'][0]['snippet']
        stats = channel_response['items'][0]['statistics']
        
        print(f"✅ Connected to: {channel_info['title']}")
        print(f"📊 Subscribers: {stats.get('subscriberCount', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Error testing YouTube API: {e}")
        return
    
    # Get analytics data
    try:
        from googleapiclient.discovery import build as build_analytics
        youtube_analytics = build_analytics("youtubeAnalytics", "v2", credentials=creds)
        
        # Get 28-day analytics
        today = datetime.utcnow().date()
        start_28 = (today - timedelta(days=28)).isoformat()
        today_str = today.isoformat()
        
        print(f"📅 Fetching analytics for: {start_28} to {today_str}")
        
        response = youtube_analytics.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_28,
            endDate=today_str,
            metrics="views,subscribersGained,subscribersLost",
            dimensions="day",
            sort="day"
        ).execute()
        
        rows = response.get("rows", [])
        if rows:
            total_views = sum(row[1] for row in rows)
            total_subs_gained = sum(row[2] for row in rows)
            total_subs_lost = sum(row[3] for row in rows)
            net_subs = total_subs_gained - total_subs_lost
            
            print(f"✅ Analytics data retrieved!")
            print(f"   📺 Views (28 days): {total_views:,}")
            print(f"   👤 Subscribers gained: {total_subs_gained}")
            print(f"   👤 Subscribers lost: {total_subs_lost}")
            print(f"   👤 Net subscribers: {net_subs}")
            
            # Update the data.json entry
            data[spurs_entry]["views_28"] = total_views
            data[spurs_entry]["subs_28"] = net_subs
            data[spurs_entry]["views_prev_28"] = total_views  # For now, set same as current
            data[spurs_entry]["subs_prev_28"] = net_subs      # For now, set same as current
            
            # Save updated data.json
            with open("public/data.json", "w") as f:
                json.dump(data, f, indent=2)
            
            print(f"✅ Updated data.json with {channel_name} analytics!")
            
        else:
            print("⚠️  No analytics data returned")
            
    except Exception as e:
        print(f"❌ Error getting analytics: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🔧 San Antonio Spurs Data Updater")
    print("=" * 40)
    
    update_spurs_data()
    
    print("\n🎯 Check public/data.json to see the updated data!")
