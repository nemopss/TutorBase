import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Tooltip, Typography } from 'antd';
import dayjs from 'dayjs';
import isoWeek from 'dayjs/plugin/isoWeek';
import { useTranslation } from 'react-i18next';
import { useResponsive } from '../../hooks/useResponsive';
import { useTheme } from '../../theme/ThemeProvider';

dayjs.extend(isoWeek);

const { Text } = Typography;

interface DashboardHistoryDayPoint {
  date: string;
  hours: number;
  lessons_count: number;
}

interface DashboardLessonLoadHeatmapProps {
  days: DashboardHistoryDayPoint[];
  fromDate: string;
  toDate: string;
}

const DAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const;
const LABEL_COLUMN_WIDTH = 26;
const CELL_GAP = 4;
const MOBILE_VISIBLE_DAYS = 84;
const MIN_CELL_SIZE = 8;
const DEFAULT_CELL_SIZE = 12;
const MONTH_TRACK_HEIGHT = 18;

const HEATMAP_COLORS = {
  low: 'rgba(70, 160, 84, 0.30)',
  medium: 'rgba(225, 183, 52, 0.34)',
  high: 'rgba(217, 92, 78, 0.42)',
} as const;

const formatHours = (value: number): string => {
  if (Number.isInteger(value)) {
    return String(value);
  }
  return value.toFixed(1).replace(/\.0$/, '');
};

