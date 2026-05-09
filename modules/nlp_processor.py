# modules/nlp_processor.py
# ---------------------------------------------------------------------------
# Reads journal text and extracts:
#   1. Sentiment score (positive / negative / neutral)
#   2. Keywords (meaningful words, filler removed)
#   3. Dominant emotion (joy, anger, fear, sadness, surprise, neutral)
# ---------------------------------------------------------------------------

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from textblob import TextBlob
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
import nltk

# Download required NLTK data if not already present
nltk.download('vader_lexicon', quiet=True)
nltk.download('stopwords', quiet=True)
nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)

# ---------------------------------------------------------------------------
# Emotion keyword map
# These are psychology-informed word lists for each basic emotion.
# The system checks which emotion's keywords appear most in the journal.
# ---------------------------------------------------------------------------
EMOTION_KEYWORDS = {
    "joy":      ["happy", "excited", "grateful", "great", "amazing", "love",
                 "wonderful", "fantastic", "cheerful", "proud", "content",
                 "blessed", "positive", "energetic", "motivated"],

    "sadness":  ["sad", "unhappy", "depressed", "lonely", "hopeless", "cry",
                 "crying", "grief", "loss", "empty", "miserable", "down",
                 "heartbroken", "disappointed", "devastated"],

    "anger":    ["angry", "frustrated", "annoyed", "irritated", "furious",
                 "rage", "hate", "mad", "bitter", "resentful", "hostile",
                 "aggressive", "outraged", "fed up"],

    "fear":     ["scared", "anxious", "nervous", "worried", "panic", "afraid",
                 "terror", "dread", "overwhelmed", "stressed", "uneasy",
                 "insecure", "fearful", "tense", "apprehensive"],

    "surprise": ["shocked", "surprised", "unexpected", "suddenly", "amazed",
                 "astonished", "unbelievable", "wow", "incredible", "stunned"],

    "neutral":  []   # fallback if no emotion keywords are found
}


def get_sentiment(text):
    """
    Returns sentiment analysis using two methods combined:
    - VADER: designed for informal text, social media, journaling
    - TextBlob: gives subjectivity score (how personal/opinionated the text is)

    Returns a dict with:
        compound_score  : -1.0 (very negative) to +1.0 (very positive)
        label           : "positive", "negative", or "neutral"
        subjectivity    : 0.0 (objective fact) to 1.0 (very personal/emotional)
    """
    # VADER analysis
    sia = SentimentIntensityAnalyzer()
    vader_scores = sia.polarity_scores(text)
    compound = round(vader_scores["compound"], 4)

    # Label based on config thresholds
    if compound >= config.POSITIVE_THRESHOLD:
        label = "positive"
    elif compound <= config.NEGATIVE_THRESHOLD:
        label = "negative"
    else:
        label = "neutral"

    # TextBlob for subjectivity
    blob = TextBlob(text)
    subjectivity = round(blob.sentiment.subjectivity, 4)

    return {
        "compound_score": compound,
        "label": label,
        "subjectivity": subjectivity
    }


def get_keywords(text, top_n=10):
    """
    Extracts the most meaningful words from the journal text.
    Removes stopwords (filler words like 'the', 'is', 'and') and
    keeps only words longer than 3 characters.

    Returns a list of the top N keywords.
    """
    stop_words = set(stopwords.words("english"))

    # Tokenize: split text into individual words
    tokens = word_tokenize(text.lower())

    # Filter: remove stopwords, short words, and non-alphabetic tokens
    keywords = [
        word for word in tokens
        if word.isalpha()
        and word not in stop_words
        and len(word) > 3
    ]

    # Count frequency of each keyword
    freq = {}
    for word in keywords:
        freq[word] = freq.get(word, 0) + 1

    # Sort by frequency and return top N
    sorted_keywords = sorted(freq, key=freq.get, reverse=True)
    return sorted_keywords[:top_n]


def get_emotion(text):
    """
    Detects the dominant emotion in the text by matching words
    against the EMOTION_KEYWORDS dictionary above.

    Returns:
        dominant_emotion (str): e.g. "joy", "fear", "sadness"
        emotion_scores   (dict): count of matched words per emotion
    """
    text_lower = text.lower()
    tokens = set(word_tokenize(text_lower))

    emotion_scores = {}
    for emotion, keywords in EMOTION_KEYWORDS.items():
        if emotion == "neutral":
            continue
        # Count how many emotion keywords appear in the journal
        score = sum(1 for word in keywords if word in tokens)
        emotion_scores[emotion] = score

    # Pick the emotion with the highest score
    dominant_emotion = max(emotion_scores, key=emotion_scores.get)

    # If nothing matched, fall back to neutral
    if emotion_scores[dominant_emotion] == 0:
        dominant_emotion = "neutral"

    return {
        "dominant_emotion": dominant_emotion,
        "emotion_scores": emotion_scores
    }


def process_journal(text):
    """
    Master function — runs all three analyses on a journal entry.
    This is what every other module will call.

    Returns a single combined dict with all NLP results.
    """
    sentiment = get_sentiment(text)
    keywords  = get_keywords(text)
    emotion   = get_emotion(text)

    return {
        "sentiment": sentiment,
        "keywords":  keywords,
        "emotion":   emotion
    }