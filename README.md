# Aira — Voice AI Doctor Appointment Assistant

A polished clinic dashboard and appointment assistant built for the NexovAI SDE Intern Round 1 assignment.

## What is included

- **React + Vite dashboard** with doctors, available slots, appointments, a live conversation panel and a phone-style call screen.
- **FastAPI backend** with doctor/slot APIs and persistent SQLite appointment storage.
- **Appointment tools**: `check_doctor_availability`, `book_appointment`, and `cancel_appointment`.
- **Gemini function calling** in the chat service when `GEMINI_API_KEY` is configured. The model receives tool declarations and the backend executes tool calls against the same appointment functions.
- **ElevenLabs speech-to-text and text-to-speech** endpoints. The dashboard can record microphone audio, send it to ElevenLabs Scribe, and play ElevenLabs-generated speech.
- **Realtime Pipecat WebRTC pipeline** at `backend/app/pipecat_pipeline.py`, using Pipecat Small WebRTC transport, ElevenLabs realtime STT/TTS and Gemini function calling. The React call screen connects through the Pipecat JavaScript client.
- **Demo mode**: without API keys, the dashboard and manual appointment flows work with seeded mock doctors/slots and a deterministic assistant response.

> This is a demonstration clinic application. It does not provide medical advice or connect to a real clinic scheduling system.

## Requirements

- Python 3.10+
- Node.js 18+
- Gemini API key for live LLM responses (optional; demo mode works without it)
- ElevenLabs API key for STT/TTS (optional; microphone transcription and generated speech require it)

## Run locally

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add GEMINI_API_KEY and ELEVENLABS_API_KEY to .env for live AI/voice
uvicorn app.main:app --reload --port 8000
```

API health: http://localhost:8000/api/health

### 2. Frontend

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Environment variables

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Enables Gemini responses and function calling |
| `GEMINI_MODEL` | Gemini model name; default `gemini-2.0-flash` |
| `ELEVENLABS_API_KEY` | Enables ElevenLabs STT and TTS |
| `ELEVENLABS_VOICE_ID` | ElevenLabs voice ID |
| `ELEVENLABS_MODEL_ID` | TTS model; default `eleven_multilingual_v2` |
| `DATABASE_PATH` | Optional SQLite database path |

Never commit `.env` or real API keys. `.env.example` contains placeholders only.

## Appointment workflow

1. The assistant asks which specialty/doctor and calls `check_doctor_availability` to retrieve real slots from the demo schedule.
2. The caller selects a slot and provides their name and phone number.
3. Before booking, the assistant must read the phone number back and receive explicit confirmation. `book_appointment` rejects a request unless `confirmed_phone=true`.
4. Cancellation searches by the caller-spoken phone number. The number must be confirmed before `cancel_appointment` can cancel an active appointment.
5. The dashboard refreshes appointment rows after successful booking or cancellation.

## Voice and Pipecat notes

The dashboard's browser microphone path records a short audio clip, posts it to `/api/voice/transcribe` (ElevenLabs Scribe), sends the transcript to `/api/chat`, and can play the reply through `/api/voice/speak` (ElevenLabs TTS). This request/response path is useful for a reproducible local demo.

The Pipecat service is the real-time voice path. Start it with:

```bash
cd backend
python -m app.pipecat_pipeline
```

It requires the Pipecat voice extras and both provider keys. The Pipecat development runner exposes `/start` on port `7860` and manages WebRTC signaling. The dashboard uses `@pipecat-ai/client-js` with `SmallWebRTCTransport` to connect to it. The HTTP audio-turn adapter remains available as a fallback/demo path.

## API endpoints

- `GET /api/health`
- `GET /api/doctors`
- `GET /api/slots?doctor_id=doc-001`
- `GET /api/appointments`
- `POST /api/appointments`
- `POST /api/appointments/cancel`
- `POST /api/chat`
- `POST /api/voice/transcribe`
- `POST /api/voice/speak`

## Demo checklist

- Start both servers and open the dashboard.
- Select a slot, enter a patient name and phone number, and confirm the number in the browser prompt.
- Show the new appointment in the upcoming list and appointments page.
- Cancel it using the matching phone number and show the status update.
- If API keys are configured, record a microphone turn and demonstrate ElevenLabs transcription and speech output.

## Pipeline description (submission-ready draft)

The browser connects to the Pipecat server over WebRTC. Pipecat streams caller audio to ElevenLabs realtime speech-to-text, passes the transcript to Gemini, and streams the response through ElevenLabs text-to-speech back to the browser. Gemini can call the doctor-availability, booking and cancellation tools; those functions read and update appointment records in SQLite. The dashboard also exposes HTTP audio endpoints as a fallback/demo path.

For a non-local Pipecat host, set `VITE_PIPECAT_URL` in the frontend environment (include `/start`). The default is `http://localhost:7860/start`.
