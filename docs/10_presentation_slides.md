# Document 10: Defense Presentation (7–10 Slides)

**Project Title:** HabitStreak — Physical Activity Tracker with Habit Streaks (*Option #28*)  
**Author:** Student (Option #28)  
**University:** Korkyt Ata Kyzylorda University, 2026

---

## Slide 1: Title & Problem Statement
* **Topic:** Option #28 — Physical Activity Tracker with Habit Streaks (*Мобильді қосымша*)
* **Problem:**
  * Paper workout logs and generic notes fail to motivate daily consistency.
  * Commercial fitness apps lock weekly consistency analytics behind paid cloud subscriptions and lack simple offline JSON backup.
* **Goal:** Build an offline-first, cross-platform mobile tracker in Python with consecutive day streaks, 7-day weekly reports, and atomic JSON backup/restore.

---

## Slide 2: Analysis of Analogs & Our Advantage
* **Analogs Compared:** *Loop Habit Tracker*, *Strava*, *Habitica*.
* **HabitStreak Advantages:**
  * Quantitative physical targets (`5.0 km`, `10000 steps`, `50 reps`, `2.5 L`) rather than simple yes/no checkboxes.
  * Automatic **Current Streak (`🔥`)**, **Longest Streak (`🏆`)**, and **Total Completed Days (`✅`)**.
  * Built-in **7-Day Weekly Report** + one-tap **JSON Backup & Restore**.

---

## Slide 3: System Architecture (ISO/IEC/IEEE 42010)
* **Three-Tier Clean Architecture:**
  1. **Presentation Layer (`tracker/mobile.py`):** Flet Material Design 3 mobile UI (`420 × 860`, 4 navigation tabs).
  2. **Business Logic Layer (`tracker/service.py`):** 100% UI-independent Python domain functions & `TrackerError` validation.
  3. **Data Storage Layer (`tracker/db.py`):** SQLite with `PRAGMA foreign_keys = ON` and 3 relational tables (`activities`, `activity_logs`, `backup_records`).

---

## Slide 4: Database Schema & Core Algorithms
* **3 Relational Entities:**
  * `activities` ($1 \rightarrow N$) `activity_logs` with `ON DELETE CASCADE` and `UNIQUE(activity_id, log_date)`.
  * `backup_records` for auditing `'EXPORT'` and `'RESTORE'` operations.
* **Streak Engine:**
  * Uses `datetime.date` delta arithmetic (`(curr - prev).days == 1`) to handle month/year rollovers (`Dec 31` $\rightarrow$ `Jan 1`).
  * Retains active streaks when yesterday was completed and today is still in progress.

---

## Slide 5: Mobile User Interface Demonstration (4 Tabs)
* **Tab 1 — 🔥 Habits:** Create goals (`Title`, `Category`, `Target`, `Unit`) and view live streak badges.
* **Tab 2 — ✅ Check-In:** Log daily progress (`YYYY-MM-DD`, value, notes) with automatic same-day upsert.
* **Tab 3 — 📊 Weekly Report:** 7-day completion rate %, daily progress bars, and per-activity cumulative volume.
* **Tab 4 — 💾 Backup (Complication):** Export all data to `.json` and restore atomically with transaction rollback protection.

---

## Slide 6: Automated Testing & Code Quality
* **Test Suite (`pytest`):** **27 automated unit tests** (`tests/test_service.py` & `tests/test_mobile.py`) — all **27 PASSED** in `0.89s`.
* **Code Coverage (`pytest-cov`):**
  * `tracker/db.py`: **100%**
  * `tracker/service.py` (Business Logic): **97%** (Requirement: $\ge 80\%$)
  * `tracker/mobile.py` (UI Controller): **91%**
  * **Total Package Coverage:** **95%**
* **Code Style:** 100% PEP 8 compliant (`ruff check` — 0 errors).

---

## Slide 7: Security, Portability & Conclusion
* **Security Measures:**
  * Parameterized SQL queries (`?`) prevent SQL injection.
  * Transactional rollback (`db.rollback()`) protects against corrupted JSON backup files.
  * Zero unnecessary mobile permissions (strict offline sandbox).
* **Cross-Platform Portability:**
  * Runs on Desktop/Web via `flet run` and builds into an Android package via `flet build apk` with zero changes to `tracker/service.py`.
