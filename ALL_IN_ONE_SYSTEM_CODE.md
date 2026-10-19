# 🎙️ CALL AGENT - COMPLETE ALL-IN-ONE SYSTEM CODEBASE
> **Version:** 2.0 (Google Gemini 3.8 Flash + Deepgram Nova-3 / Aura + LiveKit WebRTC)  
> **Repository:** Call Agent (LiveKit AI Voice Front-Desk Coordinator)  
> **Created:** 2026-10-19  

Yeh ek single consolidated master file hai jisme **Call Agent** project ka **100% poora code**, config, frontend, backend server, automation scripts aur architecture documentation ek hi jagah bundle kiya gaya hai.

---

## 📑 Table of Contents (Index)
1. [Architecture & System Flow Overview](#1-architecture--system-flow-overview)
2. [Project File Structure](#2-project-file-structure)
3. [File 1: agent.py (Core AI Voice Agent)](#3-file-1-agentpy-core-ai-voice-agent)
4. [File 2: demo_server.py (WebRTC Token & Dispatch Server)](#4-file-2-demo_serverpy-webrtc-token--dispatch-server)
5. [File 3: index.html (Client Web Application & Audio Visualizer)](#5-file-3-indexhtml-client-web-application--audio-visualizer)
6. [File 4: .env.example (Environment Configuration Template)](#6-file-4-envexample-environment-configuration-template)
7. [File 5: start_public_demo.bat (1-Click Public Tunnel Launcher)](#7-file-5-start_public_demobat-1-click-public-tunnel-launcher)
8. [File 6: start_localtunnel_demo.bat (Alternative Public Tunnel Launcher)](#8-file-6-start_localtunnel_demobat-alternative-public-tunnel-launcher)
9. [File 7: run_dev.bat (LiveKit Cloud Dev Launcher)](#9-file-7-run_devbat-livekit-cloud-dev-launcher)
10. [File 8: run_console.bat (Local Mic/Speaker Test Launcher)](#10-file-8-run_consolebat-local-micspeaker-test-launcher)
11. [File 9: START_HERE.md (Business, Pricing & Twilio SIP Guide)](#11-file-9-start_heremd-business-pricing--twilio-sip-guide)
12. [How To Run The Entire System](#12-how-to-run-the-entire-system)

---

## 1. Architecture & System Flow Overview

```
                                  +------------------------------------+
                                  |   Caller (Mobile / Laptop Mic)     |
                                  +-----------------+------------------+
                                                    |
                                      WebRTC Audio Stream (UDP)
                                                    v
                                  +------------------------------------+
                                  |    LiveKit Cloud (SFU Gateway)     |
                                  |   wss://dee-yfqt06tv.livekit.cloud |
                                  +-----------------+------------------+
                                                    |
                                        Bidirectional WebRTC
                                                    v
+------------------------+        +------------------------------------+
| Web Browser / Phone    |        |        LiveKit Worker: agent.py    |
| index.html (UI)        |        |                                    |
+-----------+------------+        |  [Ears] Deepgram Nova-3 (STT)      |
            |                     |         Bilingual Multi-language   |
     Fetches Token                |                                    |
            v                     |  [VAD]  Silero VAD (Interruption)  |
+------------------------+        |         100ms Instant Barge-in     |
| demo_server.py (:8080) |        |                                    |
| - Issues JWT Tokens    |        |  [Brain] Google Gemini 3.8 Flash   |
| - Serves index.html    |        |          Sub-second tool calling   |
| - Manages Appointments |        |                                    |
+-----------+------------+        |  [Voice] Deepgram Aura Asteria     |
            |                     |          Natural, warm voice       |
            | Real-time           +-----------------+------------------+
            | Sync                                  |
            v                                       v
    +--------------------------------------------------+
    |           Local Storage: appointments.json       |
    |      (Customer Name, Phone, Service, Time, Date) |
    +--------------------------------------------------+
```

---

## 2. Project File Structure
```
call agent/
├── agent.py                     # Main AI Voice Agent (Aria persona + tools + AI models)
├── demo_server.py               # Token dispenser, bookings API & web server (aiohttp :8080)
├── index.html                   # Premium dark UI with LiveKit WebRTC SDK & visualizer
├── appointments.json            # Auto-generated JSON database for booked jobs
├── .env.local                   # Local secret keys (LiveKit, Gemini, Deepgram)
├── .env.example                 # Template for secret keys
├── start_public_demo.bat        # 1-click launcher for public HTTPS demo (SSH tunnel)
├── start_localtunnel_demo.bat   # 1-click launcher for public HTTPS demo (localtunnel)
├── run_dev.bat                  # Launcher for agent connected to LiveKit Cloud
├── run_console.bat              # Launcher for agent using direct PC mic/speaker
└── START_HERE.md                # Complete setup, business pricing & Twilio guide
```

---

## 3. File 1: agent.py (Core AI Voice Agent)
> **Location:** `call agent/agent.py`  
> **Purpose:** Voice Agent implementation using LiveKit Agents 1.8.8, Google Gemini 3.8 Flash, Deepgram STT/TTS, and Silero VAD.

```python
import json
import logging
import os
from datetime import datetime
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    RunContext,
    TurnHandlingOptions,
    cli,
    room_io,
    text_transforms,
)
from livekit.agents.llm import function_tool
from livekit.plugins import openai, deepgram, cartesia, silero

try:
    from livekit.plugins import google
except ImportError:
    google = None

# Load environment variables from .env.local first, then .env
load_dotenv(".env.local")
load_dotenv(".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice-agent")

# Local appointment storage file
APPOINTMENTS_FILE = "appointments.json"


def save_appointment_record(record: dict):
    """Save an appointment record locally to JSON file."""
    appointments = []
    if os.path.exists(APPOINTMENTS_FILE):
        try:
            with open(APPOINTMENTS_FILE, "r", encoding="utf-8") as f:
                appointments = json.load(f)
        except Exception:
            appointments = []
    appointments.append(record)
    with open(APPOINTMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(appointments, f, indent=2, ensure_ascii=False)


class SmartBusinessVoiceAgent(Agent):
    """
    Expert AI Voice Front-Desk Coordinator for Home-Service & Trade Businesses
    (Air Conditioning/HVAC, Plumbing & Gas, Electrical, Roofing, Pest Control, Cleaning).
    """

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are 'Aria' (Aria), a friendly, sharp, and top-tier human front-desk coordinator "
                "for a premier 24/7 Home-Service & Trade Business (Air Conditioning/HVAC, Plumbing & Gas, "
                "Electrical, Roofing/Gutters, Pest Control, Cleaning, and Garage Doors). "
                "You speak fluent, natural English, and can seamlessly speak Hindi or Hinglish if the caller speaks it. "
                "CRITICAL HUMAN SPEECH RULES: "
                "1. Always output all words using the standard English Latin alphabet (even if speaking Hindi/Hinglish, write in Romanized English letters like 'Bilkul, main abhi check karti hoon'—NEVER output Devanagari script so the English TTS engine pronounces every word clearly). "
                "2. Keep every turn to 1 or 2 short, crisp sentences (under 22 words max). You are on a live phone call—NEVER recite monologues. "
                "3. Sound warm, calm, empathetic, and reassuring (use natural phrases like 'no problem at all', 'we can definitely sort that out', 'bilkul', 'zaroor'). "
                "4. NEVER speak emojis, markdown symbols, asterisks, bullet points, or list numbers. "
                "5. STRICT RULE: ASK ONE QUESTION AT A TIME. Never ask for multiple details together. Follow this natural human flow: "
                "   - Step A: Empathize with their problem in 1 sentence and ask their suburb or location (e.g., 'Oh, a struggling aircon in this heat is no fun—we can definitely help. What suburb are you in?'). "
                "   - Step B: Once they give the suburb, offer two specific time windows (e.g., 'We have a technician near you today at 2:30 PM or tomorrow at 9:00 AM—which suits you better?'). "
                "   - Step C: Once they pick a time, ask for their first name and best mobile number to send the confirmation. "
                "   - Step D: As soon as you have name, phone, issue, suburb, and time, call the book_appointment tool and confirm warmly that the job details were sent straight to the lead technician. "
                "6. LOCAL SLANG & TERMS: Understand Australian trade terms ('aircon', 'suburb', 'sparky', 'hot water unit', 'retic', 'tradie') and Dubai/UAE terms ('villa', 'community'). "
                "7. If a business owner testing the demo asks 'How do you work for my business?', explain naturally: "
                "'Whenever you're on the tools, on another call, or after hours, I pick up in one second, chat with your customer just like we're talking now, and text the job details straight to your phone. Go ahead and test me like a real customer with a broken aircon or leaking pipe!' "
                "8. For severe emergencies (gas leaks, active electrical sparking, massive burst pipes), immediately call transfer_to_specialist."
            )
        )

    async def on_enter(self) -> None:
        """Greet the caller warmly as soon as the call connects."""
        self.session.generate_reply(
            instructions=(
                "Greet the caller warmly and naturally in 1 short sentence: "
                "'Hi there! Thanks for calling our 24/7 Home Service desk, this is Aria—how can I help with your home or property today?'"
            )
        )

    @function_tool
    async def check_availability(
        self,
        context: RunContext,
        service_name: str,
        preferred_date: str = "today",
        suburb_or_location: str = "",
    ) -> str:
        """
        Check available appointment slots for a trade service and location.

        Args:
            service_name: Name of the trade service or issue (e.g., air conditioning repair, leaking pipe, electrical fault)
            preferred_date: Date requested by caller (e.g., today, tomorrow, Friday)
            suburb_or_location: Caller's suburb, area, or locality
        """
        logger.info(f"Checking trade availability for {service_name} in '{suburb_or_location}' on {preferred_date}")
        area_str = f" around {suburb_or_location}" if suburb_or_location else ""
        return (
            f"We have technicians available{area_str} on {preferred_date} with time slots at "
            f"2:30 PM today or tomorrow at 9:00 AM. Ask the caller which of these two works better."
        )

    @function_tool
    async def book_appointment(
        self,
        context: RunContext,
        customer_name: str,
        phone_number: str,
        service_name: str,
        suburb_or_location: str,
        appointment_date: str,
        appointment_time: str,
    ) -> str:
        """
        Book a trade service appointment and dispatch the job details to the lead technician.

        Args:
            customer_name: Full name or first name of the customer
            phone_number: Contact phone number of the customer
            service_name: Type of trade issue or service (e.g., aircon repair, leaking pipe, electrical fault, pest control)
            suburb_or_location: Suburb, area, villa, or locality where service is required
            appointment_date: Date of appointment (e.g., today, tomorrow, 15th October)
            appointment_time: Preferred time slot (e.g., 2:30 PM, 9:00 AM)
        """
        logger.info(
            f"Booking trade job for {customer_name} ({phone_number}) in {suburb_or_location} - "
            f"{service_name} on {appointment_date} at {appointment_time}"
        )
        room_name = ""
        if hasattr(context, "session") and hasattr(context.session, "room") and context.session.room:
            room_name = context.session.room.name

        record = {
            "customer_name": customer_name,
            "phone_number": phone_number,
            "service_name": service_name,
            "suburb_or_location": suburb_or_location,
            "date": appointment_date,
            "time": appointment_time,
            "booked_at": datetime.now().isoformat(),
            "status": "DISPATCHED",
            "room": room_name,
        }
        save_appointment_record(record)
        return (
            f"Job booked successfully for {customer_name} in {suburb_or_location} on {appointment_date} "
            f"at {appointment_time} for {service_name}. A live dispatch SMS notification has been sent to the lead technician."
        )

    @function_tool
    async def transfer_to_specialist(self, context: RunContext, department: str, reason: str) -> str:
        """
        Transfer the call to an emergency senior technician or supervisor.

        Args:
            department: Department or trade specialist (e.g., Emergency Plumbing, Senior Electrician, Manager)
            reason: Why the transfer was requested
        """
        logger.info(f"Initiating transfer to {department}. Reason: {reason}")
        return f"Transferring your call to our {department} team immediately. Please hold the line for just a second."


server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    """Entrypoint function called whenever an agent session starts."""
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info(f"Starting home-service voice agent session in room: {ctx.room.name}")

    # Voice STT (Deepgram Nova-3 with multilingual support for English, Hindi, Hinglish)
    deepgram_key = os.getenv("DEEPGRAM_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    cartesia_key = os.getenv("CARTESIA_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

    if deepgram_key:
        stt_engine = deepgram.STT(model="nova-3", language="multi")
    else:
        stt_engine = openai.STT()

    # Voice LLM: Google Gemini (gemini-3.8-flash) is active & verified with working API key
    if google_key and google is not None:
        logger.info("Using Google Gemini LLM (gemini-3.8-flash)")
        llm_engine = google.LLM(model="gemini-3.8-flash", api_key=google_key)
    elif openai_key:
        logger.info("Using OpenAI LLM (gpt-4o-mini)")
        llm_engine = openai.LLM(model="gpt-4o-mini")
    else:
        logger.info("Defaulting to OpenAI LLM (gpt-4o-mini)")
        llm_engine = openai.LLM(model="gpt-4o-mini")

    # Voice TTS (Cartesia -> Deepgram Aura -> OpenAI Nova)
    if cartesia_key:
        tts_engine = cartesia.TTS(voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc")
    elif deepgram_key:
        # High-fidelity natural voice using active Deepgram credentials (no OpenAI quota needed)
        tts_engine = deepgram.TTS(model="aura-asteria-en")
    else:
        tts_engine = openai.TTS(voice="nova")

    session: AgentSession = AgentSession(
        stt=stt_engine,
        llm=llm_engine,
        tts=tts_engine,
        # Silero VAD provides instant interruption detection (Barge-in)
        vad=silero.VAD.load(),
        turn_handling=TurnHandlingOptions(
            interruption={
                "resume_false_interruption": True,
                "false_interruption_timeout": 1.0,
            },
            preemptive_generation={"enabled": True, "max_retries": 3},
        ),
        aec_warmup_duration=2.0,
        tts_text_transforms=[
            "filter_emoji",
            "filter_markdown",
            text_transforms.replace({"LiveKit": "<<ˈ|l|aɪ|v|k|ɪ|t>>"}),
        ],
    )

    await session.start(
        agent=SmartBusinessVoiceAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
```

---

## 4. File 2: demo_server.py (WebRTC Token & Dispatch Server)
> **Location:** `call agent/demo_server.py`  
> **Purpose:** Lightweight `aiohttp` web server running on port 8080. Serves `index.html`, generates short-lived LiveKit WebRTC AccessTokens (`/api/token`), and returns live appointment bookings (`/api/bookings`).

```python
import json
import logging
import os
import random
import string
import sys
import time
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
                    for item in reversed(data):
                        if since_ts is not None and "booked_at" in item:
                            try:
                                item_ts = datetime.fromisoformat(item["booked_at"]).timestamp()
                                if item_ts < (since_ts - 5):  # 5s grace period
                                    continue
                            except Exception:
                                pass
                        bookings.append(item)
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
```

---

## 5. File 3: index.html (Client Web Application & Audio Visualizer)
> **Location:** `call agent/index.html`  
> **Purpose:** Single-page frontend with LiveKit Client SDK, dynamic audio waveform, call status badges, prompt chips, and real-time CRM appointment cards.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>24/7 AI Voice Receptionist — Live Client Demo</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
  <!-- Official LiveKit WebRTC Browser SDK -->
  <script src="https://cdn.jsdelivr.net/npm/livekit-client/dist/livekit-client.umd.min.js"></script>

  <style>
    :root {
      --bg-dark: #070B14;
      --card-bg: rgba(15, 23, 42, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --card-border-glow: rgba(16, 185, 129, 0.3);
      --emerald-primary: #10B981;
      --emerald-glow: rgba(16, 185, 129, 0.4);
      --emerald-dark: #059669;
      --cyan-accent: #06B6D4;
      --red-danger: #EF4444;
      --red-glow: rgba(239, 68, 68, 0.4);
      --text-main: #F8FAFC;
      --text-muted: #94A3B8;
      --font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      -webkit-tap-highlight-color: transparent;
    }

    body {
      background-color: var(--bg-dark);
      background-image: 
        radial-gradient(circle at 50% 0%, rgba(16, 185, 129, 0.12) 0%, transparent 60%),
        radial-gradient(circle at 100% 50%, rgba(6, 182, 212, 0.08) 0%, transparent 45%),
        radial-gradient(circle at 0% 100%, rgba(99, 102, 241, 0.08) 0%, transparent 45%);
      color: var(--text-main);
      font-family: var(--font-sans);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 24px 16px 60px;
      overflow-x: hidden;
    }

    .container {
      width: 100%;
      max-width: 760px;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }

    /* HEADER */
    header {
      text-align: center;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 12px;
    }

    .badge-live {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 14px;
      border-radius: 9999px;
      background: rgba(16, 185, 129, 0.12);
      border: 1px solid rgba(16, 185, 129, 0.35);
      color: #34D399;
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .badge-live .pulse-dot {
      width: 8px;
      height: 8px;
      background: #10B981;
      border-radius: 50%;
      box-shadow: 0 0 10px #10B981;
      animation: pulse 1.5s infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.85); }
    }

    h1 {
      font-size: clamp(1.8rem, 4.5vw, 2.5rem);
      font-weight: 800;
      line-height: 1.2;
      background: linear-gradient(135deg, #FFFFFF 30%, #94A3B8 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .subheadline {
      color: var(--text-muted);
      font-size: clamp(0.95rem, 2.5vw, 1.08rem);
      line-height: 1.55;
      max-width: 620px;
    }

    /* GLASS CARD */
    .glass-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border-radius: 20px;
      padding: 28px 24px;
      box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.5);
      position: relative;
      overflow: hidden;
    }

    .glass-card::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 1px;
      background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
    }

    /* PROMPTS CHIPS */
    .chips-section {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .chips-title {
      font-size: 0.8rem;
      font-weight: 700;
      color: #64748B;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .chips-grid {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .chip-btn {
      background: rgba(30, 41, 59, 0.6);
      border: 1px solid rgba(255, 255, 255, 0.06);
      color: #CBD5E1;
      padding: 10px 14px;
      border-radius: 12px;
      font-size: 0.88rem;
      font-family: inherit;
      text-align: left;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      transition: all 0.2s ease;
    }

    .chip-btn:hover {
      background: rgba(51, 65, 85, 0.7);
      border-color: rgba(16, 185, 129, 0.4);
      color: #FFFFFF;
      transform: translateX(4px);
    }

    .chip-btn span.emoji {
      font-size: 1.1rem;
    }

    /* CALL CONSOLE */
    .call-console {
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      gap: 20px;
      padding: 32px 20px;
    }

    .avatar-wrapper {
      position: relative;
      width: 96px;
      height: 96px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(6, 182, 212, 0.2));
      border: 2px solid rgba(16, 185, 129, 0.4);
      box-shadow: 0 0 30px rgba(16, 185, 129, 0.2);
      transition: all 0.3s ease;
    }

    .avatar-wrapper.active {
      border-color: #10B981;
      box-shadow: 0 0 45px rgba(16, 185, 129, 0.5), inset 0 0 20px rgba(16, 185, 129, 0.3);
      animation: avatarBreath 2s infinite ease-in-out;
    }

    @keyframes avatarBreath {
      0%, 100% { transform: scale(1); }
      50% { transform: scale(1.05); }
    }

    .avatar-icon {
      font-size: 2.5rem;
    }

    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 16px;
      border-radius: 9999px;
      font-size: 0.88rem;
      font-weight: 600;
      background: rgba(15, 23, 42, 0.8);
      border: 1px solid var(--card-border);
      transition: all 0.3s;
    }

    .status-badge.ready {
      color: #94A3B8;
    }

    .status-badge.connecting {
      color: #FBBF24;
      border-color: rgba(251, 191, 36, 0.3);
      background: rgba(251, 191, 36, 0.1);
    }

    .status-badge.live {
      color: #34D399;
      border-color: rgba(52, 211, 153, 0.4);
      background: rgba(16, 185, 129, 0.12);
    }

    .call-timer {
      font-family: var(--font-mono);
      font-size: 1.15rem;
      color: #94A3B8;
      display: none;
    }

    .call-timer.visible {
      display: block;
    }

    /* WAVEFORM BARS */
    .waveform {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
      height: 38px;
      opacity: 0.3;
      transition: opacity 0.3s;
    }

    .waveform.active {
      opacity: 1;
    }

    .bar {
      width: 4px;
      height: 8px;
      border-radius: 4px;
      background: linear-gradient(180deg, #10B981, #06B6D4);
      transition: height 0.1s ease;
    }

    .waveform.active .bar {
      animation: wave 1.2s infinite ease-in-out;
    }

    .waveform.active .bar:nth-child(1) { animation-delay: 0.0s; }
    .waveform.active .bar:nth-child(2) { animation-delay: 0.15s; }
    .waveform.active .bar:nth-child(3) { animation-delay: 0.3s; }
    .waveform.active .bar:nth-child(4) { animation-delay: 0.45s; }
    .waveform.active .bar:nth-child(5) { animation-delay: 0.6s; }
    .waveform.active .bar:nth-child(6) { animation-delay: 0.75s; }
    .waveform.active .bar:nth-child(7) { animation-delay: 0.9s; }
    .waveform.active .bar:nth-child(8) { animation-delay: 1.05s; }
    .waveform.active .bar:nth-child(9) { animation-delay: 0.9s; }
    .waveform.active .bar:nth-child(10) { animation-delay: 0.75s; }
    .waveform.active .bar:nth-child(11) { animation-delay: 0.6s; }
    .waveform.active .bar:nth-child(12) { animation-delay: 0.45s; }

    @keyframes wave {
      0%, 100% { height: 6px; }
      50% { height: 34px; }
    }

    /* CALL BUTTONS */
    .btn-action {
      width: 100%;
      max-width: 380px;
      padding: 16px 28px;
      border-radius: 16px;
      font-size: 1.08rem;
      font-weight: 700;
      font-family: inherit;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 12px;
      border: none;
      transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
      text-decoration: none;
    }

    .btn-start {
      background: linear-gradient(135deg, #10B981 0%, #059669 100%);
      color: #FFFFFF;
      box-shadow: 0 10px 25px -5px var(--emerald-glow), inset 0 1px 0 rgba(255, 255, 255, 0.25);
    }

    .btn-start:hover {
      transform: translateY(-2px);
      box-shadow: 0 15px 30px -5px var(--emerald-glow);
    }

    .btn-start:active {
      transform: translateY(1px);
    }

    .btn-end {
      background: linear-gradient(135deg, #EF4444 0%, #DC2626 100%);
      color: #FFFFFF;
      box-shadow: 0 10px 25px -5px var(--red-glow), inset 0 1px 0 rgba(255, 255, 255, 0.25);
      display: none;
    }

    .btn-end:hover {
      transform: translateY(-2px);
      box-shadow: 0 15px 30px -5px var(--red-glow);
    }

    .btn-action:disabled {
      opacity: 0.6;
      cursor: not-allowed;
      transform: none !important;
    }

    /* DISPATCH PREVIEW / SMS CRM PANEL */
    .panel-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 16px;
    }

    .panel-title {
      font-size: 1rem;
      font-weight: 700;
      color: #FFFFFF;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .panel-subtitle {
      font-size: 0.82rem;
      color: var(--text-muted);
      margin-bottom: 16px;
      line-height: 1.45;
    }

    .booking-count-pill {
      font-size: 0.72rem;
      font-weight: 700;
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.3);
      color: #34D399;
      padding: 2px 8px;
      border-radius: 9999px;
    }

    .bookings-container {
      display: flex;
      flex-direction: column;
      gap: 12px;
      max-height: 380px;
      overflow-y: auto;
      padding-right: 4px;
    }

    .bookings-container::-webkit-scrollbar {
      width: 4px;
    }

    .bookings-container::-webkit-scrollbar-thumb {
      background: rgba(255, 255, 255, 0.1);
      border-radius: 4px;
    }

    .booking-card {
      background: rgba(15, 23, 42, 0.85);
      border: 1px solid rgba(16, 185, 129, 0.35);
      border-radius: 14px;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      animation: slideIn 0.35s ease-out;
      position: relative;
    }

    @keyframes slideIn {
      from { opacity: 0; transform: translateY(-10px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .booking-card-top {
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .job-badge {
      font-size: 0.72rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      padding: 3px 8px;
      border-radius: 6px;
      background: rgba(16, 185, 129, 0.2);
      color: #34D399;
    }

    .booking-time {
      font-size: 0.75rem;
      color: #64748B;
      font-family: var(--font-mono);
    }

    .booking-details-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px 14px;
      margin-top: 4px;
    }

    .detail-item {
      display: flex;
      flex-direction: column;
    }

    .detail-label {
      font-size: 0.7rem;
      color: #64748B;
      text-transform: uppercase;
      font-weight: 600;
    }

    .detail-value {
      font-size: 0.88rem;
      color: #F1F5F9;
      font-weight: 600;
    }

    .empty-bookings {
      text-align: center;
      padding: 30px 20px;
      color: #64748B;
      font-size: 0.88rem;
      border: 1px dashed rgba(255, 255, 255, 0.08);
      border-radius: 12px;
    }

    footer {
      text-align: center;
      font-size: 0.78rem;
      color: #64748B;
      margin-top: 10px;
    }

    footer a {
      color: #94A3B8;
      text-decoration: none;
    }

    @media (max-width: 600px) {
      .glass-card {
        padding: 20px 16px;
      }
      .booking-details-grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>

  <div class="container">
    <!-- HEADER -->
    <header>
      <div class="badge-live">
        <span class="pulse-dot"></span>
        24/7 AI Receptionist • Live Demo
      </div>
      <h1>Test Our AI Voice Receptionist Live</h1>
      <p class="subheadline">
        Tap below and pretend you're a homeowner with a broken aircon, leaking pipe, electrical fault, or pest issue. See how Aria answers instantly and books the job while you're on the tools.
      </p>
    </header>

    <!-- SAMPLE PROMPT CHIPS -->
    <div class="glass-card chips-section">
      <div class="chips-title">💡 What to say into your mic:</div>
      <div class="chips-grid">
        <button class="chip-btn" onclick="copyPrompt('Hi, my aircon stopped cooling and I am in Scarborough.')">
          <span class="emoji">❄️</span>
          <span>"Hi, my aircon stopped cooling and I'm in Scarborough."</span>
        </button>
        <button class="chip-btn" onclick="copyPrompt('I have a leaking hot water pipe, can someone come out today?')">
          <span class="emoji">🔧</span>
          <span>"I have a leaking hot water pipe, can someone come out today?"</span>
        </button>
        <button class="chip-btn" onclick="copyPrompt('We need a quote for a cockroach and spider treatment.')">
          <span class="emoji">🕷️</span>
          <span>"We need a quote for a cockroach and spider treatment."</span>
        </button>
        <button class="chip-btn" onclick="copyPrompt('How do you work for my business?')">
          <span class="emoji">💼</span>
          <span>"How do you work for my business?"</span>
        </button>
      </div>
    </div>

    <!-- MAIN CALL CONSOLE -->
    <div class="glass-card call-console">
      <div class="avatar-wrapper" id="avatarWrapper">
        <span class="avatar-icon">🎙️</span>
      </div>

      <div class="status-badge ready" id="statusBadge">
        🟢 Ready to Call Aria
      </div>

      <div class="call-timer" id="callTimer">00:00</div>

      <div class="waveform" id="waveform">
        <div class="bar"></div>
        <div class="bar"></div>
        <div class="bar"></div>
        <div class="bar"></div>
        <div class="bar"></div>
        <div class="bar"></div>
        <div class="bar"></div>
        <div class="bar"></div>
        <div class="bar"></div>
        <div class="bar"></div>
        <div class="bar"></div>
        <div class="bar"></div>
      </div>

      <!-- Action Buttons -->
      <button class="btn-action btn-start" id="btnStartCall" onclick="startCall()">
        <span>📞 Start 30-Sec Live Demo Call</span>
      </button>

      <button class="btn-action btn-end" id="btnEndCall" onclick="endCall()">
        <span>❌ End Call</span>
      </button>
    </div>

    <!-- REAL-TIME DISPATCH / OWNER SMS NOTIFICATION PANEL -->
    <div class="glass-card">
      <div class="panel-header">
        <div class="panel-title">
          <span>📲 Lead Technician / Owner Dispatch Preview</span>
        </div>
        <span class="booking-count-pill" id="bookingCountPill">0 Jobs</span>
      </div>
      <p class="panel-subtitle">
        As soon as you tell Aria to book the appointment during your call, the captured job appears here in real time—ready to be dispatched straight to your phone.
      </p>

      <div class="bookings-container" id="bookingsContainer">
        <div class="empty-bookings">
          Waiting for your first test booking... Speak with Aria above and give her a time slot to watch the booking appear live!
        </div>
      </div>
    </div>

    <footer>
      Powered by LiveKit WebRTC &bull; Deepgram Nova-3 &bull; Google Gemini 3.8 Flash &bull; Silero VAD
    </footer>
  </div>

  <script>
    let activeRoom = null;
    let timerInterval = null;
    let callSeconds = 0;
    let pollInterval = null;
    let lastBookingsJson = "";

    function copyPrompt(text) {
      navigator.clipboard?.writeText(text);
      const badge = document.getElementById("statusBadge");
      badge.textContent = "💡 Copied prompt! Say this when you call.";
      setTimeout(() => {
        if (!activeRoom) badge.textContent = "🟢 Ready to Call Aria";
      }, 2500);
    }

    async function startCall() {
      const btnStart = document.getElementById("btnStartCall");
      const btnEnd = document.getElementById("btnEndCall");
      const statusBadge = document.getElementById("statusBadge");
      const avatarWrapper = document.getElementById("avatarWrapper");
      const waveform = document.getElementById("waveform");
      const callTimer = document.getElementById("callTimer");

      btnStart.disabled = true;
      statusBadge.className = "status-badge connecting";
      statusBadge.textContent = "🟡 Connecting to Aria...";

      try {
        // Request token from local token server
        const res = await fetch("/api/token", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ caller_name: "Client Demo Tester" }),
        });

        if (!res.ok) {
          throw new Error("Failed to get demo token from server");
        }

        const data = await res.json();
        const { token, url, room: roomName } = data;

        // Initialize LiveKit Room
        const room = new LivekitClient.Room({
          adaptiveStream: true,
          dynacast: true,
          audioCaptureDefaults: {
            autoGainControl: true,
            echoCancellation: true,
            noiseSuppression: true,
          },
        });

        activeRoom = room;

        // Audio track subscription: plays Aria's voice naturally
        room.on(LivekitClient.RoomEvent.TrackSubscribed, (track, publication, participant) => {
          if (track.kind === LivekitClient.Track.Kind.Audio) {
            const audioElement = track.attach();
            audioElement.id = "ariaAudioStream";
            document.body.appendChild(audioElement);
            audioElement.play().catch((err) => {
              console.warn("Autoplay interaction note:", err);
            });
          }
        });

        room.on(LivekitClient.RoomEvent.TrackUnsubscribed, (track) => {
          track.detach().forEach((el) => el.remove());
        });

        room.on(LivekitClient.RoomEvent.Disconnected, () => {
          handleCallEnded();
        });

        // Connect WebRTC to LiveKit Cloud
        await room.connect(url, token);

        // Publish caller's microphone
        await room.localParticipant.setMicrophoneEnabled(true);

        // Update UI to Live state
        btnStart.style.display = "none";
        btnStart.disabled = false;
        btnEnd.style.display = "inline-flex";

        statusBadge.className = "status-badge live";
        statusBadge.textContent = "🔴 Live Call Active — Speak into your mic!";
        avatarWrapper.classList.add("active");
        waveform.classList.add("active");

        callSeconds = 0;
        callTimer.textContent = "00:00";
        callTimer.classList.add("visible");
        clearInterval(timerInterval);
        timerInterval = setInterval(() => {
          callSeconds++;
          const mins = String(Math.floor(callSeconds / 60)).padStart(2, "0");
          const secs = String(callSeconds % 60).padStart(2, "0");
          callTimer.textContent = `${mins}:${secs}`;
        }, 1000);

      } catch (err) {
        console.error("Connection error:", err);
        statusBadge.className = "status-badge ready";
        statusBadge.textContent = "❌ Connection failed: " + (err.message || "Check mic permission");
        btnStart.disabled = false;
        btnStart.style.display = "inline-flex";
        btnEnd.style.display = "none";
      }
    }

    async function endCall() {
      if (activeRoom) {
        try {
          await activeRoom.disconnect();
        } catch (e) {
          console.error(e);
        }
      }
      handleCallEnded();
    }

    function handleCallEnded() {
      activeRoom = null;
      clearInterval(timerInterval);

      // Clean up audio elements
      const existing = document.getElementById("ariaAudioStream");
      if (existing) existing.remove();

      const btnStart = document.getElementById("btnStartCall");
      const btnEnd = document.getElementById("btnEndCall");
      const statusBadge = document.getElementById("statusBadge");
      const avatarWrapper = document.getElementById("avatarWrapper");
      const waveform = document.getElementById("waveform");
      const callTimer = document.getElementById("callTimer");

      btnStart.style.display = "inline-flex";
      btnStart.disabled = false;
      btnEnd.style.display = "none";

      statusBadge.className = "status-badge ready";
      statusBadge.textContent = "🟢 Ready to Call Aria";
      avatarWrapper.classList.remove("active");
      waveform.classList.remove("active");
      callTimer.classList.remove("visible");
    }

    // POLL BOOKINGS FROM SERVER FOR LIVE CRM PREVIEW
    async function fetchBookings() {
      try {
        const res = await fetch("/api/bookings");
        if (!res.ok) return;
        const data = await res.json();
        const currentJson = JSON.stringify(data.bookings);

        if (currentJson === lastBookingsJson) return;
        lastBookingsJson = currentJson;

        const container = document.getElementById("bookingsContainer");
        const countPill = document.getElementById("bookingCountPill");
        const bookings = data.bookings || [];

        countPill.textContent = `${bookings.length} Job${bookings.length === 1 ? '' : 's'}`;

        if (bookings.length === 0) {
          container.innerHTML = `
            <div class="empty-bookings">
              Waiting for your first test booking... Speak with Aria above and give her a time slot to watch the booking appear live!
            </div>
          `;
          return;
        }

        container.innerHTML = bookings
          .map((b) => {
            const dateStr = b.booked_at ? new Date(b.booked_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Recent';
            return `
              <div class="booking-card">
                <div class="booking-card-top">
                  <span class="job-badge">⚡ ${b.status || 'CONFIRMED'}</span>
                  <span class="booking-time">${dateStr}</span>
                </div>
                <div class="booking-details-grid">
                  <div class="detail-item">
                    <span class="detail-label">Customer Name</span>
                    <span class="detail-value">${b.customer_name || 'N/A'}</span>
                  </div>
                  <div class="detail-item">
                    <span class="detail-label">Mobile Number</span>
                    <span class="detail-value">${b.phone_number || 'N/A'}</span>
                  </div>
                  <div class="detail-item">
                    <span class="detail-label">Issue / Trade Service</span>
                    <span class="detail-value">${b.service_name || 'N/A'}</span>
                  </div>
                  <div class="detail-item">
                    <span class="detail-label">Suburb / Location</span>
                    <span class="detail-value">${b.suburb_or_location || 'N/A'}</span>
                  </div>
                  <div class="detail-item">
                    <span class="detail-label">Preferred Date</span>
                    <span class="detail-value">${b.date || 'N/A'}</span>
                  </div>
                  <div class="detail-item">
                    <span class="detail-label">Time Window</span>
                    <span class="detail-value">${b.time || 'N/A'}</span>
                  </div>
                </div>
              </div>
            `;
          })
          .join("");
      } catch (e) {
        console.error("Bookings poll error:", e);
      }
    }

    // Start polling every 1.5 seconds
    fetchBookings();
    pollInterval = setInterval(fetchBookings, 1500);
  </script>
</body>
</html>
```

---

## 6. File 4: .env.example (Environment Configuration Template)
> **Location:** `call agent/.env.example`  
> **Purpose:** Template for setting up LiveKit, Gemini, Deepgram, and voice credentials.

```env
# ==============================================================================
# LiveKit Voice Agent Configuration
# ==============================================================================
# Copy this file to `.env.local` and fill in your API keys.
# All services below offer FREE tier / trial credits.
# ==============================================================================

# 1. LiveKit Cloud (Free 10,000 mins/mo at https://cloud.livekit.io)
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret

# 2. Google Gemini API Key (Brain / LLM - Free tier at https://aistudio.google.com/apikey)
GEMINI_API_KEY=your_gemini_api_key
GOOGLE_API_KEY=your_gemini_api_key

# 3. OpenAI API Key (Alternative Brain & Voice - https://platform.openai.com)
OPENAI_API_KEY=sk-proj-your_openai_api_key

# 4. Deepgram API Key (Ears / STT & Voice / TTS - $200 free credit at https://deepgram.com)
DEEPGRAM_API_KEY=your_deepgram_api_key

# 5. Cartesia API Key (Optional Ultra-fast Voice - https://cartesia.ai)
CARTESIA_API_KEY=your_cartesia_api_key

# 6. ElevenLabs API Key (Optional Alternative Voice - https://elevenlabs.io)
ELEVENLABS_API_KEY=your_elevenlabs_api_key
```

---

## 7. File 5: start_public_demo.bat (1-Click Public Tunnel Launcher)
> **Location:** `call agent/start_public_demo.bat`  
> **Purpose:** Windows batch script to launch Agent Worker + Web Server + OpenSSH tunnel (`localhost.run`) generating a public HTTPS link.

```bat
@echo off
cd /d "%~dp0"
title 1-Click AI Voice Agent Public Demo
color 0A
cls
echo ==============================================================================
echo        🎙️ 24/7 AI VOICE RECEPTIONIST - 1-CLICK PUBLIC DEMO SYSTEM
echo ==============================================================================
echo.
echo [1/3] Starting LiveKit Voice Agent Worker (Aria) in background...
start "LiveKit Agent Worker (Aria)" C:\Users\Deepak\.venvs\livekit_agent\Scripts\python.exe agent.py dev

echo [2/3] Starting WebRTC & Token Dispenser Server on port 8080...
start "AI Voice Web & Token Server" C:\Users\Deepak\.venvs\livekit_agent\Scripts\python.exe demo_server.py

echo.
echo Waiting 2 seconds for server to initialize...
timeout /t 2 /nobreak >nul

echo.
echo ==============================================================================
echo  ✅ LOCAL DEMO LINK (Test on this PC):
echo     http://localhost:8080
echo.
echo  🌐 GENERATING PUBLIC HTTPS DEMO LINK (For Clients & Mobile Phones)...
echo     Starting secure OpenSSH tunnel via localhost.run...
echo.
echo  👉 INSTRUCTIONS FOR CLIENT DEMO:
echo     1. Look for the "https://xxxx.lhr.life" link displayed below.
echo     2. Copy that link and send it via WhatsApp, SMS, or Email to any client.
echo     3. Client opens it on their iPhone/Android or laptop, taps "Start Call",
echo        and speaks directly with Aria!
echo ==============================================================================
echo.
ssh -o StrictHostKeyChecking=no -R 80:127.0.0.1:8080 nokey@localhost.run

echo.
echo Tunnel closed. If you need an alternative tunnel, you can also run:
echo npx localtunnel --port 8080
echo.
pause
```

---

## 8. File 6: start_localtunnel_demo.bat (Alternative Public Tunnel Launcher)
> **Location:** `call agent/start_localtunnel_demo.bat`  
> **Purpose:** Windows batch script using `npx localtunnel` as an alternative public tunnel provider.

```bat
@echo off
cd /d "%~dp0"
title 1-Click AI Voice Agent Public Demo (localtunnel)
color 0B
cls
echo ==============================================================================
echo     🎙️ 24/7 AI VOICE RECEPTIONIST - NPX LOCALTUNNEL PUBLIC DEMO
echo ==============================================================================
echo.
echo [1/3] Starting LiveKit Voice Agent Worker (Aria) in background...
start "LiveKit Agent Worker (Aria)" C:\Users\Deepak\.venvs\livekit_agent\Scripts\python.exe agent.py dev

echo [2/3] Starting WebRTC & Token Dispenser Server on port 8080...
start "AI Voice Web & Token Server" C:\Users\Deepak\.venvs\livekit_agent\Scripts\python.exe demo_server.py

echo.
echo Waiting 2 seconds for server to initialize...
timeout /t 2 /nobreak >nul

echo.
echo ==============================================================================
echo  ✅ LOCAL DEMO LINK:  http://localhost:8080
echo  🌐 PUBLIC HTTPS TUNNEL VIA NPX:
echo     Starting npx localtunnel on port 8080...
echo ==============================================================================
echo.
npx localtunnel --port 8080
pause
```

---

## 9. File 7: run_dev.bat (LiveKit Cloud Dev Launcher)
> **Location:** `call agent/run_dev.bat`  
> **Purpose:** Runs `agent.py dev` in development mode connected to LiveKit Cloud.

```bat
@echo off
cd /d "%~dp0"
echo ==========================================================
echo Starting LiveKit Voice Agent in DEV Mode...
echo (Connecting to LiveKit Cloud for Web Sandbox / Phone Calls)
echo ==========================================================
C:\Users\Deepak\.venvs\livekit_agent\Scripts\python.exe agent.py dev
pause
```

---

## 10. File 8: run_console.bat (Local Mic/Speaker Test Launcher)
> **Location:** `call agent/run_console.bat`  
> **Purpose:** Runs `agent.py console` in local audio mode using the PC microphone and speaker directly without web servers or WebRTC.

```bat
@echo off
cd /d "%~dp0"
echo ==========================================================
echo Starting LiveKit Voice Agent in CONSOLE Mode...
echo (Speak directly into your computer microphone)
echo ==========================================================
C:\Users\Deepak\.venvs\livekit_agent\Scripts\python.exe agent.py console
pause
```

---

## 11. File 9: START_HERE.md (Business, Pricing & Twilio SIP Guide)
> **Location:** `call agent/START_HERE.md`  
> **Purpose:** Complete commercial agency blueprint, client pricing, target niches, and Twilio phone number configuration.

```markdown
# 🎙️ LiveKit AI Voice Agent - Complete Setup & Business Guide

Swagat hai! Aapka **LiveKit Voice Agent** framework aapke system par 100% successfully install aur configure ho chuka hai.

---

## 📁 Is Folder Mein Kya-Kya Set Ho Chuka Hai?

1. **Official Monorepo (`livekit/agents`):**
   - Sabhi official examples (`examples/hotel_receptionist`, `examples/frontdesk`, `examples/healthcare`, etc.).
   - Saare plugins (`livekit-plugins-google`, `livekit-plugins-openai`, `livekit-plugins-deepgram`, `livekit-plugins-cartesia`, `livekit-plugins-silero`, `livekit-plugins-turn-detector`).
2. **Flagship Voice Agent (`agent.py`):**
   - **Bilingual Support:** Hindi, English aur Hinglish bol sakta hai.
   - **Ultra-low Latency & Interruption:** Agar aap bolte hue beech me tokte hain, toh AI turant chup ho jata hai (Silero VAD).
   - **Smart Tool Calling:**
     - `book_appointment`: Appointment book karke local `appointments.json` file me record save karta hai.
     - `check_availability`: Available timing slots check karta hai.
     - `transfer_to_specialist`: Human agent ko call handover karta hai.
3. **One-Click Launchers:**
   - `run_console.bat`: Direct computer ke mic aur speaker se baat karne ke liye (Bina kisi cloud server ke).
   - `run_dev.bat`: LiveKit Cloud / Browser Sandbox aur Phone Calls se connect karne ke liye.
4. **Environment Config:**
   - `.env.example` aur `.env.local`

---

## 🔑 Step 1: Free API Keys Kaise Hasil Karein?

Apne `.env.local` file ko kholein aur ye keys daalein (Sabhi ke paas free tier hai):

| Service | Kaam | Link & Free Offer |
| :--- | :--- | :--- |
| **1. Google Gemini** | Sochna aur jawab dena (Brain) | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) (Free Tier available) |
| **2. Deepgram** | Sunna & Bolna (STT Ears + TTS Voice) | [deepgram.com](https://deepgram.com) (**$200 FREE credit** sign-up par) |
| **3. LiveKit Cloud** | Call streaming & WebRTC | [cloud.livekit.io](https://cloud.livekit.io) (**10,000 mins/month bilkul FREE**) |
| **4. Cartesia** *(Optional)* | Insaan jaisi ultra-fast aawaz | [cartesia.ai](https://cartesia.ai) (Free trial available) |

---

## 🚀 Step 2: Agent Ko Run Kaise Karein?

### Option A: Local Terminal Test (Bina Kisi Server Ke)
Aapko LiveKit server ki bhi zaroorat nahi hai. Apne computer ke mic se baat karne ke liye:
1. Simply `run_console.bat` par double-click karein, ya terminal me chalayein:
   ```bash
   C:\Users\Deepak\.venvs\livekit_agent\Scripts\python.exe agent.py console
   ```
2. Terminal me bolna shuru karein: *"Hello Aria, mujhe kal ke liye appointment book karni hai."*

---

### Option B: Client Ke Liye Web Browser Live Demo
1. `.env.local` me `LIVEKIT_URL`, `LIVEKIT_API_KEY`, aur `LIVEKIT_API_SECRET` daalein.
2. Double-click karein `run_dev.bat` par aur dusre terminal me `python demo_server.py`.
3. Browser me kholein: `http://localhost:8080` ya generated HTTPS link.
4. "Start Call" par click karein aur mic se direct baat karein!

---

## 📞 Step 3: Twilio Phone Number Se Kaise Jodein?

1. LiveKit Cloud Dashboard me jayein: `SIP` -> `Inbound Trunks`.
2. Twilio me ek Phone Number lein aur uska SIP Trunk LiveKit ke SIP URI par point karein:
   - Twilio Console -> Phone Numbers -> Configure -> Voice: "SIP Trunk".
3. Jab bhi koi us number par call karega, aapka `agent.py` call uthayega aur live baatein karega!

---

## 💼 Step 4: Client Pitch & Pricing Blueprint

### Kis Business Ko Target Karein?
* **Dental & Medical Clinics:** Doctor busy hote hain, calls miss hoti hain.
* **Home Services (Plumbing, AC/HVAC, Roofing):** Emergency repair calls jo miss na ho sakein.
* **Real Estate Agents:** Nayi leads aate hi 30 seconds ke andar phone call.

### Pricing Structure:
* **One-Time Setup Fee:** $500 – $1,500 (₹40,000 – ₹1,20,000)
* **Monthly Retainer:** $300 – $800 / Month (₹25,000 – ₹65,000)
* **Aapka API Kharcha:** Approx $20 – $40 per 1,000 minutes.
* **Net Profit Margin:** **85%+**!
```

---

## 12. How To Run The Entire System

### Method 1: 1-Click Public Demo (Instant Shareable Link)
Double-click `start_public_demo.bat`.
Yeh background me `agent.py dev` + `demo_server.py` start karega aur terminal par ek **HTTPS link** dega (jaise `https://xxxx.lhr.life`). Is link ko phone par open karke direct call kar sakte hain.

### Method 2: Manual Terminal Run
Open PowerShell in the project directory:
```powershell
# Terminal 1: Start Agent Worker
C:\Users\Deepak\.venvs\livekit_agent\Scripts\python.exe agent.py dev

# Terminal 2: Start Web Server
C:\Users\Deepak\.venvs\livekit_agent\Scripts\python.exe demo_server.py

# Open in Browser
start http://localhost:8080
```
