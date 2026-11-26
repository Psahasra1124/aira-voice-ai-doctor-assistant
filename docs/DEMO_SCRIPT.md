# 3-minute demo recording script

**0:00–0:20 — Introduction**
“Hi, this is Aira, a voice AI doctor appointment assistant for NovaCare Clinic. It can check doctor availability, book appointments and cancel existing appointments.”

**0:20–0:55 — Dashboard**
Show the overview, doctor cards, open slots, assistant chat, and upcoming appointments. Mention that doctors and slots are mock clinic data stored by the backend.

**0:55–1:45 — Booking**
Select a doctor/time slot. Enter a patient name and phone number. Confirm the number in the prompt. Show the booking confirmation and the updated appointment list.

**1:45–2:20 — Cancellation**
Cancel the same appointment. Enter the matching phone number and confirm. Show the cancelled status.

**2:20–2:50 — Voice integration**
If API keys are configured, record a short microphone request, show its transcript, and play the ElevenLabs response. Briefly mention the Pipecat pipeline entry point.

**2:50–3:00 — Close**
“The backend is FastAPI with SQLite persistence. Gemini can call the appointment tools, and ElevenLabs handles speech-to-text and text-to-speech.”
