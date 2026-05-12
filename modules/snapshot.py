# modules/snapshot.py
# ---------------------------------------------------------------------------
# Handles Daily Snapshot and Weekly Analysis generation.
# Works from day 1 — no baseline needed.
# ---------------------------------------------------------------------------

import sys
import os
import random
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.nlp_processor       import process_journal
from modules.distortion_detector import detect_distortions


# ---------------------------------------------------------------------------
# TIPS BANK
# ---------------------------------------------------------------------------

STRESS_TIPS = [
    "try box breathing — inhale 4 counts, hold 4, exhale 4, hold 4. repeat 3 times.",
    "step outside for 5 minutes. natural light and movement reset your nervous system faster than anything.",
    "write down the one thing stressing you most. just naming it reduces its power.",
    "put on a song you love and do nothing else for 3 minutes. your brain needs permission to pause.",
    "drink a glass of water slowly. sounds basic — works better than it should.",
]

AGITATION_TIPS = [
    "you seem activated right now. before doing anything important, give yourself 10 minutes.",
    "high energy isn't always bad — channel it into something physical if you can. even a short walk.",
    "when everything feels urgent, nothing actually is. pick one thing and ignore the rest.",
    "slow your breathing down deliberately. long exhale, longer than the inhale. your body will follow.",
]

REFRAME_TIPS = [
    "today felt heavy. that's okay. one hard day doesn't define the week.",
    "write down one thing — however small — that went okay today. just one.",
    "your brain is filtering for the negative right now. it's a feature, not a bug — but worth knowing.",
    "tomorrow is genuinely a fresh start. your cortisol levels actually reset overnight.",
]

POSITIVE_TIPS = [
    "you seem good today. notice what's working — it's worth knowing what to protect.",
    "solid day. the consistency of journaling itself is doing something good for you.",
    "good energy today. use it on something that matters to you.",
    "you're showing up — that counts for more than most people realize.",
]


def get_tip(mood, agitation, sentiment_label):
    if mood < 4 or sentiment_label == "negative":
        return random.choice(STRESS_TIPS)
    elif agitation > 0.6:
        return random.choice(AGITATION_TIPS)
    elif sentiment_label == "neutral" and mood < 6:
        return random.choice(REFRAME_TIPS)
    else:
        return random.choice(POSITIVE_TIPS)


# ---------------------------------------------------------------------------
# DAILY SNAPSHOT
# ---------------------------------------------------------------------------

def generate_daily_snapshot(entries_today):
    if not entries_today:
        return None

    moods   = [e.get("mood",        5) for e in entries_today]
    energys = [e.get("energy",      5) for e in entries_today]
    sleeps  = [e.get("sleep_hours", 7) for e in entries_today]
    times   = [e.get("time",       "") for e in entries_today]

    avg_mood   = round(sum(moods)   / len(moods),   1)
    avg_energy = round(sum(energys) / len(energys), 1)
    avg_sleep  = round(sum(sleeps)  / len(sleeps),  1)

    agitations    = [e.get("behavioral_signals", {}).get("agitation_score", 0) for e in entries_today]
    avg_agitation = round(sum(agitations) / len(agitations), 2)

    if len(agitations) > 1:
        if agitations[-1] > agitations[0]:
            agitation_trend = "increasing ↑"
        elif agitations[-1] < agitations[0]:
            agitation_trend = "decreasing ↓"
        else:
            agitation_trend = "stable →"
    else:
        agitation_trend = "stable →"

    combined_text    = " ".join([e.get("journal", "") for e in entries_today])
    nlp              = process_journal(combined_text)
    dist             = detect_distortions(combined_text)
    sentiment_label  = nlp["sentiment"]["label"]
    sentiment_score  = nlp["sentiment"]["compound_score"]
    dominant_emotion = nlp["emotion"]["dominant_emotion"]
    keywords         = nlp["keywords"][:6]

    tip         = get_tip(avg_mood, avg_agitation, sentiment_label)
    observation = _generate_observation(
        avg_mood, avg_energy, avg_sleep,
        sentiment_label, dominant_emotion,
        avg_agitation, agitation_trend,
        dist, len(entries_today)
    )

    return {
        "entry_count":      len(entries_today),
        "avg_mood":         avg_mood,
        "avg_energy":       avg_energy,
        "avg_sleep":        avg_sleep,
        "avg_agitation":    avg_agitation,
        "agitation_trend":  agitation_trend,
        "sentiment_label":  sentiment_label,
        "sentiment_score":  sentiment_score,
        "dominant_emotion": dominant_emotion,
        "keywords":         keywords,
        "distortions":      dist,
        "tip":              tip,
        "observation":      observation,
        "mood_over_time":   list(zip(times, moods)),
        "energy_over_time": list(zip(times, energys)),
    }


