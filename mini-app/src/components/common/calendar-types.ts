/**
 * Shared types and constants for calendar components (WeekCalendar, MonthCalendar)
 */

export type LessonStatus =
  | "scheduled"
  | "rescheduled"
  | "completed"
  | "cancelled";

export interface Lesson {
  id: number;
  scheduled_at: string;
  status: LessonStatus;
  duration_minutes?: number;
  learner_name?: string;
}

export interface CalendarCallbacks {
  onLessonClick: (lessonId: number) => void;
  onAddLesson?: (date: string) => void;
  onReschedule?: (lessonId: number, newDate?: string) => void;
  onComplete?: (lessonId: number) => void;
  onCancel?: (lessonId: number) => void;
  onDelete?: (lessonId: number) => void;
}

/** Status colors for lesson blocks - shared between Week and Month calendars */
export const statusColors: Record<
  LessonStatus,
  { bg: string; bgDark: string; border: string; text: string }
> = {
  scheduled: {
    bg: "rgba(24, 144, 255, 0.15)",
    bgDark: "rgba(24, 144, 255, 0.25)",
    border: "#1890ff",
    text: "#1890ff",
  },
  rescheduled: {
    bg: "rgba(250, 173, 20, 0.15)",
    bgDark: "rgba(250, 173, 20, 0.25)",
    border: "#faad14",
    text: "#d48806",
  },
  completed: {
    bg: "rgba(82, 196, 26, 0.15)",
    bgDark: "rgba(82, 196, 26, 0.25)",
    border: "#52c41a",
    text: "#389e0d",
  },
  cancelled: {
    bg: "rgba(255, 77, 79, 0.15)",
    bgDark: "rgba(255, 77, 79, 0.25)",
    border: "#ff4d4f",
    text: "#cf1322",
  },
};

/** Default lesson duration in minutes */
export const DEFAULT_DURATION = 60;

/** Days of week labels - use i18n keys instead: t('calendar.days.mon') etc. */
export const DAYS_FULL = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
export const DAYS_SHORT = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
