#!/usr/bin/env python3
"""
YouTube Channel Token Generator
This script generates authentication tokens for YouTube channels using OAuth 2.0.
Run this script to authenticate with a YouTube channel and save the credentials.
"""

import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# OAuth 2.0 scopes required for YouTube Analytics API
SCOPES = [
    'https://www.googleapis.com/auth/youtube.readonly',
    'https://www.googleapis.com/auth/yt-analytics.readonly'
]

def generate_token_for_channel(channel_name, channel_id):
    """
    Generates and saves an authentication token for a specific YouTube channel.
    
    Args:
        channel_name (str): Human-readable name of the channel
        channel_id (str): YouTube channel ID
    """
    print(f"🔐 Generating token for {channel_name} (Channel ID: {channel_id})")
    
    # Create tokens directory if it doesn't exist
    tokens_dir = "tokens"
    if not os.path.exists(tokens_dir):
        os.makedirs(tokens_dir)
        print(f"📁 Created tokens directory: {tokens_dir}")
    
    # Define the token file path
    token_file = os.path.join(tokens_dir, f"token_{channel_id}.pickle")
    
    # Check if token already exists
    if os.path.exists(token_file):
        print(f"⚠️  Token file already exists: {token_file}")
        response = input("Do you want to regenerate it? (y/N): ").lower().strip()
        if response != 'y':
            print("❌ Token generation cancelled.")
            return
        print("🔄 Regenerating token...")
    
    # Check if client_secrets.json exists
    client_secrets_file = "client_secrets.json"
    if not os.path.exists(client_secrets_file):
        print(f"❌ Error: {client_secrets_file} not found!")
        print("Please download your OAuth 2.0 client credentials from Google Cloud Console:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Select your project")
        print("3. Go to APIs & Services > Credentials")
        print("4. Download the OAuth 2.0 client ID as JSON")
        print("5. Rename it to 'client_secrets.json' and place it in this directory")
        return
    
    try:
        # Start OAuth 2.0 flow
        print("🔄 Starting OAuth 2.0 authentication flow...")
        flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
        
        # Run the local server for authentication
        print("🌐 Opening browser for authentication...")
        print("Please log in with the San Antonio Spurs YouTube account when prompted.")
        creds = flow.run_local_server(port=0)
        
        # Save the credentials
        with open(token_file, 'wb') as token:
            pickle.dump(creds, token)
        
        print(f"✅ Token successfully generated and saved to: {token_file}")
        print(f"🎯 Channel: {channel_name}")
        print(f"🆔 Channel ID: {channel_id}")
        
        # Test the credentials
        print("🧪 Testing credentials...")
        youtube = build('youtube', 'v3', credentials=creds)
        
        # Get channel info to verify
        channel_response = youtube.channels().list(
            part='snippet,statistics',
            id=channel_id
        ).execute()
        
        if channel_response['items']:
            channel_info = channel_response['items'][0]['snippet']
            print(f"✅ Successfully authenticated with: {channel_info['title']}")
            print(f"📊 Subscribers: {channel_response['items'][0]['statistics'].get('subscriberCount', 'N/A')}")
        else:
            print("⚠️  Warning: Could not fetch channel info, but token was saved")
            
    except Exception as e:
        print(f"❌ Error generating token: {e}")
        print("Please check your internet connection and try again.")

def main():
    """Main function to generate token for San Antonio Spurs channel."""
    print("🏀 YouTube Channel Token Generator")
    print("=" * 40)
    
    # San Antonio Spurs channel configuration
    CHANNEL_NAME = "San Antonio Spurs"
    CHANNEL_ID = "UCEZHE-0CoHqeL1LGFa2EmQw"
    
    print(f"🎯 Target Channel: {CHANNEL_NAME}")
    print(f"🆔 Channel ID: {CHANNEL_ID}")
    print()
    
    # Confirm before proceeding
    response = input("Proceed with token generation? (Y/n): ").lower().strip()
    if response in ['n', 'no']:
        print("❌ Token generation cancelled.")
        return
    
    # Generate the token
    generate_token_for_channel(CHANNEL_NAME, CHANNEL_ID)
    
    print("\n🎉 Token generation complete!")
    print("You can now run your YouTube analytics scripts with the San Antonio Spurs channel.")

if __name__ == "__main__":
    main()
