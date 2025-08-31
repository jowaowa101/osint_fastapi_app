from fastapi import APIRouter
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time

router = APIRouter()

@router.get("/twitter-trends")
def get_twitter_trends(location: str = "pakistan"):
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

        url = f"https://trends24.in/{location.lower().replace(' ', '-')}/"
        driver.get(url)
        time.sleep(5)  # Let JS load

        trend_elements = driver.find_elements(By.CSS_SELECTOR, ".trend-card__list a")
        trends = [trend.text for trend in trend_elements][:10]

        driver.quit()

        return {
            "source": "trends24",
            "location": location,
            "trends": trends
        }

    except Exception as e:
        return {"error": str(e)}


#FOR TWITTER HASHTAGS