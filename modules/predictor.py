# modules/predictor.py
# ---------------------------------------------------------------------------
# Predicts next-day mood and energy based on recent behavioral history.
#
# Approach:
#   - Weighted moving average (recent days matter more than older ones)
#   - Sleep adjustment (low sleep pulls prediction down)
#   - Sentiment adjustment (negative journal tone pulls prediction down)
#   - Confidence score (higher with more data)
#
# Only runs after BASELINE_DAYS entries exist.
# ---------------------------------------------------------------------------

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


# ---------------------------------------------------------------------------
# CORE PREDICTION ENGINE
# ---------------------------------------------------------------------------

def weighted_average(values):
    """
    Calculates a weighted average where recent values matter more.

    Example with 3 values [5, 6, 8]:
        weights = [1, 2, 3]
        result  = (5*1 + 6*2 + 8*3) / (1+2+3) = 37/6 = 6.17

    This reflects the psychological principle that recent behavior
    is a stronger predictor than older behavior.

    Parameters:
        values (list): Chronological list of numbers

    Returns:
        float: Weighted average
    """
    if not values:
        return 5.0  # neutral default

    weights = list(range(1, len(values) + 1))
    weighted_sum   = sum(v * w for v, w in zip(values, weights))
    total_weight   = sum(weights)
    return round(weighted_sum / total_weight, 2)


def get_confidence(entry_count):
    """
    Returns a confidence level based on how many entries exist.
    More data = higher confidence in predictions.

    Levels:
        < 7  days  : should not be predicting (baseline not reached)
        7–13 days  : low confidence
        14–20 days : moderate confidence
        21+ days   : high confidence

    Returns:
        confidence_label (str) : "low", "moderate", or "high"
        confidence_score (float): 0.0 to 1.0
    """
    if entry_count < config.BASELINE_DAYS:
        return "insufficient", 0.0
    elif entry_count < 14:
        score = 0.4
        label = "low"
    elif entry_count < 21:
        score = 0.7
        label = "moderate"
    else:
        score = 0.9
        label = "high"

    return label, score


# ---------------------------------------------------------------------------
# MOOD PREDICTION
# ---------------------------------------------------------------------------

def predict_mood(entries, all_nlp_results):
    """
    Predicts tomorrow's mood using:
        1. Weighted average of past mood scores
        2. Sleep adjustment: if last night's sleep was low, nudge down
        3. Sentiment adjustment: if recent journal tone is negative, nudge down

    Parameters:
        entries         (list): Raw journal entries from collector
        all_nlp_results (list): NLP results from nlp_processor

    Returns:
        predicted_mood  (float): Predicted mood score (1–10)
        adjustments     (dict) : What factors pulled the score up or down
        confidence      (str)  : "low", "moderate", or "high"
    """
    mood_scores = [e["mood"] for e in entries if "mood" in e]

    if len(mood_scores) < config.BASELINE_DAYS:
        return {
            "predicted_mood": None,
            "message": "Not enough data yet. Keep journaling.",
            "confidence": "insufficient"
        }

    # Base prediction: weighted average of all mood scores
    base = weighted_average(mood_scores)
    adjustments = {}

    # --- Sleep Adjustment ---
    # If last recorded sleep was under 6 hours, pull mood prediction down
    last_sleep = entries[-1].get("sleep_hours", 7)
    sleep_adj  = 0
    if last_sleep < 6:
        sleep_adj = -0.8
        adjustments["sleep"] = f"Low sleep ({last_sleep}h) → mood adjusted down by 0.8"
    elif last_sleep >= 8:
        sleep_adj = +0.3
        adjustments["sleep"] = f"Good sleep ({last_sleep}h) → mood adjusted up by 0.3"

    # --- Sentiment Adjustment ---
    # If last journal entry was negative, pull mood prediction down
    sentiment_adj = 0
    if all_nlp_results:
        last_sentiment = all_nlp_results[-1].get("sentiment", {}).get("compound_score", 0)
        if last_sentiment <= config.NEGATIVE_THRESHOLD:
            sentiment_adj = -0.5
            adjustments["sentiment"] = f"Negative journal tone ({last_sentiment}) → mood adjusted down by 0.5"
        elif last_sentiment >= config.POSITIVE_THRESHOLD:
            sentiment_adj = +0.3
            adjustments["sentiment"] = f"Positive journal tone ({last_sentiment}) → mood adjusted up by 0.3"

    # Final predicted mood (clamped between 1 and 10)
    predicted = base + sleep_adj + sentiment_adj
    predicted = round(max(config.MOOD_MIN, min(config.MOOD_MAX, predicted)), 2)

    confidence_label, _ = get_confidence(len(entries))

    return {
        "predicted_mood": predicted,
        "base_average":   base,
        "adjustments":    adjustments,
        "confidence":     confidence_label,
        "message": f"Predicted mood for tomorrow: {predicted}/10 (confidence: {confidence_label})"
    }


