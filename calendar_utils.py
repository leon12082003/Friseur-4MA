from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from config import WORK_HOURS
import pytz
import os

SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'service_account.json'

def get_service():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('calendar', 'v3', credentials=creds)

def is_slot_free(calendar_id, dt):
    service = get_service()
    end_dt = dt + timedelta(minutes=30)
    tz = pytz.timezone("Europe/Berlin")
    events = service.events().list(
        calendarId=calendar_id,
        timeMin=dt.astimezone(tz).isoformat(),
        timeMax=end_dt.astimezone(tz).isoformat(),
        singleEvents=True
    ).execute()
    return len(events.get("items", [])) == 0

def book_appointment(calendar_id, dt, name):
    if not is_slot_free(calendar_id, dt):
        return False
    service = get_service()
    event = {
        'summary': name,
        'start': {'dateTime': dt.isoformat(), 'timeZone': 'Europe/Berlin'},
        'end': {'dateTime': (dt + timedelta(minutes=30)).isoformat(), 'timeZone': 'Europe/Berlin'},
    }
    service.events().insert(calendarId=calendar_id, body=event).execute()
    return True

def delete_appointment(calendar_id, dt, name):
    service = get_service()
    end_dt = dt + timedelta(minutes=30)
    events = service.events().list(
        calendarId=calendar_id,
        timeMin=dt.isoformat(),
        timeMax=end_dt.isoformat(),
        singleEvents=True
    ).execute()
    for event in events.get("items", []):
        if event.get("summary", "").lower() == name.lower():
            service.events().delete(calendarId=calendar_id, eventId=event["id"]).execute()
            return True
    return False

def get_free_slots_for_day(calendar_id, date_str):
    service = get_service()
    date = datetime.fromisoformat(date_str)
    weekday = date.strftime('%a').lower()
    start_time, end_time = WORK_HOURS.get(weekday, (None, None))
    if not start_time:
        return []
    tz = pytz.timezone("Europe/Berlin")
    start_dt = tz.localize(datetime.strptime(f"{date_str}T{start_time}", "%Y-%m-%dT%H:%M"))
    end_dt = tz.localize(datetime.strptime(f"{date_str}T{end_time}", "%Y-%m-%dT%H:%M"))
    free_slots = []
    while start_dt < end_dt:
        if is_slot_free(calendar_id, start_dt):
            free_slots.append(start_dt.strftime("%H:%M"))
        start_dt += timedelta(minutes=30)
    return free_slots

def get_next_free_slots(calendar_id, count=3):
    now = datetime.now(pytz.timezone("Europe/Berlin"))
    slots = []
    for i in range(14):  # 2 Wochen
        date = now + timedelta(days=i)
        slots_today = get_free_slots_for_day(calendar_id, date.strftime("%Y-%m-%d"))
        for slot in slots_today:
            slots.append(f"{date.strftime('%Y-%m-%d')} {slot}")
            if len(slots) == count:
                return slots
    return slots