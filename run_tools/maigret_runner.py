# maigret_runner.py
import subprocess
import os
import re
import json
import requests
from bs4 import BeautifulSoup
from pathlib import Path

# 👇 Scraper helper function
def scrape_profile_data(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        bio = soup.find("meta", {"name": "description"})
        image = soup.find("meta", {"property": "og:image"})
        title = soup.title.string if soup.title else None

        return {
            "bio": bio["content"] if bio else None,
            "image": image["content"] if image else None,
            "fullname": title
        }
    except Exception as e:
        return {
            "bio": None,
            "image": None,
            "fullname": None,
            "error": str(e)
        }

# 👇 Directory to store Maigret reports temporarily
REPORT_DIR = Path(__file__).parent / "maigret_reports"
REPORT_DIR.mkdir(exist_ok=True)

# 👇 Path to Maigret virtual environment
MAIGRET_VENV_PATH = Path("/Users/apple/Desktop/osint-llm-tool/venv_maigret311/bin/python")  # <-- adjust if needed

# 👇 Main function to run Maigret and parse output
def run_maigret(username: str) -> dict:
    try:
        json_report_path = REPORT_DIR / f"report_{username}_simple.json"

        # 👇 Run Maigret using the dedicated venv python
        cmd = [
    str(MAIGRET_VENV_PATH), "-m", "maigret", username,
    '--top-sites', '50',
    '-J', 'simple',
    '--no-color',
    '--no-progressbar',
    '--folderoutput', str(REPORT_DIR)
]


        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=180
        )

        if result.returncode != 0:
            return {
                "tool": "Maigret",
                "username": username,
                "error": result.stderr.strip()
            }

        if not json_report_path.exists():
            return {
                "tool": "Maigret",
                "username": username,
                "error": f"JSON report not found at {json_report_path}",
                "raw_output": result.stdout
            }

        with open(json_report_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        profiles = {}
        for site, info in data.items():
            status_info = info.get("status", {})
            ids = status_info.get("ids", {})

            if isinstance(info, dict) and info.get("url_user") and status_info.get("status") == "Claimed":
                url = info.get("url_user")

                # Fallback scraping
                scraped = scrape_profile_data(url)

                profile_data = {
                    "url": url,
                    "username": info.get("username"),
                    "id": ids.get("username"),
                    "fullname": ids.get("fullname") or scraped.get("fullname"),
                    "bio": ids.get("bio") or scraped.get("bio"),
                    "followers": ids.get("follower_count"),
                    "country": ids.get("country"),
                    "image": ids.get("image") or scraped.get("image"),
                    "gravatar_url": ids.get("gravatar_url"),
                    "tags": status_info.get("tags", [])
                }

                # Remove keys with null values
                profiles[site] = {k: v for k, v in profile_data.items() if v is not None}

        # Cleanup JSON report
        os.remove(json_report_path)

        return {
            "tool": "Maigret",
            "username": username,
            "total_results": len(profiles),
            "profiles": profiles
        }

    except subprocess.TimeoutExpired:
        return {
            "tool": "Maigret",
            "username": username,
            "error": "Maigret timed out."
        }
    except Exception as e:
        return {
            "tool": "Maigret",
            "username": username,
            "error": str(e)
        }
