import json
import os
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("DATABASE_PATH", Path(__file__).resolve().parents[1] / "appointments.db"))


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS appointments (
            id TEXT PRIMARY KEY, doctor_id TEXT NOT NULL, doctor_name TEXT NOT NULL,
            specialty TEXT NOT NULL, patient_name TEXT NOT NULL, phone TEXT NOT NULL,
            date TEXT NOT NULL, time TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'booked',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")


def all_appointments() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM appointments ORDER BY date, time").fetchall()
        return [dict(row) for row in rows]


def find_by_phone(phone: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM appointments WHERE phone=? AND status='booked' ORDER BY date, time", (phone,)).fetchall()
        return [dict(row) for row in rows]


def create_appointment(item: dict[str, Any]):
    with connect() as conn:
        conn.execute("""INSERT INTO appointments
            (id, doctor_id, doctor_name, specialty, patient_name, phone, date, time, status)
            VALUES (:id,:doctor_id,:doctor_name,:specialty,:patient_name,:phone,:date,:time,'booked')""", item)
        row = conn.execute("SELECT * FROM appointments WHERE id=?", (item["id"],)).fetchone()
        return dict(row)


def cancel_appointment(appointment_id: str):
    with connect() as conn:
        conn.execute("UPDATE appointments SET status='cancelled' WHERE id=? AND status='booked'", (appointment_id,))
        row = conn.execute("SELECT * FROM appointments WHERE id=?", (appointment_id,)).fetchone()
        return dict(row) if row else None
