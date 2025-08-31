import praw
from fastapi import APIRouter
from datetime import datetime
from osint_fastapi_app.classifier import classify_text  # 👈 Hate classifier

reddit_router = APIRouter()

# Reddit API credentials
REDDIT_CLIENT_ID = "2bgUK1v0iAtcRbkaSrHIKg"
REDDIT_CLIENT_SECRET = "y1qHugC8wEHB1EaxdrBzFGHKfARZSw"
REDDIT_USER_AGENT = "Big_Western_8383"

# Initialize Reddit instance
reddit = praw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    user_agent=REDDIT_USER_AGENT
)

# 🔍 Live Monitor: Search keyword across Reddit
@reddit_router.get("/monitor/reddit")
def monitor_reddit_by_keyword(keyword: str, limit: int = 50):
    try:
        posts = []
        for submission in reddit.subreddit("all").search(keyword, sort="new", limit=limit):
            classification = classify_text(submission.title)

            posts.append({
                "title": submission.title,
                "author": str(submission.author),
                "url": submission.url,
                "created": datetime.utcfromtimestamp(submission.created_utc).isoformat(),
                "is_hate_speech": classification["is_hate_speech"],
                "confidence": classification["confidence"],
                "category": classification["category"],
                "explanation": classification.get("explanation"),
                "original_language": classification.get("original_language", "en")
            })

        return {
            "status": "success",
            "keyword": keyword,
            "posts": posts
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
