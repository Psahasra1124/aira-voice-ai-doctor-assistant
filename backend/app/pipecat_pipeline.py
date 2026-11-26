"""Realtime Pipecat WebRTC voice bot for Aira.

Run from backend/: python -m app.pipecat_pipeline
The Pipecat development runner exposes /start on port 7860 and manages WebRTC.
"""
import os
from dotenv import load_dotenv
load_dotenv()

from app.agent import check_doctor_availability as _check, book_appointment as _book, cancel_appointment as _cancel
from app.data import DOCTORS
from app.store import init_db

SYSTEM = """You are Aira, a warm, concise voice receptionist for NovaCare Clinic. You only manage doctor appointment availability, booking and cancellation; never diagnose or provide medical advice. You must use tools for availability, booking and cancellation and never invent slots. Ask one question at a time. For booking, collect patient name and the phone number the caller speaks. Read the full number back digit by digit and ask whether it is correct. Only after explicit confirmation may you call book_appointment with confirmed_phone=true. For cancellation, collect the number, read it back, obtain explicit confirmation, then call cancel_appointment with confirmed_phone=true. If a tool returns an error, explain it simply and offer the next step. Doctors and slots are mock data for this demo clinic."""

# Direct functions are converted into Pipecat tool schemas from their names,
# type annotations and docstrings, then advertised through LLMContext.
def check_doctor_availability(doctor_name: str = "", specialty: str = "", requested_date: str = "") -> dict:
    """Find available slots. Use doctor_name or specialty and optionally requested_date in YYYY-MM-DD format."""
    result = _check(doctor_name or None, specialty or None, requested_date or None)
    return result


def book_appointment(doctor_id: str, slot_id: str, patient_name: str, phone_number: str, confirmed_phone: bool) -> dict:
    """Book a selected available slot. Only call after caller explicitly confirms the phone number read back aloud."""
    return _book(doctor_id, slot_id, patient_name, phone_number, confirmed_phone)


def cancel_appointment(phone_number: str, confirmed_phone: bool, appointment_id: str = "") -> dict:
    """Cancel the caller's active appointment by their spoken phone number. Require explicit phone confirmation first."""
    result = _cancel(phone_number, appointment_id or None, confirmed_phone)
    return result or {"error": "Appointment not found"}


async def bot(runner_args):
    if not os.getenv("GEMINI_API_KEY") or not os.getenv("ELEVENLABS_API_KEY"):
        raise RuntimeError("Set GEMINI_API_KEY and ELEVENLABS_API_KEY in backend/.env before starting Pipecat.")
    from pipecat.frames.frames import LLMRunFrame
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineWorker
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair, LLMUserAggregatorParams
    from pipecat.runner.utils import create_transport
    from pipecat.services.elevenlabs.stt import ElevenLabsRealtimeSTTService
    from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
    from pipecat.services.google.llm import GoogleLLMService
    from pipecat.transports.base_transport import TransportParams
    from pipecat.workers.runner import WorkerRunner

    init_db()
    transport_params = {"webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True)}
    transport = await create_transport(runner_args, transport_params)
    stt = ElevenLabsRealtimeSTTService(api_key=os.environ["ELEVENLABS_API_KEY"])
    llm = GoogleLLMService(
        api_key=os.environ["GEMINI_API_KEY"],
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        settings=GoogleLLMService.Settings(system_instruction=SYSTEM),
    )
    tts = ElevenLabsTTSService(
        api_key=os.environ["ELEVENLABS_API_KEY"],
        settings=ElevenLabsTTSService.Settings(voice=os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")),
    )
    context = LLMContext(tools=[check_doctor_availability, book_appointment, cancel_appointment])
    context.add_message({"role": "system", "content": SYSTEM})
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(),
    )
    pipeline = Pipeline([
        transport.input(),
        stt,
        user_aggregator,
        llm,
        tts,
        transport.output(),
        assistant_aggregator,
    ])
    worker = PipelineWorker(pipeline, idle_timeout_secs=runner_args.pipeline_idle_timeout_secs)
    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        context.add_message({"role": "developer", "content": "Greet the caller and ask how you can help with an appointment."})
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await runner.cancel()

    await runner.run()


if __name__ == "__main__":
    from pipecat.runner.run import main
    main()
