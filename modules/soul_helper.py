# modules/soul_helper.py
# ---------------------------------------------------------------------------
# Flush Out (FO) — Your companion. Not a therapy bot.
#
# FO is:
#   - A friend who knows you from your journals
#   - A teacher who can talk about anything
#   - A caretaker who notices when you're off
#   - Chill, open, curious, warm
#
# FO can:
#   - Do small talk and casual chat
#   - Discuss science, philosophy, life, random topics
#   - Give opinions, crack light jokes, be real
#   - Gently weave in your mental state when relevant
#   - Balance general conversation with personal awareness
#
# FO never:
#   - Forces the conversation toward mental health
#   - Ignores that you're struggling if you clearly are
#   - Stays robotic or formal
# ---------------------------------------------------------------------------

import sys
import os
import json
import random
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from modules.collector           import load_all_entries
from modules.nlp_processor       import process_journal
from modules.distortion_detector import detect_distortions, get_distortion_history
from modules.pattern_detector    import run_pattern_analysis


# ---------------------------------------------------------------------------
# BUILD PSYCHOLOGICAL PROFILE
# ---------------------------------------------------------------------------

def build_profile():
    entries = load_all_entries()
    if not entries:
        return None

    all_nlp  = []
    all_dist = []

    for entry in entries:
        text = entry.get("journal", "")
        nlp  = process_journal(text)
        dist = detect_distortions(text)
        nlp["distortions"] = dist
        all_nlp.append(nlp)
        all_dist.append({"distortions": dist})

    patterns     = run_pattern_analysis(entries, all_nlp)
    dist_history = get_distortion_history(all_dist)

    moods   = [e.get("mood",        5) for e in entries]
    energys = [e.get("energy",      5) for e in entries]
    sleeps  = [e.get("sleep_hours", 7) for e in entries]

    avg_mood   = round(sum(moods)   / len(moods),   2)
    avg_energy = round(sum(energys) / len(energys), 2)
    avg_sleep  = round(sum(sleeps)  / len(sleeps),  2)

    recent_entries   = entries[-3:]
    recent_agitation = [
        e.get("behavioral_signals", {}).get("agitation_score", 0)
        for e in recent_entries
    ]
    avg_agitation = round(
        sum(recent_agitation) / len(recent_agitation), 2
    ) if recent_agitation else 0

    recent_nlp        = all_nlp[-3:]
    recent_sentiments = [
        r.get("sentiment", {}).get("compound_score", 0)
        for r in recent_nlp
    ]
    avg_recent_sentiment = round(
        sum(recent_sentiments) / len(recent_sentiments), 2
    ) if recent_sentiments else 0

    recent_emotions  = [
        r.get("emotion", {}).get("dominant_emotion", "neutral")
        for r in recent_nlp
    ]
    dominant_emotion = max(
        set(recent_emotions), key=recent_emotions.count
    ) if recent_emotions else "neutral"

    distortion_freq    = dist_history.get("frequency_map", {})
    active_distortions = [d for d, c in distortion_freq.items() if c > 1]

    return {
        "entry_count":             len(entries),
        "avg_mood":                avg_mood,
        "avg_energy":              avg_energy,
        "avg_sleep":               avg_sleep,
        "avg_recent_agitation":    avg_agitation,
        "avg_recent_sentiment":    avg_recent_sentiment,
        "dominant_recent_emotion": dominant_emotion,
        "mood_trend":              patterns.get("mood_trend",   {}).get("trend", "stable"),
        "energy_trend":            patterns.get("energy_trend", {}).get("trend", "stable"),
        "sleep_affects_mood":      patterns.get("sleep_impact", {}).get("correlation_flag", False),
        "best_day":                patterns.get("day_of_week",  {}).get("best_day",  "Unknown"),
        "worst_day":               patterns.get("day_of_week",  {}).get("worst_day", "Unknown"),
        "recurring_themes":        patterns.get("recurring_themes", []),
        "most_common_distortion":  dist_history.get("most_common", "None"),
        "active_distortions":      active_distortions,
        "raw_entries":             entries,
        "all_nlp":                 all_nlp
    }


