from datetime import date, timedelta
from typing import Any

DOCTORS = [
    {"id": "doc-001", "name": "Dr. Ananya Rao", "specialty": "Cardiology", "qualification": "MD, DM Cardiology", "experience": "12 years", "color": "violet", "about": "Preventive cardiology and heart-health consultations."},
    {"id": "doc-002", "name": "Dr. Arjun Mehta", "specialty": "Dermatology", "qualification": "MD Dermatology", "experience": "9 years", "color": "blue", "about": "Clinical and cosmetic dermatology."},
    {"id": "doc-003", "name": "Dr. Nisha Reddy", "specialty": "General Medicine", "qualification": "MD Internal Medicine", "experience": "15 years", "color": "mint", "about": "Primary care and general health consultations."},
    {"id": "doc-004", "name": "Dr. Kabir Shah", "specialty": "Orthopedics", "qualification": "MS Orthopedics", "experience": "11 years", "color": "amber", "about": "Sports injuries, joint and bone health."},
]

# Predictable demo slots. Dates are relative so the demo remains usable.
def get_slots(doctor_id: str | None = None, requested_date: str | None = None) -> list[dict[str, Any]]:
    base = date.today()
    days = [base + timedelta(days=i) for i in range(1, 5)]
    times = ["09:30 AM", "10:30 AM", "11:45 AM", "02:00 PM", "03:15 PM", "04:30 PM"]
    slots = []
    for d_idx, day in enumerate(days):
        if requested_date and day.isoformat() != requested_date:
            continue
        for doc_idx, doctor in enumerate(DOCTORS):
            if doctor_id and doctor_id != doctor["id"]:
                continue
            for t_idx, time in enumerate(times):
                # Stable gaps create a realistic-looking availability grid.
                if (d_idx + doc_idx + t_idx) % 4 == 0:
                    continue
                slots.append({"id": f"{doctor['id']}-{day.isoformat()}-{t_idx}", "doctor_id": doctor["id"], "doctor_name": doctor["name"], "specialty": doctor["specialty"], "date": day.isoformat(), "time": time, "available": True})
    return slots
