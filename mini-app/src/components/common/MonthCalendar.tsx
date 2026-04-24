import React, { useEffect, useMemo, useState } from 'react';
import { Button, Typography } from 'antd';
import { LeftOutlined, RightOutlined } from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import isoWeek from 'dayjs/plugin/isoWeek';
import { useTranslation } from 'react-i18next';
import type { Lesson } from './calendar-types';
import { DEFAULT_DURATION } from './calendar-types';
import { useTheme } from '../../theme/ThemeProvider';
import { useResponsive } from '../../hooks/useResponsive';
import { spacing } from '../../theme/tokens';
import MonthDayCell from './MonthDayCell';
import DayLessonsModal from './DayLessonsModal';
import type { CalendarVisibleRange } from './CalendarContainer';

dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.extend(isoWeek);

const { Text } = Typography;

interface MonthCalendarProps {
  lessons: Lesson[];
  timezone: string;
  onLessonClick: (lessonId: number) => void;
  onAddLesson?: (date: string) => void;
  onReschedule?: (lessonId: number) => void;
  onComplete?: (lessonId: number) => void;
  onCancel?: (lessonId: number) => void;
  onDelete?: (lessonId: number) => void;
  onRangeChange?: (range: CalendarVisibleRange) => void;
}

const MonthCalendar: React.FC<MonthCalendarProps> = ({
  lessons,
  timezone: tz,
  onLessonClick,
  onAddLesson,
  onReschedule,
  onComplete,
  onCancel,
  onDelete,
  onRangeChange,
}) => {
  const { t } = useTranslation();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme.colorScheme === 'dark';
  const colors = resolvedTheme.colors;
  const { isMobile } = useResponsive();
  
  // Translated days of week
  const daysShort = [
    t('calendar.daysShort.mon'),
    t('calendar.daysShort.tue'),
    t('calendar.daysShort.wed'),
    t('calendar.daysShort.thu'),
    t('calendar.daysShort.fri'),
    t('calendar.daysShort.sat'),
    t('calendar.daysShort.sun'),
  ];

  // Current displayed month
  const [currentMonth, setCurrentMonth] = useState<Dayjs>(() => dayjs().tz(tz).startOf('month'));
  
  // Modal state
  const [selectedDate, setSelectedDate] = useState<Dayjs | null>(null);
  const [isDayModalOpen, setIsDayModalOpen] = useState(false);

  // Generate days for the month grid (including padding days from prev/next months)
  const monthDays = useMemo(() => {
    const startOfMonth = currentMonth.startOf('month');
    const endOfMonth = currentMonth.endOf('month');
    
    // Get the day of week for the first day (0 = Sunday, 1 = Monday, etc.)
    // We want Monday as first day, so adjust
    const startDayRaw = startOfMonth.day();
    const startDayOfWeek = startDayRaw === 0 ? 7 : startDayRaw; // Sunday becomes 7
    const paddingBefore = startDayOfWeek - 1; // Days from previous month
    
    // Get the day of week for the last day
    const endDayRaw = endOfMonth.day();
    const endDayOfWeek = endDayRaw === 0 ? 7 : endDayRaw;
    const paddingAfter = 7 - endDayOfWeek; // Days from next month
    
    const days: Dayjs[] = [];
    
    // Add padding days from previous month
    for (let i = paddingBefore; i > 0; i--) {
      days.push(startOfMonth.subtract(i, 'day'));
    }
    
    // Add days of current month
    const daysInMonth = currentMonth.daysInMonth();
    for (let i = 0; i < daysInMonth; i++) {
      days.push(startOfMonth.add(i, 'day'));
    }
    
    // Add padding days from next month
    for (let i = 1; i <= paddingAfter; i++) {
      days.push(endOfMonth.add(i, 'day'));
    }
    
    return days;
  }, [currentMonth]);

  // Group lessons by date
  const lessonsByDate = useMemo(() => {
    const map: Record<string, Lesson[]> = {};
    
    lessons.forEach(lesson => {
      const dateKey = dayjs(lesson.scheduled_at).tz(tz).format('YYYY-MM-DD');
      if (!map[dateKey]) map[dateKey] = [];
      map[dateKey].push(lesson);
    });
    
    // Sort lessons by time within each day
    Object.keys(map).forEach(date => {
      map[date].sort((a, b) => 
        dayjs(a.scheduled_at).valueOf() - dayjs(b.scheduled_at).valueOf()
      );
    });
    
    return map;
  }, [lessons, tz]);

  // Calculate month statistics
  const monthStats = useMemo(() => {
    let totalLessons = 0;
    let totalMinutes = 0;
    
    monthDays.forEach(day => {
      // Only count lessons from current month
      if (day.month() === currentMonth.month()) {
        const dateKey = day.format('YYYY-MM-DD');
        const dayLessons = lessonsByDate[dateKey] || [];
        totalLessons += dayLessons.length;
        dayLessons.forEach(l => {
          totalMinutes += l.duration_minutes || DEFAULT_DURATION;
        });
      }
    });
    
    return { 
      totalLessons, 
      totalHours: Math.round(totalMinutes / 60 * 10) / 10 
    };
  }, [lessonsByDate, monthDays, currentMonth]);

  // Navigation
  const goToPrevMonth = () => setCurrentMonth(prev => prev.subtract(1, 'month'));
  const goToNextMonth = () => setCurrentMonth(prev => prev.add(1, 'month'));
  const goToToday = () => setCurrentMonth(dayjs().tz(tz).startOf('month'));

  const today = dayjs().tz(tz);
  const isCurrentMonthVisible = currentMonth.isSame(today, 'month');

  // Handle day click
  const handleDayClick = (date: Dayjs) => {
    setSelectedDate(date);
    setIsDayModalOpen(true);
  };

  // Get lessons for selected date
  const selectedDateLessons = useMemo(() => {
    if (!selectedDate) return [];
    const dateKey = selectedDate.format('YYYY-MM-DD');
    return lessonsByDate[dateKey] || [];
  }, [selectedDate, lessonsByDate]);

  // Calculate number of rows
  const rowCount = Math.ceil(monthDays.length / 7);
  const visibleRange = useMemo<CalendarVisibleRange>(() => {
    const visibleStart = currentMonth.startOf('month').startOf('isoWeek');
    const visibleEnd = currentMonth.endOf('month').endOf('isoWeek');

    return {
      from: visibleStart.startOf('day').subtract(14, 'day').toISOString(),
      to: visibleEnd.endOf('day').add(21, 'day').toISOString(),
    };
  }, [currentMonth]);

  useEffect(() => {
    if (!onRangeChange) {
      return;
    }

    onRangeChange(visibleRange);
  }, [onRangeChange, visibleRange]);

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
            onClick={goToPrevMonth}
            size="small"
          />
          <Button 
            icon={<RightOutlined />} 
            onClick={goToNextMonth}
            size="small"
          />
          <Button 
            size="small" 
            onClick={goToToday}
            style={{ 
              visibility: isCurrentMonthVisible ? 'hidden' : 'visible',
            }}
          >
            {t('calendar.today')}
          </Button>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: spacing.md }}>
          {monthStats.totalLessons > 0 && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              {monthStats.totalLessons} {monthStats.totalLessons === 1 ? t('calendar.lesson') : t('calendar.lessons')} • {monthStats.totalHours}{t('calendar.hours')}
            </Text>
          )}
          <Text strong style={{ fontSize: 14 }}>
            {currentMonth.format('MMMM YYYY')}
          </Text>
        </div>
      </div>

      {/* Day headers */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(7, 1fr)',
        background: colors.bgTertiary,
        borderRadius: '8px 8px 0 0',
        borderBottom: `1px solid ${colors.borderPrimary}`,
      }}>
        {daysShort.map((day, index) => (
          <div
            key={index}
            style={{
              padding: isMobile ? '6px 2px' : spacing.xs,
              textAlign: 'center',
            }}
          >
            <Text 
              type="secondary" 
              style={{ fontSize: isMobile ? 11 : 12, fontWeight: 500 }}
            >
              {day}
            </Text>
          </div>
        ))}
      </div>

      {/* Month grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(7, 1fr)',
        gridTemplateRows: `repeat(${rowCount}, 1fr)`,
        flex: 1,
        background: colors.bgPrimary,
        borderRadius: '0 0 8px 8px',
        overflow: 'hidden',
        border: `1px solid ${colors.borderPrimary}`,
        borderTop: 'none',
      }}>
        {monthDays.map((day, index) => {
          const dateKey = day.format('YYYY-MM-DD');
          const dayLessons = lessonsByDate[dateKey] || [];
          const isToday = day.isSame(today, 'day');
          const isCurrentMonth = day.month() === currentMonth.month();

          return (
            <MonthDayCell
              key={index}
              date={day}
              lessons={dayLessons}
              isToday={isToday}
              isCurrentMonth={isCurrentMonth}
              isDark={isDark}
              isMobile={isMobile}
              timezone={tz}
              onDayClick={handleDayClick}
              onAddLesson={onAddLesson}
            />
          );
        })}
      </div>

      {/* Day lessons modal */}
      <DayLessonsModal
        open={isDayModalOpen}
        date={selectedDate}
        lessons={selectedDateLessons}
        timezone={tz}
        onClose={() => setIsDayModalOpen(false)}
        onLessonClick={onLessonClick}
        onAddLesson={onAddLesson}
        onReschedule={onReschedule}
        onComplete={onComplete}
        onCancel={onCancel}
        onDelete={onDelete}
      />
    </div>
  );
};

export default MonthCalendar;
