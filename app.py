# app.py
# ---------------------------------------------------------------------------
# Soul Helper (SH) — Multi-user Streamlit frontend with Supabase backend
# Pages:
#   1. Journal      — multi-entry journaling
#   2. Insights     — patterns, predictions, interventions
#   3. Distortions  — CBT cognitive distortion analysis
#   4. Weekly Report— full psychological report
#   5. Flush Out    — journal-informed conversational companion
#   6. Researcher   — cross-user analysis dashboard (PIN protected)
# ---------------------------------------------------------------------------

import streamlit as st
import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from modules.collector           import (save_entry, get_session_day)
from modules.nlp_processor       import process_journal
from modules.distortion_detector import (detect_distortions, get_distortion_summary,
                                          get_distortion_history)
from modules.pattern_detector    import run_pattern_analysis
from modules.predictor           import run_predictions
from modules.intervention        import run_interventions
from modules.report_generator    import generate_weekly_report
from modules.database            import (create_user, verify_user,
                                          save_journal_entry,
                                          load_journal_entries,
                                          load_entries_by_day_db,
                                          delete_journal_entry_db,
                                          count_session_days_db,
                                          count_entries_db,
                                          save_researcher_snapshot,
                                          load_researcher_data)

# ---------------------------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Soul Helper",
    page_icon="🧠",
    layout="wide"
)

# ---------------------------------------------------------------------------
# RESEARCHER PASSWORD (change this to whatever you want)
# ---------------------------------------------------------------------------

RESEARCHER_PIN = "007700"  # Change this to your own secret PIN

# ---------------------------------------------------------------------------
# SESSION STATE INIT
# ---------------------------------------------------------------------------

if "logged_in"  not in st.session_state:
    st.session_state["logged_in"]  = False
if "username"   not in st.session_state:
    st.session_state["username"]   = None
if "user_id"    not in st.session_state:
    st.session_state["user_id"]    = None
if "fo_history" not in st.session_state:
    st.session_state["fo_history"] = []
if "fo_intent"  not in st.session_state:
    st.session_state["fo_intent"]  = None


# ---------------------------------------------------------------------------
# HELPER — Load and process all entries for current user
# ---------------------------------------------------------------------------

def load_and_process_all():
    entries  = load_journal_entries(st.session_state["username"])
    all_nlp  = []
    all_dist = []
    for entry in entries:
        text = entry.get("journal", "")
        nlp  = process_journal(text)
        dist = detect_distortions(text)
        nlp["distortions"] = dist
        all_nlp.append(nlp)
        all_dist.append({"distortions": dist})
    return entries, all_nlp, all_dist


# ===========================================================================
# LOGIN / REGISTER SCREEN
# ===========================================================================

def show_login():
    st.title("🧠 Soul Helper")
    st.markdown("*Your Psychological Digital Twin*")
    st.markdown("---")

    tab1, tab2 = st.tabs(["🔑 Login", "✨ Register"])

    # --- LOGIN ---
    with tab1:
        st.markdown("### Welcome back")
        username_in = st.text_input("Your name", key="login_username").strip().lower()
        pin_in      = st.text_input("Your PIN", type="password",
                                     max_chars=4, key="login_pin")

        if st.button("Login", use_container_width=True, key="login_btn"):
            if not username_in or not pin_in:
                st.error("Please enter both your name and PIN.")
            else:
                result = verify_user(username_in, pin_in)
                if result["success"]:
                    st.session_state["logged_in"] = True
                    st.session_state["username"]  = result["username"]
                    st.session_state["user_id"]   = result["user_id"]
                    st.rerun()
                else:
                    st.error(result["error"])

    # --- REGISTER ---
    with tab2:
        st.markdown("### Create your profile")
        st.info(
            "Your journals are private. "
            "Nobody can read them without your PIN — not even the researcher."
        )
        new_username = st.text_input("Choose a name", key="reg_username").strip().lower()
        new_pin      = st.text_input("Choose a 4-digit PIN", type="password",
                                      max_chars=4, key="reg_pin")
        confirm_pin  = st.text_input("Confirm PIN", type="password",
                                      max_chars=4, key="reg_pin2")

        if st.button("Create Profile", use_container_width=True, key="reg_btn"):
            if not new_username or not new_pin:
                st.error("Please fill in all fields.")
            elif len(new_pin) != 4 or not new_pin.isdigit():
                st.error("PIN must be exactly 4 digits.")
            elif new_pin != confirm_pin:
                st.error("PINs don't match.")
            else:
                result = create_user(new_username, new_pin)
                if result["success"]:
                    st.success(
                        f"Profile created! You can now log in as **{new_username}**."
                    )
                else:
                    st.error(result["error"])


