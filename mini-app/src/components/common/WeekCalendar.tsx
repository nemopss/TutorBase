import React, { useState, useMemo } from 'react';
import { Button, Typography } from 'antd';
import { LeftOutlined, RightOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import weekOfYear from 'dayjs/plugin/weekOfYear';
import isoWeek from 'dayjs/plugin/isoWeek';
import { useThemeMode } from '../../theme/ThemeProvider';
import { spacing } from '../../theme/tokens';

dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.extend(weekOfYear);
dayjs.extend(isoWeek);

const { Text } = Typography;

type LessonStatus = 'scheduled' | 'rescheduled' | 'completed' | 'cancelled';

interface Lesson {
  id: number;
  scheduled_at: string;
  status: LessonStatus;
  duration_minutes?: number;
}

interface WeekCalendarProps {
  lessons: Lesson[];
  timezone: string;
  onLessonClick: (lessonId: number) => void;
}

/** Status colors for lesson blocks */
const statusColors: Record<LessonStatus, { bg: string; bgDark: string; border: string; text: string }> = {
  scheduled: {
    bg: 'rgba(24, 144, 255, 0.15)',
    bgDark: 'rgba(24, 144, 255, 0.25)',
    border: '#1890ff',
    text: '#1890ff',
  },
  rescheduled: {
    bg: 'rgba(250, 173, 20, 0.15)',
    bgDark: 'rgba(250, 173, 20, 0.25)',
    border: '#faad14',
    text: '#d48806',
  },
  completed: {
    bg: 'rgba(82, 196, 26, 0.15)',
    bgDark: 'rgba(82, 196, 26, 0.25)',
    border: '#52c41a',
    text: '#389e0d',
  },
  cancelled: {
    bg: 'rgba(255, 77, 79, 0.15)',
    bgDark: 'rgba(255, 77, 79, 0.25)',
    border: '#ff4d4f',
    text: '#cf1322',
  },
};

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

// Height calculation: 1 minute = 1.2px, minimum 60px for short lessons
const PIXELS_PER_MINUTE = 1.2;
const MIN_LESSON_HEIGHT = 60;
const DEFAULT_DURATION = 60;

const getLessonHeight = (duration?: number): number => {
  const mins = duration || DEFAULT_DURATION;
  return Math.max(MIN_LESSON_HEIGHT, mins * PIXELS_PER_MINUTE);
};

/**
 * Week calendar view for lessons in Google Calendar style.
 */
const WeekCalendar: React.FC<WeekCalendarProps> = ({
  lessons,
  timezone: tz,
  onLessonClick,
}) => {
  const { resolvedTheme } = useThemeMode();
  const isDark = resolvedTheme === 'dark';
  
  // Current week start (Monday)
  const [weekStart, setWeekStart] = useState(() => dayjs().tz(tz).startOf('isoWeek'));

  // Generate days of the week
  const weekDays = useMemo(() => {
    return Array.from({ length: 7 }, (_, i) => weekStart.add(i, 'day'));
  }, [weekStart]);

  // Group lessons by day
  const lessonsByDay = useMemo(() => {
    const map: Record<string, Lesson[]> = {};
    weekDays.forEach(day => {
      map[day.format('YYYY-MM-DD')] = [];
    });
    
    lessons.forEach(lesson => {
      const lessonDate = dayjs(lesson.scheduled_at).tz(tz).format('YYYY-MM-DD');
      if (map[lessonDate]) {
        map[lessonDate].push(lesson);
      }
    });

    // Sort lessons by time within each day
    Object.keys(map).forEach(date => {
      map[date].sort((a, b) => 
        dayjs(a.scheduled_at).valueOf() - dayjs(b.scheduled_at).valueOf()
      );
    });

    return map;
  }, [lessons, weekDays, tz]);

  const goToPrevWeek = () => setWeekStart(prev => prev.subtract(1, 'week'));
  const goToNextWeek = () => setWeekStart(prev => prev.add(1, 'week'));
  const goToToday = () => setWeekStart(dayjs().tz(tz).startOf('isoWeek'));

  const weekEnd = weekStart.add(6, 'day');
  const isCurrentWeek = dayjs().tz(tz).isSame(weekStart, 'isoWeek');

  // Calculate week stats
  const weekStats = useMemo(() => {
    let totalLessons = 0;
    let totalMinutes = 0;
    Object.values(lessonsByDay).forEach(dayLessons => {
      totalLessons += dayLessons.length;
      dayLessons.forEach(l => {
        totalMinutes += l.duration_minutes || DEFAULT_DURATION;
      });
    });
    return { totalLessons, totalHours: Math.round(totalMinutes / 60 * 10) / 10 };
  }, [lessonsByDay]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 280px)', minHeight: 400 }}>
      {/* Header with navigation */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: spacing.md,
        flexWrap: 'wrap',
        gap: spacing.sm,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: spacing.xs }}>
          <Button 
            icon={<LeftOutlined />} 
            onClick={goToPrevWeek}
            size="small"
          />
          <Button 
            icon={<RightOutlined />} 
            onClick={goToNextWeek}
            size="small"
          />
          {!isCurrentWeek && (
            <Button size="small" onClick={goToToday}>
              Today
            </Button>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: spacing.md }}>
          {weekStats.totalLessons > 0 && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              {weekStats.totalLessons} lessons • {weekStats.totalHours}h
            </Text>
          )}
          <Text strong style={{ fontSize: 14 }}>
            {weekStart.format('MMM D')} – {weekEnd.format('MMM D, YYYY')}
          </Text>
        </div>
      </div>

      {/* Calendar grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(7, 1fr)',
        gridTemplateRows: 'auto 1fr',
        gap: 1,
        background: isDark ? '#303030' : '#e8e8e8',
        borderRadius: 8,
        overflow: 'hidden',
        flex: 1,
      }}>
        {/* Day headers */}
        {weekDays.map((day, index) => {
          const isToday = day.isSame(dayjs().tz(tz), 'day');
          return (
            <div
              key={`header-${index}`}
              style={{
                background: isDark ? '#1f1f1f' : '#fafafa',
                padding: `${spacing.xs}px ${spacing.xs}px`,
                textAlign: 'center',
              }}
            >
              <Text 
                type="secondary" 
                style={{ fontSize: 11, display: 'block' }}
              >
                {DAYS[index]}
              </Text>
              <Text 
                strong={isToday}
                style={{ 
                  fontSize: 16,
                  color: isToday ? '#1890ff' : undefined,
                  background: isToday ? 'rgba(24, 144, 255, 0.1)' : undefined,
                  borderRadius: '50%',
                  width: 28,
                  height: 28,
                  lineHeight: '28px',
                  display: 'inline-block',
                }}
              >
                {day.format('D')}
              </Text>
            </div>
          );
        })}

        {/* Day cells with lessons */}
        {weekDays.map((day, index) => {
          const dateKey = day.format('YYYY-MM-DD');
          const dayLessons = lessonsByDay[dateKey] || [];
          const isToday = day.isSame(dayjs().tz(tz), 'day');

          return (
            <div
              key={`cell-${index}`}
              style={{
                background: isDark 
                  ? (isToday ? '#1a1a2e' : '#141414') 
                  : (isToday ? '#f0f7ff' : '#ffffff'),
                padding: spacing.xs,
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
                overflowY: 'auto',
              }}
            >
              {dayLessons.map(lesson => {
                const lessonTime = dayjs(lesson.scheduled_at).tz(tz);
                const duration = lesson.duration_minutes || DEFAULT_DURATION;
                const endTime = lessonTime.add(duration, 'minute');
                const colors = statusColors[lesson.status];
                const statusLabel = lesson.status.charAt(0).toUpperCase() + lesson.status.slice(1);
                const height = getLessonHeight(lesson.duration_minutes);
                
                return (
                  <div
                    key={lesson.id}
                    onClick={() => onLessonClick(lesson.id)}
                    style={{
                      background: isDark ? colors.bgDark : colors.bg,
                      borderLeft: `4px solid ${colors.border}`,
                      borderRadius: 6,
                      padding: '8px 10px',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      minHeight: height,
                      display: 'flex',
                      flexDirection: 'column',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.transform = 'scale(1.02)';
                      e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.transform = 'scale(1)';
                      e.currentTarget.style.boxShadow = 'none';
                    }}
                  >
                    {/* Time range */}
                    <Text 
                      strong 
                      style={{ 
                        fontSize: 13, 
                        color: isDark ? '#fff' : colors.text,
                        display: 'block',
                        marginBottom: 2,
                      }}
                    >
                      {lessonTime.format('HH:mm')}–{endTime.format('HH:mm')}
                    </Text>
                    {/* Duration */}
                    <Text 
                      style={{ 
                        fontSize: 11, 
                        color: isDark ? 'rgba(255,255,255,0.65)' : 'rgba(0,0,0,0.55)',
                        display: 'block',
                        marginBottom: 4,
                      }}
                    >
                      {duration} min
                    </Text>
                    {/* Status badge - pushed to bottom */}
                    <div style={{ marginTop: 'auto' }}>
                      <div
                        style={{
                          fontSize: 10,
                          color: isDark ? 'rgba(255,255,255,0.85)' : colors.text,
                          background: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.05)',
                          padding: '2px 6px',
                          borderRadius: 4,
                          display: 'inline-block',
                        }}
                      >
                        {statusLabel}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div style={{
        display: 'flex',
        gap: spacing.md,
        marginTop: spacing.sm,
        flexWrap: 'wrap',
        justifyContent: 'center',
      }}>
        {Object.entries(statusColors).map(([status, colors]) => (
          <div key={status} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{
              width: 12,
              height: 12,
              borderRadius: 2,
              background: isDark ? colors.bgDark : colors.bg,
              borderLeft: `3px solid ${colors.border}`,
            }} />
            <Text type="secondary" style={{ fontSize: 11 }}>
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </Text>
          </div>
        ))}
      </div>
    </div>
  );
};

export default WeekCalendar;
