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
    tz = pytz.timezone("Europe/Berlin")
    dt = tz.localize(dt)
    end_dt = dt + timedelta(minutes=30)

    events = service.events().list(
        calendarId=calendar_id,
        timeMin=dt.isoformat(),
        timeMax=end_dt.isoformat(),
        singleEvents=True
    ).execute()

    for event in events.get("items", []):
        event_start = event["start"].get("dateTime")
        event_end = event["end"].get("dateTime")
        if event_start and event_end:
            start_dt = datetime.fromisoformat(event_start)
            end_dt_expected = datetime.fromisoformat(event_end)
            if start_dt == dt and end_dt_expected == dt + timedelta(minutes=30):
                return False
    return True

def book_appointment(calendar_id, dt, name):
    if not is_slot_free(calendar_id, dt):
        return False
    service = get_service()
    tz = pytz.timezone("Europe/Berlin")
    dt = tz.localize(dt)
    event = {
        'summary': name,
        'start': {'dateTime': dt.isoformat(), 'timeZone': 'Europe/Berlin'},
        'end': {'dateTime': (dt + timedelta(minutes=30)).isoformat(), 'timeZone': 'Europe/Berlin'},
    }
    service.events().insert(calendarId=calendar_id, body=event).execute()
    return True

def delete_appointment(calendar_id, dt, name):
    service = get_service()
    tz = pytz.timezone("Europe/Berlin")
    dt = tz.localize(dt)
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

def get_free_slots_for_day(calendar_id, date_str, after_time=None):
    service = get_service()
    date = datetime.fromisoformat(date_str)
    weekday = date.strftime('%a').lower()
    start_time, end_time = WORK_HOURS.get(weekday, (None, None))
    if not start_time:
        return []

    tz = pytz.timezone("Europe/Berlin")
    start_dt = tz.localize(datetime.strptime(f"{date_str}T{start_time}", "%Y-%m-%dT%H:%M"))
    end_dt = tz.localize(datetime.strptime(f"{date_str}T{end_time}", "%Y-%m-%dT%H:%M"))

    if after_time:
        after_dt = tz.localize(datetime.strptime(f"{date_str}T{after_time}", "%Y-%m-%dT%H:%M"))
        if after_dt > start_dt:
            start_dt = after_dt

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
        date_str = date.strftime("%Y-%m-%d")
        after_time = None
        if i == 0:
            after_time = (now + timedelta(minutes=1)).strftime("%H:%M")
        slots_today = get_free_slots_for_day(calendar_id, date_str, after_time)
        for slot in slots_today:
            slots.append(f"{date_str} {slot}")
            if len(slots) == count:
                return slots
    return slots