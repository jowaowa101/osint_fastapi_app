# osint_fastapi_app/data_sources/github_monitor.py
import os, csv
from datetime import datetime
import requests
from fastapi import APIRouter, Query

router = APIRouter()

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
CSV_PATH = os.path.join(DATA_DIR, "github_profiles.csv")

@router.get("/profile-monitor")
def monitor_github_profile(username: str = Query(..., description="GitHub username")):
    try:
        res = requests.get(f"https://api.github.com/users/{username}",
                           headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        data = res.json()
        profile = {
            "name": data.get("name", "Not available"),
            "username": data.get("login", username),
            "bio": data.get("bio", "Not available"),
            "followers": data.get("followers", "Not available"),
            "location": data.get("location", "Not available"),
            "avatar": data.get("avatar_url", ""),
            "profile": data.get("html_url", f"https://github.com/{username}")
        }
        try:
            with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([datetime.now()] + list(profile.values()))
        except Exception:
            pass
        return profile
    except Exception as e:
        return {"error": str(e)}
