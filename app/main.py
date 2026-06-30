"""
FastAPI uygulaması: route'lar ve uygulama yaşam döngüsü.

Endpoint'ler:
  GET  /              -> arayüz (index.html)
  GET  /video_feed    -> MJPEG canlı akış (multipart/x-mixed-replace)
  GET  /status        -> JSON durum (fps, bağlantılar, sayaç, hat durumu)
  POST /camera/start  -> akışı başlat
  POST /camera/stop   -> akışı durdur
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .state import AppState

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

state: AppState | None = None
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global state
    state = AppState()
    state.startup()
    try:
        yield
    finally:
        if state is not None:
            state.shutdown()


app = FastAPI(title="Konserve Kutu Kalite Kontrol - Canlı Görüntüleme (Faz 1)",
              lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/video_feed")
async def video_feed():
    assert state is not None
    return StreamingResponse(
        state.mjpeg_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/status")
async def status():
    assert state is not None
    return JSONResponse(state.status())


@app.post("/camera/start")
async def camera_start():
    assert state is not None
    try:
        state.start_streaming()
        return JSONResponse({"ok": True, "streaming": True})
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": str(exc)}, status_code=500
        )


@app.post("/camera/stop")
async def camera_stop():
    assert state is not None
    state.stop_streaming()
    return JSONResponse({"ok": True, "streaming": False})
