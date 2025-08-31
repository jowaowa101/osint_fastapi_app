# osint_fastapi_app/data_sources/phone_lookup.py
import os, csv, re
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, Form, Response
from fastapi.responses import HTMLResponse

router = APIRouter()

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
CSV_PATH = os.path.join(DATA_DIR, "phone_lookups.csv")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": "https://live-tracker.site/"
}

def _extract(soup, label):
    tag = soup.find("span", string=label)
    if tag:
        nxt = tag.find_next("span")
        return nxt.text.strip() if nxt else "Not Found"
    return "Not Found"

def lookup_number(number: str):
    url = "https://live-tracker.site/"
    try:
        res = requests.post(url, headers=HEADERS, data={"searchinfo": number}, timeout=15)
        res.raise_for_status()
    except Exception as e:
        return {"error": f"Lookup failed: {e}"}

    soup = BeautifulSoup(res.text, "html.parser")
    result = {
        "name": _extract(soup, "Name: "),
        "mobile": _extract(soup, "Mobile: "),
        "country": _extract(soup, "Country: "),
        "cnic": _extract(soup, "CNIC: "),
        "address": _extract(soup, "Address: ")
    }

    try:
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([datetime.now(), number, *result.values()])
    except Exception:
        pass

    return result

@router.get("/", response_class=HTMLResponse)
def homepage_form():
    # Kept so your current frontend that POSTs to "/" continues to work
    return """
    <form method="post">
      <input type="text" name="number" placeholder="Enter phone number"/>
      <button type="submit">Lookup</button>
    </form>
    """

@router.post("/", response_class=HTMLResponse)
def homepage_submit(number: str = Form(...)):
    data = lookup_number(number)
    if "error" in data:
        return HTMLResponse(f"<p style='color:red;'>{data['error']}</p>", status_code=502)

    return f"""
    <div>
      <h2>📋 Lookup Results</h2>
      <p><strong>Name:</strong> {data['name']}</p>
      <p><strong>Mobile:</strong> {data['mobile']}</p>
      <p><strong>Country:</strong> {data['country']}</p>
      <p><strong>CNIC:</strong> {data['cnic']}</p>
      <p><strong>Address:</strong> {data['address']}</p>
      <a href="/">🔁 Search another number</a>
    </div>
    """

# Optional JSON alias if you want it later (doesn't affect your current frontend):
@router.post("/phone-lookup")
def phone_lookup_json(number: str = Form(...)):
    return lookup_number(number)
