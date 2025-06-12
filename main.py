from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from calendar_utils import (
    is_slot_free, book_appointment, delete_appointment,
    get_free_slots_for_day, get_next_free_slots
)
from config import CALENDARS
from datetime import datetime

app = FastAPI()

class BookingRequest(BaseModel):
    employee: str
    date: str  # YYYY-MM-DD
    time: str  # HH:MM
    name: str

class AvailabilityRequest(BaseModel):
    employee: str
    date: str
    time: str

class DeleteRequest(BaseModel):
    employee: str
    date: str
    time: str
    name: str

class FreeSlotsRequest(BaseModel):
    employee: str
    date: str

class NextSlotsRequest(BaseModel):
    employee: str

@app.post("/check-availability")
def check_availability(req: AvailabilityRequest):
    calendar_id = CALENDARS.get(req.employee.lower())
    if not calendar_id:
        raise HTTPException(status_code=400, detail="Invalid employee")
    dt = datetime.fromisoformat(f"{req.date}T{req.time}")
    available = is_slot_free(calendar_id, dt)
    return {"available": available}

@app.post("/book")
def book(req: BookingRequest):
    calendar_id = CALENDARS.get(req.employee.lower())
    if not calendar_id:
        raise HTTPException(status_code=400, detail="Invalid employee")
    dt = datetime.fromisoformat(f"{req.date}T{req.time}")
    success = book_appointment(calendar_id, dt, req.name)
    if not success:
        raise HTTPException(status_code=409, detail="Time slot already booked")
    return {"status": "booked"}

@app.post("/delete")
def delete(req: DeleteRequest):
    calendar_id = CALENDARS.get(req.employee.lower())
    if not calendar_id:
        raise HTTPException(status_code=400, detail="Invalid employee")
    dt = datetime.fromisoformat(f"{req.date}T{req.time}")
    success = delete_appointment(calendar_id, dt, req.name)
    if not success:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return {"status": "deleted"}

@app.post("/free-slots")
def free_slots(req: FreeSlotsRequest):
    calendar_id = CALENDARS.get(req.employee.lower())
    if not calendar_id:
        raise HTTPException(status_code=400, detail="Invalid employee")
    free = get_free_slots_for_day(calendar_id, req.date)
    return {"free_slots": free}

@app.post("/next-free")
def next_free(req: NextSlotsRequest):
    calendar_id = CALENDARS.get(req.employee.lower())
    if not calendar_id:
        raise HTTPException(status_code=400, detail="Invalid employee")
    slots = get_next_free_slots(calendar_id)
    return {"next_slots": slots}