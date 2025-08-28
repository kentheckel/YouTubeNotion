#!/usr/bin/env python3
"""
Simple test script to verify San Antonio Spurs token is working
"""

import os
import pickle
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import pytz

def test_spurs_token():
    """Test if the San Antonio Spurs token is working correctly."""
    
    # San Antonio Spurs channel ID
    channel_id = "UCEZHE-0CoHqeL1LGFa2EmQw"
    channel_name = "San Antonio Spurs"
    
    print(f"🏀 Testing {channel_name} token...")
    print(f"Channel ID: {channel_id}")
    
    # Check if token file exists
    token_path = f"tokens/token_{channel_id}.pickle"
    if not os.path.exists(token_path):
        print(f"❌ Token file not found: {token_path}")
        return False
    
    print(f"✅ Token file found: {token_path}")
    
    try:
        # Load the token
        with open(token_path, "rb") as token_file:
            creds = pickle.load(token_file)
        print("✅ Token loaded successfully")
        
        # Test basic YouTube API access
        youtube = build('youtube', 'v3', credentials=creds)
        print("✅ YouTube API client built successfully")
        
        # Get channel info
        channel_response = youtube.channels().list(
            part='snippet,statistics',
            id=channel_id
        ).execute()
        
        if channel_response['items']:
            channel_info = channel_response['items'][0]['snippet']
            stats = channel_response['items'][0]['statistics']
            
            print(f"✅ Successfully connected to: {channel_info['title']}")
            print(f"📊 Current subscribers: {stats.get('subscriberCount', 'N/A')}")
            print(f"📺 Total views: {stats.get('viewCount', 'N/A')}")
            print(f"🎥 Total videos: {stats.get('videoCount', 'N/A')}")
            
            # Test analytics API
            try:
                from googleapiclient.discovery import build as build_analytics
                youtube_analytics = build_analytics("youtubeAnalytics", "v2", credentials=creds)
                print("✅ YouTube Analytics API client built successfully")
                
                # Try to get recent analytics (last 7 days)
                end_date = datetime.now(pytz.UTC).strftime('%Y-%m-%d')
                start_date = (datetime.now(pytz.UTC) - timedelta(days=7)).strftime('%Y-%m-%d')
                
                print(f"📅 Testing analytics for: {start_date} to {end_date}")
                
                response = youtube_analytics.reports().query(
                    ids=f"channel=={channel_id}",
                    startDate=start_date,
                    endDate=end_date,
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
                    
                    print(f"✅ Analytics data retrieved successfully!")
                    print(f"   📺 Views (7 days): {total_views:,}")
                    print(f"   👤 Subscribers gained: {total_subs_gained}")
                    print(f"   👤 Subscribers lost: {total_subs_lost}")
                    print(f"   👤 Net subscribers: {net_subs}")
                else:
                    print("⚠️  No analytics data returned (this might be normal for new channels)")
                    
            except Exception as e:
                print(f"⚠️  Analytics API test failed: {e}")
                print("   This might be due to insufficient permissions or channel restrictions")
            
            return True
            
        else:
            print("❌ No channel data returned")
            return False
            
    except Exception as e:
        print(f"❌ Error testing token: {e}")
        return False

if __name__ == "__main__":
    print("🧪 San Antonio Spurs Token Test")
    print("=" * 40)
    
    success = test_spurs_token()
    
    if success:
        print("\n🎉 Token test completed successfully!")
        print("The San Antonio Spurs channel should now work in your analytics pipeline.")
    else:
        print("\n❌ Token test failed!")
        print("Please check the error messages above.")
