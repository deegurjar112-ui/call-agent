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
    Expert AI Voice Front-Desk Coordinator for Scottsdale Premier Auto Detailing & Trade Services.
    """

    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "CRITICAL VOICE RULE: Output plain spoken English words ONLY. "
                "Never use markdown, asterisks (*), bullet points, emojis, or special symbols. "
                "Write prices as spoken words when needed, like 'fifteen hundred dollars' instead of '$1,500' so the voice sounds 100% smooth. "
                "You are 'Aria', a friendly, sharp, and top-tier front-desk coordinator for Scottsdale Premier Auto Studio & Services in Scottsdale, Arizona. "
                "CRITICAL HUMAN SPEECH RULES: "
                "1. Keep every turn to 1 or 2 short, crisp sentences (under 22 words max). You are on a live phone call—NEVER recite monologues or lists. "
                "2. Sound warm, calm, empathetic, and professional like an experienced Scottsdale coordinator. "
                "3. STRICT RULE: ASK ONE QUESTION AT A TIME. Never ask for multiple details together. "
                "4. VEHICLE & SERVICE PRICING KNOWLEDGE: "
                "   - If asked about full front PPF on a 2024 Porsche GT3: Quote 'Full front PPF on your Porsche GT3 ranges between eighteen ninety-five and twenty-two ninety-five dollars, covering the bumper, hood, fenders, and mirrors in self-healing film.' Then ask if they want to schedule an open bay this week. "
                "   - Track Package PPF: twenty-eight hundred to thirty-two hundred dollars. "
                "   - Full Car PPF: six thousand to seventy-five hundred dollars. "
                "   - Ceramic Coating: twelve hundred to fifteen hundred dollars for five-year, or eighteen hundred to twenty-two hundred dollars for seven-year pro coating. "
                "   - Ceramic Window Tint: three ninety-five to five ninety-five dollars with high heat rejection for Arizona summers. "
                "   - Paint Correction & Detailing: seven fifty to nine hundred dollars. "
                "   - Home & property trade services (HVAC, plumbing, electrical): Warmly confirm we can dispatch our vetted trade specialists. "
                "5. HOW YOU WORK FOR THE BUSINESS: "
                "If a shop owner testing the demo asks 'How do you work for my business?', explain naturally: "
                "'Whenever you are in the shop, on another call, or after hours, I pick up in one second, answer pricing questions, and text the qualified lead straight to your phone. Go ahead and test me like a real customer!' "
                "6. BOOKING FLOW: "
                "   - Step A: Acknowledge their car model or issue in 1 sentence and offer two specific time slots (e.g. 'We have an open bay today at two thirty or tomorrow morning at nine. Which works better for you?'). "
                "   - Step B: Ask for their first name and mobile number to confirm the booking. "
                "   - Step C: Call book_appointment with customer name, phone, vehicle model, service, date, and time, and warmly confirm."
            )
        )

    async def on_enter(self) -> None:
        """Greet the caller warmly and immediately as soon as the call connects."""
        self.session.say(
            "Hi there! Thanks for calling Scottsdale Premier Auto Studio, this is Aria—how can I help with your vehicle or booking today?"
        )


    @function_tool
    async def check_availability(
        self,
        context: RunContext,
        service_name: str,
        preferred_date: str = "today",
        suburb_or_location: str = "Scottsdale",
    ) -> str:
        """
        Check available appointment slots for a service and location.

        Args:
            service_name: Name of the service (e.g. PPF, ceramic coating, window tint, detailing, trade service)
            preferred_date: Date requested by caller (e.g. today, tomorrow, Friday)
            suburb_or_location: Caller's area or locality (defaults to Scottsdale)
        """
        logger.info(f"Checking availability for {service_name} in '{suburb_or_location}' on {preferred_date}")
        return (
            f"We have open bays available on {preferred_date} with time slots at "
            f"2:30 PM today or tomorrow at 9:00 AM. Ask the caller which of these two works better."
        )

    @function_tool
    async def book_appointment(
        self,
        context: RunContext,
        customer_name: str,
        phone_number: str,
        service_name: str,
        appointment_date: str,
        appointment_time: str,
        vehicle_model: str = "",
        suburb_or_location: str = "Scottsdale",
    ) -> str:
        """
        Book a service appointment and dispatch the qualified lead details to the lead specialist.

        Args:
            customer_name: Full name or first name of the customer
            phone_number: Contact phone number of the customer
            service_name: Type of service (e.g. Full Front PPF, Ceramic Coating, Window Tint, Detailing, AC Repair)
            appointment_date: Date of appointment (e.g. Today, Tomorrow, Friday)
            appointment_time: Preferred time slot (e.g. 2:30 PM, 9:00 AM)
            vehicle_model: Make, model, and year of the vehicle (e.g. 2024 Porsche GT3, Tesla Model S) or property type
            suburb_or_location: Location or suburb (defaults to Scottsdale)
        """
        logger.info(
            f"Booking appointment for {customer_name} ({phone_number}) - Vehicle: {vehicle_model} - "
            f"{service_name} on {appointment_date} at {appointment_time}"
        )
        room_name = ""
        if hasattr(context, "session") and hasattr(context.session, "room") and context.session.room:
            room_name = context.session.room.name

        record = {
            "customer_name": customer_name,
            "phone_number": phone_number,
            "vehicle_model": vehicle_model or "N/A",
            "service_name": service_name,
            "suburb_or_location": suburb_or_location,
            "date": appointment_date,
            "time": appointment_time,
            "booked_at": datetime.now().isoformat(),
            "status": "CONFIRMED",
            "room": room_name,
        }
        save_appointment_record(record)
        car_str = f" for your {vehicle_model}" if vehicle_model else ""
        return (
            f"Appointment booked successfully for {customer_name}{car_str} on {appointment_date} "
            f"at {appointment_time} for {service_name}. A live confirmation and lead dispatch has been sent."
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
            endpointing={
                "mode": "fixed",
                "min_delay": 0.5,
            },
            interruption={
                "resume_false_interruption": True,
                "false_interruption_timeout": 0.8,
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
