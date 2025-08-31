#SHAMAIM CODE:
# osint_fastapi_app/data_sources/social_graph.py
import os
import re
import time
import math
import urllib.parse
from datetime import datetime
from typing import Dict, List, Any, Optional

import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, Query
from pydantic import BaseModel

# -------------------------
# Config
# -------------------------
router = APIRouter()
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0 Safari/537.36"
    )
}
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
GRAPHS_DIR = os.path.join(STATIC_DIR, "graphs")
os.makedirs(GRAPHS_DIR, exist_ok=True)


# -------------------------
# Helpers
# -------------------------
def expand_query_variants(query: str) -> List[str]:
    q = query.strip()
    variants = {q, q.lower(), q.title()}
    RELATED = {
        "ai": ["artificial intelligence", "machine learning", "generative ai", "llm", "chatgpt"],
        "cybersecurity": ["cyber security", "info sec", "threat intel", "ransomware"],
        "blockchain": ["web3", "crypto", "ethereum", "bitcoin"],
    }
    key = q.lower()
    if key in RELATED:
        variants.update(RELATED[key])
    parts = re.split(r"[\s\-]+", q)
    for p in parts:
        if len(p) > 2:
            variants.add(p)
    return list(variants)[:8]


def search_youtube(query: str, max_results: int = 8) -> List[Dict[str, Any]]:
    results = []
    try:
        res = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": max_results,
                "key": os.getenv("YOUTUBE_API_KEY", "")
            },
            headers=HEADERS,
            timeout=12
        )
        data = res.json()
        for item in data.get("items", []):
            vid = item.get("id", {}).get("videoId")
            snip = item.get("snippet", {})
            results.append({
                "title": snip.get("title", ""),
                "link": f"https://www.youtube.com/watch?v={vid}" if vid else "",
                "channel": snip.get("channelTitle", ""),
                "publishedAt": snip.get("publishedAt", "")
            })
    except Exception:
        pass
    return results[:max_results]


def search_reddit(query: str, max_results: int = 8) -> List[Dict[str, Any]]:
    results = []
    try:
        q = urllib.parse.quote_plus(query)
        url = f"https://old.reddit.com/search?q={q}&sort=relevance&t=all"
        res = requests.get(url, headers=HEADERS, timeout=12)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            items = soup.select("div.search-result-link") or soup.select("div.thing")
            for it in items:
                title_tag = it.select_one("a.search-title") or it.select_one("a.title")
                subreddit_tag = it.select_one("a.subreddit") or it.select_one("a.author")
                if title_tag:
                    link = title_tag.get("href", "#")
                    if link.startswith("/r/"):
                        link = "https://old.reddit.com" + link
                    results.append({
                        "title": title_tag.text.strip(),
                        "link": link,
                        "subreddit": subreddit_tag.text.strip() if subreddit_tag else ""
                    })
                if len(results) >= max_results:
                    break
    except Exception:
        pass
    return results[:max_results]


def search_twitter(query: str, max_results: int = 8) -> List[Dict[str, Any]]:
    results = []
    nitter_instances = [
        "https://nitter.net",
        "https://nitter.snopyta.org",
        "https://nitter.eu.org"
    ]
    q = urllib.parse.quote_plus(query)
    for base in nitter_instances:
        try:
            url = f"{base}/search?f=tweets&q={q}"
            res = requests.get(url, headers=HEADERS, timeout=8)
            if res.status_code != 200:
                continue
            soup = BeautifulSoup(res.text, "html.parser")
            tweet_nodes = soup.select("div.tweet") or soup.select("div.timeline-item")
            for t in tweet_nodes:
                text_tag = t.select_one("div.tweet-content") or t.select_one("p")
                author_tag = t.select_one("a.username")
                link_tag = t.select_one("a[href*='/status/']")
                text = text_tag.text.strip() if text_tag else None
                author = author_tag.text.strip() if author_tag else ""
                link = urllib.parse.urljoin(base, link_tag["href"]) if link_tag else ""
                if text:
                    results.append({"text": text, "author": author, "link": link})
                if len(results) >= max_results:
                    break
            if results:
                break
        except Exception:
            continue
    return results[:max_results]


# -------------------------
# Models
# -------------------------
class SocialAutoIn(BaseModel):
    query: str
    max_items: Optional[int] = 10


