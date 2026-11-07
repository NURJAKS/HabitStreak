# Document 8: Installation and Build Guide

**Project Title:** Physical Activity Tracker with Habit Streaks (*Option #28*)  
**Target Platforms:** Android (`APK`), Linux, Windows, macOS

---

## 1. Environment Preparation

Ensure **Python 3.11+** and **Git** are installed on your machine:
```bash
python3 --version
git --version
```

Create an isolated virtual environment and install exact dependencies from `requirements.txt`:
```bash
python3 -m venv .venv
source .venv/bin/activate      # Linux / macOS
# .venv\Scripts\activate       # Windows

pip install -r requirements.txt
```

---

## 2. Running and Verifying Locally

### 2.1 Seed Demonstration Data (Optional)
```bash
.venv/bin/python seed_demo.py
```

### 2.2 Run the Mobile Application on Desktop Viewport
```bash
.venv/bin/python main.py
# Or via Flet CLI:
.venv/bin/flet run tracker/mobile.py
```

### 2.3 Run Linter and Automated Test Suite
```bash
.venv/bin/ruff check
.venv/bin/pytest --cov=tracker --cov-report=term-missing -v
```

---

## 3. Building the Android Mobile Package (APK)

Per Section 1.1 and Section 3 (Option #28) of the study guide, Flet packages the Python application into a standalone Android `.apk` using `flet build apk`.

### 3.1 Prerequisites for Android APK Packaging
* Flutter SDK (automatically managed by Flet build tools or installed in `PATH`)
* Android SDK & Java JDK 17

### 3.2 Build Command
Run the following command from the project root directory (where `main.py` and `requirements.txt` are located):
```bash
.venv/bin/flet build apk --project "HabitStreak" --description "Physical Activity Tracker with Habit Streaks"
```

### 3.3 Output Location and Installation on Phone / Emulator
Once the build finishes, the compiled package is located in:
```text
build/apk/app-release.apk
```
To install on a connected Android phone (with USB Debugging enabled) or an Android Studio Emulator (AVD):
```bash
adb install build/apk/app-release.apk
```

---

## 4. Packaging for Desktop (Optional Cross-Platform Build)

Because the business logic in `tracker/service.py` and UI in `tracker/mobile.py` are cross-platform, you can also package a standalone desktop executable on Linux or Windows:
```bash
.venv/bin/flet build linux    # On Linux
.venv/bin/flet build windows  # On Windows
```
