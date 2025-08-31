from dotenv import load_dotenv
import os
from pathlib import Path
import time
import feedparser
from fastapi import FastAPI, Request, Form, Query, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from urllib.parse import unquote
from fastapi.middleware.cors import CORSMiddleware


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
from osint_fastapi_app.data_sources.youtube_monitor import router as youtube_router
from osint_fastapi_app.data_sources.rss_monitor import rss_router
from osint_fastapi_app.data_sources.twitter_selenium_scraper import router as twitter_selenium_router
from osint_fastapi_app.data_sources.monitor_router import router as monitor_router
from osint_fastapi_app.data_sources.twitter_api import router as twitter_router
from osint_fastapi_app.data_sources.youtube_transcribe import router as youtube_transcribe_router
from osint_fastapi_app.data_sources import image_text_ocr  # ✅ OCR Router

# 📊 Graph Route
from osint_fastapi_app.data_sources.graph_routes import router as graph_router

# 🧠 Classification Routes (existing)
from osint_fastapi_app.classification_routes import router as classification_router

# 🧠 Hate Speech Keyword Detection (Shamaim’s module)

# SHAMAIM
from osint_fastapi_app.data_sources import phone_lookup
from osint_fastapi_app.data_sources import github_monitor
from osint_fastapi_app.data_sources.youtube_profile_monitor import router as youtube_router
from osint_fastapi_app.data_sources import social_graph


# 🎥 YouTube Search Dependency
from youtubesearchpython import VideosSearch

# ⚙️ FastAPI App Initialization
app = FastAPI(title="OSINT FastAPI App", version="1.0.0")

# 🔐 Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🗂️ Static and Templates Setup
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


# CORS so React frontend can talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # later you can restrict to http://localhost:3000
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 📦 Register All API Routers
app.include_router(reddit_router)
app.include_router(twitter_selenium_router)
app.include_router(youtube_router)
app.include_router(rss_router)
app.include_router(classification_router, prefix="/classification")
app.include_router(monitor_router)
app.include_router(twitter_router, prefix="/api")
app.include_router(youtube_transcribe_router)
app.include_router(image_text_ocr.router)  # ✅ Include OCR Router
app.include_router(graph_router, prefix="/social-graph", tags=["Graph"])
app.include_router(phone_lookup.router, prefix="/phone", tags=["Phone Lookup"])
app.include_router(
    github_monitor.router,
    prefix="/github",   # 👈 all routes will start with /github
    tags=["GitHub Monitor"]
)
app.include_router(youtube_router)
app.include_router(social_graph.router)





print("🚀 OSINT FastAPI Server Started")

# ================================
# Root & Web Routes
# ================================
@app.get("/")
def read_root():
    return {"message": "✅ OSINT API Running Successfully"}

@app.get("/web", response_class=HTMLResponse)
def frontend_home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# ================================
# Sherlock & Maigret Scan Endpoint for Frontend
# ================================
@app.post("/scan")
async def scan(username: str = Form(...), tool: str = Form(...)):
    if tool == "sherlock":
        output = run_sherlock(username)
    elif tool == "maigret":
        output = run_maigret(username)
    else:
        output = {"error": "Invalid tool selected."}
    return {"username": username, "tool": tool, "result": output}

# ================================
# Sherlock & Maigret Endpoints
# ================================
@app.get("/sherlock/{username}")
def sherlock_scan(username: str):
    output = run_sherlock(username)
    return {"tool": "Sherlock", "username": username, "output": output}

@app.get("/maigret/{username}")
def maigret_scan(username: str):
    output = run_maigret(username)
    return {"tool": "maigret", "username": username, "output": output}

# ================================
# RSS Keyword Endpoint
# ================================
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

# ================================
# 🎥 YouTube Search Router
# ================================
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

# ================================
# 🎥 YouTube Monitor with Hate Speech Classification
# ================================
import requests
from osint_fastapi_app.classifier import classify_text

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

youtube_monitor_router = APIRouter(prefix="/monitor", tags=["YouTube Monitor"])

@youtube_monitor_router.get("/youtube")
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
            if classification_result["is_hate_speech"]:
                label = f"Hate Speech ({classification_result['category']})"
            else:
                label = "Safe"
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

app.include_router(youtube_monitor_router)
