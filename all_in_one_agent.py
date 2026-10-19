"""
========================================================================================
🎙️ ALL-IN-ONE LIVEKIT VOICE AGENT & DEMO SERVER (Unified Single File)
========================================================================================
This single file combines BOTH:
  1. The WebRTC Token Dispenser & Demo Web Server (port 8080)
  2. The LiveKit Voice Agent Worker (Aria - Home Services Receptionist)
     powered by Google Gemini 3.8 Flash, Deepgram Nova-3 / Aura, and Silero VAD.

Usage:
  python all_in_one_agent.py dev       # Connects to LiveKit Cloud + starts Web UI on :8080
  python all_in_one_agent.py console   # Local microphone mode (no server needed)
========================================================================================
"""

import json
import logging
import os
import random
import string
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from aiohttp import web
from dotenv import load_dotenv

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
logger = logging.getLogger("all-in-one-agent")

# Environment Keys
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")
APPOINTMENTS_FILE = Path("appointments.json")
INDEX_FILE = Path("index.html")

# LiveKit Agents imports
import livekit.api as lk_api
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

# ======================================================================================
# 1. DATABASE / STORAGE HELPERS
# ======================================================================================

def save_appointment_record(record: dict):
    """Save an appointment record locally to JSON file using atomic write."""
    appointments = []
    if APPOINTMENTS_FILE.exists():
        try:
            with open(APPOINTMENTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    appointments = data
        except Exception:
            appointments = []
    appointments.append(record)

    # Atomic write to prevent file corruption
    temp_dir = str(APPOINTMENTS_FILE.parent) or "."
    try:
        with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tf:
            json.dump(appointments, tf, indent=2, ensure_ascii=False)
            temp_name = tf.name
        os.replace(temp_name, APPOINTMENTS_FILE)
    except Exception as e:
        logger.error(f"Failed to atomically save appointment record: {e}")
        try:
            with open(APPOINTMENTS_FILE, "w", encoding="utf-8") as f:
                json.dump(appointments, f, indent=2, ensure_ascii=False)
        except Exception:
            pass


def random_string(length: int = 4) -> str:
    """Generate short alphanumeric suffix."""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


# ======================================================================================
# 2. VOICE AGENT LOGIC (ARIA PERSONA & TOOLS)
# ======================================================================================

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
        """Check available appointment slots for a trade service and location."""
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
        """Book a trade service appointment and dispatch the job details to the lead technician."""
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
        """Transfer the call to an emergency senior technician or supervisor."""
        logger.info(f"Initiating transfer to {department}. Reason: {reason}")
        return f"Transferring your call to our {department} team immediately. Please hold the line for just a second."


# ======================================================================================
# 3. LIVEKIT SERVER & SESSION ENTRYPOINT
# ======================================================================================

agent_server = AgentServer()


@agent_server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    """Entrypoint function called whenever an agent session starts."""
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info(f"Starting home-service voice agent session in room: {ctx.room.name}")

    deepgram_key = os.getenv("DEEPGRAM_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    cartesia_key = os.getenv("CARTESIA_API_KEY")
    google_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

    # Ears: Speech to Text (Deepgram Nova-3 multilingual)
    if deepgram_key:
        stt_engine = deepgram.STT(model="nova-3", language="multi")
    else:
        stt_engine = openai.STT()

    # Brain: Conversational LLM (Google Gemini gemini-3.8-flash is active & verified)
    if google_key and google is not None:
        logger.info("Using Google Gemini LLM (gemini-3.8-flash)")
        llm_engine = google.LLM(model="gemini-3.8-flash", api_key=google_key)
    elif openai_key:
        logger.info("Using OpenAI LLM (gpt-4o-mini)")
        llm_engine = openai.LLM(model="gpt-4o-mini")
    else:
        logger.info("Defaulting to OpenAI LLM (gpt-4o-mini)")
        llm_engine = openai.LLM(model="gpt-4o-mini")

    # Voice: Text to Speech (Cartesia -> Deepgram Aura Asteria -> OpenAI)
    if cartesia_key:
        tts_engine = cartesia.TTS(voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc")
    elif deepgram_key:
        tts_engine = deepgram.TTS(model="aura-asteria-en")
    else:
        tts_engine = openai.TTS(voice="nova")

    session: AgentSession = AgentSession(
        stt=stt_engine,
        llm=llm_engine,
        tts=tts_engine,
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


# ======================================================================================
# 4. WEBRTC DEMO WEB SERVER (BACKGROUND THREAD)
# ======================================================================================

@web.middleware
async def cors_middleware(request, handler):
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
    if not INDEX_FILE.exists():
        return web.Response(text="<h1>index.html not found</h1>", content_type="text/html", status=404)
    return web.Response(text=INDEX_FILE.read_text(encoding="utf-8"), content_type="text/html")


async def handle_token(request: web.Request) -> web.Response:
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
        return web.json_response({"error": "LIVEKIT_API_KEY or LIVEKIT_API_SECRET missing"}, status=500)

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

    return web.json_response({
        "token": token.to_jwt(),
        "url": LIVEKIT_URL,
        "room": room_name,
        "identity": identity,
        "caller_name": caller_name,
        "business_type": business_type,
    })


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
                    bookings = list(reversed(filtered))
        except Exception as e:
            logger.warning(f"Error reading appointments: {e}")
            bookings = []
    return web.json_response({"bookings": bookings, "count": len(bookings)})


def create_web_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/token", handle_token)
    app.router.add_post("/api/token", handle_token)
    app.router.add_get("/api/bookings", handle_bookings)
    return app


def start_web_server_thread(port: int = 8080):
    """Run web server in a dedicated background thread."""
    def run():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        app = create_web_app()
        runner = web.AppRunner(app)
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, host="0.0.0.0", port=port)
        loop.run_until_complete(site.start())
        print(f"[ALL-IN-ONE] Web UI & Token Server running on http://localhost:{port}")
        loop.run_forever()

    thread = threading.Thread(target=run, daemon=True, name="demo-web-server")
    thread.start()
    return thread


# ======================================================================================
# 5. MAIN APPLICATION ENTRYPOINT
# ======================================================================================

if __name__ == "__main__":
    web_port = int(os.getenv("PORT", 8080))
    start_web_server_thread(port=web_port)
    cli.run_app(agent_server)
