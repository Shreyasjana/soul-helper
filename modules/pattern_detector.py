# modules/pattern_detector.py
# ---------------------------------------------------------------------------
# Analyzes patterns across all journal entries over time.
# Only runs after BASELINE_DAYS entries exist (set in config.py).
#
# Detects:
#   - Mood trends (improving / declining / stable)
#   - Energy trends
#   - Sleep impact on mood
#   - Day-of-week patterns (which days are consistently better/worse)
#   - Sentiment drift over time
#   - Recurring keywords (dominant life themes)
# ---------------------------------------------------------------------------

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


# ---------------------------------------------------------------------------
# TREND DETECTION
# ---------------------------------------------------------------------------

def detect_trend(values):
    """
    Given a list of numbers over time, determines if the trend is
    going up, going down, or staying stable.

    Uses simple comparison: average of second half vs first half.

    Returns: "improving", "declining", or "stable"
    """
    if len(values) < 4:
        return "stable"  # not enough data to call a trend

    mid   = len(values) // 2
    first = sum(values[:mid])  / len(values[:mid])
    second= sum(values[mid:])  / len(values[mid:])

    diff = second - first

    if diff >= 1.0:
        return "improving"
    elif diff <= -1.0:
        return "declining"
    else:
        return "stable"


def get_mood_trend(entries):
    """
    Extracts mood scores across all entries and detects direction.

    Returns:
        scores  (list): mood values in chronological order
        trend   (str) : "improving", "declining", or "stable"
        average (float): average mood across all entries
    """
    scores = [e["mood"] for e in entries if "mood" in e]
    trend  = detect_trend(scores)
    avg    = round(sum(scores) / len(scores), 2) if scores else 0

    return {
        "scores":  scores,
        "trend":   trend,
        "average": avg
    }


def get_energy_trend(entries):
    """
    Same as mood trend but for energy scores.
    """
    scores = [e["energy"] for e in entries if "energy" in e]
    trend  = detect_trend(scores)
    avg    = round(sum(scores) / len(scores), 2) if scores else 0

    return {
        "scores":  scores,
        "trend":   trend,
        "average": avg
    }


# ---------------------------------------------------------------------------
# SLEEP IMPACT ANALYSIS
# ---------------------------------------------------------------------------

def analyze_sleep_impact(entries):
    """
    Checks if low sleep correlates with low mood the same day.

    Logic:
        - Low sleep  = below 6 hours
        - Low mood   = below 5 out of 10
        - Counts how often both happen on the same day

    Returns:
        low_sleep_days      (int): Days with under 6 hrs sleep
        low_mood_after_low_sleep (int): Of those, how many also had low mood
        correlation_flag    (bool): True if more than half of low-sleep
                                    days also had low mood
        message             (str): Human readable finding
    """
    low_sleep_days            = 0
    low_mood_after_low_sleep  = 0

    for entry in entries:
        sleep = entry.get("sleep_hours", 0)
        mood  = entry.get("mood", 5)

        if sleep < 6:
            low_sleep_days += 1
            if mood < 5:
                low_mood_after_low_sleep += 1

    correlation_flag = (
        low_sleep_days > 0 and
        (low_mood_after_low_sleep / low_sleep_days) >= 0.5
    )

    if low_sleep_days == 0:
        message = "No low-sleep days recorded yet."
    elif correlation_flag:
        message = (
            f"On {low_mood_after_low_sleep} out of {low_sleep_days} "
            f"low-sleep days, your mood was also low. "
            f"Sleep appears to significantly impact your mood."
        )
    else:
        message = (
            f"You had {low_sleep_days} low-sleep day(s), but mood was "
            f"not consistently affected. You seem resilient to sleep dips."
        )

    return {
        "low_sleep_days":           low_sleep_days,
        "low_mood_after_low_sleep": low_mood_after_low_sleep,
        "correlation_flag":         correlation_flag,
        "message":                  message
    }


# ---------------------------------------------------------------------------
# DAY OF WEEK PATTERNS
# ---------------------------------------------------------------------------

