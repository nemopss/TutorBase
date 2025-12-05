import React, { useState } from 'react';
import { Calendar, Badge, Modal, List, theme } from 'antd';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import type { Lesson } from './types';
import { useResponsive } from '../../hooks/useResponsive';
import { spacing } from '../../theme/tokens';

interface MonthCalendarProps {
  lessons: Lesson[];
  onLessonClick: (lesson: Lesson) => void;
}

const MonthCalendar: React.FC<MonthCalendarProps> = ({ lessons, onLessonClick }) => {
  const { isMobile } = useResponsive();
  const { token } = theme.useToken();
  const [selectedDate, setSelectedDate] = useState<Dayjs | null>(null);
  const [dayModalOpen, setDayModalOpen] = useState(false);

  // Group lessons by date
  const lessonsByDate = lessons.reduce((acc, lesson) => {
    const date = dayjs(lesson.scheduled_at).format('YYYY-MM-DD');
    if (!acc[date]) {
      acc[date] = [];
    }
    acc[date].push(lesson);
    return acc;
  }, {} as Record<string, Lesson[]>);

  const handleDateSelect = (value: Dayjs) => {
    const dateKey = value.format('YYYY-MM-DD');
    const dayLessons = lessonsByDate[dateKey] || [];
    
    if (isMobile && dayLessons.length > 0) {
      setSelectedDate(value);
      setDayModalOpen(true);
    }
  };

  // Cell render function (replaces deprecated dateCellRender)
  const cellRender = (value: Dayjs, info: { type: string }) => {
    if (info.type !== 'date') return null;
    
    const dateKey = value.format('YYYY-MM-DD');
    const dayLessons = lessonsByDate[dateKey] || [];

    if (dayLessons.length === 0) return null;

    // Mobile: Show dots/badges only
    if (isMobile) {
      return (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 2, flexWrap: 'wrap' }}>
          {dayLessons.slice(0, 3).map((lesson) => (
            <Badge
              key={lesson.id}
              status={lesson.status === 'scheduled' ? 'processing' : lesson.status === 'completed' ? 'success' : 'error'}
            />
          ))}
          {dayLessons.length > 3 && (
            <span style={{ fontSize: 10, color: token.colorTextSecondary }}>+{dayLessons.length - 3}</span>
          )}
        </div>
      );
    }

    // Desktop: Show full list
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
                e.currentTarget.style.background = token.colorBgTextHover;
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

  const selectedDateLessons = selectedDate 
    ? lessonsByDate[selectedDate.format('YYYY-MM-DD')] || []
    : [];

  return (
    <>
      <Calendar 
        cellRender={cellRender}
        onSelect={handleDateSelect}
        fullscreen={!isMobile}
      />
      
      {/* Mobile: Day details modal */}
      <Modal
        open={dayModalOpen}
        title={selectedDate?.format('dddd, D MMMM')}
        onCancel={() => setDayModalOpen(false)}
        footer={null}
        width={isMobile ? '100%' : 400}
      >
        <List
          dataSource={selectedDateLessons}
          renderItem={(lesson) => {
            const time = dayjs(lesson.scheduled_at).format('HH:mm');
            return (
              <List.Item
                onClick={() => {
                  setDayModalOpen(false);
                  onLessonClick(lesson);
                }}
                style={{ cursor: 'pointer', padding: spacing.sm }}
              >
                <Badge 
                  status={lesson.status === 'scheduled' ? 'processing' : lesson.status === 'completed' ? 'success' : 'error'} 
                  text={`${time} - ${lesson.duration_minutes || 60} мин`}
                />
              </List.Item>
            );
          }}
        />
      </Modal>
    </>
  );
};

export default MonthCalendar;
