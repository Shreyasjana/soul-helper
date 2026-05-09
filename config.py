# config.py
# ---------------------------------------------------------------------------
# Central settings file for the Psychological Digital Twin
# Think of this as the "control panel" of the entire system
# ---------------------------------------------------------------------------

import os

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Root project folder
DATA_DIR = os.path.join(BASE_DIR, "data")
JOURNAL_DIR = os.path.join(DATA_DIR, "journals")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")
MODELS_DIR = os.path.join(DATA_DIR, "models")

# --- Baseline Rule ---
# System will NOT give any advice or predictions until this many days of data exist
BASELINE_DAYS = 7

# --- Mood Scale ---
# User rates mood from 1 to 10
MOOD_MIN = 1
MOOD_MAX = 10

# --- Energy Scale ---
# User rates energy from 1 to 10
ENERGY_MIN = 1
ENERGY_MAX = 10

# --- Sleep ---
# Healthy sleep range in hours
SLEEP_MIN = 4
SLEEP_MAX = 12

# --- NLP Settings ---
# Sentiment score thresholds (from TextBlob, range is -1.0 to +1.0)
POSITIVE_THRESHOLD = 0.2
NEGATIVE_THRESHOLD = -0.2

# --- Cognitive Distortions ---
# These are the 10 classic distortions from CBT (Cognitive Behavioral Therapy)
# Each has keyword patterns we'll scan for in journal text
DISTORTIONS = {
    "Catastrophizing": ["worst", "disaster", "ruined", "everything is over", "nothing will work"],
    "Black & White Thinking": ["always", "never", "everyone", "no one", "completely", "totally"],
    "Mind Reading": ["they think", "he thinks", "she thinks", "people think", "everyone thinks"],
    "Overgeneralization": ["every time", "nothing ever", "always happens", "this always"],
    "Emotional Reasoning": ["i feel like a failure", "i feel stupid", "i feel worthless"],
    "Self Blame": ["my fault", "i ruined", "because of me", "i caused"],
    "Fortune Telling": ["i will fail", "it won't work", "i know it'll go wrong", "i'll never"],
    "Filtering": ["nothing good", "only bad things", "no point"],
    "Should Statements": ["i should", "i must", "i have to", "i ought to"],
    "Labelling": ["i am a loser", "i am stupid", "i am a failure", "i am worthless"]
}

# --- Report Settings ---
WEEK_DAYS = 7  # Generate report every 7 days

# --- App Info ---
APP_NAME = "Psychological Digital Twin"
VERSION = "0.1.0"