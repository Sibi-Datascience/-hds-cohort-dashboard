"""
HDS Cohort Progress Dashboard — Streamlit
Replaces the Looker Studio build. Reads live data from a published
Google Sheet CSV link (Google Sheet -> File -> Share -> Publish to web -> CSV).

Run locally:  streamlit run app.py
"""

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime

st.set_page_config(page_title="HDS Cohort Progress Dashboard", layout="wide")

# ---------------------------------------------------------------------------
# CONFIG — set this to your published Google Sheet CSV link
# (Sheet -> File -> Share -> Publish to web -> pick the response tab -> CSV)
# ---------------------------------------------------------------------------
DEFAULT_CSV_URL = ""  # paste your published CSV link here, or enter it below at runtime

EXPECTED_COLUMNS = [
    "Timestamp",
    "Student_Name",
    "Certification platform",
    "Certfication Progress",
    "Final project status",
    "Overall Completion Progress (%)",
    "Assessment / Milestone type",
    "Key Milestone Status",
    "Student_Comments",
]

STUDENTS = ["Sibi", "Sohitha", "Bindu", "David", "Keerthana",
            "Nithya", "Rik", "Valsalya", "Suban"]


@st.cache_data(ttl=120)
def load_data(csv_url: str) -> pd.DataFrame:
    df = pd.read_csv(csv_url)
    df.columns = [c.strip() for c in df.columns]

    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        st.warning(f"Missing expected columns from the sheet: {missing}. "
                   f"Charts using these fields will be skipped.")

    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")

    if "Overall Completion Progress (%)" in df.columns:
        df["Overall Completion Progress (%)"] = pd.to_numeric(
            df["Overall Completion Progress (%)"], errors="coerce"
        )
        # Convert 1-10 scale to a real 0-100 percentage
        df["Progress_Percent"] = (df["Overall Completion Progress (%)"] - 1) / 9 * 100

    if "Certfication Progress" in df.columns:
        df["Certfication Progress"] = pd.to_numeric(
            df["Certfication Progress"], errors="coerce"
        )

    return df


# ---------------------------------------------------------------------------
# Sidebar — data source + navigation
# ---------------------------------------------------------------------------
st.sidebar.title("HDS Cohort Dashboard")

csv_url = st.sidebar.text_input(
    "Published Google Sheet CSV link",
    value=DEFAULT_CSV_URL,
    help="Google Sheet -> File -> Share -> Publish to web -> select response tab -> CSV -> copy link",
)

page = st.sidebar.radio("View", ["Cohort Overview (Faculty)", "Individual Student View"])

if not csv_url:
    st.info("Paste your published Google Sheet CSV link in the sidebar to load live data. "
            "Below is a preview using sample data so you can see the layout.")
    rng = np.random.default_rng(7)
    sample_rows = []
    for i in range(40):
        s = rng.choice(STUDENTS)
        ts = pd.Timestamp("2026-06-01") + pd.Timedelta(days=int(rng.integers(0, 45)))
        sample_rows.append({
            "Timestamp": ts,
            "Student_Name": s,
            "Certification platform": rng.choice(["NPTEL", "Coursera", "Udemy", "Portfolio Project"]),
            "Certfication Progress": rng.integers(10, 100),
            "Final project status": rng.choice(["Proposal", "Draft", "Review", "Final"]),
            "Overall Completion Progress (%)": rng.integers(1, 11),
            "Assessment / Milestone type": rng.choice(["Quiz/Assignment", "Milestone %"]),
            "Key Milestone Status": rng.choice(["On Track", "Blocked", "Completed"], p=[0.55, 0.2, 0.25]),
            "Student_Comments": rng.choice(["Going well.", "Need advisor input.", "Ahead of schedule.", ""]),
        })
    df = pd.DataFrame(sample_rows)
    df["Progress_Percent"] = (df["Overall Completion Progress (%)"] - 1) / 9 * 100
else:
    df = load_data(csv_url)

if df.empty:
    st.error("No data loaded yet. Submit at least one Form response, then refresh.")
    st.stop()