# ---------------------------------------------------------------------------
# CHECK IF USER IS CLEARLY STRUGGLING
# (used to gently blend care into any conversation)
# ---------------------------------------------------------------------------

def is_user_struggling(profile):
    """
    Returns True if the user's data suggests they're not doing well.
    FO uses this to gently check in even during casual chat.
    """
    if not profile:
        return False
    return (
        profile.get("mood_trend") == "declining" or
        profile.get("avg_mood", 5) < 4 or
        profile.get("avg_recent_sentiment", 0) < -0.2 or
        profile.get("avg_recent_agitation", 0) > 0.7
    )


def get_gentle_checkin(profile):
    """
    Returns a soft, optional check-in line to weave into casual responses
    when the person seems off. Not forced — just a nudge.
    """
    options = [
        "\n\n(also — you've seemed a bit off lately. no pressure, just checking in. how are you actually doing?)",
        "\n\n(side note — your energy's been low in your journals. you holding up okay?)",
        "\n\n(btw — noticed things have been heavy recently. anything you wanna talk about, or just keep it casual today?)",
        "\n\n(genuine question — how are you doing? not the 'fine' answer, the real one.)"
    ]
    return random.choice(options)


# ---------------------------------------------------------------------------
# INTENT DETECTION — expanded to cover casual + general topics
# ---------------------------------------------------------------------------

INTENT_KEYWORDS = {

    # --- Personal / emotional ---
    "decision":     ["should i", "what should i", "help me decide", "which one",
                     "is it worth", "what do i do", "do you think i should"],
    "conflict":     ["fight", "argument", "conflict", "confront", "angry at",
                     "upset with", "they said", "not talking", "hurt me", "fell out"],
    "self_doubt":   ["not good enough", "am i", "worthless", "failure", "stupid",
                     "what's wrong with me", "i always fail", "i'm bad at", "i can't do"],
    "anxiety":      ["worried", "anxious", "nervous", "scared", "panic",
                     "overwhelmed", "stressed", "freaking out", "what if"],
    "motivation":   ["not motivated", "procrastinating", "can't start", "giving up",
                     "what's the point", "lost interest", "don't feel like", "lazy"],
    "relationship": ["girlfriend", "boyfriend", "partner", "breakup", "broke up",
                     "love", "dating", "crush", "marriage", "toxic", "situationship"],
    "future":       ["future", "career", "job", "college", "exams", "where am i going",
                     "life direction", "purpose", "goal", "dream", "don't know what i want"],
    "venting":      ["i just", "nobody understands", "so tired of", "it's not fair",
                     "i hate this", "everything sucks", "worst day", "i can't take"],

    # --- Casual / general ---
    "greeting":     ["hi", "hey", "hello", "wassup", "sup", "yo", "heyy",
                     "how are you", "how u doing", "how r u", "what's up",
                     "good morning", "good night", "gm", "gn"],
    "smalltalk":    ["bored", "what do you think", "random", "fun fact",
                     "tell me something", "entertain me", "i'm free",
                     "nothing to do", "just chilling", "killing time"],
    "opinion":      ["what do you think about", "your opinion on", "do you like",
                     "do you prefer", "which is better", "thoughts on",
                     "is it good", "recommend", "worth it"],
    "learning":     ["how does", "why does", "what is", "explain", "teach me",
                     "i don't understand", "can you explain", "what's the difference",
                     "how do i learn", "tell me about"],
    "philosophy":   ["meaning of life", "why are we", "consciousness", "free will",
                     "what's real", "does god exist", "purpose of", "existence",
                     "morality", "ethics", "what happens after"],
    "science":      ["universe", "space", "black hole", "evolution", "physics",
                     "quantum", "biology", "brain", "psychology", "ai", "technology",
                     "climate", "nature", "how does the body"],
    "creativity":   ["music", "movies", "anime", "books", "art", "games",
                     "recommend a", "what to watch", "what to listen",
                     "any good", "suggestions"],
    "humor":        ["joke", "make me laugh", "say something funny", "roast",
                     "lol", "lmao", "haha", "funny"],
    "life_advice":  ["how do i", "tips for", "advice on", "what's the best way",
                     "how to deal with", "how to improve", "how to be better at"],
}


