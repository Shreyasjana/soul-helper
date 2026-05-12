# app.py
# ---------------------------------------------------------------------------
# Soul Helper (SH) — Multi-user Streamlit frontend with Supabase backend
# ---------------------------------------------------------------------------

import streamlit as st
import sys
import os
import pandas as pd
from datetime import datetime, timedelta
import pytz
IST = pytz.timezone("Asia/Kolkata")

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from modules.collector           import (save_entry, get_session_day)
from modules.nlp_processor       import process_journal
from modules.distortion_detector import (detect_distortions, get_distortion_summary,
                                          get_distortion_history)
from modules.pattern_detector    import run_pattern_analysis
from modules.predictor           import run_predictions
from modules.intervention        import run_interventions
from modules.snapshot            import generate_daily_snapshot, generate_weekly_analysis
from modules.database            import (create_user, verify_user,
                                          save_journal_entry,
                                          load_journal_entries,
                                          load_entries_by_day_db,
                                          delete_journal_entry_db,
                                          count_session_days_db,
                                          count_entries_db,
                                          save_researcher_snapshot,
                                          load_researcher_data)

st.set_page_config(page_title="Soul Helper", page_icon="🧠", layout="wide")

RESEARCHER_PASSWORD = "007700"

if "logged_in"  not in st.session_state: st.session_state["logged_in"]  = False
if "username"   not in st.session_state: st.session_state["username"]   = None
if "user_id"    not in st.session_state: st.session_state["user_id"]    = None
if "fo_history" not in st.session_state: st.session_state["fo_history"] = []
if "fo_intent"  not in st.session_state: st.session_state["fo_intent"]  = None


def load_and_process_all(username):
    entries  = load_journal_entries(username)
    all_nlp, all_dist = [], []
    for entry in entries:
        text = entry.get("journal", "")
        nlp  = process_journal(text)
        dist = detect_distortions(text)
        nlp["distortions"] = dist
        all_nlp.append(nlp)
        all_dist.append({"distortions": dist})
    return entries, all_nlp, all_dist


def build_day_chart(entries):
    day_map = {}
    for e in entries:
        day = e.get("session_day", "")
        if day not in day_map:
            day_map[day] = {"moods": [], "energys": []}
        day_map[day]["moods"].append(e.get("mood", 5))
        day_map[day]["energys"].append(e.get("energy", 5))
    sorted_days  = sorted(day_map.keys())
    avg_moods    = [round(sum(day_map[d]["moods"])   / len(day_map[d]["moods"]),   1) for d in sorted_days]
    avg_energys  = [round(sum(day_map[d]["energys"]) / len(day_map[d]["energys"]), 1) for d in sorted_days]
    short_days   = [d[5:] for d in sorted_days]
    return pd.DataFrame({"Mood": avg_moods, "Energy": avg_energys}, index=short_days)


# ===========================================================================
# LOGIN / REGISTER
# ===========================================================================

if not st.session_state["logged_in"]:
    st.title("🧠 Soul Helper")
    st.markdown("*Your Psychological Digital Twin*")
    st.markdown("---")

    tab1, tab2 = st.tabs(["🔑 Login", "✨ Register"])

    with tab1:
        st.markdown("### Welcome back")
        login_name = st.text_input("Your name", key="login_name", placeholder="Enter your username")
        login_pin  = st.text_input("Your PIN", type="password", key="login_pin",
                                   max_chars=8, placeholder="4 to 8 digits")
        if st.button("Login", use_container_width=True, key="btn_login"):
            if not login_name or not login_pin:
                st.error("Please enter both your name and PIN.")
            elif len(login_pin) < 4 or len(login_pin) > 8 or not login_pin.isdigit():
                st.error("PIN must be between 4 and 8 digits.")
            else:
                result = verify_user(login_name, login_pin)
                if result["success"]:
                    st.session_state["logged_in"] = True
                    st.session_state["username"]  = result["username"]
                    st.session_state["user_id"]   = result["user_id"]
                    st.rerun()
                else:
                    st.error(result["error"])

    with tab2:
        st.markdown("### Create your profile")
        st.info("Pick a name and a PIN (4–8 digits). Your PIN protects your journal.")
        reg_name = st.text_input("Choose a username", key="reg_name", placeholder="e.g. XXXXXXXX")
        reg_pin  = st.text_input("Choose a PIN (4–8 digits)", type="password",
                                  key="reg_pin", max_chars=8, placeholder="4 to 8 digits")
        reg_pin2 = st.text_input("Confirm PIN", type="password",
                                  key="reg_pin2", max_chars=8, placeholder="4 to 8 digits")
        if st.button("Create Account", use_container_width=True, key="btn_register"):
            if not reg_name or not reg_pin or not reg_pin2:
                st.error("Please fill in all fields.")
            elif len(reg_pin) < 4 or len(reg_pin) > 8 or not reg_pin.isdigit():
                st.error("PIN must be between 4 and 8 digits.")
            elif reg_pin != reg_pin2:
                st.error("PINs don't match.")
            else:
                result = create_user(reg_name, reg_pin)
                if result["success"]:
                    st.success(f"Account created! You can now log in as **{reg_name}**.")
                else:
                    st.error(result["error"])
    st.stop()


