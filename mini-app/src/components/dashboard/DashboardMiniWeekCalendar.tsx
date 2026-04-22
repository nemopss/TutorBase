import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Button, Tooltip, Typography } from 'antd';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezonePlugin from 'dayjs/plugin/timezone';
import isoWeek from 'dayjs/plugin/isoWeek';
import isSameOrAfter from 'dayjs/plugin/isSameOrAfter';
import { useTranslation } from 'react-i18next';
import { CalendarOutlined } from '@ant-design/icons';
import { useResponsive } from '../../hooks/useResponsive';
import { useTheme } from '../../theme/ThemeProvider';
import type { Lesson } from '../common/calendar-types';
import { DEFAULT_DURATION, statusColors } from '../common/calendar-types';
import { spacing } from '../../theme/tokens';

dayjs.extend(utc);
dayjs.extend(timezonePlugin);
dayjs.extend(isoWeek);
dayjs.extend(isSameOrAfter);

const { Text } = Typography;

interface DashboardMiniWeekCalendarProps {
  lessons: Lesson[];
  timezone: string;
  onOpenCalendar: () => void;
}

const TIME_COLUMN_WIDTH = 36;
const MOBILE_MIN_HEIGHT = 220;
const DESKTOP_MIN_HEIGHT = 280;
const TILE_RADIUS = 8;
const NOW_MARKER_COLOR = '#ff4d4f';
const DashboardMiniWeekCalendar: React.FC<DashboardMiniWeekCalendarProps> = ({
  lessons,
  timezone,
  onOpenCalendar,
}) => {
  const { t } = useTranslation();
  const { isMobile } = useResponsive();
  const { resolvedTheme } = useTheme();
  const colors = resolvedTheme.colors;
  const isDark = resolvedTheme.colorScheme === 'dark';
  const gridRef = useRef<HTMLDivElement | null>(null);
  const [measuredHeight, setMeasuredHeight] = useState(0);
  const previewHeight = Math.max(
    isMobile ? MOBILE_MIN_HEIGHT : DESKTOP_MIN_HEIGHT,
    measuredHeight || 0,
  );
  const dayKeys = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];

  useEffect(() => {
    if (!gridRef.current || typeof ResizeObserver === 'undefined') {
      return;
    }

    const node = gridRef.current;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) {
        return;
      }
      setMeasuredHeight(Math.floor(entry.contentRect.height));
    });

    observer.observe(node);
    setMeasuredHeight(Math.floor(node.getBoundingClientRect().height));

    return () => observer.disconnect();
  }, []);

  const weekStart = useMemo(() => dayjs().tz(timezone).startOf('isoWeek'), [timezone]);
  const weekDays = useMemo(
    () => Array.from({ length: 7 }, (_, index) => weekStart.add(index, 'day')),
    [weekStart],
  );

  const weekLessons = useMemo(() => {
    const weekEnd = weekStart.add(7, 'day');
    return lessons
      .filter((lesson) => {
        const lessonTime = dayjs(lesson.scheduled_at).tz(timezone);
        return lessonTime.isSameOrAfter(weekStart) && lessonTime.isBefore(weekEnd);
      })
      .sort((a, b) => dayjs(a.scheduled_at).valueOf() - dayjs(b.scheduled_at).valueOf());
  }, [lessons, timezone, weekStart]);

  const timeWindow = useMemo(() => {
    if (weekLessons.length === 0) {
      return null;
    }

    const earliestStartMinutes = Math.min(
      ...weekLessons.map((lesson) => {
        const lessonTime = dayjs(lesson.scheduled_at).tz(timezone);
        return lessonTime.hour() * 60 + lessonTime.minute();
      }),
    );

    const latestEndMinutes = Math.max(
      ...weekLessons.map((lesson) => {
        const lessonTime = dayjs(lesson.scheduled_at).tz(timezone);
        const duration = lesson.duration_minutes || DEFAULT_DURATION;
        const endTime = lessonTime.add(duration, 'minute');
        return endTime.hour() * 60 + endTime.minute();
      }),
    );

    const roundedStart = Math.max(0, Math.floor(earliestStartMinutes / 30) * 30);
    const roundedEnd = Math.min(24 * 60, Math.ceil(latestEndMinutes / 30) * 30);
    const totalMinutes = Math.max(60, roundedEnd - roundedStart);

    return {
      startMinutes: roundedStart,
      endMinutes: roundedEnd,
      totalMinutes,
    };
  }, [timezone, weekLessons]);

  const visibleHours = useMemo(() => {
    if (!timeWindow) {
      return [];
    }

    const startHour = Math.floor(timeWindow.startMinutes / 60);
    const endHour = Math.ceil(timeWindow.endMinutes / 60);
    return Array.from({ length: endHour - startHour + 1 }, (_, index) => startHour + index);
  }, [timeWindow]);

  const nowPosition = useMemo(() => {
    if (!timeWindow) {
      return null;
    }

    const now = dayjs().tz(timezone);
    const todayInWeek = weekDays.some((day) => day.isSame(now, 'day'));
    if (!todayInWeek) {
      return null;
    }

    const nowMinutes = now.hour() * 60 + now.minute();
    if (nowMinutes < timeWindow.startMinutes || nowMinutes > timeWindow.endMinutes) {
      return null;
    }

    const top = ((nowMinutes - timeWindow.startMinutes) / timeWindow.totalMinutes) * previewHeight;
    return {
      dayKey: now.format('YYYY-MM-DD'),
      top: Math.max(0, Math.min(previewHeight - 2, top)),
    };
  }, [previewHeight, timeWindow, timezone, weekDays]);

  const shouldShowLabels = useMemo(() => {
    if (weekLessons.length === 0) {
      return false;
    }

    return weekLessons.every((lesson) => {
      if (!timeWindow) {
        return false;
      }

      const duration = lesson.duration_minutes || DEFAULT_DURATION;
      const height = (duration / timeWindow.totalMinutes) * previewHeight;
      return height >= (isMobile ? 18 : 20);
    });
  }, [isMobile, previewHeight, timeWindow, weekLessons]);

  const getLessonLabel = (lesson: Lesson) => {
    const learnerName = lesson.learner_name?.trim();
    if (!learnerName) {
      return '';
    }

    return learnerName.split(/\s+/)[0];
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.sm }}>
        <Text strong>{t('pages.dashboard.miniCalendar')}</Text>
        <Button type="text" size="small" icon={<CalendarOutlined />} onClick={onOpenCalendar}>
          {t('pages.dashboard.openCalendar')}
        </Button>
      </div>

      {weekLessons.length === 0 || !timeWindow ? (
        <div
          style={{
            flex: 1,
            minHeight: 120,
            borderRadius: 8,
            border: `1px dashed ${colors.borderPrimary}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: spacing.md,
            background: colors.bgTertiary,
            overflow: 'hidden',
          }}
        >
          <Text type="secondary">{t('pages.dashboard.noLessonsThisWeek')}</Text>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: `${TIME_COLUMN_WIDTH}px repeat(7, 1fr)`,
              gap: 1,
              marginBottom: 1,
            }}
          >
            <div />
            {weekDays.map((day) => {
              const isToday = day.isSame(dayjs().tz(timezone), 'day');
              const dayIndex = day.day() === 0 ? 6 : day.day() - 1;
              return (
                <div
                  key={day.format('YYYY-MM-DD')}
                  style={{
                    textAlign: 'center',
                    paddingBottom: 4,
                    minWidth: 0,
                  }}
                >
                  <Text type="secondary" style={{ display: 'block', fontSize: 10, lineHeight: 1.2 }}>
                    {t(`calendar.daysShort.${dayKeys[dayIndex]}`)}
                  </Text>
                  <Text
                    strong={isToday}
                    style={{
                      fontSize: 11,
                      lineHeight: 1.2,
                      color: isToday ? colors.accentPrimary : colors.textPrimary,
                    }}
                  >
                    {day.format('D')}
                  </Text>
                </div>
              );
            })}
          </div>

          <div
            ref={gridRef}
            style={{
              display: 'grid',
              gridTemplateColumns: `${TIME_COLUMN_WIDTH}px repeat(7, 1fr)`,
              gap: 1,
              alignItems: 'stretch',
              flex: 1,
              minHeight: 0,
            }}
          >
            <div
              style={{
                position: 'relative',
                height: previewHeight,
                background: colors.bgTertiary,
                borderRadius: TILE_RADIUS,
                overflow: 'hidden',
                border: `1px solid ${colors.borderPrimary}`,
              }}
            >
              {visibleHours.map((hour) => {
                const top = ((hour * 60 - timeWindow.startMinutes) / timeWindow.totalMinutes) * previewHeight;
                return (
                  <div
                    key={hour}
                    style={{
                      position: 'absolute',
                      top: Math.max(0, Math.min(previewHeight - 12, top - 6)),
                      right: 6,
                    }}
                  >
                    <Text type="secondary" style={{ fontSize: 9, lineHeight: 1 }}>
                      {String(hour).padStart(2, '0')}
                    </Text>
                  </div>
                );
              })}
            </div>

            {weekDays.map((day) => {
              const dayKey = day.format('YYYY-MM-DD');
              const dayLessons = weekLessons.filter(
                (lesson) => dayjs(lesson.scheduled_at).tz(timezone).format('YYYY-MM-DD') === dayKey,
              );
              const isToday = day.isSame(dayjs().tz(timezone), 'day');

              return (
                <div
                  key={dayKey}
                  style={{
                    position: 'relative',
                    height: previewHeight,
                    background: isToday ? `${colors.accentPrimary}10` : colors.bgTertiary,
                    borderRadius: TILE_RADIUS,
                    overflow: 'hidden',
                    border: `1px solid ${colors.borderPrimary}`,
                  }}
                >
                  {visibleHours.map((hour) => {
                    const top = ((hour * 60 - timeWindow.startMinutes) / timeWindow.totalMinutes) * previewHeight;
                    return (
                      <div
                        key={`${dayKey}-${hour}`}
                        style={{
                          position: 'absolute',
                          top,
                          left: 0,
                          right: 0,
                          borderTop: `1px solid ${colors.borderPrimary}`,
                          opacity: 0.7,
                        }}
                      />
                    );
                  })}

                  {nowPosition && nowPosition.dayKey === dayKey ? (
                    <div
                      style={{
                        position: 'absolute',
                        top: nowPosition.top,
                        left: 0,
                        right: 0,
                        height: 0,
                        pointerEvents: 'none',
                        zIndex: 2,
                      }}
                    >
                      <div
                        style={{
                          position: 'absolute',
                          left: -4,
                          top: -3,
                          width: 8,
                          height: 8,
                          background: NOW_MARKER_COLOR,
                          borderRadius: '50%',
                        }}
                      />
                      <div
                        style={{
                          position: 'absolute',
                          left: 0,
                          right: 0,
                          top: -1,
                          height: 2,
                          background: NOW_MARKER_COLOR,
                        }}
                      />
                    </div>
                  ) : null}

                  {dayLessons.map((lesson) => {
                    const lessonTime = dayjs(lesson.scheduled_at).tz(timezone);
                    const duration = lesson.duration_minutes || DEFAULT_DURATION;
                    const lessonStartMinutes = lessonTime.hour() * 60 + lessonTime.minute();
                    const lessonEndMinutes = lessonStartMinutes + duration;
                    const top = ((lessonStartMinutes - timeWindow.startMinutes) / timeWindow.totalMinutes) * previewHeight;
                    const height = Math.max(12, ((lessonEndMinutes - lessonStartMinutes) / timeWindow.totalMinutes) * previewHeight);
                    const palette = statusColors[lesson.status];
                    const shortName = getLessonLabel(lesson);
                    const tooltipTitle = `${lessonTime.format('HH:mm')} · ${lesson.learner_name || t('pages.dashboard.learner')}`;

                    const block = (
                      <div
                        style={{
                          position: 'absolute',
                          top,
                          left: 2,
                          right: 2,
                          height,
                          borderRadius: 4,
                          background: isDark ? palette.bgDark : palette.bg,
                          borderLeft: `3px solid ${palette.border}`,
                          padding: '1px 3px',
                          overflow: 'hidden',
                          minWidth: 0,
                        }}
                      >
                        {shouldShowLabels && shortName ? (
                          <Text
                            style={{
                              display: 'block',
                              fontSize: 9,
                              lineHeight: 1.1,
                              color: isDark ? '#fff' : palette.text,
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                            }}
                          >
                            {shortName}
                          </Text>
                        ) : null}
                      </div>
                    );

                    return !isMobile ? (
                      <Tooltip key={lesson.id} title={tooltipTitle}>
                        {block}
                      </Tooltip>
                    ) : (
                      <div key={lesson.id} title={tooltipTitle}>
                        {block}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default DashboardMiniWeekCalendar;
