# modules/intervention.py
# ---------------------------------------------------------------------------
# Generates personalized psychological interventions based on:
#   - Mood and energy trends
#   - Sleep impact analysis
#   - Cognitive distortions detected
#   - Sentiment drift
#   - Risk flags
#
# All interventions are grounded in evidence-based psychology frameworks:
#   - CBT (Cognitive Behavioral Therapy)
#   - Behavioral Activation
#   - Sleep Hygiene research
#   - Positive Psychology
#
# IMPORTANT: This module never gives advice before baseline is reached.
# ---------------------------------------------------------------------------

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


# ---------------------------------------------------------------------------
# INTERVENTION LIBRARY
# Each intervention has:
#   - trigger  : what condition activates it
#   - title    : short label
#   - message  : what the user sees
#   - framework: which psychology framework it comes from
# ---------------------------------------------------------------------------

INTERVENTIONS = {

    "declining_mood": {
        "title":     "Your mood has been declining",
        "message": (
            "Your mood scores have been trending downward over recent days. "
            "This is a signal worth paying attention to — not a cause for alarm. \n\n"
            "Try **Behavioral Activation**: choose one small activity today that "
            "you know has brought you joy or satisfaction before, even if you don't "
            "feel motivated right now. Action often precedes motivation, not the other way around."
        ),
        "framework": "Behavioral Activation (CBT)"
    },

    "declining_energy": {
        "title":     "Your energy has been dropping",
        "message": (
            "Your energy levels have been consistently lower recently. "
            "Low energy affects focus, decision-making, and emotional resilience. \n\n"
            "Check: Are you moving your body at all during the day? Even a 10-minute "
            "walk has measurable impact on energy levels. Also review your last 3 nights "
            "of sleep — energy debt accumulates faster than most people realize."
        ),
        "framework": "Behavioral Psychology + Sleep Science"
    },

    "sleep_mood_correlation": {
        "title":     "Sleep is affecting your mood",
        "message": (
            "Your data shows a clear pattern: on days when you sleep less, "
            "your mood tends to drop. This is one of the strongest and most "
            "consistent findings in sleep research. \n\n"
            "Focus on one thing this week: keep your sleep and wake time consistent "
            "— even on weekends. Consistency in sleep timing has a stronger impact "
            "than total sleep hours alone."
        ),
        "framework": "Sleep Hygiene Research"
    },

    "negative_sentiment_drift": {
        "title":     "Your journal tone has been getting darker",
        "message": (
            "The emotional tone of your journal entries has been shifting "
            "in a more negative direction over recent days. \n\n"
            "Try a **Gratitude Reframe**: before your next journal entry, write "
            "3 things that happened today — however small — that were okay or good. "
            "This is not toxic positivity. It is training your attention to notice "
            "the full picture, not just what went wrong."
        ),
        "framework": "Positive Psychology (Seligman)"
    },

    "catastrophizing": {
        "title":     "Catastrophizing detected in your journal",
        "message": (
            "Your writing shows signs of catastrophizing — imagining worst-case "
            "scenarios as if they are certain. \n\n"
            "CBT technique: Ask yourself — **'What is the actual probability this "
            "happens? What would I tell a friend in this situation?'** "
            "Writing down the realistic best, worst, and most likely outcome "
            "can interrupt the spiral before it takes hold."
        ),
        "framework": "CBT — Cognitive Restructuring"
    },

    "black_white_thinking": {
        "title":     "All-or-nothing thinking noticed",
        "message": (
            "Words like 'always', 'never', 'everyone', 'no one' appeared in your journal. "
            "These are markers of black-and-white thinking — collapsing nuance into extremes. \n\n"
            "Practice: When you catch yourself using absolute words, pause and ask — "
            "'Is this literally true, or does it just feel that way right now?' "
            "Replace one absolute word with something more accurate."
        ),
        "framework": "CBT — Cognitive Distortion Correction"
    },

    "self_blame": {
        "title":     "You may be being too hard on yourself",
        "message": (
            "Your journal shows signs of self-blame — taking on responsibility "
            "for outcomes that were not entirely in your control. \n\n"
            "Try the **Responsibility Pie**: list all the factors that contributed "
            "to the situation. Give each a percentage. You'll usually find your "
            "share is smaller than it feels. This isn't about avoiding accountability "
            "— it's about accurate accountability."
        ),
        "framework": "CBT — Self-Compassion Techniques"
    },

    "should_statements": {
        "title":     "You're putting a lot of pressure on yourself",
        "message": (
            "'Should', 'must', 'have to' — these words create internal pressure "
            "that often leads to guilt when unmet and resentment when forced. \n\n"
            "Reframe: Replace 'I should' with 'I want to' or 'I choose to' — "
            "or honestly ask if this is something you actually value or just "
            "something you feel externally pressured to do."
        ),
        "framework": "CBT — Language Reframing"
    },

    "fortune_telling": {
        "title":     "You may be predicting failure before it happens",
        "message": (
            "Your journal contains language that predicts negative outcomes "
            "with certainty — before anything has happened. \n\n"
            "Ask yourself: 'What evidence do I actually have for this outcome? "
            "Have I been wrong about predicted outcomes before?' "
            "Write down one alternative way this situation could unfold."
        ),
        "framework": "CBT — Decatastrophizing"
    },

    "low_mood_streak": {
        "title":     "Your mood has been low for several days",
        "message": (
            "Your mood has been below 4 out of 10 for 3 or more consecutive days. "
            "This is worth taking seriously — not as a diagnosis, but as a signal. \n\n"
            "Please consider reaching out to someone you trust — a friend, family member, "
            "or counselor. You don't need to be in crisis to deserve support. "
            "Talking to someone is one of the most evidence-backed things you can do."
        ),
        "framework": "Clinical Psychology — Early Intervention"
    },

    "stable_positive": {
        "title":     "You're doing well — keep it consistent",
        "message": (
            "Your mood, energy, and journal tone have been stable and positive. "
            "This is genuinely good. \n\n"
            "Positive psychology finding: people who actively reflect on *why* "
            "things are going well (not just that they are) tend to sustain it longer. "
            "Take a moment to note what's been working — your routines, relationships, "
            "or mindset. These are worth protecting."
        ),
        "framework": "Positive Psychology"
    }

}


