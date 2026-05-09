# modules/collector.py (REFACTORED)
# ---------------------------------------------------------------------------
# Handles multi-entry journaling per day with 36-hour window.
# Each entry is timestamped and tagged with behavioral signals.
#
# Filename format: entry_YYYY-MM-DD_HH-MM-SS.json
# All entries for a day live flat in data/journals/
#
# 36-hour window rule:
#   - 00:00–11:59 AM → AMBIGUOUS: ask user (yesterday or today)
#   - 12:00 PM–23:59 → always TODAY
# ---------------------------------------------------------------------------

import json
import os
from datetime import datetime, timedelta
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


# ---------------------------------------------------------------------------
# UTILITY: Get which "day" an entry belongs to (36-hour logic)
# ---------------------------------------------------------------------------

def get_session_day(dt, user_choice=None):
    """
    Returns which calendar day this entry belongs to.

    Logic:
        - 12:00 PM – 11:59 PM → always TODAY (no ambiguity)
        - 12:00 AM – 11:59 AM → AMBIGUOUS: ask user
            - user_choice = "today"     → current calendar day
            - user_choice = "yesterday" → previous calendar day
            - user_choice = None        → defaults to yesterday

    Parameters:
        dt          (datetime): Current datetime
        user_choice (str|None): "today", "yesterday", or None
    """
    hour = dt.hour

    if hour >= 12:
        # 12 PM onwards — unambiguously TODAY
        return dt.strftime("%Y-%m-%d")
    else:
        # 12 AM – 11:59 AM — ambiguous zone
        if user_choice == "today":
            return dt.strftime("%Y-%m-%d")
        else:
            # Default to yesterday
            return (dt - timedelta(days=1)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# BEHAVIORAL SIGNAL DETECTION
# ---------------------------------------------------------------------------

def detect_typing_speed(journal_text, entry_time_seconds):
    """
    Estimates typing speed based on text length and time taken.

    Psychology insight: Fast typing with many errors suggests agitation/excitement.
    Slow typing suggests deliberate/thoughtful entry.

    Parameters:
        journal_text       (str): The journal entry text
        entry_time_seconds (int): How long user spent typing (from UI timer)

    Returns:
        typing_speed (str)  : "fast", "normal", or "slow"
        wpm          (float): Estimated words per minute
    """
    if entry_time_seconds == 0:
        return "unknown", 0

    word_count = len(journal_text.split())
    wpm = (word_count / entry_time_seconds) * 60

    if wpm > 60:
        speed = "fast"
    elif wpm > 30:
        speed = "normal"
    else:
        speed = "slow"

    return speed, round(wpm, 2)


def detect_spelling_errors(journal_text):
    """
    Counts approximate spelling mistakes using a simple heuristic.

    Psychology insight: High error count + fast typing = agitation/overwhelm.

    Returns:
        error_count (int)  : Approximate number of errors
        error_ratio (float): Errors per 100 words
    """
    common_words = {
        "the", "a", "is", "are", "was", "were", "be", "been",
        "i", "you", "he", "she", "it", "we", "they",
        "my", "your", "his", "her", "its", "our", "their",
        "and", "or", "but", "not", "no", "yes",
        "have", "has", "do", "does", "did", "will", "would",
        "can", "could", "should", "may", "might", "must",
        "to", "from", "in", "on", "at", "by", "with", "for",
        "of", "about", "as", "into", "through", "during",
        "what", "which", "who", "when", "where", "why", "how",
        "this", "that", "these", "those", "there", "here",
        "so", "just", "only", "very", "too", "also", "more", "most",
        "all", "each", "every", "both", "few", "some", "many",
        "good", "bad", "happy", "sad", "angry", "scared", "tired"
    }

    words = journal_text.lower().split()
    word_count = len(words)

    if word_count == 0:
        return 0, 0

    errors = sum(1 for w in words if w not in common_words and len(w) > 2)
    error_ratio = round((errors / word_count) * 100, 2)

    return errors, error_ratio


def calculate_agitation_score(typing_speed, wpm, error_count, error_ratio):
    """
    Combines typing speed + spelling errors into a single agitation score.

    High score (0.7–1.0) = person is agitated/excited/overwhelmed
    Low score  (0.0–0.3) = person is calm/deliberate

    Psychology: Agitation correlates with emotional dysregulation, anxiety, mania.

    Returns:
        agitation (float): 0.0 to 1.0
    """
    speed_score = 1.0 if wpm > 60 else (0.5 if wpm > 30 else 0.0)
    error_score = min(error_ratio / 30, 1.0)
    agitation   = (speed_score + error_score) / 2
    return round(agitation, 2)


# ---------------------------------------------------------------------------
# ENTRY MANAGEMENT
# ---------------------------------------------------------------------------

def save_entry(journal_text, mood, energy, sleep_hours,
               typing_time_seconds=0, session_day_override=None):
    """
    Saves a single journal entry as a JSON file.

    Filename: entry_YYYY-MM-DD_HH-MM-SS.json

    Parameters:
        journal_text         (str)  : The journal content
        mood                 (int)  : 1–10 mood rating
        energy               (int)  : 1–10 energy rating
        sleep_hours          (float): Hours of sleep last night
        typing_time_seconds  (int)  : How long user spent typing (optional)
        session_day_override (str)  : Force entry into a specific session day
                                      (used when user picks yesterday/today)

    Returns:
        entry (dict): The saved entry object
    """
    now = datetime.now()

    # Use override if provided (from user's morning choice), else auto-detect
    session_day = session_day_override if session_day_override else get_session_day(now)

    os.makedirs(config.JOURNAL_DIR, exist_ok=True)

    # Behavioral signals
    typing_speed, wpm       = detect_typing_speed(journal_text, typing_time_seconds)
    error_count, error_ratio = detect_spelling_errors(journal_text)
    agitation                = calculate_agitation_score(typing_speed, wpm,
                                                          error_count, error_ratio)

    # Build entry
    entry = {
        "entry_id":    f"{now.strftime('%Y-%m-%d_%H-%M-%S')}",
        "timestamp":   now.isoformat(),
        "session_day": session_day,
        "date":        now.strftime("%Y-%m-%d"),
        "time":        now.strftime("%H:%M:%S"),
        "day_of_week": now.strftime("%A"),
        "journal":     journal_text.strip(),
        "mood":        mood,
        "energy":      energy,
        "sleep_hours": sleep_hours,

        # Behavioral signals
        "behavioral_signals": {
            "typing_speed":    typing_speed,
            "wpm":             wpm,
            "spelling_errors": error_count,
            "error_ratio":     error_ratio,
            "agitation_score": agitation
        }
    }

    # Save as JSON
    filename = os.path.join(
        config.JOURNAL_DIR,
        f"entry_{now.strftime('%Y-%m-%d_%H-%M-%S')}.json"
    )

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(entry, f, indent=4)

    return entry


def load_entry_by_id(entry_id):
    """
    Loads a single entry by its entry_id.

    Parameters:
        entry_id (str): Format 'YYYY-MM-DD_HH-MM-SS'

    Returns:
        dict or None
    """
    if not os.path.exists(config.JOURNAL_DIR):
        return None

    for filename in os.listdir(config.JOURNAL_DIR):
        if filename.endswith(".json") and entry_id in filename:
            filepath = os.path.join(config.JOURNAL_DIR, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)

    return None


def load_all_entries(sort_by="timestamp"):
    """
    Loads ALL entries across all days, sorted chronologically.

    Returns:
        list of entry dicts, oldest first
    """
    entries = []

    if not os.path.exists(config.JOURNAL_DIR):
        return entries

    for filename in os.listdir(config.JOURNAL_DIR):
        if filename.endswith(".json"):
            filepath = os.path.join(config.JOURNAL_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    entries.append(json.load(f))
            except json.JSONDecodeError:
                continue

    entries.sort(key=lambda e: e.get("timestamp", ""))
    return entries


def load_entries_by_day(day_str):
    """
    Loads all entries for a specific session day.

    Parameters:
        day_str (str): Format 'YYYY-MM-DD'

    Returns:
        list of entries for that day, chronologically ordered
    """
    all_entries = load_all_entries()
    day_entries = [
        e for e in all_entries
        if e.get("session_day") == day_str
    ]
    return day_entries


def count_entries():
    """Returns total number of journal entries (across all days)."""
    if not os.path.exists(config.JOURNAL_DIR):
        return 0
    return len([f for f in os.listdir(config.JOURNAL_DIR) if f.endswith(".json")])


def count_session_days():
    """
    Returns number of UNIQUE session days.
    This is what we use for baseline counting, not raw entry count.
    """
    all_entries = load_all_entries()
    unique_days = set(e.get("session_day") for e in all_entries)
    return len(unique_days)


def days_until_baseline():
    """Returns how many more session days until baseline is reached."""
    remaining = config.BASELINE_DAYS - count_session_days()
    return max(0, remaining)


def baseline_reached():
    """Returns True if enough session days exist."""
    return count_session_days() >= config.BASELINE_DAYS


def get_last_entry():
    """Returns the most recent entry."""
    entries = load_all_entries()
    return entries[-1] if entries else None


def entry_exists_today():
    """
    Checks if user has journaled in the current session day.
    """
    today_session = get_session_day(datetime.now())
    return len(load_entries_by_day(today_session)) > 0


def get_agitation_trend(day_str):
    """
    Returns agitation scores for all entries on a given day.
    Useful for detecting escalating emotional state within a day.
    """
    entries = load_entries_by_day(day_str)
    agitations = [
        e.get("behavioral_signals", {}).get("agitation_score", 0)
        for e in entries
    ]
    return agitations


def delete_entry(entry_id):
    """
    Deletes a journal entry by its entry_id.

    Parameters:
        entry_id (str): Format 'YYYY-MM-DD_HH-MM-SS'

    Returns:
        bool: True if deleted, False if not found
    """
    if not os.path.exists(config.JOURNAL_DIR):
        return False

    for filename in os.listdir(config.JOURNAL_DIR):
        if filename.endswith(".json") and entry_id in filename:
            filepath = os.path.join(config.JOURNAL_DIR, filename)
            try:
                os.remove(filepath)
                return True
            except Exception:
                return False

    return False