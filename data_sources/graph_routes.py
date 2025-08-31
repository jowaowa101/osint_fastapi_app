from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict
import subprocess
import re

# ✅ Use your Maigret runner (with a safe fallback import path)
try:
    from osint_fastapi_app.data_sources.maigret_runner import run_maigret as maigret_run
except Exception:
    from osint_fastapi_app.run_tools.maigret_runner import run_maigret as maigret_run


router = APIRouter()

# ----- MODELS -----
class SiteResult(BaseModel):
    site: str
    url: str

class GraphInput(BaseModel):
    username: str
    sherlock: List[SiteResult] = []
    maigret: List[SiteResult] = []

# ----- IN-MEMORY STORAGE -----
graphs: Dict[str, Dict] = {}

# ----- GRAPH BUILDER -----
def build_graph(username: str, sherlock: List[dict], maigret: List[dict]):
    nodes = [{"id": username, "type": "user", "label": username}]
    links = []
    added_sites = set()

    def add_site(result: dict, source: str):
        site_id = result["site"]
        url = result["url"]

        if site_id not in added_sites:
            node = {
                "id": site_id,
                "type": "site",
                "label": site_id,
                "urls": [url],
            }
            # Optional: carry Maigret metadata into node if present
            for k in ("fullname", "bio", "followers", "country", "image", "gravatar_url", "tags"):
                v = result.get(k)
                if v is not None:
                    node[k] = v

            nodes.append(node)
            added_sites.add(site_id)
        else:
            # append URL if new
            for n in nodes:
                if n["id"] == site_id and "urls" in n and url not in n["urls"]:
                    n["urls"].append(url)

        links.append({
            "source": username,
            "target": site_id,
            "type": source,
            "url": url
        })

    for s in sherlock:
        add_site(s, "sherlock")
    for m in maigret:
        add_site(m, "maigret")

    return {"nodes": nodes, "links": links}

# ----- SHERLOCK HELPER -----
def run_sherlock(username: str):
    results = []
    try:
        sherlock_py = "/Users/apple/Desktop/osint-llm-tool/tools/sherlock-master/sherlock_project/sherlock.py"
        python_bin = "/Users/apple/Desktop/osint-llm-tool/venv/bin/python"  # your Sherlock venv python

        proc = subprocess.run(
            [python_bin, sherlock_py, username],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        output_text = proc.stdout if proc.returncode == 0 else proc.stderr
        # Lines like: [+] SiteName: https://...
        matches = re.findall(r'\[\+\] (.*?): (https?://[^\s]+)', output_text)
        for site, url in matches:
            results.append({"site": site.strip(), "url": url.strip()})

    except Exception as e:
        print("Sherlock runner error:", e)
    return results

# ----- MAIGRET HELPER (uses your maigret_runner.py) -----
def run_maigret(username: str):
    """
    Uses maigret_runner.run_maigret(username) which returns:
    {
      "tool": "Maigret",
      "username": "...",
      "total_results": N,
      "profiles": {
         "SiteName": {
            "url": "...", "fullname": "...", "bio": "...",
            "followers": ..., "country": "...", "image": "...", ...
         },
         ...
      }
    }
    """
    results = []
    try:
        data = maigret_run(username)

        # Error surfaced by runner
        if isinstance(data, dict) and data.get("error"):
            print("Maigret runner error:", data["error"])
            return results

        profiles = (data or {}).get("profiles", {})
        for site, profile in profiles.items():
            url = profile.get("url") or profile.get("url_user")
            if not url:
                continue  # skip entries without a resolvable URL

            item = {"site": site, "url": url}

            # carry optional metadata
            for k in ("fullname", "bio", "followers", "country", "image", "gravatar_url", "tags"):
                v = profile.get(k)
                if v is not None:
                    item[k] = v

            results.append(item)

    except Exception as e:
        print("Maigret runner error:", e)

    return results

# ----- ROUTES -----
@router.get("/{tool}/{username}")
async def get_graph_by_tool(tool: str, username: str):
    """Run either Sherlock or Maigret for a username and return the graph."""
    tool_l = tool.lower()
    if tool_l == "sherlock":
        results = run_sherlock(username)
        if not results:
            raise HTTPException(status_code=404, detail="No data found from Sherlock")
        graph = build_graph(username, results, [])
    elif tool_l == "maigret":
        results = run_maigret(username)
        if not results:
            raise HTTPException(status_code=404, detail="No data found from Maigret")
        graph = build_graph(username, [], results)
    else:
        raise HTTPException(status_code=400, detail="Tool must be 'sherlock' or 'maigret'")

    graphs[f"{tool_l}:{username}"] = graph
    return {"results": results, "graph": graph}

# Manual build route
@router.post("/build")
async def build_social_graph(data: GraphInput):
    graph = build_graph(data.username, data.sherlock, data.maigret)
    graphs[data.username] = graph
    return graph