def detect_intent(user_text):
    text_lower = user_text.lower().strip()
    scores     = {}

    for intent, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        scores[intent] = score

    best_intent = max(scores, key=scores.get)
    confidence  = scores[best_intent]

    # Very short messages default to greeting or smalltalk
    if confidence == 0:
        if len(text_lower.split()) <= 3:
            best_intent = "greeting"
        else:
            best_intent = "venting"

    return best_intent, confidence


# ---------------------------------------------------------------------------
# CLARIFYING QUESTIONS — only for personal topics, never forced for casual
# ---------------------------------------------------------------------------

CLARIFYING_QUESTIONS = {
    "decision":     ["what's making it hard — is it fear of the outcome, or not knowing what you actually want?"],
    "conflict":     ["was this one specific thing, or has it been building up for a while?"],
    "self_doubt":   ["did something just happen, or has this been sitting with you?"],
    "anxiety":      ["is this about one specific thing, or does it feel like everything at once?"],
    "motivation":   ["is this one thing you're avoiding, or more of a general flatness lately?"],
    "relationship": ["what's the core thing that's bothering you about this right now?"],
    "future":       ["is this about something specific coming up, or more of a big-picture 'where am i going' feeling?"],
    "venting":      ["do you want to talk it through, or just vent?"],
}


def get_clarifying_question(intent, conversation_history):
    # Never ask clarifying questions for casual intents
    casual_intents = {
        "greeting", "smalltalk", "opinion", "learning",
        "philosophy", "science", "creativity", "humor", "life_advice"
    }
    if intent in casual_intents:
        return None

    questions = CLARIFYING_QUESTIONS.get(intent, [])
    asked = sum(
        1 for msg in conversation_history
        if msg.get("role") == "fo" and msg.get("is_clarifying")
    )

    # Max 1 clarifying question per personal topic
    if asked < 1 and questions:
        return questions[0]

    return None


# ---------------------------------------------------------------------------
# RESPONSE BANK — casual, general, and personal
# ---------------------------------------------------------------------------

# Fun facts to drop in smalltalk
FUN_FACTS = [
    "octopuses have three hearts and blue blood. two of the hearts stop when they swim, which is why they prefer crawling.",
    "your brain generates about 70,000 thoughts per day. most of them are the same ones from yesterday.",
    "the word 'music' literally comes from the greek word for 'of the muses.' ancient greeks thought music was divine.",
    "honey never expires. archaeologists found 3000-year-old honey in egyptian tombs and it was still fine.",
    "the human body replaces most of its cells every 7-10 years. you're literally not the same person you were a decade ago.",
    "crows remember human faces and hold grudges. if you're mean to a crow, it tells other crows about you.",
    "time literally passes faster at higher altitudes. your head ages slightly faster than your feet.",
    "there are more possible chess games than atoms in the observable universe.",
    "the feeling of missing a step on stairs — that split second of panic — is called 'hypnic jerk.' it's your brain checking if you're still alive.",
    "languages shape how you think. cultures without words for left/right navigate entirely by cardinal directions and never get lost.",
]

# Light opinions / personality
FO_OPINIONS = {
    "music":     "i think music that makes you feel something you don't have words for is the best kind. genre doesn't matter.",
    "movies":    "slow burn films that trust the audience are underrated. not everything needs an explosion.",
    "anime":     "anime does things with storytelling that most mainstream media doesn't attempt. the depth is real.",
    "books":     "fiction teaches empathy better than most therapy. you literally live inside another person's mind for hours.",
    "games":     "games are one of the few art forms where YOU make choices. that's wildly underappreciated.",
    "ai":        "ai is fascinating and a little terrifying — mostly because humans are terrible at predicting what they'll actually use powerful tools for.",
    "social media": "social media isn't inherently bad. it's just that it was designed to be addictive, not to make you feel good.",
    "school":    "the school system was designed for the industrial age. most of it hasn't caught up with what humans actually need to thrive.",
    "money":     "money is a tool. the problem is most people spend their lives serving the tool instead of using it.",
    "sleep":     "sleep is the most underrated performance enhancer that exists. everything gets harder without it.",
}