# ===========================================================================
# PAGE 1 — COHORT OVERVIEW (FACULTY VIEW)
# ===========================================================================
if page == "Cohort Overview (Faculty)":
    st.title("Cohort Overview — Faculty Tracking View")

    selected_student = st.selectbox(
        "Filter to one student (leave as 'All' for the full cohort)",
        ["All"] + STUDENTS,
    )
    view_df = df if selected_student == "All" else df[df["Student_Name"] == selected_student]

    col1, col2 = st.columns(2)

    # 1. Cohort Engagement Heatmap ------------------------------------------------
    with col1:
        st.subheader("Cohort Engagement Heatmap")
        st.caption("Darker = more form updates submitted that week")
        heat_df = view_df.dropna(subset=["Timestamp"]).copy()
        if not heat_df.empty:
            heat_df["Week"] = heat_df["Timestamp"].dt.to_period("W").astype(str)
            pivot = heat_df.pivot_table(
                index="Student_Name", columns="Week", values="Timestamp",
                aggfunc="count", fill_value=0,
            )
            fig = px.imshow(pivot, aspect="auto", color_continuous_scale="Blues",
                             labels=dict(color="Submissions"))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No timestamped rows yet.")

    # 2. Overall Project Velocity Progress Grid ------------------------------------
    with col2:
        st.subheader("Overall Project Velocity")
        st.caption("Average per-certification progress (%) vs. average overall progress (%), by student")
        grid = view_df.groupby("Student_Name").agg(
            Avg_Cert_Progress=("Certfication Progress", "mean"),
            Avg_Overall_Progress=("Progress_Percent", "mean"),
        ).reset_index().sort_values("Avg_Overall_Progress", ascending=True)
        fig = go.Figure()
        fig.add_bar(y=grid["Student_Name"], x=grid["Avg_Cert_Progress"],
                    name="Cert Progress %", orientation="h")
        fig.add_bar(y=grid["Student_Name"], x=grid["Avg_Overall_Progress"],
                    name="Overall Progress %", orientation="h")
        fig.update_layout(barmode="group", xaxis_range=[0, 100], height=400)
        st.plotly_chart(fig, use_container_width=True)

    col3, col4 = st.columns(2)

    # 3. Academic Performance Gauge --------------------------------------------
    # NOTE: your current form has no Grade/Score field, so this gauge shows
    # average Overall Completion Progress (%) instead. Add a Grade/Score
    # question back to the Form if you want a true academic-performance gauge.
    with col3:
        st.subheader("Cohort Progress Gauge")
        st.caption("Adapted metric: no Grade/Score field in current form — showing avg. overall progress")
        avg_val = view_df["Progress_Percent"].mean()
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=0 if pd.isna(avg_val) else avg_val,
            gauge={
                "axis": {"range": [0, 100]},
                "steps": [
                    {"range": [0, 60], "color": "#f8d7da"},
                    {"range": [60, 80], "color": "#fff3cd"},
                    {"range": [80, 100], "color": "#d4edda"},
                ],
                "bar": {"color": "#333"},
            },
        ))
        st.plotly_chart(fig, use_container_width=True)

    # 4. Certification Status Roadmap -------------------------------------------
    # NOTE: your form no longer has a distinct "Certification / Project Name"
    # field, so this is grouped by platform instead.
    with col4:
        st.subheader("Certification Status Roadmap")
        st.caption("Grouped by platform (no distinct cert/project-name field in current form)")
        roadmap = view_df.groupby(
            ["Certification platform", "Key Milestone Status"]
        ).size().reset_index(name="Count")
        st.dataframe(roadmap, use_container_width=True, hide_index=True)


# ===========================================================================
# PAGE 2 — INDIVIDUAL STUDENT VIEW
# ===========================================================================
else:
    st.title("Individual Student View")

    student = st.selectbox("Student", STUDENTS, index=0)
    sdf = df[df["Student_Name"] == student].sort_values("Timestamp")

    if sdf.empty:
        st.info(f"No submissions yet for {student}.")
        st.stop()

    # 1. Individual Performance Trend Line ---------------------------------------
    # NOTE: no Grade/Score field currently — plotting Progress_Percent over time.
    st.subheader(f"{student}'s Progress Trend")
    st.caption("Adapted metric: plotting Overall Completion Progress (%) over time (no Grade/Score field)")
    trend = sdf.dropna(subset=["Timestamp"])
    if not trend.empty:
        fig = px.line(trend, x="Timestamp", y="Progress_Percent", markers=True)
        fig.update_yaxes(range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    # 2. Active Progress Roadmap / Timeline --------------------------------------
    with col1:
        st.subheader("Active Progress Roadmap")
        roadmap = sdf.groupby("Certification platform").agg(
            Avg_Progress=("Certfication Progress", "mean"),
            Start_Date=("Timestamp", "min"),
        ).reset_index().sort_values("Start_Date")
        fig = px.bar(roadmap, x="Avg_Progress", y="Certification platform",
                     orientation="h", range_x=[0, 100])
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(roadmap, use_container_width=True, hide_index=True)

    # 3. Personal Blocker Table ---------------------------------------------------
    with col2:
        st.subheader("Personal Blockers")
        st.caption("Only showing items that are NOT On Track / Completed")
        blockers = sdf[~sdf["Key Milestone Status"].isin(["Completed", "On Track"])]
        blockers_view = blockers[["Certification platform", "Final project status", "Key Milestone Status"]]
        if blockers_view.empty:
            st.success("No active blockers 🎉")
        else:
            st.dataframe(blockers_view, use_container_width=True, hide_index=True)

    # 4. Student Comments Log ------------------------------------------------------
    st.subheader("Comments Log")
    comments = sdf[["Timestamp", "Certification platform", "Student_Comments"]].sort_values(
        "Timestamp", ascending=False
    )
    comments = comments[comments["Student_Comments"].notna() & (comments["Student_Comments"] != "")]
    st.dataframe(comments, use_container_width=True, hide_index=True)
