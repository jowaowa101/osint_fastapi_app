#FOR TWITTER


from fastapi import APIRouter, Query, HTTPException
import os
import requests
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/monitor")

BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
if not BEARER_TOKEN:
    raise Exception("Twitter Bearer Token not set in .env")

@router.get("/twitter")
async def monitor_twitter(keyword: str = Query(..., min_length=1)):
    url = "https://api.twitter.com/2/tweets/search/recent"
    params = {
        "query": keyword,
        "max_results": 10,
        "tweet.fields": "created_at,public_metrics,author_id,lang,source",
        "expansions": "author_id",
        "user.fields": "username,name,verified,created_at,description,public_metrics"
    }
    headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    data = response.json()
    tweets = data.get("data", [])
    users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

    # Process tweets into simplified format
    results = []
    for t in tweets:
        user = users.get(t["author_id"], {})
        results.append({
            "username": user.get("username"),
            "name": user.get("name"),
            "verified": user.get("verified"),
            "followers": user.get("public_metrics", {}).get("followers_count"),
            "content": t.get("text"),
            "date": t.get("created_at"),
            "likes": t.get("public_metrics", {}).get("like_count"),
            "retweets": t.get("public_metrics", {}).get("retweet_count"),
            "url": f"https://twitter.com/{user.get('username')}/status/{t.get('id')}",
        })

    return {"keyword": keyword, "results": results}