# ===========================================================================
# SIDEBAR
# ===========================================================================

username = st.session_state["username"]
user_id  = st.session_state["user_id"]

session_day_count = count_session_days_db(username)
entry_count       = count_entries_db(username)

st.sidebar.title("🧠 Soul Helper")
st.sidebar.markdown(f"*Hey, **{username}** 👋*")
st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Your Progress")
st.sidebar.progress(min(session_day_count / config.BASELINE_DAYS, 1.0))
st.sidebar.markdown(f"**{session_day_count} / {config.BASELINE_DAYS}** days logged")
st.sidebar.markdown(f"*({entry_count} total entries)*")

if session_day_count < config.BASELINE_DAYS:
    st.sidebar.info(f"⏳ {config.BASELINE_DAYS - session_day_count} more day(s) for full weekly analysis.")
else:
    st.sidebar.success("✅ Full analysis active.")

st.sidebar.markdown("---")
page = st.sidebar.radio("Navigate",
    ["📓 Journal", "🔍 Insights", "🧩 Distortions",
     "📋 Weekly Report", "💬 Flush Out", "🔬 Researcher"])
st.sidebar.markdown("---")

if st.sidebar.button("🚪 Logout"):
    for key in ["logged_in","username","user_id","fo_history","fo_intent","session_choice"]:
        if key in st.session_state: del st.session_state[key]
    st.rerun()


# ===========================================================================
# PAGE 1 — JOURNAL
# ===========================================================================

