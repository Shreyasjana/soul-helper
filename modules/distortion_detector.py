# modules/distortion_detector.py
# ---------------------------------------------------------------------------
# Detects cognitive distortions in journal text using CBT framework.
# Cognitive distortions are irrational thinking patterns that negatively
# affect emotions and behavior — identified by Aaron Beck & David Burns.
#
# The 10 distortions we detect are loaded from config.py (DISTORTIONS dict)
# ---------------------------------------------------------------------------

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from nltk.tokenize import word_tokenize, sent_tokenize
import nltk

nltk.download('punkt',     quiet=True)
nltk.download('punkt_tab', quiet=True)


# ---------------------------------------------------------------------------
# Plain English explanations shown to the user for each distortion.
# We never show clinical jargon directly — always explain what it means.
# ---------------------------------------------------------------------------
DISTORTION_EXPLANATIONS = {
    "Catastrophizing": (
        "You may be imagining the worst possible outcome. "
        "Things might not be as severe as they feel right now."
    ),
    "Black & White Thinking": (
        "You may be seeing things as all-or-nothing. "
        "Most situations exist on a spectrum, not at extremes."
    ),
    "Mind Reading": (
        "You may be assuming what others think without actual evidence. "
        "People's thoughts are rarely what we imagine them to be."
    ),
    "Overgeneralization": (
        "You may be drawing broad conclusions from a single event. "
        "One bad experience doesn't define a pattern."
    ),
    "Emotional Reasoning": (
        "You may be treating feelings as facts. "
        "Feeling like a failure doesn't mean you are one."
    ),
    "Self Blame": (
        "You may be taking excessive responsibility for things outside your control. "
        "Not everything that goes wrong is your fault."
    ),
    "Fortune Telling": (
        "You may be predicting a negative future with false certainty. "
        "The future is genuinely unknown — outcomes surprise us constantly."
    ),
    "Filtering": (
        "You may be focusing only on the negatives while ignoring positives. "
        "Try to look at the full picture of your situation."
    ),
    "Should Statements": (
        "You may be putting rigid pressure on yourself with 'should' and 'must'. "
        "These often create guilt and frustration rather than motivation."
    ),
    "Labelling": (
        "You may be defining yourself by a single event or feeling. "
        "You are not a label — you are a person with complex experiences."
    )
}


def detect_distortions(text):
    """
    Scans journal text for cognitive distortions defined in config.DISTORTIONS.

    For each distortion type, it checks if any of its trigger phrases
    appear anywhere in the lowercased journal text.

    Returns:
        detected        (list): Names of distortions found
        details         (dict): For each found distortion — matched phrases
                                and the explanation to show the user
        distortion_count(int) : Total number of distortions found
        clean           (bool): True if no distortions were detected
    """
    text_lower = text.lower()

    detected = []
    details  = {}

    for distortion_name, trigger_phrases in config.DISTORTIONS.items():
        matched_phrases = []

        for phrase in trigger_phrases:
            if phrase in text_lower:
                matched_phrases.append(phrase)

        if matched_phrases:
            detected.append(distortion_name)
            details[distortion_name] = {
                "matched_phrases": matched_phrases,
                "explanation":     DISTORTION_EXPLANATIONS.get(distortion_name, "")
            }

    return {
        "detected":         detected,
        "details":          details,
        "distortion_count": len(detected),
        "clean":            len(detected) == 0
    }


def get_distortion_summary(detection_result):
    """
    Converts the detection result into a clean, human-readable summary.
    This is what gets displayed to the user in the app and in reports.

    Parameters:
        detection_result (dict): Output from detect_distortions()

    Returns:
        summary (str): A readable multi-line summary
    """
    if detection_result["clean"]:
        return "No cognitive distortions detected in today's entry. Your thinking patterns look balanced."

    lines = []
    lines.append(f"⚠️  {detection_result['distortion_count']} cognitive distortion(s) noticed in your journal:\n")

    for distortion in detection_result["detected"]:
        info = detection_result["details"][distortion]
        lines.append(f"🔸 {distortion}")
        lines.append(f"   Triggered by: {', '.join(info['matched_phrases'])}")
        lines.append(f"   {info['explanation']}")
        lines.append("")  # blank line between distortions

    return "\n".join(lines)


def get_distortion_history(all_entries_nlp):
    """
    Analyzes distortion patterns across all journal entries over time.
    Used by pattern_detector and report_generator.

    Parameters:
        all_entries_nlp (list): List of dicts, each containing a
                                'distortions' key from past entries

    Returns:
        frequency_map (dict): How many times each distortion appeared
        most_common   (str) : The distortion that appeared most often
        total_flagged (int) : Number of days with at least one distortion
    """
    frequency_map = {name: 0 for name in config.DISTORTIONS.keys()}
    total_flagged = 0

    for entry in all_entries_nlp:
        distortions = entry.get("distortions", {})
        detected    = distortions.get("detected", [])

        if detected:
            total_flagged += 1
            for d in detected:
                if d in frequency_map:
                    frequency_map[d] += 1

    # Find the most commonly occurring distortion
    most_common = max(frequency_map, key=frequency_map.get)
    if frequency_map[most_common] == 0:
        most_common = "None"

    return {
        "frequency_map": frequency_map,
        "most_common":   most_common,
        "total_flagged": total_flagged
    }