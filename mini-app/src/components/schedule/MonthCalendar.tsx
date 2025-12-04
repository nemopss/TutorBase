import React from 'react';
import { Calendar, Badge } from 'antd';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import type { Lesson } from './types';

interface MonthCalendarProps {
  lessons: Lesson[];
  onLessonClick: (lesson: Lesson) => void;
}

const MonthCalendar: React.FC<MonthCalendarProps> = ({ lessons, onLessonClick }) => {
  // Group lessons by date
  const lessonsByDate = lessons.reduce((acc, lesson) => {
    const date = dayjs(lesson.scheduled_at).format('YYYY-MM-DD');
    if (!acc[date]) {
      acc[date] = [];
    }
    acc[date].push(lesson);
    return acc;
  }, {} as Record<string, Lesson[]>);

  const dateCellRender = (value: Dayjs) => {
    const dateKey = value.format('YYYY-MM-DD');
    const dayLessons = lessonsByDate[dateKey] || [];

    if (dayLessons.length === 0) return null;

    return (
      <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {dayLessons.map((lesson) => {
          const time = dayjs(lesson.scheduled_at).format('HH:mm');
          
          return (
            <li 
              key={lesson.id}
              onClick={(e) => {
                e.stopPropagation();
                onLessonClick(lesson);
              }}
              style={{ 
                cursor: 'pointer',
                marginBottom: 4,
                padding: '2px 4px',
                borderRadius: 4,
                transition: 'background 0.2s'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = '#f0f0f0';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
              }}
            >
              <Badge 
                status={lesson.status === 'scheduled' ? 'processing' : lesson.status === 'completed' ? 'success' : 'error'} 
                text={time}
                style={{ fontSize: 12 }}
              />
            </li>
          );
        })}
      </ul>
    );
  };

  return (
    <Calendar 
      dateCellRender={dateCellRender}
      // Calendar starts on Monday by default in Russian locale
    />
  );
};

export default MonthCalendar;
