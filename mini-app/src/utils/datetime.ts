import dayjs, { Dayjs } from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';

dayjs.extend(utc);
dayjs.extend(timezone);

export const DEFAULT_TIMEZONE = 'Europe/Moscow';

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
    return '-';
  }

  const { timezone: tz, format = 'YYYY-MM-DD HH:mm' } = options || {};
  const parsed = ensureDayjs(value, tz);

  return parsed.isValid() ? parsed.format(format) : '-';
}

export function formatTime(
  value: string | Date | Dayjs | null | undefined,
  options?: { timezone?: string; format?: string }
): string {
  return formatDateTime(value, { timezone: options?.timezone, format: options?.format || 'HH:mm' });
}

export function formatDate(
  value: string | Date | Dayjs | null | undefined,
  options?: { timezone?: string; format?: string }
): string {
  return formatDateTime(value, { timezone: options?.timezone, format: options?.format || 'MMM DD, YYYY' });
}

export function dayjsInTimezone(
  value: string | Date | Dayjs,
  timezone?: string
): Dayjs {
  return ensureDayjs(value, timezone);
}
