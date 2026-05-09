# modules/report_generator.py
# ---------------------------------------------------------------------------
# Generates a weekly psychological report by compiling results from:
#   - collector       (raw entries)
#   - nlp_processor   (sentiment, keywords, emotion)
#   - distortion_detector (CBT pattern history)
#   - pattern_detector    (behavioral trends)
#   - predictor           (mood/energy forecast)
#   - intervention        (personalized suggestions)
#
# Report is saved as a .txt file in data/reports/
# ---------------------------------------------------------------------------

import sys
import os
import json
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from modules.nlp_processor       import process_journal
from modules.distortion_detector import detect_distortions, get_distortion_history
from modules.pattern_detector    import run_pattern_analysis
from modules.predictor           import run_predictions
from modules.intervention        import run_interventions
from modules.collector           import load_all_entries


# ---------------------------------------------------------------------------
# SECTION BUILDERS
# Each function builds one section of the report as a string
# ---------------------------------------------------------------------------

def build_header(entry_count, date_str):
    """Builds the top header of the report."""
    lines = [
        "=" * 60,
        f"  {config.APP_NAME}",
        f"  Weekly Psychological Report",
        f"  Generated: {date_str}",
        f"  Entries analyzed: {entry_count} days",
        "=" * 60,
        ""
    ]
    return "\n".join(lines)


def build_overview(entries):
    """
    Builds the overview section showing average mood,
    energy, and sleep across the week.
    """
    moods   = [e.get("mood", 0)         for e in entries]
    energys = [e.get("energy", 0)       for e in entries]
    sleeps  = [e.get("sleep_hours", 0)  for e in entries]

    avg_mood   = round(sum(moods)   / len(moods),   2) if moods   else 0
    avg_energy = round(sum(energys) / len(energys), 2) if energys else 0
    avg_sleep  = round(sum(sleeps)  / len(sleeps),  2) if sleeps  else 0

    # Mood label
    if avg_mood >= 7:
        mood_label = "Good"
    elif avg_mood >= 4:
        mood_label = "Moderate"
    else:
        mood_label = "Low — worth attention"

    lines = [
        "SECTION 1 — WEEKLY OVERVIEW",
        "-" * 40,
        f"Average Mood   : {avg_mood}/10  ({mood_label})",
        f"Average Energy : {avg_energy}/10",
        f"Average Sleep  : {avg_sleep} hours/night",
        ""
    ]
    return "\n".join(lines)


def build_mood_energy_log(entries):
    """
    Builds a day-by-day log of mood, energy, and sleep.
    """
    lines = [
        "SECTION 2 — DAILY LOG",
        "-" * 40
    ]

    for entry in entries:
        lines.append(
            f"  {entry.get('date','?')} ({entry.get('day_of_week','?')}) | "
            f"Mood: {entry.get('mood','?')}/10 | "
            f"Energy: {entry.get('energy','?')}/10 | "
            f"Sleep: {entry.get('sleep_hours','?')}h"
        )

    lines.append("")
    return "\n".join(lines)


def build_sentiment_section(all_nlp_results, entries):
    """
    Builds the emotional tone section showing sentiment
    and dominant emotion per day.
    """
    lines = [
        "SECTION 3 — EMOTIONAL TONE ANALYSIS",
        "-" * 40
    ]

    for i, result in enumerate(all_nlp_results):
        date      = entries[i].get("date", "?") if i < len(entries) else "?"
        sentiment = result.get("sentiment", {})
        emotion   = result.get("emotion",   {})

        lines.append(
            f"  {date} | "
            f"Sentiment: {sentiment.get('label','?')} "
            f"({sentiment.get('compound_score','?')}) | "
            f"Emotion: {emotion.get('dominant_emotion','?')}"
        )

    lines.append("")
    return "\n".join(lines)


def build_distortion_section(distortion_history):
    """
    Builds the cognitive distortion summary section.
    """
    freq_map    = distortion_history.get("frequency_map", {})
    most_common = distortion_history.get("most_common",   "None")
    flagged     = distortion_history.get("total_flagged", 0)

    lines = [
        "SECTION 4 — COGNITIVE DISTORTION ANALYSIS",
        "-" * 40,
        f"Days with distortions detected : {flagged}",
        f"Most frequently occurring      : {most_common}",
        "",
        "Distortion frequency breakdown:",
    ]

    for distortion, count in freq_map.items():
        if count > 0:
            lines.append(f"  {distortion:<25} : {count} day(s)")

    if all(v == 0 for v in freq_map.values()):
        lines.append("  No distortions detected across this period.")

    lines.append("")
    return "\n".join(lines)


