# Document 4: Interface Wireframes and Screen Layouts

**Project Title:** Physical Activity Tracker with Habit Streaks (*Option #28*)  
**Target Viewport:** Mobile Portrait (`420 × 860 px`) with Material Design 3 Bottom Navigation Bar

---

## Screen 1: Habits & Streaks Tab (`index = 0`)

Displays the form to create a new physical activity goal and a scrollable list of active habit cards with real-time streak counters (`🔥 Current`, `🏆 Best`, `✅ Total`).

```text
+--------------------------------------------------+
|  HabitStreak Tracker                             |
|  [Status Banner: Activity goal added!]           |
+--------------------------------------------------+
|  New Activity Goal                               |
|  +--------------------------------------------+  |
|  | Goal Title (e.g. Morning Run)              |  |
|  +--------------------------------------------+  |
|  +--------------------+  +--------------------+  |
|  | Category: Cardio v |  | Daily Target: 5.0  |  |
|  +--------------------+  +--------------------+  |
|  +--------------------+  +--------------------+  |
|  | Unit: km           |  |   [ + Add Goal ]   |  |
|  +--------------------+  +--------------------+  |
|  ----------------------------------------------  |
|  Active Habits & Streaks                         |
|  +--------------------------------------------+  |
|  | Morning Run (Cardio)              [Delete] |  |
|  | Daily Target: 5.0 km                       |  |
|  | 🔥 Current: 7d | 🏆 Best: 7d | ✅ Total: 7d |  |
|  +--------------------------------------------+  |
|  +--------------------------------------------+  |
|  | Daily 10k Steps (Steps)           [Delete] |  |
|  | Daily Target: 10000.0 steps                |  |
|  | 🔥 Current: 5d | 🏆 Best: 5d | ✅ Total: 6d |  |
|  +--------------------------------------------+  |
+--------------------------------------------------+
| [🔥 Habits] [✅ Check-In] [📊 Weekly] [💾 Backup] |
+--------------------------------------------------+
```

---

## Screen 2: Daily Check-In Tab (`index = 1`)

Allows the user to select an activity from the dropdown, input the date and achieved value, add optional notes, and inspect recent check-in history.

```text
+--------------------------------------------------+
|  HabitStreak Tracker                             |
|  [Status Banner: Daily progress logged!]         |
+--------------------------------------------------+
|  Daily Activity Check-In                         |
|  +--------------------------------------------+  |
|  | Select Activity: Morning Run (5.0 km)    v |  |
|  +--------------------------------------------+  |
|  +--------------------+  +--------------------+  |
|  | Date: 2026-11-07   |  | Achieved: 5.5      |  |
|  +--------------------+  +--------------------+  |
|  +--------------------------------------------+  |
|  | Notes (optional): Completed morning track  |  |
|  +--------------------------------------------+  |
|  [              Save Check-In                 ]  |
|  ----------------------------------------------  |
|  Recent Check-In History                         |
|  +--------------------------------------------+  |
|  | ✅ 2026-11-07 | Morning Run: 5.5/5.0 km    |  |
|  |    (Completed morning track)               |  |
|  +--------------------------------------------+  |
|  +--------------------------------------------+  |
|  | ⏳ 2026-11-06 | Pushup Session: 25.0/50.0  |  |
|  |    reps (Partial warmup)                   |  |
|  +--------------------------------------------+  |
+--------------------------------------------------+
| [🔥 Habits] [✅ Check-In] [📊 Weekly] [💾 Backup] |
+--------------------------------------------------+
```

---

## Screen 3: 7-Day Weekly Report Tab (`index = 2`)

Displays the 7-day overall completion percentage, a day-by-day visual progress bar breakdown, and cumulative volume per activity.

```text
+--------------------------------------------------+
|  HabitStreak Tracker                             |
+--------------------------------------------------+
|  7-Day Weekly Report                             |
|  Period: 2026-11-01 to 2026-11-07                |
|  +--------------------------------------------+  |
|  | Overall Completion Rate: 71.4%             |  |
|  | Completed Check-ins: 20 / 28               |  |
|  +--------------------------------------------+  |
|  Daily Goal Breakdown                            |
|  2026-11-01  [████████████░░░░]  3/4 goals       |
|  2026-11-02  [████░░░░░░░░░░░░]  1/4 goals       |
|  2026-11-03  [████████████░░░░]  3/4 goals       |
|  2026-11-04  [████████░░░░░░░░]  2/4 goals       |
|  2026-11-05  [████████████████]  4/4 goals       |
|  2026-11-06  [████████████░░░░]  3/4 goals       |
|  2026-11-07  [████████████████]  4/4 goals       |
|  ----------------------------------------------  |
|  Per-Activity Weekly Volume                      |
|  +--------------------------------------------+  |
|  | 📊 Morning Run: 7/7 days (100.0%)          |  |
|  |    Total: 38.5 km                          |  |
|  +--------------------------------------------+  |
|  +--------------------------------------------+  |
|  | 📊 Daily 10k Steps: 6/7 days (85.7%)       |  |
|  |    Total: 67200.0 steps                    |  |
|  +--------------------------------------------+  |
+--------------------------------------------------+
| [🔥 Habits] [✅ Check-In] [📊 Weekly] [💾 Backup] |
+--------------------------------------------------+
```

---

## Screen 4: Data Backup & Restore Tab (`index = 3`)

Provides one-tap JSON backup export and atomic restore (the required Complication for Option #28), along with an audit log of backup operations.

```text
+--------------------------------------------------+
|  HabitStreak Tracker                             |
|  [Status: Exported 4 goals and 23 logs]          |
+--------------------------------------------------+
|  Data Backup & Restore                           |
|  Export or restore your habit streaks as JSON.   |
|  +--------------------------------------------+  |
|  | Backup File (.json): backups/tracker.json  |  |
|  +--------------------------------------------+  |
|  +--------------------+  +--------------------+  |
|  | [ Export Backup ]  |  | [ Restore Backup ] |  |
|  +--------------------+  +--------------------+  |
|  ----------------------------------------------  |
|  Backup Audit Log                                |
|  [EXPORT] 2026-11-07 20:45:00 —                  |
|    backups/demo_snapshot.json (4 goals, 23 logs) |
|  [RESTORE] 2026-11-07 20:46:12 —                 |
|    backups/demo_snapshot.json (4 goals, 23 logs) |
+--------------------------------------------------+
| [🔥 Habits] [✅ Check-In] [📊 Weekly] [💾 Backup] |
+--------------------------------------------------+
```
