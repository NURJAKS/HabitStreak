# Document 2: Technical Specification (SRS)

**Standard Reference:** ISO/IEC/IEEE 29148:2018  
**Project Title:** Physical Activity Tracker with Habit Streaks (*Option #28*)  
**Platform:** Mobile Application (Android APK / Cross-platform Desktop & Mobile via Flet)

---

## 1. Introduction

### 1.1 Purpose
This Technical Specification defines the functional requirements, non-functional requirements, data model, constraints, and acceptance criteria for the **HabitStreak Physical Activity Tracker** mobile application.

### 1.2 Scope
The system provides local mobile management of physical activity goals, daily workout check-ins, automatic consecutive-day streak computation, 7-day statistical reporting, and full JSON data backup/restore.

### 1.3 Glossary of Terms
* **Activity (Habit Goal):** A recurring daily physical exercise or health target with a positive numeric threshold (`target_value`) and measurement unit (`unit`).
* **Check-In (Activity Log):** A dated record (`YYYY-MM-DD`) storing the user's achieved numeric value (`actual_value`) for a specific activity.
* **Streak:** The number of consecutive calendar days on which `actual_value >= target_value`.
* **Atomic Restore:** A database restoration process wrapped in a transaction so that any validation failure rolls back all changes, leaving existing data intact.

---

## 2. Users and Roles

Because this is a personal offline mobile tracker, the primary actor is the **Mobile App User**:
* **Mobile User Permissions:**
  * Create, view, and delete physical activity habit goals.
  * Log and update daily workout progress and optional notes.
  * View real-time current streaks, longest streaks, and 7-day weekly analytics.
  * Export database snapshots to JSON files and restore from JSON backups.

---

## 3. Functional Requirements (FR)

Every requirement below is unambiguous, numbered, and directly mapped to an automated test in `tests/test_service.py` or `tests/test_mobile.py`.

| ID | Requirement Description | Priority | Verification Method (Test) |
| :--- | :--- | :--- | :--- |
| **FR-01** | The system shall allow the user to create a physical activity goal specifying `title`, `category`, positive `target_value`, and `unit`. | High | `test_add_and_list_activities` |
| **FR-02** | The system shall reject duplicate activity titles and invalid activity inputs (empty title, title $> 80$ chars, empty unit, or `target_value <= 0`) with a clear `TrackerError`. | High | `test_duplicate_activity_rejected`, `test_invalid_activity_inputs` |
| **FR-03** | The system shall allow the user to delete an activity goal and automatically cascade-delete all associated daily check-in logs. | Medium | `test_delete_activity_and_cascade` |
| **FR-04** | The system shall allow the user to record daily progress (`activity_id`, `log_date` in `YYYY-MM-DD`, `actual_value >= 0`, `notes`) and automatically mark `is_completed = 1` when `actual_value >= target_value`. | High | `test_log_progress_partial_and_completed` |
| **FR-05** | Logging progress multiple times for the same activity and `log_date` shall update (upsert) the existing daily record rather than creating duplicates. | Medium | `test_same_day_upsert_updates_log` |
| **FR-06** | The system shall calculate the **current streak**, **longest streak**, and **total completed days** for any activity, including across month and year boundaries (`Dec 31` $\rightarrow$ `Jan 1`). | High | `test_continuous_streak_across_year_boundary`, `test_broken_streak_preserves_longest` |
| **FR-07** | The current streak shall remain active on `reference_date` (today) if the activity was completed either today or yesterday (`reference_date - 1 day`), and reset to `0` if yesterday was missed. | High | `test_active_streak_from_yesterday` |
| **FR-08** | The system shall generate a **7-Day Weekly Report** containing overall completion rate (%), daily completed goal counts for each of the 7 days, and per-activity completed days and total volume. | High | `test_weekly_report_aggregation` |
| **FR-09** | **Complication (Backup):** The system shall export all activities and activity logs into a structured UTF-8 `.json` file and record an `'EXPORT'` audit entry in `backup_records`. | High | `test_backup_export_and_restore_roundtrip` |
| **FR-10** | **Complication (Restore):** The system shall validate and atomically restore activities and logs from a `.json` backup file, rolling back on malformed JSON or invalid schema and recording a `'RESTORE'` audit entry. | High | `test_backup_restore_invalid_files_rollback` |

---

## 4. Non-Functional Requirements (NFR)

| ID | Category | Requirement Description | Priority | Verification Criterion |
| :--- | :--- | :--- | :--- | :--- |
| **NFR-01** | **Architecture** | Business logic (`tracker/service.py`) shall have zero dependencies on the UI framework (`flet`), enabling reuse across Mobile, Desktop, and Web interfaces. | High | Code inspection (`import flet` absent from `service.py` and `db.py`) |
| **NFR-02** | **Security** | All SQLite operations shall use parameterized SQL queries (`?` placeholders) and enable `PRAGMA foreign_keys = ON`. | High | Security review of `tracker/service.py` & `tracker/db.py` |
| **NFR-03** | **Quality & Testing** | Automated unit test coverage of the core logic shall be at least **80%** (actual achieved: **97%** on `service.py`, **95%** overall), and all code shall pass `ruff check` (PEP 8). | High | `pytest --cov=tracker` and `ruff check` |
| **NFR-04** | **Performance** | Calculating streaks and generating the 7-day weekly report for up to 1,000 log records shall complete in under **0.5 seconds**. | Medium | `pytest` execution timer (27 tests run in `< 1.0s`) |
| **NFR-05** | **Portability** | The application shall run on Python 3.11+ across Linux, Windows, macOS, and compile to Android APK via `flet build apk`. | Medium | Cross-platform execution via `flet run` |

---

## 5. Constraints and Assumptions

* **Python Version:** Python 3.11 or newer (tested on Python 3.12.3).
* **Storage Engine:** Built-in `sqlite3` local database (`activity_tracker.sqlite`). Single-user local mobile usage does not require a multi-writer database server like PostgreSQL.
* **Date Granularity:** Daily habit logs are keyed by calendar date (`YYYY-MM-DD`).

---

## 6. Data Model Summary

The system persists three relational entities in SQLite:
1. **`activities`**: Defines each habit goal (`id`, `title`, `category`, `target_value`, `unit`, `created_at`).
2. **`activity_logs`**: Stores daily check-ins (`id`, `activity_id` FK, `log_date`, `actual_value`, `is_completed`, `notes`).
3. **`backup_records`**: Stores audit logs of backup exports and restores (`id`, `created_at`, `file_path`, `activities_count`, `logs_count`, `action`).

---

## 7. Acceptance Criteria for Defense

1. Application launches cleanly in mobile viewport via `python3 main.py` or `flet run`.
2. All 4 mobile tabs (*Habits*, *Check-In*, *Weekly*, *Backup*) operate without unhandled exceptions.
3. `pytest --cov=tracker` passes all 27 tests with $\ge 80\%$ coverage.
4. `ruff check` reports 0 style errors.
