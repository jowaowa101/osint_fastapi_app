# osint_fastapi_app/data_sources/youtube_profile_monitor.py
import os
import requests
from fastapi import APIRouter, Query
from dotenv import load_dotenv

router = APIRouter()
load_dotenv()  # loads variables from .env file

# Get API key from environment
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

@router.get("/youtube-channel-monitor")
def youtube_channel_monitor(channel_name: str = Query(..., alias="channel_name")):
    """
    Finds a channel by name and returns summary + latest videos.
    Requires YOUTUBE_API_KEY. If absent, returns a helpful error.
    """
    if not YOUTUBE_API_KEY:
        return {"error": "YOUTUBE_API_KEY not set in environment."}

    try:
        # Step 1: search for channel
        search = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "q": channel_name,
                "type": "channel",
                "maxResults": 1,
                "key": YOUTUBE_API_KEY
            }, timeout=12
        ).json()

        items = search.get("items", [])
        if not items:
            return {"error": f"No channel found for '{channel_name}'."}

        channel_id = items[0]["snippet"]["channelId"]
        channel_title = items[0]["snippet"]["title"]
        channel_desc = items[0]["snippet"].get("description", "")
        channel_thumb = items[0]["snippet"]["thumbnails"].get("default", {}).get("url", "")

        # Step 2: channel stats
        chans = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={
                "part": "statistics,snippet",
                "id": channel_id,
                "key": YOUTUBE_API_KEY
            }, timeout=12
        ).json()
        stats = (chans.get("items") or [{}])[0].get("statistics", {})
        subs = stats.get("subscriberCount", "N/A")

        # Step 3: latest videos
        vids = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "channelId": channel_id,
                "order": "date",
                "maxResults": 5,
                "type": "video",
                "key": YOUTUBE_API_KEY
            }, timeout=12
        ).json()

        latest = []
        for it in vids.get("items", []):
            vid = it["id"]["videoId"]
            sn = it["snippet"]
            latest.append({
                "title": sn["title"],
                "link": f"https://www.youtube.com/watch?v={vid}",
                "thumbnail": sn["thumbnails"].get("medium", {}).get("url", "")
            })

        return {
            "name": channel_title,
            "description": channel_desc,
            "subscribers": subs,
            "profile_pic": channel_thumb,
            "url": f"https://www.youtube.com/channel/{channel_id}",
            "latest_videos": latest
        }

    except Exception as e:
        return {"error": f"YouTube monitor failed: {e}"}
