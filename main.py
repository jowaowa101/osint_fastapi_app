from dotenv import load_dotenv
import os
from pathlib import Path
import time
import feedparser
from fastapi import FastAPI, Request, Form, Query, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from urllib.parse import unquote

# Selenium imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# Load environment variables
load_dotenv()

# 🔍 Core OSINT Runners
from osint_fastapi_app.run_tools.sherlock_runner import run_sherlock
from osint_fastapi_app.run_tools.maigret_runner import run_maigret

# 📡 Data Source Routers
from osint_fastapi_app.data_sources.reddit_monitor import reddit_router
from osint_fastapi_app.data_sources.youtube_monitor import router as youtube_monitor_router
from osint_fastapi_app.data_sources.rss_monitor import rss_router
from osint_fastapi_app.data_sources.twitter_selenium_scraper import router as twitter_selenium_router
from osint_fastapi_app.data_sources.monitor_router import router as monitor_router
from osint_fastapi_app.data_sources.twitter_api import router as twitter_router
from osint_fastapi_app.data_sources.youtube_transcribe import router as youtube_transcribe_router
from osint_fastapi_app.data_sources import image_text_ocr
from osint_fastapi_app.data_sources.graph_routes import router as graph_router
from osint_fastapi_app.classification_routes import router as classification_router
from osint_fastapi_app.data_sources import phone_lookup, github_monitor, social_graph

# YouTube Search
from youtubesearchpython import VideosSearch
import requests
from osint_fastapi_app.classifier import classify_text

# ⚙️ FastAPI App Initialization
app = FastAPI(title="OSINT FastAPI App", version="1.0.0")

# Path to built React frontend
frontend_path = os.path.join(os.path.dirname(__file__), "../osint-frontend/build")

# ----------------------------
# CORS Middleware
# ----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For public deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# Static Files & Templates
# ----------------------------
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Mount React static files if build exists
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=os.path.join(frontend_path, "static")), name="static")

# ----------------------------
# API Routers
# ----------------------------
app.include_router(reddit_router)
app.include_router(twitter_selenium_router)
app.include_router(youtube_monitor_router)
app.include_router(rss_router)
app.include_router(classification_router, prefix="/classification")
app.include_router(monitor_router)
app.include_router(twitter_router, prefix="/api")
app.include_router(youtube_transcribe_router)
app.include_router(image_text_ocr.router)
app.include_router(graph_router, prefix="/social-graph", tags=["Graph"])
app.include_router(phone_lookup.router, prefix="/phone", tags=["Phone Lookup"])
app.include_router(github_monitor.router, prefix="/github", tags=["GitHub Monitor"])
app.include_router(social_graph.router)

# ----------------------------
# Root & Health Check
# ----------------------------
@app.get("/api/health")
def health_check():
    return {"message": "✅ OSINT API Running Successfully"}

# ----------------------------
# Sherlock & Maigret Endpoints
# ----------------------------
@app.post("/scan")
async def scan(username: str = Form(...), tool: str = Form(...)):
    if tool == "sherlock":
        output = run_sherlock(username)
    elif tool == "maigret":
        output = run_maigret(username)
    else:
        output = {"error": "Invalid tool selected."}
    return {"username": username, "tool": tool, "result": output}

@app.get("/sherlock/{username}")
def sherlock_scan(username: str):
    return {"tool": "Sherlock", "username": username, "output": run_sherlock(username)}

@app.get("/maigret/{username}")
def maigret_scan(username: str):
    return {"tool": "Maigret", "username": username, "output": run_maigret(username)}

# ----------------------------
# RSS Feed Endpoints
# ----------------------------
RSS_FEEDS = [
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "http://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://www.theverge.com/rss/index.xml"
]

@app.get("/api/rss")
def get_rss_posts(keyword: str = Query(...), max_posts: int = 5):
    results = []
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            if keyword.lower() in entry.title.lower() or keyword.lower() in entry.summary.lower():
                results.append({
                    "title": entry.title,
                    "link": entry.link,
                    "summary": entry.summary,
                    "published": entry.get("published")
                })
            if len(results) >= max_posts:
                break
        if len(results) >= max_posts:
            break
    return results

@app.get("/api/rss/custom")
def get_custom_rss(feed_url: str = Query(...), max_posts: int = 5):
    decoded_url = unquote(feed_url)
    feed = feedparser.parse(decoded_url)
    results = []
    for entry in feed.entries[:max_posts]:
        results.append({
            "title": entry.title,
            "link": entry.link,
            "summary": entry.get("summary", ""),
            "published": entry.get("published", "")
        })
    return results

# ----------------------------
# YouTube Search Router
# ----------------------------
youtube_search_router = APIRouter(prefix="/youtube", tags=["YouTube"])

@youtube_search_router.get("/search")
def search_youtube(query: str = Query(..., description="Search term for YouTube"), limit: int = 5):
    try:
        videos_search = VideosSearch(query, limit=limit)
        results = videos_search.result()
        videos = [
            {
                "title": video["title"],
                "duration": video.get("duration"),
                "link": video["link"],
                "views": video.get("viewCount", {}).get("short"),
                "thumbnails": video.get("thumbnails", []),
                "channel": video.get("channel", {}).get("name"),
            }
            for video in results["result"]
        ]
        return {"query": query, "results": videos}
    except Exception as e:
        return {"error": str(e)}

app.include_router(youtube_search_router)

# ----------------------------
# YouTube Monitor with Hate Speech Classification
# ----------------------------
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

youtube_monitor_router2 = APIRouter(prefix="/monitor", tags=["YouTube Monitor"])

@youtube_monitor_router2.get("/youtube")
def youtube_monitor(keyword: str = Query(..., description="Search keyword for YouTube videos")):
    if not YOUTUBE_API_KEY:
        return {"error": "YouTube API key not found in environment variables"}
    url = (
        "https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet&maxResults=10&q={keyword}&key={YOUTUBE_API_KEY}&type=video"
    )
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        results = []
        for item in data.get("items", []):
            video_id = item["id"]["videoId"]
            snippet = item["snippet"]
            text_to_classify = f"{snippet['title']} {snippet.get('description', '')}"
            classification_result = classify_text(text_to_classify)
            label = f"Hate Speech ({classification_result['category']})" if classification_result["is_hate_speech"] else "Safe"
            results.append({
                "title": snippet["title"],
                "channel": snippet["channelTitle"],
                "published_at": snippet["publishedAt"],
                "description": snippet.get("description", ""),
                "thumbnail": snippet["thumbnails"]["high"]["url"],
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
                "hate_speech_label": label,
                "confidence": classification_result["confidence"],
                "explanation": classification_result["explanation"]
            })
        return {
            "tool": "YouTube Monitor",
            "keyword": keyword,
            "total_results": len(results),
            "results": results
        }
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

app.include_router(youtube_monitor_router2)

# ----------------------------
# Serve React Frontend
# ----------------------------
@app.get("/{full_path:path}", response_class=HTMLResponse)
async def serve_react(full_path: str):
    index_file = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"error": "React frontend build not found."}

print("🚀 OSINT FastAPI Server Started")
