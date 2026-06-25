import json
import os
import sys
from datetime import date, datetime

from dotenv import load_dotenv
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

load_dotenv()

WORKOUT_TYPES = {
    0: "טכניקה",    # Monday
    2: "מהירות",    # Wednesday
    5: "ריצה קלה",  # Saturday
}

GARMIN_EMAIL = os.getenv("GARMIN_EMAIL")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD")


def connect() -> Garmin:
    if not GARMIN_EMAIL or not GARMIN_PASSWORD:
        print("Error: GARMIN_EMAIL and GARMIN_PASSWORD must be set in .env")
        sys.exit(1)
    try:
        client = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
        client.login()
        return client
    except GarminConnectAuthenticationError:
        print("Error: Login failed — check your GARMIN_EMAIL and GARMIN_PASSWORD in .env")
        sys.exit(1)
    except GarminConnectTooManyRequestsError:
        print("Error: Too many requests — Garmin rate-limited this IP. Try again later.")
        sys.exit(1)
    except GarminConnectConnectionError as e:
        print(f"Error: Could not reach Garmin Connect — {e}")
        sys.exit(1)


def _format_pace(duration_min: float, distance_km: float) -> str:
    """Return pace as MM:SS string, e.g. '5:42'."""
    total_seconds = (duration_min / distance_km) * 60
    mins = int(total_seconds // 60)
    secs = int(total_seconds % 60)
    return f"{mins}:{secs:02d}"


def parse_activity(a: dict) -> dict:
    distance_km = round((a.get("distance") or 0) / 1000, 2)
    duration_min = round((a.get("duration") or 0) / 60, 2)

    if distance_km > 0 and duration_min > 0:
        pace = _format_pace(duration_min, distance_km)
    else:
        pace = None

    date_str = a.get("startTimeLocal")
    workout_type = None
    if date_str:
        try:
            workout_type = WORKOUT_TYPES.get(datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").weekday())
        except ValueError:
            pass

    return {
        "date": date_str,
        "workout_type": workout_type,
        "name": a.get("activityName"),
        "distance_km": distance_km,
        "duration_minutes": duration_min,
        "pace_min_per_km": pace,
        "average_hr": a.get("averageHR"),
        "max_hr": a.get("maxHR"),
        "avg_cadence_spm": a.get("averageRunningCadenceInStepsPerMinute"),
        "training_effect_aerobic": a.get("aerobicTrainingEffect"),
        "training_effect_anaerobic": a.get("anaerobicTrainingEffect"),
        "training_load": a.get("activityTrainingLoad"),
        "vo2max_estimate": a.get("vO2MaxValue"),
        "calories": a.get("calories"),
    }


def fetch_hr_zones(client: Garmin, activity_id: int) -> list | None:
    try:
        data = client.get_activity_hr_in_timezones(activity_id)
        return data
    except Exception as e:
        print(f"Warning: Could not fetch HR zones — {e}")
    return None


def fetch_vo2max(client: Garmin) -> float | None:
    try:
        today = date.today().isoformat()
        data = client.get_max_metrics(today)
        # Response is a list of daily metric objects
        if isinstance(data, list):
            for entry in data:
                generic = entry.get("generic") or {}
                vo2 = generic.get("vo2MaxPreciseValue") or generic.get("vo2MaxValue")
                if vo2 is not None:
                    return round(float(vo2), 1)
        elif isinstance(data, dict):
            # Alternate shape: {"allMetrics": {"metricsMap": {"WELLNESS_VO2_MAX": [...]}}}
            try:
                entries = data["allMetrics"]["metricsMap"]["WELLNESS_VO2_MAX"]
                if entries:
                    return round(float(entries[0]["value"]), 1)
            except (KeyError, IndexError, TypeError):
                pass
    except Exception as e:
        print(f"Warning: Could not fetch VO2 Max — {e}")
    return None


def main():
    print("Connecting to Garmin Connect...")
    client = connect()
    print("Login successful.\n")

    print("Fetching last 20 running activities...")
    raw = client.get_activities(start=0, limit=20, activitytype="running")
    activities = [parse_activity(a) for a in raw]

    last_activity_id = raw[0].get("activityId") if raw else None
    print(f"Fetching HR zones for most recent activity (id={last_activity_id})...")
    hr_zones = fetch_hr_zones(client, last_activity_id) if last_activity_id else None

    print("Fetching current VO2 Max...")
    vo2max = fetch_vo2max(client)

    output = {
        "fetched_at": datetime.now().isoformat(),
        "vo2max_current": vo2max,
        "last_activity_hr_zones": hr_zones,
        "activities": activities,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    dates = sorted(a["date"] for a in activities if a["date"])
    date_range = f"{dates[0]} to {dates[-1]}" if dates else "N/A"

    print(f"\nDone.")
    print(f"  Activities fetched : {len(activities)}")
    print(f"  Date range         : {date_range}")
    print(f"  VO2 Max (current)  : {vo2max}")
    print(f"  Saved to           : data.json")


if __name__ == "__main__":
    main()
