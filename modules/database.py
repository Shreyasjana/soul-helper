# modules/database.py
# ---------------------------------------------------------------------------
# Handles all communication between Soul Helper and Supabase database.
# This replaces local JSON file storage for multi-user cloud deployment.
# ---------------------------------------------------------------------------

import os
import hashlib
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ---------------------------------------------------------------------------
# UTILITY
# ---------------------------------------------------------------------------

def hash_pin(pin: str) -> str:
    """Hashes a 4-digit PIN using SHA-256. Never stores raw PINs."""
    return hashlib.sha256(pin.encode()).hexdigest()


# ---------------------------------------------------------------------------
# USER MANAGEMENT
# ---------------------------------------------------------------------------

def create_user(username: str, pin: str) -> dict:
    """
    Creates a new user profile in the database.

    Parameters:
        username (str): Display name chosen by user
        pin      (str): 4-digit PIN

    Returns:
        dict: Result with success/error info
    """
    try:
        # Check if username already exists
        existing = supabase.table("users")\
            .select("id")\
            .eq("username", username.lower().strip())\
            .execute()

        if existing.data:
            return {"success": False, "error": "Username already taken."}

        # Create user
        result = supabase.table("users").insert({
            "username": username.lower().strip(),
            "pin_hash": hash_pin(pin)
        }).execute()

        return {"success": True, "data": result.data}

    except Exception as e:
        return {"success": False, "error": str(e)}