const DashboardLessonLoadHeatmap: React.FC<DashboardLessonLoadHeatmapProps> = ({
  days,
  fromDate,
  toDate,
}) => {
  const { t } = useTranslation();
  const { isMobile } = useResponsive();
  const { resolvedTheme } = useTheme();
  const colors = resolvedTheme.colors;
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [containerWidth, setContainerWidth] = useState(0);

  useEffect(() => {
    if (!containerRef.current || typeof ResizeObserver === 'undefined') {
      return;
    }

    const node = containerRef.current;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) {
        return;
      }
      setContainerWidth(Math.floor(entry.contentRect.width));
    });

    observer.observe(node);
    setContainerWidth(Math.floor(node.getBoundingClientRect().width));

    return () => observer.disconnect();
  }, []);

  const visibleRange = useMemo(() => {
    const requestedStart = dayjs(fromDate).startOf('day');
    const requestedEnd = dayjs(toDate).startOf('day');
    const mobileStart = requestedEnd.subtract(MOBILE_VISIBLE_DAYS - 1, 'day').startOf('day');
    return {
      start: isMobile && mobileStart.isAfter(requestedStart) ? mobileStart : requestedStart,
      end: requestedEnd,
    };
  }, [fromDate, isMobile, toDate]);

  const visibleDays = useMemo(() => {
    const items: dayjs.Dayjs[] = [];
    let current = visibleRange.start;
    while (!current.isAfter(visibleRange.end, 'day')) {
      items.push(current);
      current = current.add(1, 'day');
    }
    return items;
  }, [visibleRange]);

  const dayStatsByKey = useMemo(
    () => new Map(days.map((item) => [item.date, item])),
    [days],
  );

  const calendarBounds = useMemo(() => {
    const start = visibleRange.start.startOf('isoWeek');
    const end = visibleRange.end.endOf('isoWeek');
    return { start, end };
  }, [visibleRange]);

  const weeks = useMemo(() => {
    const result: dayjs.Dayjs[][] = [];
    let cursor = calendarBounds.start;
    while (!cursor.isAfter(calendarBounds.end, 'day')) {
      result.push(Array.from({ length: 7 }, (_, index) => cursor.add(index, 'day')));
      cursor = cursor.add(1, 'week');
    }
    return result;
  }, [calendarBounds]);

  const maxHours = useMemo(
    () => Math.max(0, ...visibleDays.map((day) => dayStatsByKey.get(day.format('YYYY-MM-DD'))?.hours ?? 0)),
    [dayStatsByKey, visibleDays],
  );

  const isEmpty = maxHours <= 0;
  const weekColumnWidth = useMemo(() => {
    if (weeks.length === 0) {
      return DEFAULT_CELL_SIZE;
    }
    const availableWidth = Math.max(
      0,
      containerWidth - LABEL_COLUMN_WIDTH - 8 - ((weeks.length - 1) * CELL_GAP),
    );
    if (availableWidth <= 0) {
      return DEFAULT_CELL_SIZE;
    }
    return Math.max(MIN_CELL_SIZE, Math.floor(availableWidth / weeks.length));
  }, [containerWidth, weeks.length]);

  const gridWidth = useMemo(
    () => Math.max(0, (weeks.length * weekColumnWidth) + ((weeks.length - 1) * CELL_GAP)),
    [weekColumnWidth, weeks.length],
  );

  const monthAnchors = useMemo(() => {
    const rawAnchors: { key: string; label: string; left: number }[] = [];
    const seenMonths = new Set<string>();
    weeks.forEach((week, weekIndex) => {
      const inRangeDays = week.filter(
        (day) => !day.isBefore(visibleRange.start, 'day') && !day.isAfter(visibleRange.end, 'day'),
      );
      if (inRangeDays.length === 0) {
        return;
      }
      const labelDay =
        inRangeDays.find((day) => day.date() === 1)
        || (rawAnchors.length === 0 ? inRangeDays[0] : null);
      if (!labelDay) {
        return;
      }
      const monthKey = labelDay.format('YYYY-MM');
      if (seenMonths.has(monthKey)) {
        return;
      }
      seenMonths.add(monthKey);
      rawAnchors.push({
        key: monthKey,
        label: labelDay.format('MMM'),
        left: weekIndex * (weekColumnWidth + CELL_GAP),
      });
    });

    const minLabelGap = isMobile ? 28 : 42;
    let lastAcceptedLeft = Number.NEGATIVE_INFINITY;

    return rawAnchors.filter((anchor, index) => {
      if (index === 0) {
        lastAcceptedLeft = anchor.left;
        return true;
      }
      if (anchor.left - lastAcceptedLeft < minLabelGap) {
        return false;
      }
      lastAcceptedLeft = anchor.left;
      return true;
    });
  }, [isMobile, visibleRange.end, visibleRange.start, weekColumnWidth, weeks]);

  const getCellColor = (hours: number, inRange: boolean): string => {
    if (!inRange) {
      return 'transparent';
    }
    if (hours <= 0) {
      return colors.bgTertiary;
    }
    if (hours <= 1) {
      return HEATMAP_COLORS.low;
    }
    if (hours <= 2) {
      return 'rgba(70, 160, 84, 0.46)';
    }
    if (hours <= 4) {
      return HEATMAP_COLORS.medium;
    }
    return HEATMAP_COLORS.high;
  };

  if (isEmpty) {
    return (
      <div
        style={{
          flex: 1,
          minHeight: 180,
          borderRadius: 8,
          background: colors.bgTertiary,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 16,
        }}
      >
        <Text type="secondary">{t('pages.dashboard.level3.heatmap.empty')}</Text>
      </div>
    );
  }

  return (
    <div ref={containerRef} style={{ display: 'flex', flexDirection: 'column', gap: 12, width: '100%' }}>
      <div
        style={{
          position: 'relative',
          height: MONTH_TRACK_HEIGHT,
          marginLeft: LABEL_COLUMN_WIDTH + 8,
          width: gridWidth,
          maxWidth: '100%',
          overflow: 'hidden',
        }}
      >
        {monthAnchors.map((anchor) => (
          <div
            key={anchor.key}
            style={{
              position: 'absolute',
              left: anchor.left,
              top: 0,
              whiteSpace: 'nowrap',
              pointerEvents: 'none',
              lineHeight: 1,
            }}
          >
            <Text type="secondary" style={{ fontSize: isMobile ? 10 : 11, lineHeight: 1 }}>
              {anchor.label.charAt(0).toUpperCase() + anchor.label.slice(1)}
            </Text>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', width: '100%' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateRows: `repeat(7, ${weekColumnWidth}px)`,
            gap: CELL_GAP,
            width: LABEL_COLUMN_WIDTH,
            flex: '0 0 auto',
          }}
        >
          {DAY_KEYS.map((dayKey) => (
            <div
              key={dayKey}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-start',
              }}
            >
              <Text type="secondary" style={{ fontSize: 10, lineHeight: 1 }}>
                {t(`calendar.daysShort.${dayKey}`)}
              </Text>
            </div>
          ))}
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: `repeat(${weeks.length}, ${weekColumnWidth}px)`,
            gap: CELL_GAP,
            width: gridWidth,
            maxWidth: '100%',
            minWidth: 0,
          }}
        >
          {weeks.map((week, weekIndex) => (
            <div
              key={`week-${weekIndex}`}
              style={{
                display: 'grid',
                gridTemplateRows: `repeat(7, ${weekColumnWidth}px)`,
                gap: CELL_GAP,
              }}
            >
              {week.map((day) => {
                const dayKey = day.format('YYYY-MM-DD');
                const stats = dayStatsByKey.get(dayKey);
                const inRange = !day.isBefore(visibleRange.start, 'day') && !day.isAfter(visibleRange.end, 'day');
                const hours = stats?.hours ?? 0;
                const lessonsCount = stats?.lessons_count ?? 0;
                const isToday = day.isSame(dayjs(), 'day');
                const content = (
                  <div
                    style={{
                      width: weekColumnWidth,
                      height: weekColumnWidth,
                      borderRadius: 4,
                      background: getCellColor(hours, inRange),
                      boxSizing: 'border-box',
                      border: isToday && inRange ? `1px solid ${colors.accentPrimary}` : '1px solid transparent',
                    }}
                  />
                );

                if (!inRange) {
                  return <div key={dayKey}>{content}</div>;
                }

                return (
                  <Tooltip
                    key={dayKey}
                    trigger={isMobile ? ['click'] : ['hover']}
                    title={
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <span>{day.format('D MMM YYYY')}</span>
                        <span>
                          {t('pages.dashboard.level3.heatmap.tooltipHours', {
                            hours: formatHours(hours),
                            lessons: lessonsCount,
                          })}
                        </span>
                      </div>
                    }
                  >
                    {content}
                  </Tooltip>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default DashboardLessonLoadHeatmap;
