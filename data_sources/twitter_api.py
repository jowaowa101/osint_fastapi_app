import snscrape.modules.twitter as sntwitter
from fastapi import APIRouter
from datetime import datetime

router = APIRouter()

@router.get("/tweets")
def get_tweets(query: str, limit: int = 10):
    tweets_list = []

    try:
        for i, tweet in enumerate(sntwitter.TwitterSearchScraper(f"{query} lang:en").get_items()):
            if i >= limit:
                break
            tweets_list.append({
                "id": tweet.id,
                "text": tweet.content,
                "created_at": tweet.date.strftime("%Y-%m-%d %H:%M:%S"),
                "author_id": tweet.user.username,
                "lang": tweet.lang
            })

        if not tweets_list:
            return {"message": "No tweets found"}

        return tweets_list

    except Exception as e:
        return {"error": str(e)}
import os
import requests
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
router = APIRouter()

BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
if not BEARER_TOKEN:
    raise ValueError("Twitter Bearer Token not found in environment variables")

TWITTER_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"

@router.get("/tweets")
def get_tweets(query: str):
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}"
    }
    params = {
        "query": query,
        "max_results": 10,
        "tweet.fields": "created_at,author_id,lang"
    }

    response = requests.get(TWITTER_SEARCH_URL, headers=headers, params=params)

    # If we hit a rate limit
    if response.status_code == 429:
        reset_timestamp = response.headers.get("x-rate-limit-reset")
        if reset_timestamp:
            reset_time = datetime.fromtimestamp(int(reset_timestamp))
            wait_seconds = int((reset_time - datetime.now()).total_seconds())

        # Convert seconds to minutes and seconds
            minutes, seconds = divmod(wait_seconds, 60)
            human_readable = f"{minutes} minutes and {seconds} seconds"

            return {
                "error": "Rate limit reached",
                "retry_after_seconds": wait_seconds,
                "retry_after_human": human_readable,
                "retry_at": reset_time.strftime("%I:%M:%S %p")  # e.g. "06:40:30 PM"
            }
        raise HTTPException(status_code=429, detail="Rate limit reached. Try again later.")


    if not response.ok:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    data = response.json()
    tweets = data.get("data", [])

    if not tweets:
        return {"message": "No tweets found"}

    return [
        {
            "id": t["id"],
            "text": t["text"],
            "created_at": t["created_at"],
            "author_id": t["author_id"],
            "lang": t.get("lang", None)
        }
        for t in tweets
    ]