if page == "📓 Journal":
    st.title("📓 Daily Journal")
    st.markdown("Write freely. This is your space. The system will read between the lines so you don't have to.")
    st.caption("📌 This is where you journal daily. You can write multiple times a day. After saving, you'll get an instant mood and emotion analysis. Click 'Today's Snapshot' anytime to see a full summary of your day.")    
    st.markdown("---")

    now  = datetime.now(IST)
    hour = now.hour

    if 0 <= hour < 12:
        st.markdown(f"### {now.strftime('%A, %d %B %Y')} — {now.strftime('%I:%M %p')}")
        st.warning(f"⏰ It's {now.strftime('%I:%M %p')}. Which day do you want this entry to belong to?")
        col_opt1, col_opt2 = st.columns(2)
        with col_opt1:
            if st.button(f"📅 Yesterday  ({(now-timedelta(days=1)).strftime('%A, %d %B')})",
                         use_container_width=True, key="session_yesterday"):
                st.session_state["session_choice"] = "yesterday"
        with col_opt2:
            if st.button(f"📅 Today  ({now.strftime('%A, %d %B')})",
                         use_container_width=True, key="session_today"):
                st.session_state["session_choice"] = "today"
        if "session_choice" not in st.session_state:
            st.session_state["session_choice"] = "yesterday"
        user_choice   = st.session_state["session_choice"]
        today_session = get_session_day(now, user_choice=user_choice)
        choice_label  = (now-timedelta(days=1)).strftime("%A, %d %B") if user_choice=="yesterday" else now.strftime("%A, %d %B")
        st.info(f"✅ Entry will be saved under: **{choice_label}** ({today_session})")
    else:
        today_session = get_session_day(now)
        if "session_choice" in st.session_state: del st.session_state["session_choice"]
        st.markdown(f"### {now.strftime('%A, %d %B %Y')}")

    today_entries = load_entries_by_day_db(username, today_session)
    st.markdown("---")
    st.info("💡 **Multi-entry:** You can journal multiple times. Each entry is timestamped.")
    st.markdown("#### ✍️ Write a New Entry")

    journal_text = st.text_area("What's on your mind?", height=200,
                                 placeholder="Write about your day, how you're feeling...",
                                 key="journal_input")
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1: mood   = st.slider("😊 Mood",           config.MOOD_MIN,        config.MOOD_MAX,        5)
    with col2: energy = st.slider("⚡ Energy",          config.ENERGY_MIN,      config.ENERGY_MAX,      5)
    with col3: sleep  = st.slider("😴 Sleep (hours)",  float(config.SLEEP_MIN),float(config.SLEEP_MAX),7.0,step=0.5)
    st.markdown("---")

    if st.button("💾 Save Entry", use_container_width=True):
        if not journal_text.strip():
            st.error("Please write something before saving.")
        else:
            entry     = save_entry(journal_text, mood, energy, sleep,
                                   typing_time_seconds=0, session_day_override=today_session)
            db_result = save_journal_entry(username, user_id, entry)
            if db_result["success"]:
                st.success(f"✅ Entry saved at **{entry['time']}** under session: **{entry['session_day']}**")
            else:
                st.error(f"Save failed: {db_result['error']}")

            st.markdown("---")
            st.markdown("### 🔍 Quick Analysis")
            nlp  = process_journal(journal_text)
            dist = detect_distortions(journal_text)
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                label = nlp["sentiment"]["label"]
                score = nlp["sentiment"]["compound_score"]
                emoji = "😊" if label=="positive" else ("😔" if label=="negative" else "😐")
                st.metric("Sentiment", f"{emoji} {label.title()}", f"Score: {score}")
            with col_b:
                st.metric("Dominant Emotion", nlp["emotion"]["dominant_emotion"].title())
            with col_c:
                ag     = entry['behavioral_signals']['agitation_score']
                em_ag  = "🔥" if ag>0.7 else ("⚡" if ag>0.4 else "😌")
                st.metric("Agitation Level", f"{em_ag} {ag}")
            if nlp["keywords"]:
                st.markdown("**Key themes:** " + " ".join([f"`{k}`" for k in nlp["keywords"]]))
            if not dist["clean"]:
                st.markdown("---")
                st.warning(get_distortion_summary(dist))

    # Daily Snapshot
    st.markdown("---")
    today_entries = load_entries_by_day_db(username, today_session)

    if st.button("📊 Today's Snapshot", use_container_width=False):
        if not today_entries:
            st.info("No entries yet today. Write something first.")
        else:
            snap = generate_daily_snapshot(today_entries)
            if snap:
                st.markdown(f"### 📊 Daily Snapshot — {today_session}")
                st.markdown(f"*Based on {snap['entry_count']} entry/entries*")
                c1, c2, c3, c4 = st.columns(4)
                with c1: st.metric("Avg Mood",   f"{snap['avg_mood']}/10")
                with c2: st.metric("Avg Energy", f"{snap['avg_energy']}/10")
                with c3: st.metric("Avg Sleep",  f"{snap['avg_sleep']}h")
                with c4:
                    em = "🔥" if snap['avg_agitation']>0.7 else ("⚡" if snap['avg_agitation']>0.4 else "😌")
                    st.metric("Agitation", f"{em} {snap['avg_agitation']}")
                st.markdown(
                    f"**Emotion:** {snap['dominant_emotion'].title()}  |  "
                    f"**Tone:** {snap['sentiment_label'].title()}  |  "
                    f"**Agitation trend:** {snap['agitation_trend']}"
                )
                if snap["mood_over_time"]:
                    st.markdown("**Mood across today's entries:**")
                    mood_df = pd.DataFrame(snap["mood_over_time"], columns=["Time","Mood"]).set_index("Time")
                    st.line_chart(mood_df)
                if snap["keywords"]:
                    st.markdown("**Today's themes:** " + "  ".join([f"`{k}`" for k in snap["keywords"]]))
                st.markdown("---")
                st.info(f"💭 **Observation:** {snap['observation']}")
                tip_emoji = "🧘" if any(w in snap["tip"] for w in ["breath","stress","slow"]) else "💡"
                st.success(f"{tip_emoji} **Today's tip:** {snap['tip']}")
                if not snap["distortions"]["clean"]:
                    st.markdown("---")
                    st.warning(get_distortion_summary(snap["distortions"]))

    # All entries today
    st.markdown("---")
    st.markdown(f"### 📝 Entries for {today_session}  ({len(today_entries)} total)")
    if today_entries:
        for i, e in enumerate(today_entries, 1):
            entry_id  = e.get("entry_id","?")
            agitation = e['behavioral_signals']['agitation_score']
            with st.expander(f"Entry {i}  —  {e['time']}  |  Mood: {e['mood']}/10  |  Agitation: {agitation}"):
                col_left, col_right = st.columns([4,1])
                with col_left:
                    st.markdown(f"**Time:** {e['time']}  |  **Mood:** {e['mood']}/10  |  **Energy:** {e['energy']}/10  |  **Sleep:** {e['sleep_hours']}h")
                    st.info(e['journal'])
                with col_right:
                    st.markdown("&nbsp;", unsafe_allow_html=True)
                    if st.button("🗑️ Delete", key=f"delete_{entry_id}"):
                        delete_journal_entry_db(entry_id, username)
                        st.success("Deleted.")
                        st.rerun()
    else:
        st.info("No entries yet for this session. Start writing above.")

