
# Autonomous Study Planner 📚

A general-purpose, adaptive study planning web application built with Python, Streamlit, SQLite, and Pandas.

## Problem Statement

Students and self-learners often struggle to organize their subjects, meet deadlines, revise difficult topics, and monitor progress.

## Solution

The Autonomous Study Planner creates a prioritized study plan, records learning progress, suggests revision, provides customizable quizzes, and helps students track focused study sessions.

## Features

- General-purpose subject and task management
- Deadline-aware study prioritization
- Adaptive daily study plan
- Automatic reprioritization after progress updates
- Revision reminders based on confidence and time
- Custom quiz creation and self-assessment
- Focus timer and study-session tracking
- Progress dashboard and quiz history
- CSV export of the daily plan
- Local SQLite database

## Technology Stack

- Python
- Streamlit
- SQLite
- Pandas
- Git and GitHub

## Installation

1. Install Python and Git.
2. Clone this repository.
3. Create and activate a virtual environment.
4. Install dependencies:

   `python -m pip install -r requirements.txt`

5. Run the application:

   `python -m streamlit run app.py`

6. Open the local URL displayed in the terminal.

## How the Planner Works

1. The user creates study tasks and deadlines.
2. The decision engine calculates priorities.
3. The daily plan allocates the available study time.
4. The user records completion and confidence.
5. The planner recalculates priorities and recommends
   what to study next.
6. Quiz results and revision reminders help the user
   identify topics that need further practice.

## Current Limitations

- Users record their own progress.
- The initial version does not automatically read calendars.
- Quiz questions are created by users.
- The timer needs a manual refresh to update the displayed countdown.
- The scheduling engine uses transparent rules, not a paid AI model.
- Data is stored locally on the computer running the app.

## Future Enhancements

- Automatic timer refresh and notifications
- Calendar integration
- Spaced-repetition algorithms
- Importing tasks from spreadsheets
- Optional AI-assisted quiz generation
- Secure accounts and cloud database
- More detailed learning analytics

## Author

Add your name and GitHub profile here.
