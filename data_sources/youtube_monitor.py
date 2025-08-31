import logging
import os
import tempfile
import shutil
import requests
from fastapi import APIRouter, Query
from pydantic import BaseModel
import yt_dlp

# Import your classifier function
from osint_fastapi_app.classifier import classify_text

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# YouTube API Key from env (or your actual key)
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "AIzaSyANv9Sl58eelH4O2AWIK9uTWq9GxQtclL0")

# ===========================
# 📌 Endpoint: Monitor YouTube
# ===========================
@router.get("/monitor/youtube")
def youtube_monitor(keyword: str = Query(..., description="Search keyword for YouTube videos"),
                    max_posts: int = Query(10, description="Maximum number of videos to fetch")):
    """
    Fetch YouTube videos for a search keyword and classify them for hate speech.
    Returns a frontend-safe JSON structure.
    """
    if not YOUTUBE_API_KEY or YOUTUBE_API_KEY == "YOUR_API_KEY_HERE":
        return {"error": "YouTube API key not found. Set YOUTUBE_API_KEY in environment."}

    url = (
        f"https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet&maxResults={max_posts}&q={keyword}&key={YOUTUBE_API_KEY}&type=video"
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

            # Call classifier
            classification_result = classify_text(text_to_classify)

            # Simplify for frontend
            label = "Safe"
            if classification_result.get("is_hate_speech"):
                label = f"Hate Speech ({classification_result.get('category', 'N/A')})"

            results.append({
                "title": snippet["title"],
                "channel": snippet["channelTitle"],
                "published_at": snippet["publishedAt"],
                "description": snippet.get("description", ""),
                "thumbnail": snippet["thumbnails"]["high"]["url"],
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
                "hate_speech_label": label,
                "confidence": classification_result.get("confidence", 0.0),
                "explanation": str(classification_result.get("explanation", ""))  # convert to string
            })

        logger.info(f"Fetched {len(results)} videos for keyword: {keyword}")
        return {
            "tool": "YouTube Monitor",
            "keyword": keyword,
            "total_results": len(results),
            "results": results
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching YouTube data: {str(e)}")
        return {"error": str(e)}


# ===============================
# 📌 Endpoint: YouTube Transcribe
# ===============================
class TranscribeRequest(BaseModel):
    url: str
    model_size: str = "small"
    vad: bool = False


@router.post("/youtube/transcribe")
async def transcribe_youtube(req: TranscribeRequest):
    """
    Download YouTube audio and transcribe using WhisperX (CPU fallback).
    """
    import whisperx  # Import here to avoid startup error if module missing

    tmpdir = tempfile.mkdtemp()
    # ✅ only basename without extension, yt_dlp + FFmpeg will append .mp3
    audio_base = os.path.join(tmpdir, "audio")
    audio_path = f"{audio_base}.mp3"

    try:
        logger.info(f"Transcribing URL: {req.url} with model {req.model_size}")

        # Download audio
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": audio_base,  # <-- no extension here
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}
            ],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([req.url])
        logger.info(f"Audio downloaded to {audio_path}")

        # Load WhisperX model
        model = whisperx.load_model(req.model_size, device="cpu", compute_type="float32")
        logger.info("WhisperX model loaded")

        # Transcribe (WhisperX returns a dict, not a tuple!)
        result = model.transcribe(audio_path, batch_size=16)

        segments = result.get("segments", [])
        info = {
            "language": result.get("language"),
            "language_probability": result.get("language_probability"),
            "duration": result.get("duration"),
        }

        # Make segments frontend-safe
        safe_segments = [
            {"start": s["start"], "end": s["end"], "text": s["text"]}
            for s in segments
        ]

        full_text = " ".join([seg["text"] for seg in safe_segments])

        return {
            "url": req.url,
            "language": info.get("language"),
            "language_probability": info.get("language_probability"),
            "duration": info.get("duration"),
            "segments": safe_segments,
            "full_text": full_text,
        }

    except Exception as e:
        logger.error(f"Transcription failed: {str(e)}")
        return {"error": str(e)}

    finally:
        if os.path.exists(tmpdir):
            shutil.rmtree(tmpdir)
            logger.info(f"Cleaned temporary directory {tmpdir}")
