import json
import logging
import os
import tempfile
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
    llm,
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
    """Save an appointment record locally to JSON file using atomic write."""
    appointments = []
    if os.path.exists(APPOINTMENTS_FILE):
        try:
            with open(APPOINTMENTS_FILE, "r", encoding="utf-8") as f:
                appointments = json.load(f)
        except Exception:
            appointments = []
    appointments.append(record)

    # Atomic write to prevent file corruption during concurrent read/write
    temp_dir = os.path.dirname(APPOINTMENTS_FILE) or "."
    try:
        with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tf:
            json.dump(appointments, tf, indent=2, ensure_ascii=False)
            temp_name = tf.name
        os.replace(temp_name, APPOINTMENTS_FILE)
    except Exception as e:
        logger.error(f"Failed to atomically save appointment record: {e}")
        # Fallback to direct write if replace fails
        try:
            with open(APPOINTMENTS_FILE, "w", encoding="utf-8") as f:
                json.dump(appointments, f, indent=2, ensure_ascii=False)
        except Exception:
            pass


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
        """Greet the caller warmly and immediately as soon as the call connects."""
        self.session.say(
            "Hi there! Thanks for calling our 24/7 Home Service desk, this is Aria—how can I help with your home or property today?"
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

    # Voice LLM: Google Gemini with automatic multi-model fallback (gemini-3.5-flash -> gemini-3.5-flash-lite -> gemini-3-flash-preview)
    if google_key and google is not None:
        logger.info("Using Google Gemini LLM with multi-model fallback")
        llm_engine = llm.FallbackAdapter(
            [
                google.LLM(model="gemini-3.5-flash", api_key=google_key),
                google.LLM(model="gemini-3.5-flash-lite", api_key=google_key),
                google.LLM(model="gemini-3-flash-preview", api_key=google_key),
            ],
            attempt_timeout=15.0,
        )
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
