import csv
import os
import requests
from time import sleep

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_VIDEO_DB_ID = os.environ["NOTION_VIDEO_DB_ID"]

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def create_notion_page(video):
    props = {
        "Video Title": {"title": [{"text": {"content": video["Video Title"]}}]},
        "Channel Name": {"rich_text": [{"text": {"content": video["Channel Name"]}}]},
        "Video URL": {"url": video["Video URL"]},
        "Date Published": {"date": {"start": video["Date Published"]}},
        "Views": {"number": int(video["Views"]) if video["Views"] else 0},
        "Subs Gained": {"number": int(video["Subs Gained"]) if video["Subs Gained"] else 0},
        "Revenue": {"number": float(video["Revenue"]) if video["Revenue"] else 0},
        "Avg View %": {"number": float(video["Avg View %"]) if video["Avg View %"] else 0},
        "Avg View Min": {"number": float(video["Avg View Min"]) if video["Avg View Min"] else 0},
        "Format": {"select": {"name": video["Format"]}},
        "Thumbnail": {"url": video["Thumbnail"]}
    }

    payload = {
        "parent": {"database_id": NOTION_VIDEO_DB_ID},
        "properties": props
    }

    res = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload)
    print(f"{video['Video Title']} ({res.status_code})")
    if res.status_code != 200:
        print(res.text)
    sleep(0.3)  # prevent rate limiting

# Load the data and upload
with open("notion_video_upload_ready.csv", newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        create_notion_page(row)