# -------------------------
# Routes
# -------------------------
@router.post("/social-graph/auto")
def social_graph_auto(payload: SocialAutoIn):
    query = (payload.query or "").strip()
    if not query:
        return {"error": "query is required"}
    max_items = int(payload.max_items or 10)
    variants = expand_query_variants(query)
    if query not in variants:
        variants.insert(0, query)

    youtube_items, twitter_items, reddit_items = [], [], []
    for v in variants:
        if len(youtube_items) < max_items:
            youtube_items.extend(search_youtube(v, max_items))
        if len(twitter_items) < max_items:
            twitter_items.extend(search_twitter(v, max_items))
        if len(reddit_items) < max_items:
            reddit_items.extend(search_reddit(v, max_items))
        if len(youtube_items) >= max_items and len(twitter_items) >= max_items and len(reddit_items) >= max_items:
            break
        time.sleep(0.2)

    youtube_items = youtube_items[:max_items] or [{"title": f"No results for '{query}' on YouTube", "link": "#"}]
    twitter_items = twitter_items[:max_items] or [{"text": f"No results for '{query}' on Twitter", "link": "#"}]
    reddit_items = reddit_items[:max_items] or [{"title": f"No results for '{query}' on Reddit", "link": "#"}]

    center_id = f"center_{re.sub(r'[^a-zA-Z0-9]', '_', query)[:40]}"
    nodes_json = [{"id": center_id, "label": query, "type": "center"}]
    edges_json = []

    platforms = {"YouTube": youtube_items, "Twitter": twitter_items, "Reddit": reddit_items}
    for platform, items in platforms.items():
        hub_id = f"hub_{platform}"
        nodes_json.append({"id": hub_id, "label": platform, "type": "platform"})
        edges_json.append({"from": center_id, "to": hub_id})
        for idx, item in enumerate(items):
            item_id = f"{platform}_{idx+1}"
            if platform == "YouTube":
                label = item.get("title") or str(item)
                link = item.get("link", "#")
                meta = {"platform": "YouTube", "channel": item.get("channel", ""), "link": link}
            elif platform == "Twitter":
                label = item.get("text") or str(item)
                link = item.get("link", "#")
                meta = {"platform": "Twitter", "author": item.get("author", ""), "link": link}
            else:
                label = item.get("title") or str(item)
                link = item.get("link", "#")
                meta = {"platform": "Reddit", "subreddit": item.get("subreddit", ""), "link": link}
            nodes_json.append({"id": item_id, "label": label, "type": "item", "platform": platform, "meta": meta})
            edges_json.append({"from": hub_id, "to": item_id})

    # Optional: Save image visualization
    try:
        import networkx as nx
        import matplotlib.pyplot as plt
        G = nx.Graph()
        G.add_node(center_id)
        for e in edges_json:
            G.add_edge(e["from"], e["to"])
        pos = nx.spring_layout(G)
        nx.draw(G, pos, with_labels=False, node_size=500, font_size=8)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = re.sub(r"[^a-zA-Z0-9]+", "_", query)[:40]
        img_name = f"social_{safe}_{ts}.png"
        img_path = os.path.join(GRAPHS_DIR, img_name)
        plt.savefig(img_path, dpi=150)
        plt.close()
        image_url = f"/static/graphs/{img_name}"
    except Exception:
        image_url = None

    return {"status": "ok", "query": query, "nodes": nodes_json, "edges": edges_json, "image_url": image_url}


@router.get("/social-graph")
def social_graph(query: str = Query(...), max_items: int = 6):
    q = (query or "").strip()
    if not q:
        return {"error": "query required"}
    youtube = search_youtube(q, max_items)
    twitter = search_twitter(q, max_items)
    reddit = search_reddit(q, max_items)

    center_id = f"center_{re.sub(r'[^a-zA-Z0-9]', '_', q)[:40]}"
    nodes, edges = [{"id": center_id, "label": q, "type": "center"}], []
    platforms = {"YouTube": youtube, "Twitter": twitter, "Reddit": reddit}
    for platform, items in platforms.items():
        hub_id = f"hub_{platform}"
        nodes.append({"id": hub_id, "label": platform, "type": "platform"})
        edges.append({"from": center_id, "to": hub_id})
        for idx, item in enumerate(items):
            item_id = f"{platform}_{idx+1}"
            label = item.get("title") if platform != "Twitter" else item.get("text")
            nodes.append({"id": item_id, "label": label or str(item), "type": "item", "platform": platform, "meta": {"link": item.get("link", "#")}})
            edges.append({"from": hub_id, "to": item_id})
    return {"status": "ok", "query": q, "nodes": nodes, "edges": edges}
