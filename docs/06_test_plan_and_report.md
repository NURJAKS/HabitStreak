# Document 6: Test Plan, Test Protocol, and Coverage Report

**Project Title:** Physical Activity Tracker with Habit Streaks (*Option #28*)  
**Test Framework:** `pytest 9.2.0` + `pytest-cov 7.1.0`

---

## 1. Test Strategy and Scope

In accordance with Section 1.5.5 of the study guide:
* **Isolation:** Every test uses an isolated in-memory SQLite database (`connect(":memory:")`) or temporary filesystem directory (`tmp_path` fixture) so tests never interfere with one another.
* **Three-Case Rule:** Every feature is verified across:
  1. **Normal Case (Happy Path):** Valid activity creation, daily completion check-in, weekly report aggregation, and JSON backup roundtrip.
  2. **Boundary / Edge Case:** Exact threshold (`actual_value == target_value`), consecutive streak across year transition (`2025-12-31` $\rightarrow$ `2026-01-01`), active streak carried over from yesterday, and same-day log upsert.
  3. **Error / Negative Case:** Empty/overlong strings, zero or negative targets, malformed date strings, non-existent IDs, invalid backup file extensions, and corrupted JSON payloads with rollback verification.

---

## 2. Test Execution Protocol (27 Automated Test Cases)

| ID | Test Function | Steps / Input Scenario | Expected Result | Actual Result | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-01** | `test_add_and_list_activities` | Add `"Daily Steps"` (`10000 steps`) and list activities | Returns `id=2`, streaks initialized to `0` | `id=2`, streaks `0` | **PASSED** |
| **TC-02** | `test_duplicate_activity_rejected` | Add `"Morning Run"` when `"Morning Run"` already exists | Raises `TrackerError("already exists")` | `TrackerError` raised | **PASSED** |
| **TC-03..10** | `test_invalid_activity_inputs` (8 parameterized cases) | Pass empty title, whitespace title, 90-char title, empty category, `0` target, `-10` target, `"invalid"` target, empty unit | Raises `TrackerError` for all 8 invalid inputs | `TrackerError` raised | **PASSED** |
| **TC-11** | `test_delete_activity_and_cascade` | Log progress for `id=1`, delete `id=1`, then delete `id=1` again | Logs cascade-deleted; second delete raises `TrackerError` | Cascade verified, `TrackerError` raised | **PASSED** |
| **TC-12** | `test_log_progress_partial_and_completed` | Log `3.2 km` (below `5.0`) on Nov 1 and `5.0 km` on Nov 2 | Nov 1 has `is_completed=0`; Nov 2 has `is_completed=1` | Matched | **PASSED** |
| **TC-13** | `test_same_day_upsert_updates_log` | Log `2.0 km` then `6.0 km` on `2026-11-05` | Single row updated to `6.0 km`, `is_completed=1`, streak `1` | Matched | **PASSED** |
| **TC-14..19** | `test_invalid_log_inputs` (6 parameterized cases) | Pass `"2026/11/01"`, `"bad-date"`, `12345`, `-1.0`, `"not-a-number"`, and `activity_id=999` | Raises `TrackerError` for all 6 invalid inputs | `TrackerError` raised | **PASSED** |
| **TC-20** | `test_continuous_streak_across_year_boundary` | Log completed on `2025-12-30`, `2025-12-31`, `2026-01-01`, `2026-01-02` | `current_streak=4`, `longest_streak=4`, `total_completed=4` | `4, 4, 4` | **PASSED** |
| **TC-21** | `test_broken_streak_preserves_longest` | Complete Nov 1–3, skip Nov 4, complete Nov 5–6 | `current_streak=2`, `longest_streak=3`, `total_completed=5` | `2, 3, 5` | **PASSED** |
| **TC-22** | `test_active_streak_from_yesterday` | Complete Nov 5–6; check on Nov 7 (pending) and Nov 8 (missed) | Nov 7 `current_streak=2`; Nov 8 `current_streak=0` | `2` then `0` | **PASSED** |
| **TC-23** | `test_weekly_report_aggregation` | Log 4 days on Activity 1 and 3 days on Activity 2 in 7-day window | `completed_checkins=7`, `possible=14`, `completion_rate=50.0%` | `50.0%` | **PASSED** |
| **TC-24** | `test_backup_export_and_restore_roundtrip` | Export 2 activities + 2 logs to JSON, delete all, restore from JSON | Data fully restored; `backup_records` logs `EXPORT` & `RESTORE` | Matched | **PASSED** |
| **TC-25** | `test_backup_restore_invalid_files_rollback` | Test `.txt` path, missing file, malformed JSON, missing keys, non-list collections | Raises `TrackerError` and rolls back transaction safely | Intact DB, `TrackerError` raised | **PASSED** |
| **TC-26** | `test_mobile_ui_controller_workflow` | Execute full UI lifecycle across all 4 tabs (add, log, report, backup, delete, restore) | All 4 tabs render and status banner updates cleanly | Matched | **PASSED** |
| **TC-27** | `test_mobile_ui_error_handling` | Trigger invalid actions in UI handlers | `TrackerError` caught and displayed in red status banner | Matched | **PASSED** |

---

## 3. Code Coverage Report

Command executed:
```bash
pytest --cov=tracker --cov-report=term-missing -v
```

Output:
```text
Name                  Stmts   Miss  Cover   Missing
---------------------------------------------------
tracker/__init__.py       1      0   100%
tracker/db.py            11      0   100%
tracker/mobile.py       118     11    91%   328-354, 358
tracker/service.py      204      7    97%   157, 358, 414-418
---------------------------------------------------
TOTAL                   334     18    95%
============================== 27 passed in 0.89s ==============================
```

* **Core Business Logic Coverage (`tracker/service.py`):** **97%** (Requirement: $\ge 80\%$).
* **Total Package Coverage (`tracker/`):** **95%**.
