import feedparser
from fastapi import APIRouter

rss_router = APIRouter()

RSS_FEEDS = {
    "BBC": "http://feeds.bbci.co.uk/news/rss.xml",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "Dawn": "https://www.dawn.com/feeds/home",
    "CNN": "http://rss.cnn.com/rss/edition.rss"
}

@rss_router.get("/trends/rss")
def get_rss_trends():
    results = []
    for source, url in RSS_FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:  # Limit to top 5 per source
            results.append({
                "source": source,
                "title": entry.title,
                "link": entry.link,
                "summary": entry.summary if "summary" in entry else "",
                "published": entry.published if "published" in entry else ""
            })
    return {"items": results}


#HAVENT DISPLAYED IN FRONTEND YET