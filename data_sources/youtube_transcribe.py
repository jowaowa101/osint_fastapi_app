import os
import sys
import tempfile
import shutil
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from yt_dlp import YoutubeDL
import json
import time

router = APIRouter(prefix="/youtube", tags=["YouTube Transcription"])


class YTRequest(BaseModel):
    url: str
    model_size: str = "small"
    vad: bool = True


@router.post("/transcribe")
def transcribe_youtube(req: YTRequest):
    """
    Regular transcription (non-streaming)
    """
    tempdir = tempfile.mkdtemp(prefix="yt_")
    audio_path = os.path.join(tempdir, "audio.m4a")

    try:
        print(f"[DEBUG] Starting download for: {req.url}")
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(tempdir, "audio.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "192",
            }],
            "quiet": True,
        }
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([req.url])

        if not os.path.exists(audio_path):
            raise HTTPException(status_code=500, detail="Failed to download audio.")

        from faster_whisper import WhisperModel

        print(f"[DEBUG] Loading Whisper model: {req.model_size}")
        model = WhisperModel(req.model_size, device="cpu", compute_type="int8")

        print("[DEBUG] Starting transcription...")
        segments, info = model.transcribe(
            audio_path,
            vad_filter=req.vad,
            vad_parameters=dict(min_silence_duration_ms=500),
        )
        print("[DEBUG] Transcription finished!")

        segs_list = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segments]

        # Debug: check if text was extracted
        if not segs_list or all(s["text"] == "" for s in segs_list):
            print("[WARNING] No transcript text extracted.")
            return {
                "url": req.url,
                "language": info.language,
                "language_probability": float(info.language_probability),
                "duration": float(info.duration),
                "segments": [],
                "full_text": ""
            }

        return {
            "url": req.url,
            "language": info.language,
            "language_probability": float(info.language_probability),
            "duration": float(info.duration),
            "segments": segs_list,
            "full_text": " ".join([s["text"] for s in segs_list]).strip()
        }

    except Exception as e:
        print(f"[ERROR] {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

    finally:
        shutil.rmtree(tempdir, ignore_errors=True)


@router.get("/transcribe_stream")
def transcribe_youtube_stream(url: str, model_size: str = "small", vad: bool = True):
    """
    Stream transcription segments to the frontend via SSE
    """
    tempdir = tempfile.mkdtemp(prefix="yt_")
    audio_path = os.path.join(tempdir, "audio.m4a")

    def event_generator():
        try:
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(tempdir, "audio.%(ext)s"),
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                    "preferredquality": "192",
                }],
                "quiet": True,
            }
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            if not os.path.exists(audio_path):
                yield f"data: {json.dumps({'error': 'Failed to download audio.'})}\n\n"
                return

            from faster_whisper import WhisperModel

            model = WhisperModel(model_size, device="cpu", compute_type="int8")
            segments, info = model.transcribe(
                audio_path,
                vad_filter=vad,
                vad_parameters=dict(min_silence_duration_ms=500),
            )

            # Collect segments while streaming
            full_text_parts = []
            for s in segments:
                seg_data = {
                    "start": round(s.start, 2),
                    "end": round(s.end, 2),
                    "text": s.text.strip()
                }
                full_text_parts.append(s.text.strip())
                yield f"data: {json.dumps(seg_data)}\n\n"
                time.sleep(0.1)  # simulate streaming pace

            # Send final transcript once all segments are done
            yield f"data: {json.dumps({'full_text': ' '.join(full_text_parts)})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            shutil.rmtree(tempdir, ignore_errors=True)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ==============================
# New: YouTube Validation Route
# ==============================
class YTValidateRequest(BaseModel):
    url: str
    model_size: str = "small"
    vad: bool = True


@router.post("/validate")
def validate_youtube_video(req: YTValidateRequest):
    """
    Validate a YouTube video URL and transcribe only the first 60 seconds.
    """
    tempdir = tempfile.mkdtemp(prefix="yt_validate_")
    audio_path = os.path.join(tempdir, "audio.m4a")

    try:
        print(f"[DEBUG] Validating YouTube video: {req.url}")

        # Metadata extraction without full download
        ydl_opts_info = {"quiet": True, "skip_download": True}
        with YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(req.url, download=False)

        # Quick checks
        if info.get("is_live"):
            return {"ready_for_transcription": False, "error": "Live videos cannot be transcribed."}
        if info.get("duration") is None or info.get("duration") <= 0:
            return {"ready_for_transcription": False, "error": "Invalid or unknown video duration."}

        video_duration = min(info.get("duration"), 3600)  # optional max 1 hour

        print(f"[DEBUG] Video duration: {video_duration} seconds, downloading first 60s only...")

        # Download only first 60 seconds using yt-dlp's download_sections
        ydl_opts_download = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(tempdir, "audio.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "192",
            }],
            "download_sections": {"*": "0-60"},  # <-- FIXED: proper yt-dlp syntax
            "quiet": True,
        }
        with YoutubeDL(ydl_opts_download) as ydl:
            ydl.download([req.url])

        if not os.path.exists(audio_path):
            return {"ready_for_transcription": False, "error": "Failed to download first 60 seconds of audio."}

        from faster_whisper import WhisperModel

        print(f"[DEBUG] Loading Whisper model: {req.model_size}")
        model = WhisperModel(req.model_size, device="cpu", compute_type="int8")

        print("[DEBUG] Transcribing first 60 seconds...")
        segments, info_trans = model.transcribe(
            audio_path,
            vad_filter=req.vad,
            vad_parameters=dict(min_silence_duration_ms=500),
        )
        print("[DEBUG] 1-minute transcription finished!")

        seg_texts = [s.text.strip() for s in segments if s.text.strip()]
        sample_text = " ".join(seg_texts)[:200] if seg_texts else ""

        return {
            "url": req.url,
            "title": info.get("title"),
            "duration": video_duration,
            "ready_for_transcription": True,
            "sample_transcript": sample_text,
            "language": info_trans.language
        }

    except Exception as e:
        print(f"[ERROR] Validation failed: {e}")
        return {"ready_for_transcription": False, "error": str(e)}

    finally:
        shutil.rmtree(tempdir, ignore_errors=True)