# ===========================================================================
# MAIN APP (after login)
# ===========================================================================

def show_main_app():
    username          = st.session_state["username"]
    user_id           = st.session_state["user_id"]
    session_day_count = count_session_days_db(username)
    entry_count       = count_entries_db(username)
    baseline          = session_day_count >= config.BASELINE_DAYS

    # --- SIDEBAR ---
    st.sidebar.title("🧠 Soul Helper")
    st.sidebar.markdown(f"*Hey, {username}* 👋")
    st.sidebar.markdown("---")

    st.sidebar.markdown("### 📊 Your Progress")
    st.sidebar.progress(min(session_day_count / config.BASELINE_DAYS, 1.0))
    st.sidebar.markdown(f"**{session_day_count} / {config.BASELINE_DAYS}** days logged")
    st.sidebar.markdown(f"*({entry_count} total entries)*")

    if not baseline:
        remaining = max(0, config.BASELINE_DAYS - session_day_count)
        st.sidebar.warning(f"⏳ {remaining} more day(s) before insights unlock.")
    else:
        st.sidebar.success("✅ Baseline reached — insights active.")

    st.sidebar.markdown("---")

    page = st.sidebar.radio(
        "Navigate",
        ["📓 Journal", "🔍 Insights", "🧩 Distortions",
         "📋 Weekly Report", "💬 Flush Out", "🔬 Researcher"]
    )

    if st.sidebar.button("🚪 Logout", use_container_width=True):
        for key in ["logged_in", "username", "user_id",
                    "fo_history", "fo_intent", "session_choice"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

    # =======================================================================
    # PAGE 1 — JOURNAL
    # =======================================================================

    if page == "📓 Journal":

        st.title("📓 Daily Journal")
        st.markdown(
            "Write freely. This is your space. "
            "The system will read between the lines so you don't have to."
        )
        st.markdown("---")

        now  = datetime.now()
        hour = now.hour

        if 0 <= hour < 12:
            st.markdown(
                f"### {now.strftime('%A, %d %B %Y')} — {now.strftime('%I:%M %p')}"
            )
            st.warning(
                f"⏰ It's {now.strftime('%I:%M %p')}. "
                "Which day do you want this entry to belong to?"
            )

            col_opt1, col_opt2 = st.columns(2)

            with col_opt1:
                yesterday_label = (now - timedelta(days=1)).strftime("%A, %d %B")
                if st.button(
                    f"📅 Yesterday  ({yesterday_label})",
                    use_container_width=True,
                    key="session_yesterday"
                ):
                    st.session_state["session_choice"] = "yesterday"

            with col_opt2:
                today_label = now.strftime("%A, %d %B")
                if st.button(
                    f"📅 Today  ({today_label})",
                    use_container_width=True,
                    key="session_today"
                ):
                    st.session_state["session_choice"] = "today"

            if "session_choice" not in st.session_state:
                st.session_state["session_choice"] = "yesterday"

            user_choice   = st.session_state["session_choice"]
            today_session = get_session_day(now, user_choice=user_choice)

            choice_label = (
                (now - timedelta(days=1)).strftime("%A, %d %B")
                if user_choice == "yesterday"
                else now.strftime("%A, %d %B")
            )
            st.info(
                f"✅ Entry will be saved under: **{choice_label}** ({today_session})"
            )

        else:
            today_session = get_session_day(now)
            if "session_choice" in st.session_state:
                del st.session_state["session_choice"]
            st.markdown(f"### {now.strftime('%A, %d %B %Y')}")

        today_entries = load_entries_by_day_db(username, today_session)

        st.markdown("---")
        st.info(
            "💡 **Multi-entry:** You can journal multiple times. "
            "Each entry is timestamped and analyzed individually."
        )

        st.markdown("#### ✍️ Write a New Entry")

        journal_text = st.text_area(
            "What's on your mind?",
            height=200,
            placeholder="Write about your day, how you're feeling...",
            key="journal_input"
        )

        st.markdown("---")
        col1, col2, col3 = st.columns(3)

        with col1:
            mood = st.slider("😊 Mood", config.MOOD_MIN, config.MOOD_MAX, 5,
                             help="1 = Very low, 10 = Excellent")
        with col2:
            energy = st.slider("⚡ Energy", config.ENERGY_MIN, config.ENERGY_MAX, 5,
                               help="1 = Exhausted, 10 = Fully energized")
        with col3:
            sleep = st.slider("😴 Sleep (hours)", float(config.SLEEP_MIN),
                              float(config.SLEEP_MAX), 7.0, step=0.5)

        st.markdown("---")

        if st.button("💾 Save Entry", use_container_width=True):
            if not journal_text.strip():
                st.error("Please write something before saving.")
            else:
                # Save locally first (to get entry object)
                entry = save_entry(
                    journal_text, mood, energy, sleep,
                    typing_time_seconds=0,
                    session_day_override=today_session
                )

                # Save to Supabase
                db_result = save_journal_entry(username, user_id, entry)

                if db_result["success"]:
                    st.success(
                        f"✅ Entry saved at **{entry['time']}** "
                        f"under session: **{entry['session_day']}**"
                    )
                else:
                    st.error(f"Save failed: {db_result['error']}")

                # Quick NLP feedback
                st.markdown("---")
                st.markdown("### 🔍 Quick Analysis of This Entry")

                nlp  = process_journal(journal_text)
                dist = detect_distortions(journal_text)

                col_a, col_b, col_c = st.columns(3)

                with col_a:
                    sentiment = nlp["sentiment"]
                    label     = sentiment["label"]
                    score     = sentiment["compound_score"]
                    emoji     = "😊" if label == "positive" else \
                                ("😔" if label == "negative" else "😐")
                    st.metric("Sentiment", f"{emoji} {label.title()}",
                              f"Score: {score}")

                with col_b:
                    emotion = nlp["emotion"]["dominant_emotion"].title()
                    st.metric("Dominant Emotion", emotion)

                with col_c:
                    agitation = entry['behavioral_signals']['agitation_score']
                    emoji_ag  = "🔥" if agitation > 0.7 else \
                                ("⚡" if agitation > 0.4 else "😌")
                    st.metric("Agitation Level", f"{emoji_ag} {agitation}",
                              help="0.0 = calm  |  1.0 = very agitated")

                keywords = nlp["keywords"]
                if keywords:
                    st.markdown("**Key themes in this entry:**")
                    st.markdown(" ".join([f"`{kw}`" for kw in keywords]))

                if not dist["clean"]:
                    st.markdown("---")
                    st.warning(get_distortion_summary(dist))

        # All entries for today
        st.markdown("---")
        today_entries = load_entries_by_day_db(username, today_session)
        st.markdown(
            f"### 📝 Entries for {today_session}  ({len(today_entries)} total)"
        )

        if today_entries:
            for i, e in enumerate(today_entries, 1):
                entry_id  = e.get("entry_id", "?")
                agitation = e['behavioral_signals']['agitation_score']

                with st.expander(
                    f"Entry {i}  —  {e['time']}  |  "
                    f"Mood: {e['mood']}/10  |  "
                    f"Agitation: {agitation}"
                ):
                    col_left, col_right = st.columns([4, 1])

                    with col_left:
                        st.markdown(
                            f"**Time:** {e['time']}  |  "
                            f"**Mood:** {e['mood']}/10  |  "
                            f"**Energy:** {e['energy']}/10  |  "
                            f"**Sleep:** {e['sleep_hours']}h"
                        )
                        st.info(e['journal'])

                    with col_right:
                        st.markdown("&nbsp;", unsafe_allow_html=True)
                        if st.button("🗑️ Delete", key=f"delete_{entry_id}"):
                            delete_journal_entry_db(entry_id, username)
                            st.success("Deleted.")
                            st.rerun()
        else:
            st.info("No entries yet for this session. Start writing above.")

    # =======================================================================
    # PAGE 2 — INSIGHTS
    # =======================================================================

    elif page == "🔍 Insights":

        st.title("🔍 Behavioral Insights")

        if not baseline:
            st.warning(
                f"⏳ Insights unlock after {config.BASELINE_DAYS} days. "
                f"You have {session_day_count} days so far. Keep going."
            )
            st.stop()

        entries, all_nlp, all_dist = load_and_process_all()
        pattern_results    = run_pattern_analysis(entries, all_nlp)
        prediction_results = run_predictions(entries, all_nlp)
        last_dist          = all_dist[-1].get("distortions", {}) if all_dist else {}
        intervention_res   = run_interventions(
            pattern_results, prediction_results, last_dist
        )

        st.markdown("---")

        st.markdown("### 📈 Mood & Energy Trends")
        col1, col2   = st.columns(2)
        mood_trend   = pattern_results["mood_trend"]
        energy_trend = pattern_results["energy_trend"]

        with col1:
            t = mood_trend["trend"]
            e = "📈" if t == "improving" else ("📉" if t == "declining" else "➡️")
            st.metric("Mood Trend", f"{e} {t.title()}",
                      f"Avg: {mood_trend['average']}/10")
            st.line_chart(mood_trend["scores"])

        with col2:
            t = energy_trend["trend"]
            e = "📈" if t == "improving" else ("📉" if t == "declining" else "➡️")
            st.metric("Energy Trend", f"{e} {t.title()}",
                      f"Avg: {energy_trend['average']}/10")
            st.line_chart(energy_trend["scores"])

        st.markdown("---")

        st.markdown("### 😴 Sleep Impact")
        if pattern_results["sleep_impact"]["correlation_flag"]:
            st.warning(pattern_results["sleep_impact"]["message"])
        else:
            st.info(pattern_results["sleep_impact"]["message"])

        st.markdown("---")

        st.markdown("### 📅 Day of Week Patterns")
        day_data = pattern_results["day_of_week"]
        col3, col4 = st.columns(2)
        with col3:
            st.success(f"🌟 Best day: **{day_data.get('best_day','?')}**")
        with col4:
            st.error(f"⚠️ Hardest day: **{day_data.get('worst_day','?')}**")
        if day_data.get("day_averages"):
            st.bar_chart(day_data["day_averages"])

        st.markdown("---")

        st.markdown("### 🏷️ Recurring Life Themes")
        themes = pattern_results.get("recurring_themes", [])
        if themes:
            st.markdown(" ".join([f"`{t}`" for t in themes]))
        else:
            st.info("Not enough data yet.")

        st.markdown("---")

        st.markdown("### 🔮 Tomorrow's Forecast")
        mood_pred   = prediction_results["mood_prediction"]
        energy_pred = prediction_results["energy_prediction"]
        col5, col6  = st.columns(2)

        with col5:
            if mood_pred.get("predicted_mood"):
                st.metric("Predicted Mood",
                          f"{mood_pred['predicted_mood']}/10",
                          f"Confidence: {mood_pred['confidence']}")
        with col6:
            if energy_pred.get("predicted_energy"):
                st.metric("Predicted Energy",
                          f"{energy_pred['predicted_energy']}/10",
                          f"Confidence: {energy_pred['confidence']}")

        risk = prediction_results["risk_flags"]
        if risk["flagged"]:
            st.markdown("---")
            for flag in risk["flags"]:
                st.error(flag)

        st.markdown("---")

        st.markdown("### 💡 Personalized Interventions")
        st.markdown(
            "*Based on your behavioral data, grounded in evidence-based psychology.*"
        )
        for item in intervention_res.get("interventions", []):
            with st.expander(f"🔸 {item['title']}"):
                st.markdown(item["message"])
                st.markdown(f"*Framework: {item['framework']}*")

        # Auto-save researcher snapshot
        entries_all = load_journal_entries(username)
        if entries_all:
            moods   = [e.get("mood",        5) for e in entries_all]
            energys = [e.get("energy",      5) for e in entries_all]
            sleeps  = [e.get("sleep_hours", 7) for e in entries_all]

            all_dist_flat = get_distortion_history(all_dist)

            save_researcher_snapshot(username, {
                "avg_mood":               round(sum(moods)   / len(moods),   2),
                "avg_energy":             round(sum(energys) / len(energys), 2),
                "avg_sleep":              round(sum(sleeps)  / len(sleeps),  2),
                "mood_trend":             pattern_results["mood_trend"]["trend"],
                "energy_trend":           pattern_results["energy_trend"]["trend"],
                "dominant_emotion":       all_nlp[-1].get("emotion", {}).get(
                                          "dominant_emotion", "neutral") if all_nlp else "neutral",
                "most_common_distortion": all_dist_flat.get("most_common", "None"),
                "predictions":            prediction_results,
                "entry_count":            len(entries_all)
            })

    # =======================================================================
    # PAGE 3 — DISTORTIONS
    # =======================================================================

    elif page == "🧩 Distortions":

        st.title("🧩 Cognitive Distortion Tracker")
        st.markdown(
            "Cognitive distortions are irrational thinking patterns identified in CBT. "
            "Tracking them over time reveals your personal thinking signature."
        )
        st.markdown("---")

        if entry_count == 0:
            st.info("No journal entries yet. Start journaling.")
            st.stop()

        entries, all_nlp, all_dist = load_and_process_all()

        st.markdown("### 🔍 Most Recent Entry Analysis")
        now           = datetime.now()
        today_session = get_session_day(now)
        today_entries = load_entries_by_day_db(username, today_session)

        if today_entries:
            latest_dist = detect_distortions(today_entries[-1].get("journal", ""))
            summary     = get_distortion_summary(latest_dist)
            if latest_dist["clean"]:
                st.success(summary)
            else:
                st.warning(summary)
        else:
            st.info("No entries yet for today's session.")

        st.markdown("---")

        if baseline:
            st.markdown("### 📊 Distortion History")
            history     = get_distortion_history(all_dist)
            freq_map    = history["frequency_map"]
            most_common = history["most_common"]
            flagged     = history["total_flagged"]

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Days with distortions", flagged)
            with col2:
                st.metric("Most common distortion", most_common)

            active = {k: v for k, v in freq_map.items() if v > 0}
            if active:
                st.bar_chart(active)
            else:
                st.success("No distortions detected across your history.")
        else:
            st.info(
                f"Historical tracking unlocks after {config.BASELINE_DAYS} days. "
                f"You have {session_day_count} days."
            )

    # =======================================================================
    # PAGE 4 — WEEKLY REPORT
    # =======================================================================

    elif page == "📋 Weekly Report":

        st.title("📋 Weekly Psychological Report")
        st.markdown("---")

        if not baseline:
            st.warning(
                f"Reports unlock after {config.BASELINE_DAYS} days. "
                f"You have {session_day_count} days."
            )
            st.stop()

        if st.button("📄 Generate My Report", use_container_width=True):
            with st.spinner("Analyzing and compiling report..."):
                entries, all_nlp, all_dist = load_and_process_all()
                pattern_results    = run_pattern_analysis(entries, all_nlp)
                prediction_results = run_predictions(entries, all_nlp)
                dist_history       = get_distortion_history(all_dist)
                last_dist          = all_dist[-1].get("distortions", {}) \
                                     if all_dist else {}
                intervention_res   = run_interventions(
                    pattern_results, prediction_results, last_dist
                )

                from modules.report_generator import (
                    build_header, build_overview, build_mood_energy_log,
                    build_sentiment_section, build_distortion_section,
                    build_pattern_section, build_prediction_section,
                    build_intervention_section, build_footer
                )
                import os
                date_str    = datetime.now().strftime("%Y-%m-%d %H:%M")
                report_text = "\n".join([
                    build_header(len(entries), date_str),
                    build_overview(entries),
                    build_mood_energy_log(entries),
                    build_sentiment_section(all_nlp, entries),
                    build_distortion_section(dist_history),
                    build_pattern_section(pattern_results),
                    build_prediction_section(prediction_results),
                    build_intervention_section(intervention_res),
                    build_footer()
                ])

            st.success("✅ Report generated!")
            st.markdown("---")
            st.text(report_text)

    # =======================================================================
    # PAGE 5 — FLUSH OUT
    # =======================================================================

    elif page == "💬 Flush Out":

        st.title("💬 Flush Out")
        st.markdown(
            "*Your personal assistant — trained on your journals, not on strangers.*"
        )
        st.markdown("---")

        with st.expander("💡 What is Flush Out?"):
            st.markdown("""
**Flush Out (FO)** is your personal companion — part friend, part advisor, part caretaker.

Unlike any other chatbot, FO actually **knows you**. It reads your journal entries over time and builds a psychological understanding of who you are — your mood patterns, emotional tendencies, thinking habits, and the things that affect you most.

**What FO can do:**
- 💬 **Just chat** — smalltalk, random topics, jokes, killing time
- 🧠 **Teach you things** — science, psychology, philosophy, life concepts
- 🎯 **Give real opinions** — on music, AI, school, relationships, anything
- 🤝 **Help you think through problems** — decisions, conflicts, anxiety, motivation
- 🫂 **Check in on you** — if your journals show you're struggling, FO notices

**One rule:** the more you journal, the better FO knows you.
            """)

        st.markdown("---")

        if entry_count == 0:
            st.warning("Write a few journal entries first, then come talk to FO.")
            st.stop()

        from modules.soul_helper import flush_out, save_conversation

        # Override soul_helper's load to use DB entries
        import modules.soul_helper as sh_module
        import modules.collector   as col_module

        original_load = col_module.load_all_entries

        def load_for_user():
            return load_journal_entries(st.session_state["username"])

        col_module.load_all_entries = load_for_user

        if "fo_history" not in st.session_state:
            st.session_state["fo_history"] = []
        if "fo_intent" not in st.session_state:
            st.session_state["fo_intent"] = None

        for msg in st.session_state["fo_history"]:
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(msg["text"])
            else:
                with st.chat_message("assistant"):
                    st.markdown(msg["text"])

        user_input = st.chat_input("Talk to Flush Out...")

        if user_input:
            st.session_state["fo_history"].append({
                "role": "user",
                "text": user_input
            })

            response, is_clarifying, intent = flush_out(
                user_input,
                st.session_state["fo_history"]
            )

            st.session_state["fo_intent"] = intent
            st.session_state["fo_history"].append({
                "role":          "fo",
                "text":          response,
                "is_clarifying": is_clarifying
            })

            col_module.load_all_entries = original_load
            st.rerun()

        col_module.load_all_entries = original_load

        st.markdown("---")
        col_save, col_clear = st.columns(2)

        with col_save:
            if st.button("💾 Save Conversation", use_container_width=True):
                if st.session_state["fo_history"]:
                    save_conversation(st.session_state["fo_history"])
                    st.success("Conversation saved.")
                else:
                    st.info("Nothing to save yet.")

        with col_clear:
            if st.button("🗑️ Clear Conversation", use_container_width=True):
                st.session_state["fo_history"] = []
                st.session_state["fo_intent"]  = None
                st.rerun()

    # =======================================================================
    # PAGE 6 — RESEARCHER DASHBOARD
    # =======================================================================

    elif page == "🔬 Researcher":

        st.title("🔬 Researcher Dashboard")
        st.markdown("*Cross-user psychological analysis — no journal text visible.*")
        st.markdown("---")

        # PIN protection
        if "researcher_auth" not in st.session_state:
            st.session_state["researcher_auth"] = False

        if not st.session_state["researcher_auth"]:
            st.warning("🔒 This page is PIN-protected.")
            r_pin = st.text_input("Enter Researcher PIN",
                                   type="password", max_chars=6)
            if st.button("Unlock", use_container_width=True):
                if r_pin == RESEARCHER_PIN:
                    st.session_state["researcher_auth"] = True
                    st.rerun()
                else:
                    st.error("Wrong PIN.")
            st.stop()

        # --- Researcher content ---
        st.success("✅ Access granted.")

        data = load_researcher_data()

        if not data:
            st.info(
                "No analysis data yet. "
                "Users need to visit the Insights page to generate snapshots."
            )
            st.stop()

        st.markdown(f"### 👥 {len(data)} User(s) Analyzed")
        st.markdown("---")

        for user_data in data:
            uname       = user_data.get("username", "unknown")
            risk_flag   = user_data.get("risk_flagged", False)
            entry_count = user_data.get("entry_count", 0)

            # Header with risk indicator
            risk_label = "🔴 FLAGGED" if risk_flag else "🟢 Stable"
            st.markdown(f"## {uname.title()}  —  {risk_label}")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Avg Mood",   f"{user_data.get('avg_mood',   0)}/10")
            with col2:
                st.metric("Avg Energy", f"{user_data.get('avg_energy', 0)}/10")
            with col3:
                st.metric("Avg Sleep",  f"{user_data.get('avg_sleep',  0)}h")
            with col4:
                st.metric("Entries",    entry_count)

            col5, col6, col7 = st.columns(3)

            with col5:
                mood_t = user_data.get("mood_trend", "stable")
                emoji  = "📈" if mood_t == "improving" else \
                         ("📉" if mood_t == "declining" else "➡️")
                st.metric("Mood Trend", f"{emoji} {mood_t.title()}")

            with col6:
                st.metric("Dominant Emotion",
                          user_data.get("dominant_emotion", "neutral").title())

            with col7:
                st.metric("Most Common Distortion",
                          user_data.get("most_common_distortion", "None"))

            if risk_flag:
                st.error(
                    f"⚠️ **{uname.title()}** has been flagged. "
                    f"Mood, sentiment, or sleep patterns suggest they may be struggling. "
                    f"Consider checking in with them."
                )

            st.markdown(f"*Last snapshot: {user_data.get('snapshot_date', '?')}*")
            st.markdown("---")

        if st.button("🔒 Lock Dashboard", use_container_width=True):
            st.session_state["researcher_auth"] = False
            st.rerun()


# ===========================================================================
# ROUTER — Login screen or main app
# ===========================================================================

if st.session_state["logged_in"]:
    show_main_app()
else:
    show_login()