def analyze_day_of_week(entries):
    """
    Groups mood and energy scores by day of the week.
    Finds which day is consistently best and worst for this individual.

    Returns:
        day_averages (dict): Average mood per day name
        best_day     (str) : Day with highest average mood
        worst_day    (str) : Day with lowest average mood
    """
    day_data = {}

    for entry in entries:
        day   = entry.get("day_of_week", "Unknown")
        mood  = entry.get("mood", 5)

        if day not in day_data:
            day_data[day] = []
        day_data[day].append(mood)

    # Calculate average mood per day
    day_averages = {
        day: round(sum(scores) / len(scores), 2)
        for day, scores in day_data.items()
    }

    if not day_averages:
        return {
            "day_averages": {},
            "best_day":     "Unknown",
            "worst_day":    "Unknown"
        }

    best_day  = max(day_averages, key=day_averages.get)
    worst_day = min(day_averages, key=day_averages.get)

    return {
        "day_averages": day_averages,
        "best_day":     best_day,
        "worst_day":    worst_day
    }


# ---------------------------------------------------------------------------
# KEYWORD THEMES OVER TIME
# ---------------------------------------------------------------------------

def get_recurring_themes(all_nlp_results, top_n=5):
    """
    Aggregates keywords across all journal entries to find
    the dominant life themes for this individual.

    Parameters:
        all_nlp_results (list): List of NLP result dicts from nlp_processor
        top_n           (int) : How many top themes to return

    Returns:
        themes (list): Top N most recurring keywords across all entries
    """
    frequency_map = {}

    for result in all_nlp_results:
        keywords = result.get("keywords", [])
        for word in keywords:
            frequency_map[word] = frequency_map.get(word, 0) + 1

    sorted_themes = sorted(frequency_map, key=frequency_map.get, reverse=True)
    return sorted_themes[:top_n]


# ---------------------------------------------------------------------------
# SENTIMENT DRIFT
# ---------------------------------------------------------------------------

def get_sentiment_drift(all_nlp_results):
    """
    Tracks how overall sentiment has shifted over time.
    Compares first half of entries to second half.

    Returns:
        scores  (list): Sentiment compound scores over time
        drift   (str) : "improving", "declining", or "stable"
        message (str) : Human readable interpretation
    """
    scores = [
        r["sentiment"]["compound_score"]
        for r in all_nlp_results
        if "sentiment" in r
    ]

    if len(scores) < 4:
        return {
            "scores":  scores,
            "drift":   "stable",
            "message": "Not enough entries yet to detect sentiment drift."
        }

    mid    = len(scores) // 2
    first  = sum(scores[:mid]) / len(scores[:mid])
    second = sum(scores[mid:]) / len(scores[mid:])
    diff   = second - first

    if diff >= 0.1:
        drift   = "improving"
        message = "Your overall emotional tone has been improving recently."
    elif diff <= -0.1:
        drift   = "declining"
        message = "Your overall emotional tone has been declining. Worth paying attention to."
    else:
        drift   = "stable"
        message = "Your emotional tone has been relatively stable over this period."

    return {
        "scores":  scores,
        "drift":   drift,
        "message": message
    }


# ---------------------------------------------------------------------------
# MASTER FUNCTION
# ---------------------------------------------------------------------------

def run_pattern_analysis(entries, all_nlp_results):
    """
    Runs all pattern analyses and returns a single combined result.
    This is what report_generator and intervention modules will call.

    Parameters:
        entries         (list): All raw journal entries from collector
        all_nlp_results (list): All NLP results from nlp_processor

    Returns:
        Full pattern analysis dict
    """
    return {
        "mood_trend":       get_mood_trend(entries),
        "energy_trend":     get_energy_trend(entries),
        "sleep_impact":     analyze_sleep_impact(entries),
        "day_of_week":      analyze_day_of_week(entries),
        "recurring_themes": get_recurring_themes(all_nlp_results),
        "sentiment_drift":  get_sentiment_drift(all_nlp_results)
    }