"""Longevity dashboard.

Reads daily briefs from Turso (when TURSO_DB_URL + TURSO_AUTH_TOKEN are set,
e.g. on Streamlit Community Cloud) and otherwise from the local SQLite DB.
Both paths go through db.py so behaviour is identical locally and in the cloud.
"""

import json
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import db

ACCENT = "#5ce0d8"
GOOD = "#5ce0d8"
WARN = "#f5a623"
BAD = "#ef5d5d"
MUTED = "#8a93a6"

st.set_page_config(page_title="Longevity Dashboard", page_icon="🫀", layout="wide")

st.markdown(
    """
    <style>
      .block-container { padding-top: 2rem; }
      h1, h2, h3 { letter-spacing: -0.01em; }
      .verdict-card {
          background: #141825; border: 1px solid #232a3d; border-radius: 14px;
          padding: 1.1rem 1.4rem; margin-bottom: 0.5rem;
      }
      .verdict-card .verdict { font-size: 1.35rem; font-weight: 650; color: #5ce0d8; }
      .flag-high { color: #ef5d5d; font-weight: 600; }
      .muted { color: #8a93a6; }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- #
# Data access
# --------------------------------------------------------------------------- #
def _using_cloud() -> bool:
    return bool(os.environ.get("TURSO_DB_URL") and os.environ.get("TURSO_AUTH_TOKEN"))


@st.cache_data(ttl=300, show_spinner=False)
def load_briefs() -> list[dict]:
    """Fetch all daily briefs (newest first) as a list of plain dicts."""
    conn = db.get_cloud_db() if _using_cloud() else db.get_local_db()
    db.init_db(conn)
    rows = conn.execute(
        "SELECT date, verdict, brief, garmin_json, created_at "
        "FROM daily_briefs ORDER BY date DESC"
    ).fetchall()
    cols = ["date", "verdict", "brief", "garmin_json", "created_at"]
    result = [dict(zip(cols, r)) for r in rows]
    try:
        conn.close()
    except Exception:
        pass
    return result


def parse_garmin(brief: dict) -> dict:
    try:
        return json.loads(brief.get("garmin_json") or "{}") or {}
    except (json.JSONDecodeError, TypeError):
        return {}


def latest_with_labs(briefs: list[dict]) -> dict | None:
    """Return lab_results from the most recent brief that contains them."""
    for brief in briefs:  # already newest-first
        g = parse_garmin(brief)
        if g.get("lab_results"):
            return g["lab_results"]
    return None


def fmt(value, suffix: str = "", dash: str = "—"):
    if value is None or value == "":
        return dash
    return f"{value}{suffix}"


# --------------------------------------------------------------------------- #
# Load
# --------------------------------------------------------------------------- #
st.title("🫀 Longevity Dashboard")
st.caption(("Cloud (Turso)" if _using_cloud() else "Local SQLite") + " · auto-refreshes every 5 min")

briefs = load_briefs()
if not briefs:
    st.info("No briefs yet. Run `save_brief.py` to populate the database.")
    st.stop()

latest = briefs[0]
g = parse_garmin(latest)
sleep = g.get("sleep") or {}
hrv = g.get("hrv") or {}
recovery = g.get("recovery") or {}
training = g.get("training") or {}

tab_today, tab_sleep, tab_training, tab_trends, tab_labs = st.tabs(
    ["Today", "Sleep & Recovery", "Training", "Trends", "Labs"]
)

# --------------------------------------------------------------------------- #
# Today
# --------------------------------------------------------------------------- #
with tab_today:
    st.markdown(
        f"<div class='verdict-card'><div class='muted'>{latest['date']}</div>"
        f"<div class='verdict'>{latest.get('verdict') or 'No verdict'}</div></div>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Training Readiness",
              fmt(recovery.get("training_readiness_score")),
              recovery.get("training_readiness_level") or None)
    c2.metric("Body Battery (wake)", fmt(recovery.get("body_battery_at_wakeup")))
    c3.metric("Resting HR", fmt(recovery.get("resting_heart_rate"), " bpm"))
    c4.metric("Avg Stress", fmt(recovery.get("avg_stress")))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Sleep Score", fmt(sleep.get("score")))
    c6.metric("Sleep Duration", fmt(sleep.get("total_sleep_hours"), " h"))
    c7.metric("HRV (last night)", fmt(hrv.get("last_night_avg_ms"), " ms"), hrv.get("status") or None)
    c8.metric("Steps", fmt(g.get("steps_today")))

    if latest.get("brief"):
        st.markdown("### Daily Brief")
        st.write(latest["brief"])

# --------------------------------------------------------------------------- #
# Sleep & Recovery
# --------------------------------------------------------------------------- #
with tab_sleep:
    st.subheader("Last Night")
    stages = {
        "Deep": sleep.get("deep_sleep_minutes"),
        "REM": sleep.get("rem_sleep_minutes"),
        "Light": sleep.get("light_sleep_minutes"),
        "Awake": sleep.get("awake_minutes"),
    }
    have_stages = any(v for v in stages.values())

    col_a, col_b = st.columns([1.2, 1])
    with col_a:
        if have_stages:
            fig = go.Figure(
                go.Bar(
                    x=list(stages.values()),
                    y=list(stages.keys()),
                    orientation="h",
                    marker_color=[GOOD, "#7aa2f7", "#9aa5b1", WARN],
                    text=[fmt(v, " min", "") for v in stages.values()],
                    textposition="auto",
                )
            )
            fig.update_layout(
                template="plotly_dark", height=300,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=10, r=10, t=10, b=10), xaxis_title="minutes",
            )
            st.plotly_chart(fig, width="stretch")
        else:
            st.caption("No sleep-stage data for the latest night.")
    with col_b:
        st.metric("Total Sleep", fmt(sleep.get("total_sleep_hours"), " h"))
        st.metric("Sleep Score", fmt(sleep.get("score")))
        st.metric("Respiration (avg)", fmt(sleep.get("respiration_average")))
        st.caption(f"{fmt(sleep.get('sleep_start'))} → {fmt(sleep.get('sleep_end'))}")

    st.subheader("Recovery")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Current Body Battery", fmt(recovery.get("current_body_battery")))
    r2.metric("Body Battery at Wake", fmt(recovery.get("body_battery_at_wakeup")))
    r3.metric("Max Stress", fmt(recovery.get("max_stress")))
    r4.metric("Morning Readiness", fmt(recovery.get("morning_readiness")))

    h1, h2, h3, h4 = st.columns(4)
    h1.metric("HRV last night", fmt(hrv.get("last_night_avg_ms"), " ms"))
    h2.metric("HRV 5-day avg", fmt(hrv.get("five_day_avg_ms"), " ms"))
    h3.metric("HRV weekly high", fmt(hrv.get("weekly_high_ms"), " ms"))
    h4.metric("HRV weekly low", fmt(hrv.get("weekly_low_ms"), " ms"))

# --------------------------------------------------------------------------- #
# Training
# --------------------------------------------------------------------------- #
with tab_training:
    t1, t2, t3, t4 = st.columns(4)
    t1.metric("Training Load", fmt(training.get("training_load")), training.get("load_status") or None)
    t2.metric("Fitness Age", fmt(training.get("fitness_age")))
    t3.metric("Endurance Score", fmt(training.get("endurance_score")))
    t4.metric("Hill Score", fmt(training.get("hill_score")))

    race = training.get("race_predictions") or {}
    if race:
        st.subheader("Race Predictions")
        race_df = pd.DataFrame(
            [{"Distance": str(k), "Predicted Time": str(v)} for k, v in race.items()]
        )
        st.dataframe(race_df, hide_index=True, width="stretch")

    for label, key in [("Today's Activities", "activities_today"),
                       ("Yesterday's Activities", "activities_yesterday")]:
        acts = g.get(key) or []
        if acts:
            st.subheader(label)
            st.dataframe(pd.DataFrame(acts), hide_index=True, width="stretch")

    if not race and not (g.get("activities_today") or g.get("activities_yesterday")):
        st.caption("No training detail in the latest record.")

# --------------------------------------------------------------------------- #
# Trends (7-day)
# --------------------------------------------------------------------------- #
with tab_trends:
    trend = g.get("seven_day_trend") or []
    if trend:
        tdf = pd.DataFrame(trend).sort_values("date")
        series = [
            ("sleep_score", "Sleep Score", GOOD),
            ("hrv_last_night_avg_ms", "HRV (ms)", "#7aa2f7"),
            ("resting_hr", "Resting HR (bpm)", WARN),
        ]
        for col, title, color in series:
            if col in tdf and tdf[col].notna().any():
                fig = go.Figure(
                    go.Scatter(
                        x=tdf["date"], y=tdf[col], mode="lines+markers",
                        line=dict(color=color, width=2.5), marker=dict(size=7),
                    )
                )
                fig.update_layout(
                    template="plotly_dark", title=title, height=260,
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=10, r=10, t=40, b=10),
                )
                st.plotly_chart(fig, width="stretch")
        with st.expander("Raw 7-day data"):
            st.dataframe(tdf, hide_index=True, width="stretch")
    else:
        st.caption("No 7-day trend data in the latest record.")

# --------------------------------------------------------------------------- #
# Labs
# --------------------------------------------------------------------------- #
with tab_labs:
    labs = latest_with_labs(briefs)
    if not labs:
        st.info("No lab results found in any stored brief.")
    else:
        st.caption(
            f"Test date: {fmt(labs.get('test_date'))} · "
            f"Source: {fmt(labs.get('source'))}"
        )

        flags = labs.get("reference_flags") or {}
        if flags:
            st.subheader("⚠️ Flagged Markers")
            for name, info in flags.items():
                info = info or {}
                st.markdown(
                    f"<span class='flag-high'>{name}: {fmt(info.get('value'))} "
                    f"({fmt(info.get('flag'))})</span> — ref {fmt(info.get('ref_range'))}",
                    unsafe_allow_html=True,
                )
                if info.get("note"):
                    st.caption(info["note"])

        def panel(title: str, data: dict):
            if not data:
                return
            st.subheader(title)
            df = pd.DataFrame(
                [{"Marker": k, "Value": v} for k, v in data.items()]
            )
            st.dataframe(df, hide_index=True, width="stretch")

        col_l, col_r = st.columns(2)
        with col_l:
            panel("Lipid Panel", labs.get("lipid_panel") or {})
            panel("Glycemic", labs.get("glycemic") or {})
        with col_r:
            panel("Metabolic Panel", labs.get("metabolic_panel") or {})

        optimal = labs.get("optimal_ranges_for_athlete") or {}
        if optimal:
            with st.expander("Optimal ranges for athlete"):
                for k, v in optimal.items():
                    st.markdown(f"**{k}** — {v}")

        not_tested = labs.get("not_tested_recommend_next_time") or []
        if not_tested:
            with st.expander("Recommended next time (not tested)"):
                for item in not_tested:
                    st.markdown(f"- {item}")
