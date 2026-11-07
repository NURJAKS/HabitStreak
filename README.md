# Physical Activity Tracker with Habit Streaks (Option 28)

A cross-platform mobile application built with **Python (Flet)** and **SQLite** for tracking daily physical activity goals, calculating habit streaks, generating 7-day analytics reports, and performing full data backup & restore.

## Project Structure

```text
mobile project/
├── README.md
├── requirements.txt
├── .gitignore
├── docs/                  # Coursework documentation package (10 documents)
├── backups/               # Default directory for JSON backups
├── tracker/
│   ├── __init__.py
│   ├── db.py              # SQLite connection and schema management
│   ├── service.py         # Core business logic (UI-independent)
│   └── mobile.py          # Flet mobile user interface
└── tests/
    ├── __init__.py
    └── test_service.py    # Automated pytest unit tests (>=80% coverage)
```

## Setup & Installation

```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

## Running the Mobile App

```bash
flet run tracker/mobile.py
# Or directly via Python:
python3 -m tracker.mobile
```

## Running Tests & Coverage

```bash
pytest -q
pytest --cov=tracker --cov-report=term-missing
```

## Building Android APK

```bash
flet build apk
```
