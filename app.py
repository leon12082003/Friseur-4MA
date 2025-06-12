
from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
import datetime

app = Flask(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]
SERVICE_ACCOUNT_FILE = "credentials.json"

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

CALENDARS = {
    "Lisa Fischer": "c196fca542ff5176c621b1805596e015fb2affc1e0cb73c43cf5559379116380@group.calendar.google.com",
    "Marco Richter": "00edbaec6022faf25bbd87a7649ef058121d30171af4efd10ecc0393e34db90e@group.calendar.google.com",
    "Marie Zeiser": "1e3a7437847c760bf08026e4fd7eb4a2692c599e8de1181fd8c87837be524e7@group.calendar.google.com",
    "Max Herrmann": "5b679eaf3a0999b06265e6b21dd202080e8b2338650475e1cbd8f17ab34f861@group.calendar.google.com"
}

def get_service():
    return build("calendar", "v3", credentials=credentials)

@app.route("/check_availability", methods=["POST"])
def check_availability():
    data = request.get_json()
    friseur = data.get("friseur")
    date = data.get("date")
    time = data.get("time")

    calendar_id = CALENDARS.get(friseur)
    if not calendar_id:
        return jsonify({"success": False, "message": "Friseur nicht gefunden"}), 400

    start_datetime = datetime.datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    end_datetime = start_datetime + datetime.timedelta(minutes=60)

    service = get_service()
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_datetime.isoformat() + "Z",
        timeMax=end_datetime.isoformat() + "Z",
        singleEvents=True
    ).execute()

    events = events_result.get("items", [])

    if events:
        return jsonify({"success": False, "message": "Termin ist bereits vergeben"})
    return jsonify({"success": True})

@app.route("/book", methods=["POST"])
def book():
    data = request.get_json()
    friseur = data.get("friseur")
    date = data.get("date")
    time = data.get("time")
    name = data.get("name")

    calendar_id = CALENDARS.get(friseur)
    if not calendar_id:
        return jsonify({"success": False, "message": "Friseur nicht gefunden"}), 400

    start_datetime = datetime.datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    end_datetime = start_datetime + datetime.timedelta(minutes=60)

    service = get_service()
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_datetime.isoformat() + "Z",
        timeMax=end_datetime.isoformat() + "Z",
        singleEvents=True
    ).execute()

    if events_result.get("items"):
        return jsonify({"success": False, "message": "Termin bereits vergeben"}), 409

    event = {
        "summary": name,
        "start": {"dateTime": start_datetime.isoformat(), "timeZone": "Europe/Berlin"},
        "end": {"dateTime": end_datetime.isoformat(), "timeZone": "Europe/Berlin"},
    }

    service.events().insert(calendarId=calendar_id, body=event).execute()
    return jsonify({"success": True})

@app.route("/cancel", methods=["POST"])
def cancel():
    data = request.get_json()
    friseur = data.get("friseur")
    date = data.get("date")
    time = data.get("time")
    name = data.get("name")

    calendar_id = CALENDARS.get(friseur)
    if not calendar_id:
        return jsonify({"success": False, "message": "Friseur nicht gefunden"}), 400

    service = get_service()
    start_datetime = datetime.datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    end_datetime = start_datetime + datetime.timedelta(minutes=60)

    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_datetime.isoformat() + "Z",
        timeMax=end_datetime.isoformat() + "Z",
        singleEvents=True
    ).execute()

    deleted = False
    for event in events_result.get("items", []):
        if name.lower() in event.get("summary", "").lower():
            service.events().delete(calendarId=calendar_id, eventId=event["id"]).execute()
            deleted = True

    if deleted:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "Kein passender Termin gefunden"})

@app.route("/free_slots_by_date", methods=["POST"])
def free_slots_by_date():
    data = request.get_json()
    friseur = data.get("friseur")
    date = data.get("date")
    calendar_id = CALENDARS.get(friseur)
    if not calendar_id:
        return jsonify({"success": False, "message": "Friseur nicht gefunden"}), 400

    service = get_service()
    date_start = datetime.datetime.strptime(date, "%Y-%m-%d")
    date_end = date_start + datetime.timedelta(days=1)

    appointments = service.events().list(
        calendarId=calendar_id,
        timeMin=date_start.isoformat() + "Z",
        timeMax=date_end.isoformat() + "Z",
        singleEvents=True
    ).execute().get("items", [])

    booked_times = [event["start"]["dateTime"][11:16] for event in appointments]
    opening_hours = [f"{hour:02}:00" for hour in range(9, 18)]
    free_times = [t for t in opening_hours if t not in booked_times]

    return jsonify({"success": True, "free_slots": free_times})

@app.route("/next_free_slots", methods=["POST"])
def next_free_slots():
    data = request.get_json()
    friseur = data.get("friseur")
    calendar_id = CALENDARS.get(friseur)
    if not calendar_id:
        return jsonify({"success": False, "message": "Friseur nicht gefunden"}), 400

    service = get_service()
    now = datetime.datetime.utcnow()
    future = now + datetime.timedelta(days=14)

    possible_slots = []
    for day_offset in range(14):
        date = now + datetime.timedelta(days=day_offset)
        opening_hours = [f"{hour:02}:00" for hour in range(9, 18)]
        for hour in opening_hours:
            slot_time = datetime.datetime.strptime(date.strftime("%Y-%m-%d") + f" {hour}", "%Y-%m-%d %H:%M")
            if slot_time < now:
                continue

            end_time = slot_time + datetime.timedelta(minutes=60)
            events = service.events().list(
                calendarId=calendar_id,
                timeMin=slot_time.isoformat() + "Z",
                timeMax=end_time.isoformat() + "Z",
                singleEvents=True
            ).execute().get("items", [])

            if not events:
                possible_slots.append({"date": date.strftime("%Y-%m-%d"), "time": hour})
            if len(possible_slots) == 3:
                return jsonify({"success": True, "next_slots": possible_slots})

    return jsonify({"success": True, "next_slots": possible_slots})

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
