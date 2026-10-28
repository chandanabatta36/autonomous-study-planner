
import sqlite3
import time
import random
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st


# =========================================================
# 1. APP CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Autonomous Study Planner",
    page_icon="📚",
    layout="wide"
)

DB_NAME = "study_planner.db"

st.title("📚 Autonomous Study Planner")
st.caption(
    "Plan smarter. Track progress. Adapt your learning."
)


# =========================================================
# 2. DATABASE
# =========================================================

def connect_db():
    return sqlite3.connect(DB_NAME)


def initialize_database():
    with connect_db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                topic TEXT NOT NULL,
                deadline TEXT NOT NULL,
                difficulty INTEGER NOT NULL,
                minutes INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                confidence INTEGER NOT NULL DEFAULT 3,
                last_studied TEXT,
                created_at TEXT NOT NULL
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS quiz_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                topic TEXT NOT NULL,
                question TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_option TEXT NOT NULL,
                explanation TEXT
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS quiz_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                topic TEXT NOT NULL,
                score INTEGER NOT NULL,
                total INTEGER NOT NULL,
                taken_at TEXT NOT NULL
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS focus_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                minutes INTEGER NOT NULL,
                session_date TEXT NOT NULL
            )
        """)


def read_table(table_name):
    # Only call this function with the table names used below.
    allowed = {
        "tasks", "quiz_questions",
        "quiz_results", "focus_sessions"
    }

    if table_name not in allowed:
        raise ValueError("Unknown database table.")

    with connect_db() as con:
        return pd.read_sql_query(
            f"SELECT * FROM {table_name} ORDER BY id DESC",
            con
        )


def add_task(subject, topic, deadline, difficulty, minutes):
    with connect_db() as con:
        con.execute("""
            INSERT INTO tasks
            (subject, topic, deadline, difficulty,
             minutes, status, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, 'Pending', 3, ?)
        """, (
            subject.strip(),
            topic.strip(),
            deadline.isoformat(),
            difficulty,
            minutes,
            date.today().isoformat()
        ))


def update_task(task_id, status, confidence):
    studied_date = (
        date.today().isoformat()
        if status == "Completed"
        else None
    )

    with connect_db() as con:
        con.execute("""
            UPDATE tasks
            SET status = ?, confidence = ?,
                last_studied = ?
            WHERE id = ?
        """, (status, confidence, studied_date, task_id))


def add_question(
    subject, topic, question,
    a, b, c, d, correct, explanation
):
    with connect_db() as con:
        con.execute("""
            INSERT INTO quiz_questions
            (subject, topic, question, option_a,
             option_b, option_c, option_d,
             correct_option, explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            subject.strip(), topic.strip(), question.strip(),
            a.strip(), b.strip(), c.strip(), d.strip(),
            correct, explanation.strip()
        ))