def verify_user(username: str, pin: str) -> dict:
    """
    Verifies a user's PIN and returns their profile.

    Returns:
        dict: {success, user_id, username} or {success: False, error}
    """
    try:
        result = supabase.table("users")\
            .select("id, username, pin_hash")\
            .eq("username", username.lower().strip())\
            .execute()

        if not result.data:
            return {"success": False, "error": "Username not found."}

        user = result.data[0]

        if user["pin_hash"] != hash_pin(pin):
            return {"success": False, "error": "Incorrect PIN."}

        return {
            "success":  True,
            "user_id":  user["id"],
            "username": user["username"]
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def get_all_users() -> list:
    """Returns list of all usernames. Used by researcher dashboard."""
    try:
        result = supabase.table("users")\
            .select("username, created_at")\
            .execute()
        return result.data or []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# JOURNAL MANAGEMENT
# ---------------------------------------------------------------------------

def save_journal_entry(username: str, user_id: str, entry: dict) -> dict:
    """
    Saves a journal entry to Supabase for a specific user.

    Parameters:
        username (str) : The user's name
        user_id  (str) : Their UUID from the users table
        entry    (dict): The full entry object from collector.py

    Returns:
        dict: Success or error
    """
    try:
        signals = entry.get("behavioral_signals", {})

        result = supabase.table("journals").insert({
            "user_id":         user_id,
            "username":        username,
            "entry_id":        entry.get("entry_id", ""),
            "timestamp":       entry.get("timestamp", ""),
            "session_day":     entry.get("session_day", ""),
            "date":            entry.get("date", ""),
            "time":            entry.get("time", ""),
            "day_of_week":     entry.get("day_of_week", ""),
            "journal":         entry.get("journal", ""),
            "mood":            entry.get("mood", 5),
            "energy":          entry.get("energy", 5),
            "sleep_hours":     entry.get("sleep_hours", 7),
            "agitation_score": signals.get("agitation_score", 0),
            "wpm":             signals.get("wpm", 0),
            "spelling_errors": signals.get("spelling_errors", 0),
        }).execute()

        return {"success": True, "data": result.data}

    except Exception as e:
        return {"success": False, "error": str(e)}


def load_journal_entries(username: str) -> list:
    """
    Loads all journal entries for a specific user, sorted by timestamp.

    Parameters:
        username (str): The user's name

    Returns:
        list of entry dicts
    """
    try:
        result = supabase.table("journals")\
            .select("*")\
            .eq("username", username)\
            .order("timestamp", desc=False)\
            .execute()

        entries = []
        for row in (result.data or []):
            # Reconstruct entry format expected by modules
            entry = {
                "entry_id":    row["entry_id"],
                "timestamp":   row["timestamp"],
                "session_day": row["session_day"],
                "date":        row["date"],
                "time":        row["time"],
                "day_of_week": row["day_of_week"],
                "journal":     row["journal"],
                "mood":        row["mood"],
                "energy":      row["energy"],
                "sleep_hours": row["sleep_hours"],
                "behavioral_signals": {
                    "agitation_score": row["agitation_score"],
                    "wpm":             row["wpm"],
                    "spelling_errors": row["spelling_errors"],
                    "typing_speed":    "unknown",
                    "error_ratio":     0
                }
            }
            entries.append(entry)

        return entries

    except Exception as e:
        return []


def load_entries_by_day_db(username: str, session_day: str) -> list:
    """
    Loads all entries for a specific session day for a user.
    """
    try:
        result = supabase.table("journals")\
            .select("*")\
            .eq("username", username)\
            .eq("session_day", session_day)\
            .order("timestamp", desc=False)\
            .execute()

        entries = []
        for row in (result.data or []):
            entry = {
                "entry_id":    row["entry_id"],
                "timestamp":   row["timestamp"],
                "session_day": row["session_day"],
                "date":        row["date"],
                "time":        row["time"],
                "day_of_week": row["day_of_week"],
                "journal":     row["journal"],
                "mood":        row["mood"],
                "energy":      row["energy"],
                "sleep_hours": row["sleep_hours"],
                "behavioral_signals": {
                    "agitation_score": row["agitation_score"],
                    "wpm":             row["wpm"],
                    "spelling_errors": row["spelling_errors"],
                    "typing_speed":    "unknown",
                    "error_ratio":     0
                }
            }
            entries.append(entry)

        return entries

    except Exception as e:
        return []


def delete_journal_entry_db(entry_id: str, username: str) -> bool:
    """
    Deletes a specific journal entry by entry_id for a user.
    Username check ensures users can only delete their own entries.
    """
    try:
        supabase.table("journals")\
            .delete()\
            .eq("entry_id", entry_id)\
            .eq("username", username)\
            .execute()
        return True
    except Exception:
        return False


def count_session_days_db(username: str) -> int:
    """
    Returns number of unique session days for a user.
    Used for baseline counting.
    """
    try:
        result = supabase.table("journals")\
            .select("session_day")\
            .eq("username", username)\
            .execute()

        unique_days = set(row["session_day"] for row in (result.data or []))
        return len(unique_days)

    except Exception:
        return 0


def count_entries_db(username: str) -> int:
    """Returns total entry count for a user."""
    try:
        result = supabase.table("journals")\
            .select("id")\
            .eq("username", username)\
            .execute()
        return len(result.data or [])
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# RESEARCHER ANALYTICS
# ---------------------------------------------------------------------------

def save_researcher_snapshot(username: str, analysis: dict) -> dict:
    """
    Saves an anonymous analysis snapshot for the researcher dashboard.
    Contains NO raw journal text — only metrics.

    Parameters:
        username (str)   : User being analyzed
        analysis (dict)  : Output from pattern/prediction modules
    """
    try:
        mood_pred = analysis.get("predictions", {}).get("mood_prediction", {})
        risk      = analysis.get("predictions", {}).get("risk_flags", {})

        result = supabase.table("researcher_analytics").insert({
            "username":               username,
            "snapshot_date":          datetime.now().strftime("%Y-%m-%d"),
            "avg_mood":               analysis.get("avg_mood", 0),
            "avg_energy":             analysis.get("avg_energy", 0),
            "avg_sleep":              analysis.get("avg_sleep", 0),
            "mood_trend":             analysis.get("mood_trend", "stable"),
            "energy_trend":           analysis.get("energy_trend", "stable"),
            "dominant_emotion":       analysis.get("dominant_emotion", "neutral"),
            "most_common_distortion": analysis.get("most_common_distortion", "None"),
            "risk_flagged":           risk.get("flagged", False),
            "entry_count":            analysis.get("entry_count", 0),
        }).execute()

        return {"success": True}

    except Exception as e:
        return {"success": False, "error": str(e)}


def load_researcher_data() -> list:
    """
    Loads latest analysis snapshot for every user.
    Used by researcher dashboard.
    Returns list of anonymous analysis dicts (no journal text).
    """
    try:
        # Get all users
        users = get_all_users()
        researcher_data = []

        for user in users:
            username = user["username"]

            # Get latest snapshot for this user
            result = supabase.table("researcher_analytics")\
                .select("*")\
                .eq("username", username)\
                .order("created_at", desc=True)\
                .limit(1)\
                .execute()

            if result.data:
                researcher_data.append(result.data[0])

        return researcher_data

    except Exception:
        return []