def build_pattern_section(pattern_results):
    """
    Builds the behavioral patterns section.
    """
    mood_trend   = pattern_results.get("mood_trend",   {})
    energy_trend = pattern_results.get("energy_trend", {})
    sleep_impact = pattern_results.get("sleep_impact", {})
    day_of_week  = pattern_results.get("day_of_week",  {})
    themes       = pattern_results.get("recurring_themes", [])
    sent_drift   = pattern_results.get("sentiment_drift",  {})

    lines = [
        "SECTION 5 — BEHAVIORAL PATTERNS",
        "-" * 40,
        f"Mood trend     : {mood_trend.get('trend','?').upper()}",
        f"  Scores       : {mood_trend.get('scores',[])}",
        f"  Average      : {mood_trend.get('average','?')}/10",
        "",
        f"Energy trend   : {energy_trend.get('trend','?').upper()}",
        f"  Scores       : {energy_trend.get('scores',[])}",
        f"  Average      : {energy_trend.get('average','?')}/10",
        "",
        f"Sentiment drift: {sent_drift.get('drift','?').upper()}",
        f"  {sent_drift.get('message','')}",
        "",
        f"Sleep impact   : {sleep_impact.get('message','')}",
        "",
        f"Best day of week  : {day_of_week.get('best_day','?')}",
        f"Worst day of week : {day_of_week.get('worst_day','?')}",
        "",
        f"Recurring life themes : {', '.join(themes) if themes else 'None detected'}",
        ""
    ]
    return "\n".join(lines)


def build_prediction_section(prediction_results):
    """
    Builds the prediction and risk flags section.
    """
    mood_pred   = prediction_results.get("mood_prediction",   {})
    energy_pred = prediction_results.get("energy_prediction", {})
    risk        = prediction_results.get("risk_flags",        {})

    lines = [
        "SECTION 6 — PREDICTIONS",
        "-" * 40,
        f"Predicted mood tomorrow   : "
        f"{mood_pred.get('predicted_mood','Insufficient data')}/10 "
        f"(confidence: {mood_pred.get('confidence','?')})",
        f"Predicted energy tomorrow : "
        f"{energy_pred.get('predicted_energy','Insufficient data')}/10 "
        f"(confidence: {energy_pred.get('confidence','?')})",
        ""
    ]

    # Risk flags
    flags = risk.get("flags", [])
    if flags:
        lines.append("RISK FLAGS:")
        for flag in flags:
            lines.append(f"  {flag}")
    else:
        lines.append("Risk flags: None detected this week.")

    lines.append("")
    return "\n".join(lines)


def build_intervention_section(intervention_results):
    """
    Builds the personalized interventions section.
    """
    lines = [
        "SECTION 7 — PERSONALIZED INTERVENTIONS",
        "-" * 40,
        ""
    ]

    interventions = intervention_results.get("interventions", [])
    for i, item in enumerate(interventions, 1):
        lines.append(f"{i}. {item['title']}")
        lines.append(f"   {item['message']}")
        lines.append(f"   Framework: {item['framework']}")
        lines.append("")

    return "\n".join(lines)


def build_footer():
    """Builds the report footer."""
    lines = [
        "=" * 60,
        "  This report is generated by your Psychological Digital Twin.",
        "  It is for personal reflection only — not clinical diagnosis.",
        "  If you are struggling, please speak to a mental health professional.",
        "=" * 60
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MASTER REPORT GENERATOR
# ---------------------------------------------------------------------------

def generate_weekly_report():
    """
    Orchestrates the full weekly report generation.

    Steps:
        1. Load all journal entries
        2. Run NLP on each entry
        3. Run distortion detection on each entry
        4. Run pattern analysis across all entries
        5. Run predictions
        6. Run interventions
        7. Assemble all sections into one report
        8. Save to data/reports/

    Returns:
        report_text (str) : Full report as a string
        filepath    (str) : Where the report was saved
    """

    # --- Load entries ---
    entries = load_all_entries()

    if len(entries) < config.BASELINE_DAYS:
        return {
            "report_text": (
                f"Not enough data to generate a report yet.\n"
                f"You need at least {config.BASELINE_DAYS} journal entries.\n"
                f"Current entries: {len(entries)}"
            ),
            "filepath": None
        }

    # --- Run NLP on all entries ---
    all_nlp_results = []
    all_distortion_results = []

    for entry in entries:
        journal_text = entry.get("journal", "")
        nlp_result   = process_journal(journal_text)
        dist_result  = detect_distortions(journal_text)

        # Attach distortions into NLP result for history analysis
        nlp_result["distortions"] = dist_result
        all_nlp_results.append(nlp_result)
        all_distortion_results.append({"distortions": dist_result})

    # --- Run all analysis modules ---
    pattern_results      = run_pattern_analysis(entries, all_nlp_results)
    prediction_results   = run_predictions(entries, all_nlp_results)
    distortion_history   = get_distortion_history(all_distortion_results)
    intervention_results = run_interventions(
        pattern_results,
        prediction_results,
        all_distortion_results[-1].get("distortions", {})
    )

    # --- Assemble report ---
    date_str    = datetime.now().strftime("%Y-%m-%d %H:%M")
    report_text = "\n".join([
        build_header(len(entries), date_str),
        build_overview(entries),
        build_mood_energy_log(entries),
        build_sentiment_section(all_nlp_results, entries),
        build_distortion_section(distortion_history),
        build_pattern_section(pattern_results),
        build_prediction_section(prediction_results),
        build_intervention_section(intervention_results),
        build_footer()
    ])

    # --- Save report ---
    os.makedirs(config.REPORTS_DIR, exist_ok=True)
    filename = f"report_{datetime.now().strftime('%Y-%m-%d')}.txt"
    filepath = os.path.join(config.REPORTS_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report_text)

    return {
        "report_text": report_text,
        "filepath":    filepath
    }