# -------------------------------------------------------------------
    # PAST ENTRIES BROWSER
    # -------------------------------------------------------------------
    st.markdown("---")
    st.markdown("### 📅 Browse Past Entries")
    st.caption("View your journal entries from any previous day.")

    all_entries_ever = load_journal_entries(username)

    if not all_entries_ever:
        st.info("No past entries yet.")
    else:
        # Get all unique session days
        all_days = sorted(
            set(e.get("session_day", "") for e in all_entries_ever),
            reverse=True
        )

        selected_day = st.selectbox(
            "Select a date",
            options=all_days,
            key="past_day_selector"
        )

        if selected_day:
            past_entries = load_entries_by_day_db(username, selected_day)

            if past_entries:
                st.markdown(f"**{len(past_entries)} entry/entries for {selected_day}:**")
                for i, e in enumerate(past_entries, 1):
                    with st.expander(
                        f"Entry {i}  —  {e['time']}  |  "
                        f"Mood: {e['mood']}/10  |  "
                        f"Energy: {e['energy']}/10"
                    ):
                        st.markdown(
                            f"**Time:** {e['time']}  |  "
                            f"**Mood:** {e['mood']}/10  |  "
                            f"**Energy:** {e['energy']}/10  |  "
                            f"**Sleep:** {e['sleep_hours']}h"
                        )
                        st.info(e['journal'])

                        # Quick NLP on past entry
                        nlp  = process_journal(e['journal'])
                        dist = detect_distortions(e['journal'])

                        col_x, col_y, col_z = st.columns(3)
                        with col_x:
                            label = nlp["sentiment"]["label"]
                            emoji = "😊" if label=="positive" else ("😔" if label=="negative" else "😐")
                            st.caption(f"Sentiment: {emoji} {label.title()}")
                        with col_y:
                            emotion = nlp["emotion"]["dominant_emotion"].title()
                            st.caption(f"Emotion: {emotion}")
                        with col_z:
                            ag = e['behavioral_signals']['agitation_score']
                            st.caption(f"Agitation: {ag}")

                        if not dist["clean"]:
                            st.warning(get_distortion_summary(dist))
            else:
                st.info(f"No entries found for {selected_day}.")


# ===========================================================================
# PAGE 2 — INSIGHTS (from day 1)
# ===========================================================================