def _generate_observation(avg_mood, avg_energy, avg_sleep,
                           sentiment, emotion, agitation,
                           agitation_trend, dist, entry_count):
    lines = []

    if avg_mood >= 7:
        lines.append(f"mood sitting at {avg_mood}/10 — genuinely good day.")
    elif avg_mood >= 5:
        lines.append(f"mood at {avg_mood}/10 — steady, nothing alarming.")
    elif avg_mood >= 3:
        lines.append(f"mood at {avg_mood}/10 — a bit low today. worth paying attention to.")
    else:
        lines.append(f"mood at {avg_mood}/10 — rough day. that's okay, it happens.")

    if avg_energy >= 7 and avg_mood < 5:
        lines.append("interesting — energy is up but mood is down. something specific is weighing on you.")
    elif avg_energy < 4 and avg_mood >= 6:
        lines.append("good mood but low energy — probably just tired. rest will help.")

    if avg_sleep < 5.5:
        lines.append(f"only {avg_sleep}h of sleep — that's going to show up somewhere today.")

    if agitation > 0.6:
        lines.append(f"your writing shows some agitation ({agitation_trend}) — something's got you activated.")

    if dist["distortion_count"] > 0:
        top = dist["detected"][0]
        lines.append(f"noticed some {top.lower()} in your writing today.")

    if emotion not in ["neutral", "joy"]:
        lines.append(f"dominant emotional tone: {emotion}.")

    if entry_count > 1:
        lines.append(f"you checked in {entry_count} times today — that kind of awareness matters.")

    return " ".join(lines[:3])


# ---------------------------------------------------------------------------
# WEEKLY ANALYSIS
# ---------------------------------------------------------------------------

def generate_weekly_analysis(all_entries):
    if not all_entries:
        return []

    first_date = datetime.fromisoformat(all_entries[0]["timestamp"]).date()
    weeks      = {}

    for entry in all_entries:
        entry_date = datetime.fromisoformat(entry["timestamp"]).date()
        week_num   = (entry_date - first_date).days // 7
        if week_num not in weeks:
            weeks[week_num] = []
        weeks[week_num].append(entry)

    week_analyses = []

    for week_num in sorted(weeks.keys()):
        week_entries = weeks[week_num]

        dates      = [datetime.fromisoformat(e["timestamp"]).date() for e in week_entries]
        start_date = min(dates).strftime("%d %b")
        end_date   = max(dates).strftime("%d %b %Y")
        label      = f"Week {week_num + 1}  —  {start_date} to {end_date}"

        moods      = [e.get("mood",        5) for e in week_entries]
        energys    = [e.get("energy",      5) for e in week_entries]
        sleeps     = [e.get("sleep_hours", 7) for e in week_entries]
        agitations = [e.get("behavioral_signals", {}).get("agitation_score", 0) for e in week_entries]

        avg_mood      = round(sum(moods)      / len(moods),      1)
        avg_energy    = round(sum(energys)    / len(energys),    1)
        avg_sleep     = round(sum(sleeps)     / len(sleeps),     1)
        avg_agitation = round(sum(agitations) / len(agitations), 2)

        combined_text    = " ".join([e.get("journal", "") for e in week_entries])
        nlp              = process_journal(combined_text)
        dist             = detect_distortions(combined_text)
        dominant_emotion = nlp["emotion"]["dominant_emotion"]
        sentiment        = nlp["sentiment"]["label"]
        keywords         = nlp["keywords"][:5]

        session_days = list(set(e.get("session_day", "") for e in week_entries))

        if len(moods) > 1:
            mid    = len(moods) // 2
            first  = sum(moods[:mid]) / len(moods[:mid])
            second = sum(moods[mid:]) / len(moods[mid:])
            if second - first >= 0.5:
                mood_trend = "improving"
            elif first - second >= 0.5:
                mood_trend = "declining"
            else:
                mood_trend = "stable"
        else:
            mood_trend = "stable"

        day_mood_map = {}
        for e in week_entries:
            day = e.get("session_day", "")
            if day not in day_mood_map:
                day_mood_map[day] = []
            day_mood_map[day].append(e.get("mood", 5))

        day_avg_moods = {
            day: round(sum(v) / len(v), 1)
            for day, v in sorted(day_mood_map.items())
        }

        day_energy_map = {}
        for e in week_entries:
            day = e.get("session_day", "")
            if day not in day_energy_map:
                day_energy_map[day] = []
            day_energy_map[day].append(e.get("energy", 5))

        day_avg_energys = {
            day: round(sum(v) / len(v), 1)
            for day, v in sorted(day_energy_map.items())
        }

        week_analyses.append({
            "week_num":         week_num + 1,
            "label":            label,
            "entry_count":      len(week_entries),
            "day_count":        len(session_days),
            "avg_mood":         avg_mood,
            "avg_energy":       avg_energy,
            "avg_sleep":        avg_sleep,
            "avg_agitation":    avg_agitation,
            "mood_trend":       mood_trend,
            "dominant_emotion": dominant_emotion,
            "sentiment":        sentiment,
            "keywords":         keywords,
            "distortions":      dist,
            "day_avg_moods":    day_avg_moods,
            "day_avg_energys":  day_avg_energys,
        })

    return week_analyses