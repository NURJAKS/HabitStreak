# Document 9: Explanatory Note (Түсіндірме жазба)

**University:** Korkyt Ata Kyzylorda University (Қорқыт ата атындағы Қызылорда университеті)  
**Course:** Cross-Platform Web, Mobile, and Desktop Application Development with Python  
**Project Option:** #28 — Physical Activity Tracker with Habit Streaks (*Әдеттер тізбегі бар физикалық белсенділікті бақылау құралы*)  
**Year:** 2026

---

## 1. Introduction and Project Objectives

Regular physical activity is essential for health and academic productivity, yet maintaining daily exercise consistency is challenging without immediate visual feedback. The objective of **Course Project #28** is to design, implement, test, and document a cross-platform mobile application — **HabitStreak Tracker** — that enables users to:
1. Define quantitative daily physical activity goals (`target_value` + `unit`).
2. Log daily workout completions (`YYYY-MM-DD`) and automatically track **consecutive day habit streaks** (`current_streak` and `longest_streak`).
3. Analyze a **7-day weekly report** with overall completion rates, daily progress bars, and cumulative volume per activity.
4. Perform **local JSON backup export and atomic restore** (the advanced complication requirement for Option #28).

---

## 2. Requirements Engineering Summary (ISO/IEC/IEEE 29148:2018)

In accordance with ISO/IEC/IEEE 29148:2018, all system requirements were formulated to be unambiguous, numbered, and directly verifiable by automated tests:
* **10 Functional Requirements (`FR-01` to `FR-10`):** Cover goal creation, duplicate/invalid input rejection, cascade deletion, daily check-in evaluation, same-day upsert, streak computation across month/year boundaries, 7-day weekly reporting, and JSON backup/restore.
* **5 Non-Functional Requirements (`NFR-01` to `NFR-05`):** Enforce strict separation of concerns (`service.py` independent of Flet), parameterized SQL queries (`?`), $\ge 80\%$ test coverage, $< 0.5\text{s}$ calculation latency, and cross-platform portability.

---

## 3. Architectural Design Decisions (ISO/IEC/IEEE 42010:2022)

### 3.1 Three-Tier Separation of Concerns
The project is divided into three strictly separated modules:
1. **Storage Layer (`tracker/db.py`):** Configures SQLite with `sqlite3.Row` and `PRAGMA foreign_keys = ON`, defining three normalized tables (`activities`, `activity_logs`, `backup_records`).
2. **Business Logic Layer (`tracker/service.py`):** Contains pure Python domain functions with zero UI dependencies. All validation errors raise a dedicated `TrackerError` exception.
3. **Mobile Presentation Layer (`tracker/mobile.py` & `main.py`):** Implements a 4-tab Flet mobile interface (`Habits`, `Check-In`, `Weekly`, `Backup`) that delegates all computations to `tracker/service.py`.

### 3.2 Justification of SQLite and Known Limitations
* **Why SQLite?** SQLite is built into the Python standard library (`sqlite3`), requires no external database daemon, and stores all tables in a single portable file (`activity_tracker.sqlite`), making it ideal for an offline mobile application. Also, using only pure-Python standard library modules (`sqlite3`, `json`, `datetime`) avoids native C-extension packaging issues during `flet build apk` (as highlighted in Section 1.1 of the study guide).
* **Limitations:** SQLite locks the database file during write operations, allowing only one writer at a time. For a single-user mobile device this is completely sufficient; if migrated to a multi-user cloud backend, PostgreSQL would be adopted.

---

## 4. Core Algorithms and Edge Cases

### 4.1 Consecutive Day Streak Calculation
For any activity, `calculate_streak()` queries all rows where `is_completed = 1` ordered chronologically:
* **Boundary Condition 1 (Year/Month Rollover):** Using `datetime.date` arithmetic (`(curr - prev).days == 1`), a streak from `2025-12-30` through `2026-01-02` is accurately evaluated as a 4-day continuous chain (`test_continuous_streak_across_year_boundary`).
* **Boundary Condition 2 (Pending Today vs. Missed Yesterday):** If a user completed their workout yesterday (`reference_date - 1 day`) and has not yet logged today's workout, `_compute_current_streak()` preserves their active streak. If both today and yesterday have no completed check-in, `current_streak` resets to `0` while `longest_streak` preserves their historical record (`test_active_streak_from_yesterday`, `test_broken_streak_preserves_longest`).
* **Boundary Condition 3 (Same-Day Multiple Logs):** The table constraint `UNIQUE(activity_id, log_date)` combined with `ON CONFLICT(activity_id, log_date) DO UPDATE` ensures logging twice on the same date updates the daily record instead of inflating the streak (`test_same_day_upsert_updates_log`).

### 4.2 Atomic JSON Backup & Restore (Complication)
To fulfill the Option #28 complication requirement:
* `export_backup()` serializes all `activities` and `activity_logs` to a formatted UTF-8 `.json` file and logs an `'EXPORT'` event in `backup_records`.
* `restore_backup()` validates the JSON schema before executing `DELETE` and `INSERT` statements inside a transaction. If any record is malformed, `db.rollback()` restores the prior database state completely (`test_backup_restore_invalid_files_rollback`).

---

## 5. Verification, Testing, and Code Quality

* **Code Style (PEP 8):** Checked with `ruff check` — **0 warnings or errors**. All functions include type annotations and PEP 257 docstrings.
* **Unit Testing (`pytest`):** **27 automated tests** executed in **0.89 seconds**, with **100% pass rate**.
* **Code Coverage (`pytest-cov`):** **97% coverage** on `tracker/service.py`, **100% coverage** on `tracker/db.py`, and **95% total package coverage** (exceeding the 80% requirement).

---

## 6. Answers to Mandatory Defense & Security Questions (Section 3, Option #28)

1. **Why was this technology stack (Flet + SQLite) chosen?**
   Flet enables building a responsive Material Design 3 mobile application in pure Python that runs on desktop during development (`flet run`) and compiles into an Android APK (`flet build apk`) without requiring Java/Kotlin or C-extension dependencies. SQLite provides ACID-compliant relational storage locally on the mobile device without needing a remote server.
2. **How is data protected in the application?**
   * All SQL queries use parameterized `?` placeholders, completely preventing SQL injection.
   * Relational integrity is enforced via `PRAGMA foreign_keys = ON`, `UNIQUE` constraints, and `CHECK (target_value > 0)` / `CHECK (actual_value >= 0)` database constraints.
   * Backup restoration is transactional (`db.rollback()` on failure), protecting existing user data against corrupted backup files.
   * The mobile package requests zero intrusive device permissions (no camera, GPS, or contacts access).
3. **What edge cases were tested?**
   * Year-end and month-end consecutive streaks (`2025-12-30` to `2026-01-02`).
   * Active streak retention when yesterday was completed and today is still in progress.
   * Same-day repeated check-in upserts (`2.0 km` updated to `6.0 km` on the same date).
   * Partial progress below target (`actual_value < target_value`) vs. exact target match (`actual_value == target_value`).
   * Rollback recovery when restoring missing, non-JSON, malformed, or schema-invalid backup files.
4. **What changes are needed to run the application on a second platform (Web or Desktop)?**
   Because `tracker/service.py` and `tracker/db.py` are 100% decoupled from the UI, **zero changes** are needed in the business logic or database layers. Furthermore, Flet itself can launch the exact same `tracker/mobile.py` code as a Desktop window (`flet run`) or Web application (`flet run --web`), or `tracker/service.py` can be imported directly into a Flask/FastAPI web server.

---

## 7. Conclusion

All tasks and requirements for **Option #28 (Physical Activity Tracker with Habit Streaks)** have been fulfilled. The separation of concerns between `tracker/service.py` and `tracker/mobile.py` yielded a maintainable, secure, and cross-platform codebase backed by 27 automated tests and 97% business logic coverage.

---

## 8. References

1. Aitimov M. Zh. *Python көмегімен платформааралық веб, мобильді және жұмыс үстелі қосымшаларын әзірлеу: Оқу құралы*. — Kyzylorda: Korkyt Ata Kyzylorda University, 2026.
2. ISO/IEC/IEEE 29148:2018 — *Systems and software engineering — Life cycle processes — Requirements engineering*.
3. ISO/IEC/IEEE 42010:2022 — *Software, systems and enterprise — Architecture description*.
4. Van Rossum G., Warsaw B., Coghlan N. *PEP 8 — Style Guide for Python Code*. Python Software Foundation.
5. Flet Official Documentation — *Building Cross-Platform Mobile Apps in Python*: https://flet.dev/docs/
6. Python Standard Library Documentation — *sqlite3 — DB-API 2.0 interface for SQLite databases*: https://docs.python.org/3/library/sqlite3.html
