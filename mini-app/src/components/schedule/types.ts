import dayjs from "dayjs";
import "dayjs/locale/ru";
import weekday from "dayjs/plugin/weekday";
import localeData from "dayjs/plugin/localeData";
import isoWeek from "dayjs/plugin/isoWeek";
import timezone from "dayjs/plugin/timezone";
import utc from "dayjs/plugin/utc";

// Configure dayjs
dayjs.extend(weekday);
dayjs.extend(localeData);
dayjs.extend(isoWeek);
dayjs.extend(timezone);
dayjs.extend(utc);
dayjs.locale("ru");

// Types
export interface Lesson {
  id: number;
  scheduled_at: string;
  status: "scheduled" | "completed" | "cancelled";
  duration_minutes: number;
}

export type ViewMode = "month" | "week" | "list";

// Constants
export const STATUS_COLORS = {
  scheduled: "#1890ff", // blue
  completed: "#52c41a", // green
  cancelled: "#ff4d4f", // red
} as const;

// Status labels are now handled via i18n - use t('calendar.status.scheduled') etc.
// This constant is kept for backward compatibility but should not be used directly
export const STATUS_LABELS = {
  scheduled: "scheduled",
  completed: "completed",
  cancelled: "cancelled",
} as const;
