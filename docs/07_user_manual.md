# Document 7: User Manual

**Application Name:** HabitStreak — Physical Activity Tracker with Habit Streaks (*Option #28*)

---

## 1. Purpose and System Requirements

**HabitStreak** helps you build daily physical exercise and health habits by tracking your quantitative daily targets, calculating your consecutive day streaks (`🔥 Current` and `🏆 Best`), summarizing your 7-day weekly performance, and backing up your data locally.

### Minimum System Requirements
* **Desktop / Development Mode:** Windows 10/11, Linux (Ubuntu 22.04+), or macOS 12+; Python 3.11+; 200 MB RAM.
* **Mobile Device (Android):** Android 8.0 (API 26) or newer; 60 MB free storage.

---

## 2. Installation and Startup

### Step 1: Create Virtual Environment & Install Packages
```bash
python3 -m venv .venv
source .venv/bin/activate      # Linux / macOS
# .venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

### Step 2: (Optional) Load Demo Habits & 7-Day Streak Data
To populate the tracker with 4 sample habits (*Morning Run*, *Daily 10k Steps*, *Pushup Session*, *Water Hydration*) and 7 days of historical check-ins:
```bash
python3 seed_demo.py
```

### Step 3: Launch the Application
```bash
python3 main.py
# Or using the Flet CLI:
flet run tracker/mobile.py
```

---

## 3. Typical User Scenarios

### Scenario 1: How to Create a Physical Activity Goal
1. Open the **🔥 Habits** tab (selected by default on launch).
2. Enter the **Goal Title** (e.g., `Morning Run`).
3. Select a **Category** from the dropdown (`Cardio`, `Strength`, `Flexibility`, `Steps`, `Hydration`, `Sport`).
4. Enter a positive **Daily Target** (e.g., `5`) and **Unit** (e.g., `km`).
5. Tap **Add Goal**. A green confirmation banner *"Activity goal added!"* will appear, and your new habit card will be listed below.

### Scenario 2: How to Record a Daily Check-In and Build a Streak
1. Tap the **✅ Check-In** tab on the bottom navigation bar.
2. Choose your habit from the **Select Activity** dropdown.
3. Verify the **Date (`YYYY-MM-DD`)** (defaults to today's date).
4. Enter your **Achieved Value** (e.g., `5.5`) and optional **Notes** (e.g., `Completed morning track`).
5. Tap **Save Check-In**:
   * If `Achieved Value >= Daily Target`, the entry is marked `✅` (completed) and your consecutive day streak increases!
   * If you log again on the same date for the same activity, your entry for that day is automatically updated.

### Scenario 3: How to View Your 7-Day Weekly Report
1. Tap the **📊 Weekly** tab on the bottom navigation bar.
2. Review the summary card showing your **Overall Completion Rate (%)** and total completed check-ins out of all possible check-ins for the last 7 days.
3. Inspect the **Daily Goal Breakdown** progress bars for each day of the week and the **Per-Activity Weekly Volume** cards (showing total `km`, `steps`, `reps`, or `L` accumulated over the 7-day period).

### Scenario 4: How to Backup and Restore Your Data
1. Tap the **💾 Backup** tab on the bottom navigation bar.
2. Enter a `.json` file path in **Backup File (.json)** (default: `backups/tracker_backup.json`).
3. Tap **Export Backup** to save all habits and logs to disk.
4. Tap **Restore Backup** at any time to validate and atomically restore your habits and logs from that `.json` file.

### Scenario 5: How to Switch Languages (KZ, RU, EN)
1. Locate the trilingual switch capsule (`[ KZ | RU | EN ]`) in the top right of the persistent header bar.
2. Tap any language pill:
   * **KZ (Қазақша)**: Instantly translates the header, navigation tabs, modal dialogs, category badges, KPI stats, weekly analysis, and notifications to Kazakh.
   * **RU (Русский)**: Instantly translates all interface elements, form fields, and messages to Russian.
   * **EN (English)**: Restores the default international English interface.

### Scenario 6: How to Toggle Dark and Light Themes
1. Locate the theme toggle button (☀️ / 🌙) directly next to the language switcher in the top header.
2. Tap the button to toggle between:
   * **Light Mode (Duolingo Flat 2.0)**: Crisp `#F7F7F7` canvas, clean white cards `#FFFFFF`, and high-contrast typography.
   * **Dark Mode (Duolingo Obsidian Slate)**: Deep `#131F24` background, `#202F36` slate cards with subtle borders, and vivid neon accent badges for night use.

---

## 4. Error Messages and Troubleshooting

| Error Message Shown in App | Cause | What to Do |
| :--- | :--- | :--- |
| `Error: Activity title must not be empty` | You tapped *Add Goal* with a blank title field. | Enter a descriptive habit name (1–80 characters). |
| `Error: Activity '...' already exists` | A habit with the exact same title already exists. | Choose a distinct title or use the existing habit. |
| `Error: Target value must be greater than zero` | Target value was `0`, negative, or non-numeric. | Enter a positive number such as `5` or `10000`. |
| `Error: Date must be in YYYY-MM-DD format` | The check-in date was typed in an invalid format. | Use `YYYY-MM-DD` format (for example, `2026-11-07`). |
| `Error: Backup file must have a .json extension` | Backup path did not end with `.json`. | Ensure the file path ends with `.json` (e.g., `backups/my_data.json`). |
| `Error: Backup file not found` | You tapped *Restore Backup* for a file that does not exist. | Check the file path or run *Export Backup* first. |

> **Important Note for Defense Submission:** Before printing or submitting this User Manual, run `python3 seed_demo.py && python3 main.py` and insert screenshots of the 4 tabs from your screen corresponding to Option #28.
