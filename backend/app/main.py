import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from .data import DOCTORS, get_slots
from .store import init_db, all_appointments
from .agent import handle_message, book_appointment, cancel_appointment, check_doctor_availability, elevenlabs_stt, elevenlabs_tts

app = FastAPI(title="Aira Voice Appointment Assistant", version="1.0.0", description="Demo clinic appointment assistant")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def startup():
    init_db()

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1200)
    history: list[dict[str, str]] = []
    context: dict = {}

class BookingRequest(BaseModel):
    doctor_id: str
    slot_id: str
    patient_name: str = "Guest"
    phone_number: str
    confirmed_phone: bool = False

class CancelRequest(BaseModel):
    phone_number: str
    appointment_id: str | None = None
    confirmed_phone: bool = False

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "aira", "gemini_configured": bool(os.getenv("GEMINI_API_KEY")), "elevenlabs_configured": bool(os.getenv("ELEVENLABS_API_KEY")), "mode": "live" if os.getenv("GEMINI_API_KEY") else "demo"}

@app.get("/api/doctors")
def doctors():
    return DOCTORS

@app.get("/api/slots")
def slots(doctor_id: str | None = None, requested_date: str | None = None, specialty: str | None = None):
    result = check_doctor_availability(doctor_name=None, specialty=specialty, requested_date=requested_date)["slots"] if specialty else get_slots(doctor_id, requested_date)
    booked = {(a["doctor_id"], a["date"], a["time"]) for a in all_appointments() if a["status"] == "booked"}
    return [s for s in result if (s["doctor_id"], s["date"], s["time"]) not in booked]

@app.get("/api/appointments")
def appointments():
    return all_appointments()

@app.post("/api/appointments")
def create_booking(body: BookingRequest):
    try:
        return book_appointment(body.doctor_id, body.slot_id, body.patient_name, body.phone_number, body.confirmed_phone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.post("/api/appointments/cancel")
def cancel_booking(body: CancelRequest):
    try:
        result = cancel_appointment(body.phone_number, body.appointment_id, body.confirmed_phone)
        if not result:
            raise ValueError("Appointment not found.")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@app.post("/api/chat")
async def chat(body: ChatRequest):
    try:
        reply, context = await handle_message(body.message, body.history, body.context)
        return {"reply": reply, "context": context, "appointments": all_appointments()}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Assistant error: {exc}")

@app.post("/api/voice/transcribe")
async def transcribe(file: UploadFile = File(...)):
    try:
        text = await elevenlabs_stt(await file.read(), file.filename or "recording.webm")
        return {"text": text}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

@app.post("/api/voice/speak")
async def speak(body: ChatRequest):
    try:
        audio = await elevenlabs_tts(body.message)
        if audio is None:
            raise HTTPException(status_code=400, detail="ElevenLabs is not configured. Add ELEVENLABS_API_KEY to backend/.env.")
        return Response(content=audio, media_type="audio/mpeg")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ElevenLabs TTS error: {exc}")
