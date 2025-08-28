# 🏀 San Antonio Spurs YouTube Channel Token Setup Guide

## Overview
This guide will help you set up authentication for the San Antonio Spurs YouTube channel so you can access analytics data.

## Prerequisites
1. **Google Cloud Project** with YouTube Data API v3 and YouTube Analytics API enabled
2. **OAuth 2.0 Client Credentials** downloaded from Google Cloud Console
3. **Access to San Antonio Spurs YouTube Channel** (which you now have! 🎉)

## Step-by-Step Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Get OAuth 2.0 Credentials
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project
3. Navigate to **APIs & Services** > **Credentials**
4. Click **Create Credentials** > **OAuth 2.0 Client IDs**
5. Choose **Desktop application** as the application type
6. Download the JSON file
7. **Rename it to `client_secrets.json`** and place it in your project root directory

### 3. Generate the Token
```bash
python generate_token.py
```

The script will:
- Open your browser for authentication
- Ask you to log in with the San Antonio Spurs YouTube account
- Generate and save the authentication token
- Test the connection to verify it works

### 4. Verify Setup
After successful token generation, you should see:
- ✅ Token successfully generated and saved
- ✅ Successfully authenticated with: [Channel Name]
- 📊 Subscribers: [Number]

## File Structure After Setup
```
YouTubeNotion/
├── tokens/
│   ├── token_UC2ozVs4pg2K3uFLw6-0ayCQ.pickle  # All The Smoke
│   ├── token_UCa9W_cPwwbDlwBwHOd1YWoQ.pickle  # KG Certified
│   ├── token_UC9Qy3sHrr5wil-rkYcmcNcw.pickle  # Morning Kombat
│   ├── token_UCFPoJNd0d4k1H9A6UOlikcg.pickle  # All The Smoke Fight
│   ├── token_UCBX_Qx_Hx5QTuEL72YVyn_A.pickle  # Ring Champs
│   ├── token_UCf5fcEALUCA53oUW3mc8tiQ.pickle  # Victor Oladipo
│   └── token_UCEZHE-0CoHqeL1LGFa2EmQw.pickle  # San Antonio Spurs ✨ NEW!
├── generate_token.py
├── client_secrets.json
└── ... (other files)
```

## Troubleshooting

### "client_secrets.json not found"
- Make sure you downloaded the OAuth credentials from Google Cloud Console
- Rename the file to exactly `client_secrets.json`
- Place it in the project root directory

### Authentication Errors
- Ensure you're logged into the correct Google account
- Make sure the account has access to the San Antonio Spurs channel
- Check that your Google Cloud project has the necessary APIs enabled

### Permission Errors
- Verify the YouTube Data API v3 and YouTube Analytics API are enabled
- Check that your OAuth consent screen includes the necessary scopes

## Next Steps
Once the token is generated, you can:
1. Run `python main.py` to test the full analytics pipeline
2. Use `python analytics_updater.py` for regular analytics updates
3. The San Antonio Spurs channel will now be included in all analytics operations

## Security Notes
- Keep your `client_secrets.json` and token files secure
- Don't commit them to version control
- The tokens directory is already in your `.gitignore`

---

🎯 **Ready to go!** Run `python generate_token.py` when you're ready to authenticate with the San Antonio Spurs channel.
