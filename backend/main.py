"""
Showroom Photo Booth -- backend.

Run locally:
    pip install -r requirements.txt
    uvicorn main:app --host 0.0.0.0 --port 8000

Then open http://localhost:8000 in a browser.

The first time you process an image, rembg will download its model
(~176MB) and cache it -- that request will be slow; every request
after that is fast.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import pathlib

from processing import process_image, get_session

app = FastAPI(title="Showroom Photo Booth")

# Loosen this to your real domain(s) once deployed, if you split
# frontend/backend onto different hosts. Not needed if served together
# (the setup below serves both from the same origin).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = pathlib.Path(__file__).parent.parent / "frontend"


@app.on_event("startup")
def warm_up_model():
    # Loads (and if needed, downloads) the segmentation model once at
    # startup so the first user request isn't the one stuck waiting.
    get_session()


@app.post("/api/process")
async def process_endpoint(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file.")
    try:
        raw = await file.read()
        result_bytes = process_image(raw)
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the frontend
        raise HTTPException(status_code=500, detail=f"Couldn't process this photo: {exc}") from exc

    return Response(content=result_bytes, media_type="image/jpeg")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve the frontend last, so /api/* routes above take priority.
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
