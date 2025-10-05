# Reminder Migration Plan

## Goals
- Move from `lesson_reminders` table (legacy) to new `lesson_packages` / `lessons` / `reminder_rules` / `reminder_instances` setup.
- Preserve reminder history (responses, comments, statuses) for learners.
- Ensure scheduler and admin UI operate solely on new tables.

## Existing Data
- `lesson_reminders`: contains adhoc reminders (lesson/payment) with `student_name`, `chat_identifier`, `kind`, `is_recurring`, schedule fields, responses, comments.
- Learners/Bot users already normalized (`learners`, `bot_users`).

## Migration Steps
1. **Identify unique learners:**
   - Group `lesson_reminders` by `chat_identifier` (chat_id) → match existing `learners` (via bot_user.chat_id).
   - If learner absent, create placeholder learner (display name = reminder.student_name).

2. **Create default packages:**
   - For each learner, create package "Legacy reminders" (status `active`, timezone `Europe/Moscow`, notes about migration).
   - `start_date`: min reminder `created_at`; `end_date`: max `next_run_at` or `created_at`.

3. **Create lessons:**
   - For recurring reminders: create weekly lessons per `days` + `lesson_time`.
   - For one-time reminders: create single lessons at `lesson_datetime`.
   - Lesson sequence derived from chronological order.

4. **Create reminder rules/instances:**
   - Lesson reminders → `REMINDER_TYPE_LESSON_CONFIRM` or `REMINDER_TYPE_HOMEWORK` equivalent.
   - Payment reminders → `REMINDER_TYPE_PAYMENT_WEEK/DAY` with template key.
   - Copy `comment`, `active`, response state into instance fields.

5. **Scheduler adjustments:**
   - Ensure fallback to legacy removed after migration toggle.
   - Provide feature flag to disable legacy processing during rollout.

6. **Admin UI:**
   - Remove menu items leading to legacy reminder creation once migration complete.

## Rollout
- Run migration script offline (Alembic data migration or async script).
- Verify scheduler outputs, admin package lists.
- Take backup before flipping flag.

