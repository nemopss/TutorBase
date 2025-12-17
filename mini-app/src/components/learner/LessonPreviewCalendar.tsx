import React, { useState, useMemo } from 'react';
import { Card, Button, Typography } from 'antd';
import { LeftOutlined, RightOutlined } from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';
import { useTranslation } from 'react-i18next';
import { useTheme } from '../../theme/ThemeProvider';
import { spacing } from '../../theme/tokens';

const { Text } = Typography;

interface PreviewDate {
  datetime: string;
  duration: number;
}

interface LessonPreviewCalendarProps {
  dates: PreviewDate[];
  onDatesChange: (dates: PreviewDate[]) => void;
  startDate: Dayjs;
}

const WEEKDAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];

const LessonPreviewCalendar: React.FC<LessonPreviewCalendarProps> = ({
  dates,
  onDatesChange,
  startDate,
}) => {
  const { t } = useTranslation();
  const { resolvedTheme } = useTheme();
  const colors = resolvedTheme.colors;
  
  const [currentMonth, setCurrentMonth] = useState(() => startDate.startOf('month'));

  // Get all days in the current month view
  const calendarDays = useMemo(() => {
    const start = currentMonth.startOf('month').startOf('week');
    const end = currentMonth.endOf('month').endOf('week');
    const days: Dayjs[] = [];
    let day = start;
    while (day.isBefore(end) || day.isSame(end, 'day')) {
      days.push(day);
      day = day.add(1, 'day');
    }
    return days;
  }, [currentMonth]);

  // Map dates to day strings for quick lookup
  const dateMap = useMemo(() => {
    const map = new Map<string, PreviewDate>();
    dates.forEach((d) => {
      const key = dayjs(d.datetime).format('YYYY-MM-DD');
      map.set(key, d);
    });
    return map;
  }, [dates]);

  const handleDayClick = (day: Dayjs) => {
    const key = day.format('YYYY-MM-DD');
    const existing = dateMap.get(key);
    
    if (existing) {
      // Remove date
      onDatesChange(dates.filter((d) => dayjs(d.datetime).format('YYYY-MM-DD') !== key));
    } else {
      // Add date with default time and duration
      const newDate: PreviewDate = {
        datetime: day.hour(12).minute(0).toISOString(),
        duration: 60,
      };
      onDatesChange([...dates, newDate].sort((a, b) => 
        dayjs(a.datetime).valueOf() - dayjs(b.datetime).valueOf()
      ));
    }
  };

  const isCurrentMonth = (day: Dayjs) => day.month() === currentMonth.month();
  const isToday = (day: Dayjs) => day.isSame(dayjs(), 'day');
  const hasLesson = (day: Dayjs) => dateMap.has(day.format('YYYY-MM-DD'));

  return (
    <Card
      style={{
        background: colors.bgSecondary,
        borderColor: colors.borderPrimary,
      }}
    >
      {/* Header with month navigation */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        marginBottom: spacing.md,
      }}>
        <Button 
          type="text" 
          icon={<LeftOutlined />} 
          onClick={() => setCurrentMonth(currentMonth.subtract(1, 'month'))}
        />
        <Text strong style={{ fontSize: 16 }}>
          {currentMonth.format('MMMM YYYY')}
        </Text>
        <Button 
          type="text" 
          icon={<RightOutlined />} 
          onClick={() => setCurrentMonth(currentMonth.add(1, 'month'))}
        />
      </div>

      {/* Weekday headers */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(7, 1fr)',
        gap: 2,
        marginBottom: spacing.xs,
      }}>
        {WEEKDAYS.map((day) => (
          <div 
            key={day} 
            style={{ 
              textAlign: 'center', 
              padding: spacing.xs,
              color: colors.textSecondary,
              fontSize: 12,
            }}
          >
            {t(`schedule.daysShort.${day}`)}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(7, 1fr)',
        gap: 2,
      }}>
        {calendarDays.map((day) => {
          const inMonth = isCurrentMonth(day);
          const today = isToday(day);
          const lesson = hasLesson(day);
          
          return (
            <div
              key={day.format('YYYY-MM-DD')}
              onClick={() => handleDayClick(day)}
              style={{
                aspectRatio: '1',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: 8,
                cursor: 'pointer',
                background: lesson 
                  ? colors.accentPrimary 
                  : today 
                    ? colors.bgTertiary 
                    : 'transparent',
                color: lesson 
                  ? '#fff' 
                  : inMonth 
                    ? colors.textPrimary 
                    : colors.textTertiary,
                fontWeight: today || lesson ? 600 : 400,
                fontSize: 14,
                transition: 'all 0.2s',
                border: today && !lesson ? `1px solid ${colors.accentPrimary}` : 'none',
              }}
            >
              {day.date()}
            </div>
          );
        })}
      </div>

      {/* Lesson count */}
      <div style={{ 
        marginTop: spacing.md, 
        textAlign: 'center',
        color: colors.textSecondary,
      }}>
        <Text>
          {dates.length} {t('calendar.lessons')} • {t('schedulePreview.clickToEdit')}
        </Text>
      </div>
    </Card>
  );
};

export default LessonPreviewCalendar;