# ---------------------------------------------------------------------------
# INTERVENTION SELECTOR
# ---------------------------------------------------------------------------

def select_interventions(pattern_results, prediction_results, distortion_results):
    """
    Looks at all analysis results and selects the most relevant
    interventions for this individual at this point in time.

    Priority order:
        1. Risk flags (most urgent)
        2. Cognitive distortions (most psychology-specific)
        3. Mood / energy trends
        4. Sleep impact
        5. Sentiment drift
        6. Positive reinforcement if all is well

    Parameters:
        pattern_results    (dict): Output from pattern_detector.run_pattern_analysis()
        prediction_results (dict): Output from predictor.run_predictions()
        distortion_results (dict): Output from distortion_detector.detect_distortions()

    Returns:
        selected (list): List of intervention dicts to show the user
    """
    selected = []

    # --- 1. Risk Flags (highest priority) ---
    risk = prediction_results.get("risk_flags", {})
    if risk.get("flagged"):
        selected.append(INTERVENTIONS["low_mood_streak"])

    # --- 2. Cognitive Distortions ---
    detected_distortions = distortion_results.get("detected", [])

    distortion_map = {
        "Catastrophizing":       "catastrophizing",
        "Black & White Thinking":"black_white_thinking",
        "Self Blame":            "self_blame",
        "Should Statements":     "should_statements",
        "Fortune Telling":       "fortune_telling"
    }

    for distortion_name, key in distortion_map.items():
        if distortion_name in detected_distortions:
            selected.append(INTERVENTIONS[key])

    # --- 3. Mood Trend ---
    mood_trend = pattern_results.get("mood_trend", {}).get("trend", "stable")
    if mood_trend == "declining":
        selected.append(INTERVENTIONS["declining_mood"])

    # --- 4. Energy Trend ---
    energy_trend = pattern_results.get("energy_trend", {}).get("trend", "stable")
    if energy_trend == "declining":
        selected.append(INTERVENTIONS["declining_energy"])

    # --- 5. Sleep Impact ---
    sleep_corr = pattern_results.get("sleep_impact", {}).get("correlation_flag", False)
    if sleep_corr:
        selected.append(INTERVENTIONS["sleep_mood_correlation"])

    # --- 6. Sentiment Drift ---
    drift = pattern_results.get("sentiment_drift", {}).get("drift", "stable")
    if drift == "declining":
        selected.append(INTERVENTIONS["negative_sentiment_drift"])

    # --- 7. Positive Reinforcement (if nothing negative triggered) ---
    if not selected:
        selected.append(INTERVENTIONS["stable_positive"])

    # Remove duplicates while preserving order
    seen   = set()
    unique = []
    for item in selected:
        key = item["title"]
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique


def format_interventions(interventions):
    """
    Formats the selected interventions into a clean readable string
    for display in the app and in weekly reports.

    Returns:
        str: Formatted intervention text
    """
    if not interventions:
        return "No specific interventions triggered today."

    lines = []
    for i, intervention in enumerate(interventions, 1):
        lines.append(f"### {i}. {intervention['title']}")
        lines.append(intervention["message"])
        lines.append(f"*Framework: {intervention['framework']}*")
        lines.append("")

    return "\n".join(lines)


def run_interventions(pattern_results, prediction_results, distortion_results):
    """
    Master function — selects and formats all interventions.
    This is what app.py and report_generator will call.

    Returns:
        interventions (list): Raw intervention dicts
        formatted     (str) : Display-ready text
    """
    interventions = select_interventions(
        pattern_results,
        prediction_results,
        distortion_results
    )

    return {
        "interventions": interventions,
        "formatted":     format_interventions(interventions),
        "count":         len(interventions)
    }