def generate_response(user_text, intent, profile, conversation_history):
    """
    Generates a response based on intent.
    Casual intents get open, knowledgeable, warm replies.
    Personal intents get journal-informed, thoughtful replies.
    Struggling users get gentle care woven in even to casual replies.
    """
    text_lower         = user_text.lower().strip()
    struggling         = is_user_struggling(profile)
    mood_trend         = profile.get("mood_trend",              "stable")
    avg_mood           = profile.get("avg_mood",                5)
    avg_agitation      = profile.get("avg_recent_agitation",   0)
    avg_sleep          = profile.get("avg_sleep",               7)
    dominant_emotion   = profile.get("dominant_recent_emotion", "neutral")
    active_distortions = profile.get("active_distortions",     [])
    sleep_affects_mood = profile.get("sleep_affects_mood",      False)
    best_day           = profile.get("best_day",                "Unknown")
    energy_trend       = profile.get("energy_trend",            "stable")
    themes             = profile.get("recurring_themes",        [])

    checkin = get_gentle_checkin(profile) if struggling else ""

    # =====================================================================
    # CASUAL INTENTS
    # =====================================================================

    # ---- GREETING ----
    if intent == "greeting":
        hour = datetime.now().hour

        if avg_mood >= 7 and mood_trend != "declining":
            mood_line = "you've been doing pretty well lately from what i can tell."
        elif mood_trend == "declining" or avg_mood < 5:
            mood_line = "things have seemed a bit heavy for you recently — hope today's treating you better."
        else:
            mood_line = "things seem steady on your end."

        if hour < 12:
            openers = [
                f"morning! {mood_line} what's the plan today?",
                f"hey, good morning! {mood_line} you got anything going on today?",
            ]
        elif hour < 17:
            openers = [
                f"hey! {mood_line} how's the day going so far?",
                f"yo, what's up! {mood_line} anything interesting happening?",
            ]
        else:
            openers = [
                f"hey! {mood_line} how was today?",
                f"evening! {mood_line} how'd the day go?",
            ]

        return random.choice(openers)

    # ---- SMALL TALK ----
    elif intent == "smalltalk":
        responses = [
            f"okay since you're bored — random fact: {random.choice(FUN_FACTS)}\n\nwhat do you think about that?",
            f"bored? same honestly. here's something interesting: {random.choice(FUN_FACTS)}",
            f"alright, killing time — {random.choice(FUN_FACTS)}\n\nweird right?",
            f"oh i've got one — {random.choice(FUN_FACTS)}\n\nthe world's lowkey wild.",
        ]
        response = random.choice(responses)
        if struggling:
            response += checkin
        return response

    # ---- OPINION ----
    elif intent == "opinion":
        # Check if it matches a known topic
        for topic, opinion in FO_OPINIONS.items():
            if topic in text_lower:
                response = f"honestly? {opinion}"
                if struggling:
                    response += checkin
                return response

        # Generic opinion response
        response = (
            "i genuinely have thoughts on most things — "
            "what specifically do you want my take on? "
            "i'll give you an actual opinion, not a 'well it depends' answer."
        )
        if struggling:
            response += checkin
        return response

    # ---- LEARNING / EXPLAINING ----
    elif intent == "learning":
        # Try to figure out what they want explained
        topic_hints = {
            "brain":        "the brain is basically a prediction machine. it's constantly making guesses about what will happen next and updating based on what's wrong. that's literally how perception, emotion, and memory all work.",
            "psychology":   "psychology at its core is just the study of why people do what they do. and the honest answer is — most of the time, people don't actually know why they do what they do. the reasons come after.",
            "ai":           "ai right now works by pattern matching at enormous scale. it doesn't 'understand' anything — it predicts what the next word, image, or action should be based on what it's seen before. impressive, but different from thinking.",
            "quantum":      "quantum mechanics basically says that at the smallest scales, particles don't have fixed states until you observe them. the act of measuring changes the thing being measured. it broke physics when they found it.",
            "black hole":   "a black hole is what happens when gravity wins completely. the mass is so dense that not even light can escape. time literally slows down near them — if you were next to one, you'd age slower than someone far away.",
            "consciousness":"consciousness is one of the hardest problems in science — we don't actually know why physical brain processes create subjective experience. it's called 'the hard problem' and nobody has cracked it yet.",
            "evolution":    "evolution is just change over time through selection. whatever helps you survive long enough to reproduce gets passed on. it's not trying to make things 'better' — it's just whatever worked.",
            "sleep":        "sleep is when your brain consolidates memories, clears out waste products, and resets emotional regulation. skip it and literally everything gets worse — mood, focus, decision-making, health. it's not lazy, it's maintenance.",
            "memory":       "memory isn't like a video recording — it's reconstructive. every time you remember something, you're slightly rewriting it. memories change each time you access them. which is kind of wild.",
            "habits":       "habits form in a loop: cue, routine, reward. the brain automates repeated behaviors to save energy. to change a habit you keep the cue and reward but swap the routine — cold turkey rarely works.",
            "dopamine":     "dopamine isn't actually the 'pleasure' chemical — it's the 'anticipation' chemical. it spikes before you get the reward, not during. that's why scrolling and gambling are so addictive — the maybe is more powerful than the yes.",
            "anxiety":      "anxiety is your threat detection system misfiring. it's designed for tigers, not emails. the physical sensations are real — the danger usually isn't. the body doesn't know the difference between a real threat and an imagined one.",
            "stoicism":     "stoicism basically says: focus only on what you can control, accept what you can't. not because the world is fair, but because burning energy on what you can't change is just suffering twice.",
            "philosophy":   "philosophy is basically organized thinking about things that can't be settled by facts alone — ethics, meaning, consciousness, knowledge. it's less about finding answers and more about asking better questions.",
        }

        for keyword, explanation in topic_hints.items():
            if keyword in text_lower:
                response = explanation
                if struggling:
                    response += checkin
                return response

        # General learning response
        response = (
            "i love this — what do you want to understand? "
            "give me the topic and i'll break it down in a way that actually makes sense. "
            "no textbook answers."
        )
        if struggling:
            response += checkin
        return response

    # ---- PHILOSOPHY ----
    elif intent == "philosophy":
        philosophy_responses = [
            "the meaning of life question is interesting because most people assume there's a single answer waiting to be found. but meaning might be something you create, not discover. the search itself might be the point.",
            "free will is genuinely unsolved. your brain makes a decision about 300-500 milliseconds before you're consciously aware of it. does that mean choice is an illusion, or just that consciousness isn't where we think it is?",
            "consciousness is the weirdest problem in existence. why does physical stuff — neurons firing — produce subjective experience? we can explain everything the brain DOES, but not why any of it FEELS like anything.",
            "the universe being 13.8 billion years old and you existing right now at this exact moment is statistically absurd. not sure what that means, but it definitely means something.",
            "morality without a rulebook is hard — but most ethical frameworks converge on similar things: reduce suffering, treat others as ends not means, be consistent. the details differ but the core is similar.",
        ]

        response = random.choice(philosophy_responses)
        response += "\n\nwhat's your take? i'm genuinely curious."
        if struggling:
            response += checkin
        return response

    # ---- SCIENCE ----
    elif intent == "science":
        response = f"okay here's something interesting — {random.choice(FUN_FACTS)}\n\nwhat specifically were you curious about? i can go deeper on almost anything."
        if struggling:
            response += checkin
        return response

    # ---- CREATIVITY (music, movies, books, etc.) ----
    elif intent == "creativity":
        for topic, opinion in FO_OPINIONS.items():
            if topic in text_lower:
                response = f"{opinion}\n\nwhat kind of {topic} are you into? i can actually give you decent recommendations if you tell me what you like."
                if struggling:
                    response += checkin
                return response

        response = (
            "i'm into most things creatively — what are you looking for? "
            "give me a vibe or something you already like and i'll work with that."
        )
        if struggling:
            response += checkin
        return response

    # ---- HUMOR ----
    elif intent == "humor":
        jokes = [
            "why don't scientists trust atoms?\n\nbecause they make up everything.",
            "i told my brain to stop overthinking.\n\nit said 'okay but first let's think about why we overthink.'",
            "my sleep schedule walked so my anxiety could run.",
            "me at 3am: i should sleep\nalso me at 3am: but what if i instead think about every embarrassing thing i've ever done",
            "the human body is 70% water.\n\nso we're basically just cucumbers with anxiety.",
            "fun fact: worrying about something doesn't change the outcome.\n\nunfun fact: knowing that doesn't stop the worrying.",
        ]
        response = random.choice(jokes)
        if struggling:
            response += "\n\n" + "(but also — " + get_gentle_checkin(profile).strip("()\n ") + ")"
        return response

    # ---- LIFE ADVICE ----
    elif intent == "life_advice":
        advice_map = {
            "focus":        "try working in 25-minute blocks with 5-minute breaks — it's called pomodoro. sounds simple but it actually works because it makes the task feel finite.",
            "sleep":        "keep your wake time consistent, even on weekends. that one thing does more than any sleep supplement.",
            "study":        "active recall beats re-reading every time. close the book and try to explain what you just read out loud. whatever you can't explain, you don't actually know yet.",
            "confidence":   "confidence comes from doing, not from feeling ready. act first, the feeling follows. nobody feels ready before something scary.",
            "productivity": "the question isn't 'how do i do more' — it's 'what actually matters.' most productivity problems are clarity problems in disguise.",
            "friends":      "good friendships need consistency more than intensity. small regular contact matters more than big occasional meetups.",
            "discipline":   "discipline is overrated as a feeling. what actually works is removing friction and making the good choice the easy choice. design your environment.",
            "anxiety":      "when anxiety spikes, your breath is the fastest way back. slow exhale longer than the inhale — it activates your parasympathetic system. not a metaphor, actual physiology.",
            "anger":        "anger is almost always a secondary emotion. something else — hurt, fear, embarrassment — comes first. find that thing and you find the real problem.",
            "procrastination": "procrastination is rarely about laziness — it's usually about fear of failure or perfectionism. lower the bar. bad first draft beats no first draft.",
        }

        for keyword, advice in advice_map.items():
            if keyword in text_lower:
                response = advice
                if struggling:
                    response += checkin
                return response

        response = (
            "i've got thoughts on most things — what specifically are you trying to figure out or get better at? "
            "the more specific you are, the more useful i can actually be."
        )
        if struggling:
            response += checkin
        return response

    # =====================================================================
    # PERSONAL INTENTS (journal-informed)
    # =====================================================================

    profile_opener = ""
    profile_notes  = []

    if mood_trend == "declining":
        profile_notes.append("your mood has been sliding a bit lately")
    elif mood_trend == "improving":
        profile_notes.append("your mood has been picking up recently")
    if avg_agitation > 0.6:
        profile_notes.append("you've been pretty activated emotionally in your recent entries")
    if dominant_emotion not in ["neutral", "joy"]:
        profile_notes.append(f"there's been a lot of {dominant_emotion} showing up in what you write")
    if sleep_affects_mood and avg_sleep < 6.5:
        profile_notes.append("your sleep has been rough and that's hitting your mood hard")
    if "Catastrophizing" in active_distortions:
        profile_notes.append("you tend to spiral toward worst-case scenarios more than you realize")
    if "Mind Reading" in active_distortions:
        profile_notes.append("you often assume what others think without checking")
    if "Self Blame" in active_distortions:
        profile_notes.append("you carry more blame than is actually yours")

    if profile_notes:
        profile_opener = f"honestly — {profile_notes[0]}."

    # ---- DECISION ----
    if intent == "decision":
        if "Catastrophizing" in active_distortions or "Fortune Telling" in active_distortions:
            return (
                f"okay so {profile_opener} and that's probably making this feel bigger than it is.\n\n"
                f"your brain is doing that thing where it jumps to worst case and treats it like it's already decided. it's not.\n\n"
                f"write down the realistic best, worst, and most likely outcome. not the dramatic version — the actual likely one. "
                f"you'll find the most likely case is way more manageable than it feels.\n\n"
                f"what does your gut say when you're not in panic mode?"
            )
        elif mood_trend == "declining":
            return (
                f"real talk — {profile_opener} and that's not the best headspace for big decisions.\n\n"
                f"when we're low we default to safe and risk-averse — not necessarily right.\n\n"
                f"if this can wait even a couple days, let it. your best days tend to be {best_day}s. "
                f"use that energy if you can.\n\nwhat's the actual deadline here?"
            )
        else:
            return (
                f"you seem grounded right now — that's actually a decent state to decide from.\n\n"
                f"what does this come down to at its core — logic, fear of judgment, or not knowing what you actually want? "
                f"those three need very different answers."
            )

    # ---- CONFLICT ----
    elif intent == "conflict":
        if "Mind Reading" in active_distortions:
            return (
                f"before anything — {profile_opener} and that matters here.\n\n"
                f"how much of this is something they actually did versus what you think they meant? "
                f"those are two very different problems.\n\n"
                f"if it's real — say something. pick a calm moment, talk about how you felt, not what they did wrong.\n\n"
                f"but if you're partly reacting to what you think they're thinking — worth checking that first."
            )
        elif avg_agitation > 0.6:
            return (
                f"{profile_opener} — and confronting someone when you're this activated rarely goes how you want.\n\n"
                f"not because you're wrong. you might be totally right. "
                f"but the emotional charge usually drowns out the actual message.\n\n"
                f"sleep on it if you can. then say what you need to say."
            )
        else:
            return (
                f"from your journals — you feel better when you address things rather than let them sit.\n\n"
                f"what's the one thing you most need them to understand? just that one thing. start there."
            )

    # ---- SELF DOUBT ----
    elif intent == "self_doubt":
        if "Labelling" in active_distortions or "Emotional Reasoning" in active_distortions:
            return (
                f"hey — {profile_opener} and i want to gently push back here.\n\n"
                f"you're doing that thing where feeling something becomes proof of it. "
                f"'i feel like a failure' is not the same as 'i am a failure.' your brain is lying to you.\n\n"
                f"what would you tell a close friend who said exactly what you just said to me?"
            )
        elif mood_trend == "declining":
            return (
                f"self-doubt gets louder when mood is low — it feels like truth but it's a symptom.\n\n"
                f"this isn't the moment to evaluate your worth. your journals have more going on than this one moment is showing you.\n\n"
                f"what specifically happened that triggered this?"
            )
        else:
            return (
                f"the fact that you're questioning yourself means you care about doing things right. "
                f"that's not weakness — that's conscientiousness.\n\n"
                f"what's the specific thing you're doubting right now? let's actually look at it."
            )

    # ---- ANXIETY ----
    elif intent == "anxiety":
        if sleep_affects_mood and avg_sleep < 6.5:
            return (
                f"first — your sleep has been rough and it's making everything feel heavier than it is. that's real.\n\n"
                f"anxiety after bad sleep amplifies everything. not dismissing it — just worth knowing the filter it's coming through.\n\n"
                f"is there something specific feeding this, or does it feel like a general weight?"
            )
        elif "Fortune Telling" in active_distortions or "Catastrophizing" in active_distortions:
            return (
                f"{profile_opener} — your brain is treating uncertainty like confirmed disaster. it's not.\n\n"
                f"how many things you were anxious about in the last month actually happened the way you feared? "
                f"be honest. your track record of surviving is 100% so far."
            )
        else:
            return (
                f"anxiety almost always has one thing at the center even when it feels like everything.\n\n"
                f"if you had to point to the ONE thing underneath all of this — what would it be?"
            )

    # ---- MOTIVATION ----
    elif intent == "motivation":
        if energy_trend == "declining":
            return (
                f"your energy has been dropping in your journals — this isn't laziness, it's depletion. they feel the same but they're not.\n\n"
                f"pushing harder from empty just adds guilt on top of tiredness.\n\n"
                f"what's the smallest possible version of what you need to do? just the first 5 minutes. that's it."
            )
        elif avg_mood < 5:
            return (
                f"low motivation when mood is down is a mood problem, not a you problem.\n\n"
                f"what's one thing that used to make you feel even slightly alive or interested? even a small version of that today changes the whole day."
            )
        else:
            return (
                f"sometimes low motivation is your brain flagging that something about this specific thing doesn't sit right.\n\n"
                f"is this about not wanting to do THIS thing, or not wanting to do anything at all right now?"
            )

    # ---- RELATIONSHIP ----
    elif intent == "relationship":
        if "Mind Reading" in active_distortions:
            return (
                f"{profile_opener} — and in relationships that pattern creates a lot of pain that doesn't need to exist.\n\n"
                f"what do you know for certain from their actual words or actions? versus what are you filling in yourself?"
            )
        elif avg_agitation > 0.6:
            return (
                f"you're running pretty activated right now — relationship stuff always feels more intense in that state.\n\n"
                f"what's the core thing you need from this person — understanding, space, or something actually changing?"
            )
        else:
            return (
                f"relationships come up a lot in your journals — they clearly matter a lot to you.\n\n"
                f"what do you need most right now — to vent, figure out what to do, or something else?"
            )

    # ---- FUTURE ----
    elif intent == "future":
        if "Fortune Telling" in active_distortions:
            return (
                f"{profile_opener} — when it comes to the future that pattern makes everything feel predetermined in the worst way.\n\n"
                f"the future isn't decided. your predictions about how things go haven't always been right — and that's actually good news here.\n\n"
                f"what part of the future feels most uncertain right now? let's look at that one thing."
            )
        elif mood_trend == "declining":
            return (
                f"when mood is sliding, the future looks darker than it probably is. same future, different filter.\n\n"
                f"what does your gut say you actually want — not what feels realistic, just what you genuinely want?"
            )
        else:
            return (
                f"thinking about where you're going means you care — that's worth something.\n\n"
                f"what's the part that feels most unclear or unsettling right now?"
            )

    # ---- VENTING ----
    elif intent == "venting":
        return (
            f"i'm here. sounds like a lot is sitting on you.\n\n"
            f"you don't have to explain it perfectly — just say it. what's the heaviest part right now?"
        )

    # ---- FALLBACK ----
    else:
        response = "i'm here — what's going on?"
        if struggling:
            response += checkin
        return response


# ---------------------------------------------------------------------------
# SAVE CONVERSATION
# ---------------------------------------------------------------------------

def save_conversation(conversation_history):
    os.makedirs(config.JOURNAL_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename  = os.path.join(
        config.JOURNAL_DIR,
        f"fo_conversation_{timestamp}.json"
    )
    log = {
        "type":      "flush_out_conversation",
        "timestamp": datetime.now().isoformat(),
        "messages":  conversation_history
    }
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=4)
    return filename


# ---------------------------------------------------------------------------
# MASTER FUNCTION
# ---------------------------------------------------------------------------

def flush_out(user_text, conversation_history):
    """
    Main entry point. Decides whether to clarify or respond.
    """
    profile = build_profile()

    if not profile or profile["entry_count"] == 0:
        return (
            "hey! i don't really know you yet — "
            "write a few journal entries first and then come talk to me. "
            "the more i learn from your entries, the more useful i can be.",
            False,
            "unknown"
        )

    intent, confidence = detect_intent(user_text)
    clarifying         = get_clarifying_question(intent, conversation_history)

    if clarifying and len(conversation_history) < 3:
        return clarifying, True, intent

    response = generate_response(
        user_text, intent, profile, conversation_history
    )

    return response, False, intent