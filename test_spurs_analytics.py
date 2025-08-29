#!/usr/bin/env python3
"""
Test script to debug San Antonio Spurs analytics collection
"""

import os
import sys
import pickle
from datetime import datetime, timedelta
import pytz

# Add current directory to path to import functions
sys.path.append('.')

def test_spurs_analytics():
    """Test the exact analytics collection logic used in main.py"""
    
    channel_id = "UCEZHE-0CoHqeL1LGFa2EmQw"
    channel_name = "San Antonio Spurs"
    
    print(f"🧪 Testing {channel_name} analytics collection...")
    print(f"Channel ID: {channel_id}")
    
    # Test 1: Check if token file exists
    script_dir = os.path.dirname(os.path.realpath(__file__))
    token_path = os.path.join(script_dir, "tokens", f"token_{channel_id}.pickle")
    
    print(f"Token path: {token_path}")
    print(f"Token exists: {os.path.exists(token_path)}")
    
    if not os.path.exists(token_path):
        print("❌ Token file not found!")
        return
    
    # Test 2: Try to load the token
    try:
        with open(token_path, "rb") as token_file:
            creds = pickle.load(token_file)
        print("✅ Token loaded successfully")
    except Exception as e:
        print(f"❌ Error loading token: {e}")
        return
    
    # Test 3: Test the fetch_analytics_for_range function
    try:
        from main import fetch_analytics_for_range
        
        today = datetime.utcnow().date()
        start_28 = (today - timedelta(days=28)).isoformat()
        today_str = today.isoformat()
        
        print(f"Testing analytics for: {start_28} to {today_str}")
        
        views_28, subs_28 = fetch_analytics_for_range(creds, channel_id, start_28, today_str)
        
        print(f"✅ Analytics fetched successfully!")
        print(f"   Views (28 days): {views_28:,}")
        print(f"   Subscribers (28 days): {subs_28}")
        
    except Exception as e:
        print(f"❌ Error in fetch_analytics_for_range: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 4: Test the get_uploads_in_range function
    try:
        from main import get_uploads_in_range
        
        today = datetime.utcnow().date()
        start_28 = (today - timedelta(days=28)).isoformat()
        today_str = today.isoformat()
        
        uploads_28 = get_uploads_in_range(channel_id, start_28, today_str, creds)
        
        print(f"✅ Uploads fetched successfully!")
        print(f"   Uploads (28 days): {uploads_28}")
        
    except Exception as e:
        print(f"❌ Error in get_uploads_in_range: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🔍 San Antonio Spurs Analytics Debug Test")
    print("=" * 50)
    
    test_spurs_analytics()
