from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from ytmusicapi import YTMusic
import yt_dlp
import os
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Spotifry API",
    description="Free music streaming API powered by YouTube Music",
    version="1.0.0",
)

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ytmusic = YTMusic()

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

@app.get("/")
def root():
    return {
        "name": "Spotifry API",
        "version": "1.0.0",
        "status": "running",
    }

@app.get("/api/search")
def search(q: str = Query(..., min_length=1)):
    start_time = time.time()
    try:
        logger.info(f"Searching for: {q}")
        results = ytmusic.search(q, filter="songs", limit=20)

        formatted = []
        for item in results:
            try:
                formatted.append({
                    "id": item.get("videoId", ""),
                    "title": item.get("title", "Unknown Title"),
                    "artist": ", ".join([a["name"] for a in item.get("artists", [])]) or "Unknown Artist",
                    "img": item.get("thumbnails", [{}])[-1].get("url", "") if item.get("thumbnails") else "",
                    "duration": item.get("duration_seconds", 0),
                })
            except (KeyError, TypeError) as e:
                logger.warning(f"Skipping malformed track: {e}")
                continue

        elapsed = time.time() - start_time
        logger.info(f"Search completed in {elapsed:.2f}s, found {len(formatted)} results")

        return formatted
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search failed")

@app.get("/api/stream")
def stream(id: str = Query(..., min_length=1)):
    start_time = time.time()
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'timeout': 30,
        'extractor_retries': 3,
    }
    try:
        logger.info(f"Extracting stream for video ID: {id}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={id}", download=False)

        url = info.get("url")
        if not url:
            raise HTTPException(status_code=404, detail="Stream URL not found")

        elapsed = time.time() - start_time
        logger.info(f"Stream extracted in {elapsed:.2f}s")

        return {
            "url": url,
            "title": info.get("title", "Unknown"),
            "duration": info.get("duration", 0),
        }
    except HTTPException:
        raise
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp download error: {e}")
        raise HTTPException(status_code=404, detail="Video not available")
    except Exception as e:
        logger.error(f"Stream extraction error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to extract stream")

@app.get("/api/health")
def health():
    return {"status": "healthy", "timestamp": time.time()}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