elif page == "🔍 Insights":
    st.title("🔍 Insights")
    st.caption("📌 This page shows how your mood, energy, and emotions have changed over time. You'll see graphs, patterns, sleep impact, day-of-week trends, predictions for tomorrow, and personalized suggestions — all based on your journal data. Updates every time you journal.")
    if entry_count == 0:
        st.info("Write your first journal entry to start seeing insights.")
        st.stop()

    entries, all_nlp, all_dist = load_and_process_all(username)

    # Single combined mood + energy graph
    st.markdown("### 📈 Mood & Energy Over Time")
    chart_df = build_day_chart(entries)
    st.line_chart(chart_df)

    moods   = [e.get("mood",5)        for e in entries]
    energys = [e.get("energy",5)      for e in entries]
    sleeps  = [e.get("sleep_hours",7) for e in entries]
    c1,c2,c3 = st.columns(3)
    with c1: st.metric("Avg Mood",   f"{round(sum(moods)/len(moods),1)}/10")
    with c2: st.metric("Avg Energy", f"{round(sum(energys)/len(energys),1)}/10")
    with c3: st.metric("Avg Sleep",  f"{round(sum(sleeps)/len(sleeps),1)}h")

    if len(set(e.get("session_day","") for e in entries)) >= 2:
        pattern_results    = run_pattern_analysis(entries, all_nlp)
        prediction_results = run_predictions(entries, all_nlp)
        last_dist          = all_dist[-1].get("distortions",{}) if all_dist else {}
        intervention_res   = run_interventions(pattern_results, prediction_results, last_dist)
        dist_history       = get_distortion_history(all_dist)

        save_researcher_snapshot(username, {
            "username":               username,
            "avg_mood":               round(sum(moods)/len(moods),2),
            "avg_energy":             round(sum(energys)/len(energys),2),
            "avg_sleep":              round(sum(sleeps)/len(sleeps),2),
            "mood_trend":             pattern_results.get("mood_trend",{}).get("trend","stable"),
            "energy_trend":           pattern_results.get("energy_trend",{}).get("trend","stable"),
            "dominant_emotion":       "neutral",
            "most_common_distortion": dist_history.get("most_common","None"),
            "entry_count":            len(entries),
            "predictions":            prediction_results,
        })

        st.markdown("---")
        st.markdown("### 😴 Sleep Impact")
        if pattern_results["sleep_impact"]["correlation_flag"]:
            st.warning(pattern_results["sleep_impact"]["message"])
        else:
            st.info(pattern_results["sleep_impact"]["message"])

        st.markdown("---")
        st.markdown("### 📅 Day of Week Patterns")
        day_data = pattern_results["day_of_week"]
        c3,c4 = st.columns(2)
        with c3: st.success(f"🌟 Best day: **{day_data.get('best_day','?')}**")
        with c4: st.error(f"⚠️ Hardest day: **{day_data.get('worst_day','?')}**")

        st.markdown("---")
        st.markdown("### 🏷️ Recurring Life Themes")
        themes = pattern_results.get("recurring_themes",[])
        if themes:
            st.markdown(" ".join([f"`{t}`" for t in themes]))
        else:
            st.info("Keep journaling — themes will emerge soon.")

        st.markdown("---")
        st.markdown("### 🔮 Tomorrow's Forecast")
        mood_pred   = prediction_results["mood_prediction"]
        energy_pred = prediction_results["energy_prediction"]
        c5,c6 = st.columns(2)
        with c5:
            if mood_pred.get("predicted_mood"):
                st.metric("Predicted Mood", f"{mood_pred['predicted_mood']}/10",
                          f"Confidence: {mood_pred['confidence']}")
        with c6:
            if energy_pred.get("predicted_energy"):
                st.metric("Predicted Energy", f"{energy_pred['predicted_energy']}/10",
                          f"Confidence: {energy_pred['confidence']}")

        risk = prediction_results["risk_flags"]
        if risk["flagged"]:
            st.markdown("---")
            for flag in risk["flags"]: st.error(flag)

        st.markdown("---")
        st.markdown("### 💡 Personalized Interventions")
        for item in intervention_res.get("interventions",[]):
            with st.expander(f"🔸 {item['title']}"):
                st.markdown(item["message"])
                st.markdown(f"*Framework: {item['framework']}*")
    else:
        st.info("Add one more day of entries to unlock pattern analysis.")

    # Weekly breakdown
    st.markdown("---")
    st.markdown("### 📆 Weekly Breakdown")
    week_analyses = generate_weekly_analysis(entries)
    if not week_analyses:
        st.info("Keep journaling — weekly breakdown will appear soon.")
    else:
        for week in week_analyses:
            with st.expander(f"📅 {week['label']}  —  {week['day_count']} days  |  Avg Mood: {week['avg_mood']}/10"):
                wc1,wc2,wc3,wc4 = st.columns(4)
                with wc1: st.metric("Avg Mood",   f"{week['avg_mood']}/10")
                with wc2: st.metric("Avg Energy", f"{week['avg_energy']}/10")
                with wc3: st.metric("Avg Sleep",  f"{week['avg_sleep']}h")
                with wc4: st.metric("Mood Trend", week["mood_trend"].title())
                st.markdown(
                    f"**Dominant Emotion:** {week['dominant_emotion'].title()}  |  "
                    f"**Tone:** {week['sentiment'].title()}  |  "
                    f"**Entries:** {week['entry_count']}"
                )
                if week["day_avg_moods"]:
                    sorted_keys  = sorted(week["day_avg_moods"].keys())
                    short_labels = [d[5:] for d in sorted_keys]
                    week_df = pd.DataFrame({
                        "Mood":   [week["day_avg_moods"][d]   for d in sorted_keys],
                        "Energy": [week["day_avg_energys"][d] for d in sorted_keys]
                    }, index=short_labels)
                    st.line_chart(week_df)
                if week["keywords"]:
                    st.markdown("**Week themes:** " + "  ".join([f"`{k}`" for k in week["keywords"]]))
                if not week["distortions"]["clean"]:
                    st.warning(get_distortion_summary(week["distortions"]))


