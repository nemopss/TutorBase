import dayjs, { Dayjs } from "dayjs";
import utc from "dayjs/plugin/utc";
import timezone from "dayjs/plugin/timezone";

dayjs.extend(utc);
dayjs.extend(timezone);

export const DEFAULT_TIMEZONE = "Europe/Moscow";

const OFFSET_REGEX = /([zZ])|([+-]\d{2}:?\d{2})$/;

function ensureDayjs(value: string | Date | Dayjs, tz?: string): Dayjs {
  const zone = tz || DEFAULT_TIMEZONE;

  if (dayjs.isDayjs(value)) {
    return value.tz(zone);
  }

  if (value instanceof Date) {
    return dayjs(value).tz(zone);
  }

  const hasExplicitOffset = OFFSET_REGEX.test(value);
  const base = hasExplicitOffset ? dayjs(value) : dayjs.utc(value);
  return base.tz(zone);
}

export function formatDateTime(
  value: string | Date | Dayjs | null | undefined,
  options?: { timezone?: string; format?: string }
): string {
  if (!value) {
    return "-";
  }

  const { timezone: tz, format = "YYYY-MM-DD HH:mm" } = options || {};
  const parsed = ensureDayjs(value, tz);

  return parsed.isValid() ? parsed.format(format) : "-";
}

export function formatTime(
  value: string | Date | Dayjs | null | undefined,
  options?: { timezone?: string; format?: string }
): string {
  return formatDateTime(value, {
    timezone: options?.timezone,
    format: options?.format || "HH:mm",
  });
}

export function formatDate(
  value: string | Date | Dayjs | null | undefined,
  options?: { timezone?: string; format?: string }
): string {
  return formatDateTime(value, {
    timezone: options?.timezone,
    format: options?.format || "MMM DD, YYYY",
  });
}

export function dayjsInTimezone(
  value: string | Date | Dayjs,
  timezone?: string
): Dayjs {
  return ensureDayjs(value, timezone);
}

/**
 * Formats next lesson date in relative format for display.
 *
 * @param dateStr - ISO datetime string or null
 * @param t - i18n translation function
 * @param timezone - Optional timezone (defaults to DEFAULT_TIMEZONE)
 * @returns Formatted string:
 *   - "Today, HH:mm" if lesson is today
 *   - "Tomorrow, HH:mm" if lesson is tomorrow
 *   - "DD MMM, HH:mm" if lesson is more than 1 day away
 *   - Translated "No lessons" if dateStr is null
 */
export function formatNextLessonDate(
  dateStr: string | null | undefined,
  t: (key: string) => string,
  timezone?: string
): string {
  if (!dateStr) {
    return t("common.noLessons");
  }

  const tz = timezone || DEFAULT_TIMEZONE;
  const lessonDate = ensureDayjs(dateStr, tz);
  const now = dayjs().tz(tz);

  if (!lessonDate.isValid()) {
    return t("common.noLessons");
  }

  const timeStr = lessonDate.format("HH:mm");

  // Check if today
  if (lessonDate.isSame(now, "day")) {
    return `${t("common.today")}, ${timeStr}`;
  }

  // Check if tomorrow
  const tomorrow = now.add(1, "day");
  if (lessonDate.isSame(tomorrow, "day")) {
    return `${t("common.tomorrow")}, ${timeStr}`;
  }

  // More than 1 day away - show date
  return lessonDate.format("D MMM, HH:mm");
}
