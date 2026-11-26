import json
import os
import re
import uuid
from datetime import date
from typing import Any
import httpx
from .data import DOCTORS, get_slots
from .store import all_appointments, cancel_appointment as db_cancel, create_appointment, find_by_phone


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) < 10 or len(digits) > 13:
        raise ValueError("Please provide a valid phone number with 10 to 13 digits.")
    return digits


def check_doctor_availability(doctor_name: str | None = None, specialty: str | None = None, requested_date: str | None = None) -> dict[str, Any]:
    doctor = None
    if doctor_name:
        doctor = next((d for d in DOCTORS if doctor_name.lower() in d["name"].lower()), None)
    if specialty and not doctor:
        doctor = next((d for d in DOCTORS if specialty.lower() in d["specialty"].lower()), None)
    slots = get_slots(doctor["id"] if doctor else None, requested_date)
    if not doctor and specialty:
        slots = [s for s in slots if specialty.lower() in s["specialty"].lower()]
    return {"slots": slots[:18], "count": len(slots[:18]), "message": f"Found {min(len(slots),18)} available slots." if slots else "No slots found for that selection."}


def book_appointment(doctor_id: str, slot_id: str, patient_name: str, phone_number: str, confirmed_phone: bool) -> dict[str, Any]:
    if not confirmed_phone:
        raise ValueError("The phone number must be read back and explicitly confirmed before booking.")
    phone = normalize_phone(phone_number)
    doctor = next((d for d in DOCTORS if d["id"] == doctor_id), None)
    slot = next((s for s in get_slots(doctor_id) if s["id"] == slot_id), None)
    if not doctor or not slot:
        raise ValueError("That doctor or slot is not available. Please check availability again.")
    if any(a["doctor_id"] == doctor_id and a["date"] == slot["date"] and a["time"] == slot["time"] and a["status"] == "booked" for a in all_appointments()):
        raise ValueError("Sorry, that slot has just been booked. Please choose another slot.")
    item = {"id": f"APT-{uuid.uuid4().hex[:7].upper()}", "doctor_id": doctor_id, "doctor_name": doctor["name"], "specialty": doctor["specialty"], "patient_name": patient_name.strip() or "Guest", "phone": phone, "date": slot["date"], "time": slot["time"]}
    return create_appointment(item)


def cancel_appointment(phone_number: str, appointment_id: str | None = None, confirmed_phone: bool = False) -> dict[str, Any]:
    if not confirmed_phone:
        raise ValueError("The phone number must be read back and explicitly confirmed before cancellation.")
    phone = normalize_phone(phone_number)
    matches = find_by_phone(phone)
    if appointment_id:
        matches = [a for a in matches if a["id"] == appointment_id]
    if not matches:
        raise ValueError("I couldn't find an active appointment for that confirmed phone number.")
    return db_cancel(matches[0]["id"])


SYSTEM_PROMPT = """You are Aira, a warm, concise voice receptionist for NovaCare Clinic. You are not a doctor and never provide medical diagnosis or emergency advice. Your job is only appointment availability, booking and cancellation. Use only the provided clinic data and tool results; never invent a slot. Ask one question at a time. Before booking or cancelling, collect the caller's name (for booking) and phone number, read the full phone number back digit-by-digit and ask for explicit confirmation. Do not call book_appointment or cancel_appointment until confirmed_phone is true. For booking, check availability first and ask the caller to select a specific slot. If user says today/tomorrow, ask for or resolve an exact date when ambiguous. Be clear that this is a demo clinic."""

