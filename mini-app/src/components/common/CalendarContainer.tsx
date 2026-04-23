import React, { useState } from 'react';
import { Segmented } from 'antd';
import { CalendarOutlined, AppstoreOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type { Lesson } from './calendar-types';
import WeekCalendar from './WeekCalendar';
import MonthCalendar from './MonthCalendar';
import { spacing } from '../../theme/tokens';

type CalendarView = 'week' | 'month';
export interface CalendarVisibleRange {
  from: string;
  to: string;
}

interface CalendarContainerProps {
  lessons: Lesson[];
  timezone: string;
  onLessonClick: (lessonId: number) => void;
  onAddLesson?: (date: string) => void;
  onReschedule?: (lessonId: number, newDate?: string) => void;
  onComplete?: (lessonId: number) => void;
  onCancel?: (lessonId: number) => void;
  onDelete?: (lessonId: number) => void;
  defaultView?: CalendarView;
  onRangeChange?: (range: CalendarVisibleRange) => void;
}

const CalendarContainer: React.FC<CalendarContainerProps> = ({
  lessons,
  timezone,
  onLessonClick,
  onAddLesson,
  onReschedule,
  onComplete,
  onCancel,
  onDelete,
  defaultView = 'week',
  onRangeChange,
}) => {
  const { t } = useTranslation();
  const [view, setView] = useState<CalendarView>(defaultView);

  const viewOptions = [
    {
      label: t('calendar.week'),
      value: 'week' as CalendarView,
      icon: <CalendarOutlined />,
    },
    {
      label: t('calendar.month'),
      value: 'month' as CalendarView,
      icon: <AppstoreOutlined />,
    },
  ];

  return (
    <div>
      {/* View switcher */}
      <div style={{ marginBottom: spacing.md }}>
        <Segmented
          options={viewOptions}
          value={view}
          onChange={(value) => setView(value as CalendarView)}
        />
      </div>

      {/* Calendar view */}
      {view === 'week' ? (
        <WeekCalendar
          lessons={lessons}
          timezone={timezone}
          onLessonClick={onLessonClick}
          onAddLesson={onAddLesson}
          onReschedule={onReschedule}
          onComplete={onComplete}
          onCancel={onCancel}
          onDelete={onDelete}
          onRangeChange={onRangeChange}
        />
      ) : (
        <MonthCalendar
          lessons={lessons}
          timezone={timezone}
          onLessonClick={onLessonClick}
          onAddLesson={onAddLesson}
          onReschedule={onReschedule}
          onComplete={onComplete}
          onCancel={onCancel}
          onDelete={onDelete}
          onRangeChange={onRangeChange}
        />
      )}
    </div>
  );
};

export default CalendarContainer;