# ===========================================================================
# PAGE 3 — DISTORTIONS
# ===========================================================================

elif page == "🧩 Distortions":
    st.title("🧩 Cognitive Distortion Tracker")
    st.caption("📌 Cognitive distortions are irrational thinking patterns — like catastrophizing, self-blame, or black-and-white thinking. This page scans your journal text for these patterns using CBT (Cognitive Behavioral Therapy) frameworks and tracks which ones show up most often in your thinking.")    
    st.markdown("---")
    if entry_count == 0:
        st.info("No journal entries yet.")
        st.stop()

    entries, all_nlp, all_dist = load_and_process_all(username)
    st.markdown("### 🔍 Most Recent Entry Analysis")
    today_entries = load_entries_by_day_db(username, get_session_day(datetime.now(IST)))
    if today_entries:
        latest_dist = detect_distortions(today_entries[-1].get("journal",""))
        summary     = get_distortion_summary(latest_dist)
        if latest_dist["clean"]: st.success(summary)
        else: st.warning(summary)
    else:
        st.info("No entries yet for today's session.")

    st.markdown("---")
    if len(entries) >= 2:
        st.markdown("### 📊 Distortion History")
        history     = get_distortion_history(all_dist)
        freq_map    = history["frequency_map"]
        c1,c2 = st.columns(2)
        with c1: st.metric("Days with distortions", history["total_flagged"])
        with c2: st.metric("Most common distortion", history["most_common"])
        active = {k:v for k,v in freq_map.items() if v>0}
        if active: st.bar_chart(active)
        else: st.success("No distortions detected across your history.")
    else:
        st.info("Add more entries to see distortion history.")


# ===========================================================================
# PAGE 4 — WEEKLY REPORT
# ===========================================================================

elif page == "📋 Weekly Report":
    st.title("📋 Weekly Psychological Report")
    st.caption("📌 Click the button to generate a full report of your psychological patterns — mood trends, energy levels, sleep, emotional tone, cognitive distortions, and personalized interventions. All your data compiled into one readable summary.")    
    st.markdown("---")
    if entry_count == 0:
        st.info("No entries yet. Start journaling first.")
        st.stop()

    if st.button("📄 Generate My Report", use_container_width=True):
        with st.spinner("Analyzing your data..."):
            entries  = load_journal_entries(username)
            all_nlp, all_dist = [], []
            for entry in entries:
                text = entry.get("journal","")
                nlp  = process_journal(text)
                dist = detect_distortions(text)
                nlp["distortions"] = dist
                all_nlp.append(nlp)
                all_dist.append({"distortions": dist})
            dist_history = get_distortion_history(all_dist)
            last_dist    = all_dist[-1].get("distortions",{}) if all_dist else {}

        st.markdown("---")
        st.markdown(f"## 🧠 Report for {username.title()}")
        st.markdown(f"*{datetime.now(IST).strftime('%d %B %Y, %I:%M %p')}  |  {len(entries)} entries  |  {session_day_count} days*")
        st.markdown("---")

        moods   = [e.get("mood",5)        for e in entries]
        energys = [e.get("energy",5)      for e in entries]
        sleeps  = [e.get("sleep_hours",7) for e in entries]
        c1,c2,c3 = st.columns(3)
        with c1: st.metric("Avg Mood",   f"{round(sum(moods)/len(moods),1)}/10")
        with c2: st.metric("Avg Energy", f"{round(sum(energys)/len(energys),1)}/10")
        with c3: st.metric("Avg Sleep",  f"{round(sum(sleeps)/len(sleeps),1)}h")

        st.markdown("### 📈 Mood & Energy Over All Days")
        st.line_chart(build_day_chart(entries))

        st.markdown("---")
        st.markdown("### 🧩 Cognitive Distortions")
        st.markdown(f"**Days with distortions:** {dist_history.get('total_flagged',0)}  |  **Most common:** {dist_history.get('most_common','None')}")

        if len(entries) >= 2:
            pattern_results    = run_pattern_analysis(entries, all_nlp)
            prediction_results = run_predictions(entries, all_nlp)
            intervention_res   = run_interventions(pattern_results, prediction_results, last_dist)
            st.markdown("---")
            st.markdown("### 💡 Personalized Interventions")
            for item in intervention_res.get("interventions",[]):
                with st.expander(f"🔸 {item['title']}"):
                    st.markdown(item["message"])
                    st.markdown(f"*{item['framework']}*")
            risk = prediction_results["risk_flags"]
            if risk["flagged"]:
                st.markdown("---")
                st.markdown("### ⚠️ Risk Flags")
                for flag in risk["flags"]: st.error(flag)

        st.markdown("---")
        st.markdown("### 📆 Week-by-Week Summary")
        for week in generate_weekly_analysis(entries):
            st.markdown(
                f"**{week['label']}** — Mood: {week['avg_mood']}/10  |  "
                f"Energy: {week['avg_energy']}/10  |  Sleep: {week['avg_sleep']}h  |  "
                f"Trend: {week['mood_trend'].title()}  |  Emotion: {week['dominant_emotion'].title()}"
            )