async def _gemini_reply(message: str, history: list[dict[str, str]], context: dict[str, Any]) -> str:
    """Chat completion via OpenRouter (OpenAI-compatible), with local appointment tools."""
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        return demo_reply(message, context)

    model = os.getenv("OPENROUTER_MODEL", "openrouter/free")
    messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n\nClinic doctors: " + json.dumps(DOCTORS, ensure_ascii=False) + "\nCaller state: " + json.dumps(context, ensure_ascii=False)}]
    for item in history[-8:]:
        role = "assistant" if item.get("role") == "assistant" else "user"
        messages.append({"role": role, "content": item.get("content", "")})
    messages.append({"role": "user", "content": message})

    tools = [
        {"type": "function", "function": {"name": "check_doctor_availability", "description": "Check real available appointment slots for a doctor, specialty and optional ISO date.", "parameters": {"type": "object", "properties": {"doctor_name": {"type": "string"}, "specialty": {"type": "string"}, "requested_date": {"type": "string", "description": "YYYY-MM-DD"}}}}},
        {"type": "function", "function": {"name": "book_appointment", "description": "Book a selected available slot. Only call after reading the caller's phone number back and receiving explicit yes confirmation.", "parameters": {"type": "object", "required": ["doctor_id", "slot_id", "patient_name", "phone_number", "confirmed_phone"], "properties": {"doctor_id": {"type": "string"}, "slot_id": {"type": "string"}, "patient_name": {"type": "string"}, "phone_number": {"type": "string"}, "confirmed_phone": {"type": "boolean"}}}}},
        {"type": "function", "function": {"name": "cancel_appointment", "description": "Cancel an active appointment by caller phone number. Only call after reading the number back and receiving explicit yes confirmation.", "parameters": {"type": "object", "required": ["phone_number", "confirmed_phone"], "properties": {"phone_number": {"type": "string"}, "appointment_id": {"type": "string"}, "confirmed_phone": {"type": "boolean"}}}}}
    ]

    async with httpx.AsyncClient(timeout=60) as client:
        for _ in range(4):
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "Aira Voice Appointment Assistant"},
                json={"model": model, "messages": messages, "tools": tools, "tool_choice": "auto", "temperature": 0.25, "max_tokens": 450}
            )
            response.raise_for_status()
            payload = response.json()
            choice = payload["choices"][0]["message"]
            calls = choice.get("tool_calls") or []
            if not calls:
                return (choice.get("content") or "I'm sorry, I couldn't understand that. Could you repeat?").strip()
            messages.append({"role": "assistant", "content": choice.get("content"), "tool_calls": calls})
            for call in calls:
                name = call["function"]["name"]
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                    if name == "check_doctor_availability":
                        result = check_doctor_availability(args.get("doctor_name"), args.get("specialty"), args.get("requested_date"))
                    elif name == "book_appointment":
                        result = book_appointment(args["doctor_id"], args["slot_id"], args.get("patient_name", "Guest"), args["phone_number"], bool(args.get("confirmed_phone", False)))
                    elif name == "cancel_appointment":
                        result = cancel_appointment(args["phone_number"], args.get("appointment_id"), bool(args.get("confirmed_phone", False)))
                    else:
                        result = {"error": "Unknown tool"}
                except Exception as exc:
                    result = {"error": str(exc)}
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, ensure_ascii=False)})
        return "I couldn't complete that request just now. Please try again."


def demo_reply(message: str, context: dict[str, Any]) -> str:
    text = message.lower()
    if any(w in text for w in ["cancel", "delete", "remove"]):
        return "I can help cancel an appointment. May I have the phone number used when booking? I will read it back for confirmation before making any changes."
    if any(w in text for w in ["book", "appointment", "schedule"]):
        if not context.get("phone_confirmed"):
            if not context.get("phone_number"):
                return "Certainly. Which doctor or speciality would you prefer? I can check the available appointments first."
            return f"I have {context['phone_number']} as your phone number. Is that correct? Please say yes to confirm."
        if not context.get("selected_slot"):
            return "I found available appointments. Please choose a doctor and a time from the slots shown on the dashboard."
        return "Great. I have your details. Please confirm the phone number once more before I book the selected slot."
    if any(w in text for w in ["available", "availability", "slot", "doctor"]):
        return "We have Cardiology, Dermatology, General Medicine and Orthopedics. Which speciality would you like, and do you have a preferred date?"
    if "yes" in text or "correct" in text:
        context["phone_confirmed"] = True
        return "Thank you, your number is confirmed. Would you like to check availability, book an appointment, or cancel an existing one?"
    return "Hello, I'm Aira, the NovaCare appointment assistant. I can check doctor availability, book an appointment, or cancel one. What would you like to do?"


async def handle_message(message: str, history: list[dict[str, str]], context: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    reply = await _gemini_reply(message, history, context)
    return reply, context


async def elevenlabs_tts(text: str) -> bytes | None:
    key = os.getenv("ELEVENLABS_API_KEY")
    if not key:
        return None
    voice = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    model = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}", headers={"xi-api-key": key, "Accept": "audio/mpeg", "Content-Type": "application/json"}, json={"text": text, "model_id": model, "voice_settings": {"stability": 0.48, "similarity_boost": 0.78}})
        response.raise_for_status()
        return response.content


async def elevenlabs_stt(audio: bytes, filename: str = "recording.webm") -> str:
    key = os.getenv("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("Add ELEVENLABS_API_KEY to backend/.env to enable server-side speech recognition.")
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post("https://api.elevenlabs.io/v1/speech-to-text", headers={"xi-api-key": key}, data={"model_id": "scribe_v1"}, files={"file": (filename, audio, "audio/webm")})
        response.raise_for_status()
        return response.json().get("text", "").strip()