def save_quiz_result(subject, topic, score, total):
    with connect_db() as con:
        con.execute("""
            INSERT INTO quiz_results
            (subject, topic, score, total, taken_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            subject, topic, score, total,
            datetime.now().isoformat(timespec="seconds")
        ))


def save_focus_session(topic, minutes):
    with connect_db() as con:
        con.execute("""
            INSERT INTO focus_sessions
            (topic, minutes, session_date)
            VALUES (?, ?, ?)
        """, (topic, minutes, date.today().isoformat()))


initialize_database()


# =========================================================
# 3. AUTONOMOUS DECISION ENGINE
# =========================================================

def get_priority(task):
    """
    Higher score means the task should be considered sooner.
    This is a transparent rule-based decision system.
    """

    today = date.today()
    due_date = date.fromisoformat(task["deadline"])
    days_left = (due_date - today).days

    # Urgency increases near the deadline.
    if days_left < 0:
        urgency = 100
    elif days_left == 0:
        urgency = 90
    elif days_left <= 2:
        urgency = 70
    elif days_left <= 7:
        urgency = 45
    else:
        urgency = 20

    difficulty_score = task["difficulty"] * 8
    low_confidence_score = (6 - task["confidence"]) * 7

    return (
        urgency
        + difficulty_score
        + low_confidence_score
    )


def build_adaptive_plan(tasks, available_minutes):
    """
    Create today's plan from pending tasks.
    Deadline, difficulty and confidence affect the order.
    """

    pending = tasks[tasks["status"] != "Completed"].copy()

    if pending.empty:
        return pd.DataFrame(), 0

    pending["priority"] = pending.apply(
        get_priority, axis=1
    )

    pending = pending.sort_values(
        by=["priority", "deadline"],
        ascending=[False, True]
    )

    plan = []
    remaining = available_minutes

    for _, task in pending.iterrows():
        task_minutes = int(task["minutes"])

        if remaining <= 0:
            break

        # Schedule a full task when possible.
        # Otherwise allocate the remaining time as a work block.
        allocated = min(task_minutes, remaining)

        plan.append({
            "Task ID": int(task["id"]),
            "Subject": task["subject"],
            "Topic": task["topic"],
            "Study minutes": allocated,
            "Full task estimate": task_minutes,
            "Deadline": task["deadline"],
            "Priority score": int(task["priority"]),
            "Reason": explain_priority(task)
        })

        remaining -= allocated

    return pd.DataFrame(plan), remaining


def explain_priority(task):
    due_date = date.fromisoformat(task["deadline"])
    days_left = (due_date - date.today()).days

    if days_left < 0:
        return "Overdue — needs attention"
    if days_left == 0:
        return "Deadline is today"
    if task["confidence"] <= 2:
        return "Low confidence — revise this topic"
    if task["difficulty"] >= 4:
        return "Difficult topic — allow extra practice"
    if days_left <= 2:
        return "Deadline is approaching"

    return "Next task based on priority"


def get_revision_tasks(tasks):
    """
    Suggest revision when confidence is low,
    or a topic has not been studied recently.
    """

    if tasks.empty:
        return tasks

    today = date.today()
    revisions = []

    for _, task in tasks.iterrows():
        if task["status"] != "Completed":
            continue

        reasons = []

        if int(task["confidence"]) <= 2:
            reasons.append("Low confidence")

        last_studied = task["last_studied"]

        if last_studied:
            last_date = date.fromisoformat(last_studied)
            days_since = (today - last_date).days

            if days_since >= 3:
                reasons.append(
                    f"Last studied {days_since} days ago"
                )

        if reasons:
            item = task.to_dict()
            item["Revision reason"] = "; ".join(reasons)
            revisions.append(item)

    return pd.DataFrame(revisions)


# =========================================================
# 4. SIDEBAR SETTINGS
# =========================================================

st.sidebar.header("⚙️ Study Settings")

available_hours = st.sidebar.slider(
    "Study hours available today",
    min_value=1,
    max_value=12,
    value=3
)

available_minutes = available_hours * 60

st.sidebar.info(
    f"Today's study budget: {available_minutes} minutes"
)

tasks = read_table("tasks")
quiz_results = read_table("quiz_results")
focus_sessions = read_table("focus_sessions")
questions = read_table("quiz_questions")


# =========================================================
# 5. NAVIGATION
# =========================================================

pages = [
    "Dashboard",
    "Subjects & Tasks",
    "Adaptive Study Plan",
    "Revision Planner",
    "Quizzes & Self-Assessment",
    "Focus Timer"
]

page = st.sidebar.radio("Navigate", pages)


# =========================================================
# 6. DASHBOARD
# =========================================================

if page == "Dashboard":
    st.header("📊 Your Learning Dashboard")

    total_tasks = len(tasks)

    completed_tasks = (
        int((tasks["status"] == "Completed").sum())
        if total_tasks else 0
    )

    pending_tasks = total_tasks - completed_tasks

    completion_rate = (
        round(completed_tasks / total_tasks * 100)
        if total_tasks else 0
    )

    total_focus_minutes = (
        int(focus_sessions["minutes"].sum())
        if not focus_sessions.empty else 0
    )

    quiz_accuracy = (
        round(
            quiz_results["score"].sum()
            / quiz_results["total"].sum() * 100
        )
        if not quiz_results.empty
        and quiz_results["total"].sum() > 0
        else 0
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Total Tasks", total_tasks)
    c2.metric("Completed", completed_tasks)
    c3.metric("Completion Rate", f"{completion_rate}%")
    c4.metric("Quiz Accuracy", f"{quiz_accuracy}%")

    st.subheader("Today's Summary")

    st.write(f"**Pending tasks:** {pending_tasks}")
    st.write(
        f"**Total recorded focus time:** "
        f"{total_focus_minutes} minutes"
    )

    if total_tasks:
        st.progress(completion_rate / 100)

    st.subheader("🤖 Planner Recommendation")

    if tasks.empty:
        st.info(
            "Start by adding subjects and tasks "
            "in the Subjects & Tasks section."
        )
    elif pending_tasks == 0:
        st.success(
            "All tasks are completed! Add new goals "
            "or review topics you find difficult."
        )
    else:
        plan, _ = build_adaptive_plan(
            tasks, available_minutes
        )

        if not plan.empty:
            next_task = plan.iloc[0]

            st.success(
                f"Next: {next_task['Subject']} — "
                f"{next_task['Topic']}"
            )

            st.write(f"**Why:** {next_task['Reason']}")
            st.write(
                f"**Suggested study time:** "
                f"{next_task['Study minutes']} minutes"
            )

    if not tasks.empty:
        st.subheader("Task Status")
        status_counts = (
            tasks["status"]
            .value_counts()
            .rename_axis("Status")
            .reset_index(name="Count")
        )
        st.bar_chart(status_counts.set_index("Status"))


# =========================================================
# 7. SUBJECTS AND TASKS
# =========================================================

elif page == "Subjects & Tasks":
    st.header("📘 Subjects & Tasks")

    st.write(
        "Add any subject or learning goal. Examples: "
        "Mathematics, Physics, English, Python, "
        "accounting, or an entrance-exam topic."
    )

    with st.form("add_task_form", clear_on_submit=True):
        subject = st.text_input(
            "Subject or course",
            placeholder="e.g. Mathematics"
        )

        topic = st.text_input(
            "Topic or task",
            placeholder="e.g. Integration practice"
        )

        deadline = st.date_input(
            "Deadline",
            value=date.today() + timedelta(days=7),
            min_value=date.today()
        )

        difficulty = st.slider(
            "Difficulty",
            min_value=1,
            max_value=5,
            value=3,
            help="1 = easy, 5 = very difficult"
        )

        minutes = st.number_input(
            "Estimated study time (minutes)",
            min_value=5,
            max_value=600,
            value=30,
            step=5
        )

        add_button = st.form_submit_button("Add Task")

        if add_button:
            if not subject.strip() or not topic.strip():
                st.error("Please enter both subject and topic.")
            else:
                add_task(
                    subject, topic, deadline,
                    difficulty, int(minutes)
                )
                st.success("Task added to your study planner.")
                st.rerun()

    st.divider()
    st.subheader("Update Task Progress")

    tasks = read_table("tasks")

    if tasks.empty:
        st.info("No tasks yet. Add your first task above.")
    else:
        task_options = {
            f"#{row['id']} | {row['subject']} — {row['topic']}":
            int(row["id"])
            for _, row in tasks.iterrows()
        }

        chosen_label = st.selectbox(
            "Choose a task",
            list(task_options.keys())
        )

        chosen_id = task_options[chosen_label]

        chosen_task = tasks[
            tasks["id"] == chosen_id
        ].iloc[0]

        new_status = st.selectbox(
            "Status",
            ["Pending", "In Progress", "Completed"],
            index=[
                "Pending", "In Progress", "Completed"
            ].index(chosen_task["status"])
        )

        confidence = st.slider(
            "How confident are you with this topic?",
            min_value=1,
            max_value=5,
            value=int(chosen_task["confidence"]),
            help="1 = not confident, 5 = very confident"
        )

        if st.button("Save Progress"):
            update_task(chosen_id, new_status, confidence)
            st.success("Progress updated.")
            st.rerun()

        st.subheader("All Tasks")

        display_columns = [
            "id", "subject", "topic", "deadline",
            "difficulty", "minutes", "status", "confidence"
        ]

        st.dataframe(
            tasks[display_columns],
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# 8. ADAPTIVE STUDY PLAN
# =========================================================

elif page == "Adaptive Study Plan":
    st.header("🗓️ Adaptive Study Plan")

    tasks = read_table("tasks")

    st.write(
        "The planner prioritizes deadlines, difficult topics, "
        "and topics with low confidence. Unfinished work "
        "remains available for future scheduling."
    )

    if tasks.empty:
        st.info("Add some tasks before generating your plan.")
    else:
        plan, remaining = build_adaptive_plan(
            tasks, available_minutes
        )

        if plan.empty:
            st.success("No pending tasks. Great work!")
        else:
            st.subheader("Recommended Tasks for Today")

            st.dataframe(
                plan,
                use_container_width=True,
                hide_index=True
            )

            allocated = int(plan["Study minutes"].sum())

            st.metric(
                "Planned study time",
                f"{allocated} / {available_minutes} minutes"
            )

            if remaining > 0:
                st.info(
                    f"{remaining} minutes remain in today's "
                    "study budget."
                )

            csv_data = plan.to_csv(index=False).encode("utf-8")

            st.download_button(
                "Download Today's Plan",
                data=csv_data,
                file_name="today_study_plan.csv",
                mime="text/csv"
            )

            st.subheader("How the planner decides")

            st.markdown("""
            - **Urgency:** approaching and overdue deadlines
              receive higher priority.
            - **Difficulty:** difficult tasks receive additional
              priority.
            - **Confidence:** low-confidence topics are
              recommended earlier.
            - **Adaptation:** changing task status or confidence
              recalculates the recommended plan.
            """)


# =========================================================
# 9. REVISION PLANNER
# =========================================================

elif page == "Revision Planner":
    st.header("🔁 Revision Planner")

    tasks = read_table("tasks")
    revisions = get_revision_tasks(tasks)

    st.write(
        "Completed topics with low confidence, or topics "
        "not studied for several days, appear here."
    )

    if revisions.empty:
        st.success(
            "No revision reminders yet. Complete a task, "
            "record your confidence, and check back later."
        )
    else:
        revision_columns = [
            "subject", "topic", "last_studied",
            "confidence", "Revision reason"
        ]

        st.dataframe(
            revisions[revision_columns],
            use_container_width=True,
            hide_index=True
        )

    st.caption(
        "Revision suggestions are based on recorded completion, "
        "confidence, and elapsed days. They are reminders, "
        "not a guarantee of learning or retention."
    )


# =========================================================
# 10. QUIZZES AND SELF-ASSESSMENT
# =========================================================

elif page == "Quizzes & Self-Assessment":
    st.header("📝 Quizzes & Self-Assessment")

    st.subheader("Create Your Own Quiz Question")

    st.write(
        "Add questions from any subject. You can create "
        "your own questions and answer choices."
    )

    with st.form("question_form", clear_on_submit=True):
        q_subject = st.text_input(
            "Subject", placeholder="e.g. Biology"
        )

        q_topic = st.text_input(
            "Topic", placeholder="e.g. Cell structure"
        )

        question = st.text_area("Question")

        a = st.text_input("Option A")
        b = st.text_input("Option B")
        c = st.text_input("Option C")
        d = st.text_input("Option D")

        correct = st.selectbox(
            "Correct option",
            ["A", "B", "C", "D"]
        )

        explanation = st.text_area(
            "Explanation (optional)"
        )

        save_question = st.form_submit_button(
            "Save Quiz Question"
        )

        if save_question:
            required = [
                q_subject, q_topic, question, a, b, c, d
            ]

            if not all(value.strip() for value in required):
                st.error("Fill in all required question fields.")
            else:
                add_question(
                    q_subject, q_topic, question,
                    a, b, c, d, correct, explanation
                )
                st.success("Quiz question saved.")
                st.rerun()

    st.divider()
    st.subheader("Take a Quiz")

    questions = read_table("quiz_questions")

    if questions.empty:
        st.info(
            "Create at least one quiz question to start."
        )
    else:
        subjects = sorted(questions["subject"].unique())

        quiz_subject = st.selectbox(
            "Choose a subject",
            subjects
        )

        subject_questions = questions[
            questions["subject"] == quiz_subject
        ]

        topics = sorted(subject_questions["topic"].unique())

        quiz_topic = st.selectbox(
            "Choose a topic",
            topics
        )

        quiz_questions = subject_questions[
            subject_questions["topic"] == quiz_topic
        ].reset_index(drop=True)

        if st.button("Start / Reset Quiz"):
            st.session_state.quiz_order = random.sample(
                list(quiz_questions["id"]),
                len(quiz_questions)
            )
            st.session_state.quiz_submitted = False
            st.session_state.quiz_subject = quiz_subject
            st.session_state.quiz_topic = quiz_topic

        quiz_order = st.session_state.get("quiz_order", [])

        if (
            quiz_order
            and st.session_state.get("quiz_subject") == quiz_subject
            and st.session_state.get("quiz_topic") == quiz_topic
        ):
            ordered_questions = (
                quiz_questions.set_index("id")
                .loc[quiz_order]
                .reset_index()
            )

            with st.form("take_quiz_form"):
                answers = {}

                for i, row in ordered_questions.iterrows():
                    st.markdown(
                        f"**Question {i + 1}:** {row['question']}"
                    )

                    options = {
                        "A": row["option_a"],
                        "B": row["option_b"],
                        "C": row["option_c"],
                        "D": row["option_d"]
                    }

                    answers[int(row["id"])] = st.radio(
                        f"Choose an answer for question {i + 1}",
                        ["A", "B", "C", "D"],
                        format_func=lambda x, opts=options:
                            f"{x}. {opts[x]}",
                        key=f"answer_{row['id']}"
                    )

                submitted_quiz = st.form_submit_button(
                    "Submit Quiz"
                )

            if submitted_quiz:
                score = 0

                for _, row in ordered_questions.iterrows():
                    if answers[int(row["id"])] == row["correct_option"]:
                        score += 1

                total = len(ordered_questions)

                save_quiz_result(
                    quiz_subject, quiz_topic, score, total
                )

                st.session_state.last_quiz_result = {
                    "score": score,
                    "total": total,
                    "subject": quiz_subject,
                    "topic": quiz_topic,
                    "answers": answers.copy(),
                    "question_ids": quiz_order.copy()
                }

                st.session_state.quiz_order = []
                st.rerun()

    result = st.session_state.get("last_quiz_result")

    if result:
        st.divider()
        st.subheader("Latest Quiz Result")

        percentage = round(
            result["score"] / result["total"] * 100
        )

        st.metric(
            "Your score",
            f"{result['score']} / {result['total']}"
        )

        st.progress(percentage / 100)

        st.write(f"Accuracy: **{percentage}%**")

        if percentage < 60:
            st.warning(
                "Consider revising this topic and trying "
                "another quiz."
            )
        elif percentage < 80:
            st.info(
                "Good start. Review any mistakes and practise again."
            )
        else:
            st.success(
                "Good result! Schedule a later revision "
                "to reinforce your learning."
            )

    quiz_history = read_table("quiz_results")

    if not quiz_history.empty:
        st.subheader("Quiz History")
        st.dataframe(
            quiz_history[
                ["subject", "topic", "score", "total", "taken_at"]
            ],
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# 11. FOCUS TIMER
# =========================================================

elif page == "Focus Timer":
    st.header("⏱️ Focus Timer")

    st.write(
        "Choose a topic and a focus duration. When the timer "
        "finishes, record the completed session."
    )

    focus_topic = st.text_input(
        "What will you focus on?",
        value="Study session"
    )

    focus_minutes = st.select_slider(
        "Focus duration",
        options=[5, 10, 15, 20, 25, 30, 45, 60],
        value=25
    )

    if "focus_end_time" not in st.session_state:
        st.session_state.focus_end_time = None

    if "focus_duration" not in st.session_state:
        st.session_state.focus_duration = 0

    if st.button("Start / Restart Timer"):
        st.session_state.focus_duration = focus_minutes
        st.session_state.focus_end_time = (
            time.time() + focus_minutes * 60
        )
        st.rerun()

    if st.session_state.focus_end_time is not None:
        remaining_seconds = max(
            0,
            int(st.session_state.focus_end_time - time.time())
        )

        mins, secs = divmod(remaining_seconds, 60)

        st.subheader(f"{mins:02d}:{secs:02d}")

        if remaining_seconds > 0:
            st.caption(
                "The timer updates when the app reruns. "
                "Use the Refresh Timer button to update it."
            )

            if st.button("Refresh Timer"):
                st.rerun()
        else:
            st.success(
                "Focus period finished! Take a short break."
            )

            if st.button("Record Completed Focus Session"):
                if not focus_topic.strip():
                    st.error("Enter a topic before recording.")
                else:
                    save_focus_session(
                        focus_topic,
                        st.session_state.focus_duration
                    )

                    st.session_state.focus_end_time = None
                    st.success("Focus session recorded.")
                    st.rerun()

            if st.button("Clear Timer"):
                st.session_state.focus_end_time = None
                st.rerun()

    focus_history = read_table("focus_sessions")

    if not focus_history.empty:
        st.divider()
        st.subheader("Recorded Focus Sessions")

        st.dataframe(
            focus_history,
            use_container_width=True,
            hide_index=True
        )


# =========================================================
# 12. FOOTER
# =========================================================

st.divider()

st.caption(
    "Built with Python, Streamlit, SQLite and Pandas. "
    "Free, rule-based adaptive study planning prototype."
)
