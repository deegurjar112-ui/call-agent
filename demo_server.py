import json
import logging
import os
import random
import string
import sys
import time
from datetime import datetime
from pathlib import Path
from aiohttp import web
from dotenv import load_dotenv
import livekit.api as lk_api

# Reconfigure stdout/stderr for Unicode safety on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Load environment configuration
load_dotenv(".env.local")
load_dotenv(".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("demo-server")

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")
APPOINTMENTS_FILE = Path("appointments.json")
INDEX_FILE = Path("index.html")

if not LIVEKIT_URL or not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
    logger.warning("LiveKit credentials not fully configured in environment!")


def random_string(length: int = 4) -> str:
    """Generate short alphanumeric suffix."""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


@web.middleware
async def cors_middleware(request, handler):
    """Enable CORS for all incoming requests."""
    if request.method == "OPTIONS":
        response = web.Response(status=200)
    else:
        try:
            response = await handler(request)
        except web.HTTPException as ex:
            response = ex
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


async def handle_index(request: web.Request) -> web.Response:
    """Serve the single-page client demo interface."""
    if not INDEX_FILE.exists():
        return web.Response(
            text="<h1>index.html not found. Please ensure index.html exists in the project root.</h1>",
            content_type="text/html",
            status=404,
        )
    return web.Response(text=INDEX_FILE.read_text(encoding="utf-8"), content_type="text/html")


async def handle_token(request: web.Request) -> web.Response:
    """
    Generate an ephemeral LiveKit AccessToken for WebRTC demo calls.
    Supports both GET (query parameters) and POST (JSON body).
    """
    caller_name = "Homeowner"
    business_type = "Home Services"

    if request.method == "POST":
        try:
            data = await request.json()
            caller_name = data.get("caller_name", caller_name)
            business_type = data.get("business_type", business_type)
        except Exception:
            pass
    elif request.method == "GET":
        caller_name = request.query.get("caller_name", caller_name)
        business_type = request.query.get("business_type", business_type)

    if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        return web.json_response(
            {"error": "LIVEKIT_API_KEY or LIVEKIT_API_SECRET not set in environment"},
            status=500,
        )

    # Unique room for every client demo session
    timestamp = int(time.time())
    room_name = f"demo-room-{timestamp}-{random_string(4)}"
    identity = f"caller-{random_string(6)}"

    token = (
        lk_api.AccessToken(api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_name(caller_name)
        .with_grants(
            lk_api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
    )

    jwt_token = token.to_jwt()
    logger.info(f"Issued demo token for '{caller_name}' in room '{room_name}'")

    return web.json_response(
        {
            "token": jwt_token,
            "url": LIVEKIT_URL,
            "room": room_name,
            "identity": identity,
            "caller_name": caller_name,
            "business_type": business_type,
        }
    )


async def handle_bookings(request: web.Request) -> web.Response:
    """
    Return all booked jobs from appointments.json (newest first).
    Supports optional ?since=<timestamp_ms_or_iso> query parameter to filter bookings
    and preserve caller privacy.
    """
    bookings = []
    since_param = request.query.get("since")
    since_ts = None
    if since_param:
        try:
            since_ts = float(since_param) / 1000.0  # ms timestamp
        except ValueError:
            try:
                since_ts = datetime.fromisoformat(since_param).timestamp()
            except Exception:
                pass

    if APPOINTMENTS_FILE.exists():
        try:
            with open(APPOINTMENTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    filtered = []
                    for item in data:
                        if not isinstance(item, dict):
                            continue
                        if since_ts is not None and "booked_at" in item:
                            try:
                                item_ts = datetime.fromisoformat(item["booked_at"]).timestamp()
                                if item_ts < (since_ts - 5):  # 5s grace period
                                    continue
                            except Exception:
                                pass
                        filtered.append(item)
                    # Present newest bookings first consistently
                    bookings = list(reversed(filtered))
        except Exception as e:
            logger.warning(f"Error reading appointments file: {e}")
            bookings = []

    return web.json_response({"bookings": bookings, "count": len(bookings)})


def create_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/token", handle_token)
    app.router.add_post("/api/token", handle_token)
    app.router.add_get("/api/bookings", handle_bookings)
    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", 8080))
    print("=" * 65)
    print("[LIVEKIT VOICE AGENT] - CLIENT DEMO & TOKEN SERVER")
    print("=" * 65)
    print(f" Local Web Demo:    http://localhost:{port}")
    print(f" LiveKit Cloud URL: {LIVEKIT_URL}")
    print(f" Bookings Storage:  {APPOINTMENTS_FILE.resolve()}")
    print("=" * 65)
    web.run_app(app, host="0.0.0.0", port=port)
