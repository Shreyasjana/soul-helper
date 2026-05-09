# modules/collector.py
# ---------------------------------------------------------------------------
# Handles all user input collection and saves it as a daily journal entry.
# Each entry is saved as a JSON file named by date: 2025-04-27.json
# ---------------------------------------------------------------------------

import json
import os
from datetime import datetime
import sys

# This lets us import config.py from the root folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def get_today_filename():
    """Returns the filename for today's journal entry based on current date."""
    today = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(config.JOURNAL_DIR, f"{today}.json")


def entry_exists_today():
    """Checks if the user has already submitted an entry today."""
    return os.path.exists(get_today_filename())


def save_entry(journal_text, mood, energy, sleep_hours):
    """
    Packages and saves the user's daily input as a JSON file.

    Parameters:
        journal_text (str): What the user wrote in their journal
        mood        (int): Self-rated mood score (1–10)
        energy      (int): Self-rated energy score (1–10)
        sleep_hours (float): Hours of sleep last night
    """

    # Make sure the journals folder exists
    os.makedirs(config.JOURNAL_DIR, exist_ok=True)

    # Build the entry as a dictionary
    entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": datetime.now().strftime("%H:%M:%S"),
        "day_of_week": datetime.now().strftime("%A"),       # e.g. "Monday"
        "journal": journal_text.strip(),
        "mood": mood,
        "energy": energy,
        "sleep_hours": sleep_hours
    }

    # Save it as a JSON file named by today's date
    filename = get_today_filename()
    with open(filename, "w") as f:
        json.dump(entry, f, indent=4)

    return entry


def load_entry(date_str):
    """
    Loads a single journal entry by date string.

    Parameters:
        date_str (str): Date in format 'YYYY-MM-DD'

    Returns:
        dict or None
    """
    filepath = os.path.join(config.JOURNAL_DIR, f"{date_str}.json")
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return None


def load_all_entries():
    """
    Loads all saved journal entries sorted by date (oldest first).

    Returns:
        list of dicts
    """
    entries = []

    # Make sure the folder exists before trying to read from it
    if not os.path.exists(config.JOURNAL_DIR):
        return entries

    for filename in sorted(os.listdir(config.JOURNAL_DIR)):
        if filename.endswith(".json"):
            filepath = os.path.join(config.JOURNAL_DIR, filename)
            with open(filepath, "r") as f:
                entries.append(json.load(f))

    return entries


def count_entries():
    """Returns how many journal entries exist so far."""
    if not os.path.exists(config.JOURNAL_DIR):
        return 0
    return len([f for f in os.listdir(config.JOURNAL_DIR) if f.endswith(".json")])


def days_until_baseline():
    """
    Tells the user how many more days until the system starts giving insights.
    Returns 0 if baseline is already reached.
    """
    remaining = config.BASELINE_DAYS - count_entries()
    return max(0, remaining)


def baseline_reached():
    """Returns True if enough entries exist to start analysis."""
    return count_entries() >= config.BASELINE_DAYS