# ---------------------------------------------------------------------------
# ENERGY PREDICTION
# ---------------------------------------------------------------------------

def predict_energy(entries, all_nlp_results):
    """
    Predicts tomorrow's energy using same logic as mood prediction.
    Sleep is an even stronger predictor of energy than mood.

    Returns:
        predicted_energy (float): Predicted energy score (1–10)
        adjustments      (dict) : Factors that shifted the score
        confidence       (str)  : Confidence level
    """
    energy_scores = [e["energy"] for e in entries if "energy" in e]

    if len(energy_scores) < config.BASELINE_DAYS:
        return {
            "predicted_energy": None,
            "message": "Not enough data yet. Keep journaling.",
            "confidence": "insufficient"
        }

    base = weighted_average(energy_scores)
    adjustments = {}

    # --- Sleep Adjustment (stronger for energy than mood) ---
    last_sleep = entries[-1].get("sleep_hours", 7)
    sleep_adj  = 0
    if last_sleep < 5:
        sleep_adj = -1.5
        adjustments["sleep"] = f"Very low sleep ({last_sleep}h) → energy adjusted down by 1.5"
    elif last_sleep < 6:
        sleep_adj = -0.8
        adjustments["sleep"] = f"Low sleep ({last_sleep}h) → energy adjusted down by 0.8"
    elif last_sleep >= 8:
        sleep_adj = +0.5
        adjustments["sleep"] = f"Good sleep ({last_sleep}h) → energy adjusted up by 0.5"

    # --- Mood Adjustment (mood and energy are correlated) ---
    mood_adj = 0
    last_mood = entries[-1].get("mood", 5)
    if last_mood < 4:
        mood_adj = -0.5
        adjustments["mood"] = f"Low mood ({last_mood}/10) → energy adjusted down by 0.5"
    elif last_mood >= 8:
        mood_adj = +0.3
        adjustments["mood"] = f"High mood ({last_mood}/10) → energy adjusted up by 0.3"

    # Final predicted energy (clamped between 1 and 10)
    predicted = base + sleep_adj + mood_adj
    predicted = round(max(config.ENERGY_MIN, min(config.ENERGY_MAX, predicted)), 2)

    confidence_label, _ = get_confidence(len(entries))

    return {
        "predicted_energy": predicted,
        "base_average":     base,
        "adjustments":      adjustments,
        "confidence":       confidence_label,
        "message": f"Predicted energy for tomorrow: {predicted}/10 (confidence: {confidence_label})"
    }


# ---------------------------------------------------------------------------
# RISK FLAG
# ---------------------------------------------------------------------------

def check_risk_flags(entries, all_nlp_results):
    """
    Checks for early warning signs that need attention.
    These are not diagnoses — they are signals to be aware of.

    Flags:
        - Mood below 4 for 3+ consecutive days
        - Negative sentiment for 3+ consecutive days
        - Sleep below 5 hours for 3+ consecutive days
        - 3+ cognitive distortions detected in last 3 days

    Returns:
        flags   (list): List of active warning messages
        flagged (bool): True if any risk is detected
    """
    flags = []

    # Only check last 3 entries
    recent = entries[-3:] if len(entries) >= 3 else entries
    recent_nlp = all_nlp_results[-3:] if len(all_nlp_results) >= 3 else all_nlp_results

    # --- Low mood streak ---
    moods = [e.get("mood", 5) for e in recent]
    if all(m < 4 for m in moods):
        flags.append(
            "⚠️  Your mood has been low (below 4/10) for 3 or more days. "
            "Consider speaking to someone you trust."
        )

    # --- Negative sentiment streak ---
    sentiments = [
        r.get("sentiment", {}).get("compound_score", 0)
        for r in recent_nlp
    ]
    if all(s <= config.NEGATIVE_THRESHOLD for s in sentiments):
        flags.append(
            "⚠️  Your journal tone has been consistently negative. "
            "This may reflect accumulated stress or emotional fatigue."
        )

    # --- Low sleep streak ---
    sleeps = [e.get("sleep_hours", 7) for e in recent]
    if all(s < 5 for s in sleeps):
        flags.append(
            "⚠️  You have slept under 5 hours for 3+ consecutive days. "
            "Chronic sleep deprivation significantly impacts cognition and mood."
        )

    return {
        "flags":   flags,
        "flagged": len(flags) > 0
    }


# ---------------------------------------------------------------------------
# MASTER FUNCTION
# ---------------------------------------------------------------------------

def run_predictions(entries, all_nlp_results):
    """
    Runs all predictions and risk checks.
    This is what app.py and report_generator will call.

    Returns:
        Combined prediction result dict
    """
    return {
        "mood_prediction":   predict_mood(entries, all_nlp_results),
        "energy_prediction": predict_energy(entries, all_nlp_results),
        "risk_flags":        check_risk_flags(entries, all_nlp_results)
    }