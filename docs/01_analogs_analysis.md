# Document 1: Problem Statement and Analysis of Analogs

**Project Option:** #28 — Physical Activity Tracker with Habit Streaks (*Әдеттер тізбегі бар физикалық белсенділікті бақылау құралы*)  
**Application Type:** Mobile (Flet + SQLite)

---

## 1. Problem Statement

University students and office workers frequently struggle to maintain consistent physical activity routines (such as running, daily step targets, strength exercises, or hydration). Most people track workouts sporadically in paper notebooks or generic note-taking apps, which leads to three core problems:
1. **Lack of Immediate Visual Motivation:** Without a clear **daily streak chain** (consecutive days of meeting a daily goal), users easily skip days and abandon habits.
2. **No Weekly Volume & Consistency Feedback:** Users cannot quickly see their 7-day completion rate or cumulative physical volume (total kilometers run, total repetitions completed) over the past week.
3. **Cloud Lock-In & Data Loss Risk:** Many commercial mobile fitness trackers require paid subscriptions, mandatory cloud accounts, or internet connectivity, and do not allow simple local JSON backup and restore when switching devices.

**Solution:** **HabitStreak Tracker** is an offline-first, cross-platform mobile application built in Python with **Flet** and **SQLite** that enables users to define measurable physical activity goals, record daily check-ins, track current and all-time longest habit streaks, inspect 7-day analytical reports, and export/restore full JSON backups locally.

---

## 2. Target Users and Primary Use Cases

### Target User Profiles
* **Students & Amateur Athletes:** Track daily cardio (running, cycling), strength exercises (pushups, planks), and step goals between classes.
* **Health-Conscious Individuals:** Build sustainable daily movement and hydration streaks without sharing personal health data with third-party cloud servers.
* **Fitness Coaches / PE Instructors:** Recommend a lightweight, open-source habit tracker where students can export weekly progress or JSON backups.

### Three Core User Workflows
1. **Goal Creation & Streak Tracking:** The user creates a measurable daily activity goal (e.g., *"Morning Run — 5.0 km"*). Each day the user logs their result, the system compares `actual_value >= target_value` and automatically increments or resets the consecutive day streak (`🔥 Current Streak` and `🏆 Longest Streak`).
2. **Weekly Progress Review:** At the end of the week, the user opens the **Weekly Report** tab to inspect their overall 7-day completion percentage, daily goal completion progress bars, and total volume achieved per activity.
3. **Data Backup & Device Migration (Complication):** Before resetting their phone or switching devices, the user opens the **Backup** tab to export all habits and logs into a validated `.json` file and restores it atomically with one tap.

---

## 3. Comparative Analysis of Existing Analogs

We analyzed three popular mobile applications in the habit-tracking and physical activity domain:

| Criterion | 1. Loop Habit Tracker | 2. Strava | 3. Habitica | **HabitStreak (Our Project #28)** |
| :--- | :--- | :--- | :--- | :--- |
| **Primary Focus** | General yes/no habits | GPS outdoor sports social network | RPG gamified to-do & habit list | **Physical activity goals + habit streaks** |
| **Offline Operation** | Full offline support | Limited (requires cloud sync for analytics) | Requires internet connection | **100% Offline-first (SQLite)** |
| **Quantitative Targets** | Basic numeric habits | Detailed GPS telemetry | Binary check-ins only | **Numeric targets + units (`km`, `reps`, `steps`)** |
| **Streak Calculation** | Weighted score & streaks | Paid subscription required for full training logs | Basic streak counter | **Current Streak + Longest Streak + Total Days** |
| **Weekly Report** | Monthly/yearly charts | Paid subscription (Strava Summit) | No weekly volume summary | **Built-in 7-day completion rate & volume report** |
| **Local JSON Backup & Restore** | SQLite/CSV export | Web-only bulk archive request | Account cloud sync only | **Instant one-tap JSON Export & Atomic Restore** |
| **Privacy & Cost** | Free, Open Source (Android only) | Freemium (expensive subscription, cloud tracking) | Freemium (in-app purchases) | **Free, Open Source, Cross-Platform (Python/Flet)** |

### Key Conclusions from Analog Analysis
* **Strava** is overly complex for daily indoor habits (such as pushups, stretching, or water intake) and locks weekly consistency analytics behind a paid subscription.
* **Habitica** requires constant internet access and lacks quantitative volume aggregation (e.g., summing total kilometers or repetitions over 7 days).
* **Loop Habit Tracker** is a strong offline benchmark, but **HabitStreak (Project #28)** specifically bridges quantitative physical workout targets (`target_value` + `unit`) with automatic streak chains, a dedicated 7-day weekly report, and cross-platform Python/Flet portability with validated JSON backup and restore.