# ===========================================================================
# PAGE 5 — FLUSH OUT
# ===========================================================================

elif page == "💬 Flush Out":
    st.title("💬 Flush Out")
    st.caption("📌 FO is your personal companion — it knows you from your journals. Talk about anything: your day, problems, random topics, philosophy, or just chat. The more you journal, the more personal and accurate FO's responses become.")    
    st.markdown("*Your personal assistant — trained on your journals, not on strangers.*")
    st.markdown("---")

    with st.expander("💡 What is Flush Out?"):
        st.markdown("""
**Flush Out (FO)** is your personal companion — part friend, part advisor, part caretaker.

Unlike any other chatbot, FO actually **knows you**. It reads your journal entries and builds
a psychological understanding of who you are.

**What FO can do:**
- 💬 Just chat — smalltalk, random topics, jokes, killing time
- 🧠 Teach you things — science, psychology, philosophy, life concepts
- 🎯 Give real opinions — on music, AI, school, relationships, anything
- 🤝 Help you think through problems — decisions, conflicts, anxiety, motivation
- 🫂 Check in on you — if your journals show you're struggling, FO notices
        """)

    st.markdown("---")
    if entry_count == 0:
        st.warning("Write a few journal entries first and then come talk to FO.")
        st.stop()

    from modules.soul_helper import flush_out, save_conversation
    import modules.soul_helper as sh_module

    def supabase_build_profile():
        entries = load_journal_entries(username)
        if not entries: return None
        all_nlp, all_dist = [], []
        for entry in entries:
            text = entry.get("journal","")
            nlp  = process_journal(text)
            dist = detect_distortions(text)
            nlp["distortions"] = dist
            all_nlp.append(nlp)
            all_dist.append({"distortions": dist})
        from modules.pattern_detector    import run_pattern_analysis
        from modules.distortion_detector import get_distortion_history
        patterns     = run_pattern_analysis(entries, all_nlp)
        dist_history = get_distortion_history(all_dist)
        moods   = [e.get("mood",5)        for e in entries]
        energys = [e.get("energy",5)      for e in entries]
        sleeps  = [e.get("sleep_hours",7) for e in entries]
        recent_entries       = entries[-3:]
        recent_agitation     = [e.get("behavioral_signals",{}).get("agitation_score",0) for e in recent_entries]
        avg_agitation        = round(sum(recent_agitation)/len(recent_agitation),2) if recent_agitation else 0
        recent_nlp           = all_nlp[-3:]
        recent_sentiments    = [r.get("sentiment",{}).get("compound_score",0) for r in recent_nlp]
        avg_recent_sentiment = round(sum(recent_sentiments)/len(recent_sentiments),2) if recent_sentiments else 0
        recent_emotions      = [r.get("emotion",{}).get("dominant_emotion","neutral") for r in recent_nlp]
        dominant_emotion     = max(set(recent_emotions),key=recent_emotions.count) if recent_emotions else "neutral"
        distortion_freq      = dist_history.get("frequency_map",{})
        active_distortions   = [d for d,c in distortion_freq.items() if c>1]
        return {
            "entry_count":             len(entries),
            "avg_mood":                round(sum(moods)/len(moods),2),
            "avg_energy":              round(sum(energys)/len(energys),2),
            "avg_sleep":               round(sum(sleeps)/len(sleeps),2),
            "avg_recent_agitation":    avg_agitation,
            "avg_recent_sentiment":    avg_recent_sentiment,
            "dominant_recent_emotion": dominant_emotion,
            "mood_trend":              patterns.get("mood_trend",{}).get("trend","stable"),
            "energy_trend":            patterns.get("energy_trend",{}).get("trend","stable"),
            "sleep_affects_mood":      patterns.get("sleep_impact",{}).get("correlation_flag",False),
            "best_day":                patterns.get("day_of_week",{}).get("best_day","Unknown"),
            "worst_day":               patterns.get("day_of_week",{}).get("worst_day","Unknown"),
            "recurring_themes":        patterns.get("recurring_themes",[]),
            "most_common_distortion":  dist_history.get("most_common","None"),
            "active_distortions":      active_distortions,
            "raw_entries":             entries,
            "all_nlp":                 all_nlp
        }

    sh_module.build_profile = supabase_build_profile

    for msg in st.session_state["fo_history"]:
        if msg["role"]=="user":
            with st.chat_message("user"): st.markdown(msg["text"])
        else:
            with st.chat_message("assistant"): st.markdown(msg["text"])

    user_input = st.chat_input("Talk to Flush Out...")
    if user_input:
        st.session_state["fo_history"].append({"role":"user","text":user_input})
        response, is_clarifying, intent = flush_out(user_input, st.session_state["fo_history"])
        st.session_state["fo_intent"] = intent
        st.session_state["fo_history"].append({"role":"fo","text":response,"is_clarifying":is_clarifying})
        st.rerun()

    st.markdown("---")
    c_save, c_clear = st.columns(2)
    with c_save:
        if st.button("💾 Save Conversation", use_container_width=True):
            if st.session_state["fo_history"]:
                save_conversation(st.session_state["fo_history"])
                st.success("Conversation saved.")
            else: st.info("Nothing to save yet.")
    with c_clear:
        if st.button("🗑️ Clear Conversation", use_container_width=True):
            st.session_state["fo_history"] = []
            st.session_state["fo_intent"]  = None
            st.rerun()


# ===========================================================================
# PAGE 6 — RESEARCHER
# ===========================================================================

elif page == "🔬 Researcher":
    st.title("🔬 Researcher Dashboard")
    st.caption("📌 Password-protected page for the researcher only. Shows behavioral analysis of all users — mood trends, emotional patterns, distortion frequency, and risk flags. Raw journal text is never shown here.")
    st.markdown("*Cross-user psychological analysis — no raw journal text.*")
    st.markdown("---")

    if "researcher_auth" not in st.session_state:
        st.session_state["researcher_auth"] = False

    if not st.session_state["researcher_auth"]:
        pwd = st.text_input("Enter Researcher PIN", type="password")
        if st.button("Unlock"):
            if pwd == RESEARCHER_PASSWORD:
                st.session_state["researcher_auth"] = True
                st.rerun()
            else: st.error("Wrong PIN.")
        st.stop()

    data = load_researcher_data()
    if not data:
        st.info("No user data available yet.")
        st.stop()

    st.markdown(f"### 👥 {len(data)} User(s) Analyzed")
    st.markdown("---")

    for user_data in data:
        uname     = user_data.get("username","?").title()
        flagged   = user_data.get("risk_flagged",False)
        flag_icon = "🚨" if flagged else "✅"
        with st.expander(
            f"{flag_icon} **{uname}**  —  "
            f"Mood: {user_data.get('avg_mood','?')}/10  |  "
            f"Entries: {user_data.get('entry_count','?')}  |  "
            f"{'⚠️ FLAGGED' if flagged else 'Stable'}"
        ):
            c1,c2,c3 = st.columns(3)
            with c1:
                st.metric("Avg Mood",   f"{user_data.get('avg_mood','?')}/10")
                st.metric("Mood Trend", user_data.get("mood_trend","?").title())
            with c2:
                st.metric("Avg Energy",   f"{user_data.get('avg_energy','?')}/10")
                st.metric("Energy Trend", user_data.get("energy_trend","?").title())
            with c3:
                st.metric("Avg Sleep", f"{user_data.get('avg_sleep','?')}h")
                st.metric("Entries",   user_data.get("entry_count","?"))
            st.markdown("---")
            st.markdown(
                f"**Dominant Emotion:** {user_data.get('dominant_emotion','?').title()}  |  "
                f"**Most Common Distortion:** {user_data.get('most_common_distortion','None')}  |  "
                f"**Risk Flagged:** {'YES ⚠️' if flagged else 'No'}"
            )
            if flagged:
                st.error(f"⚠️ {uname} has been flagged. Their mood/sentiment has been consistently low. Consider checking in.")

    st.markdown("---")
    st.markdown("*Raw journal text is never shown here. Only behavioral metrics.*")