import React, { useMemo } from 'react';
import { Card, Typography } from 'antd';
import dayjs, { Dayjs } from 'dayjs';
import type { Lesson } from './types';
import { STATUS_COLORS } from './types';

const { Text } = Typography;

interface WeekViewProps {
  lessons: Lesson[];
  currentDate: Dayjs;
  onLessonClick: (lesson: Lesson) => void;
}

const WeekView: React.FC<WeekViewProps> = ({ lessons, currentDate, onLessonClick }) => {
  // Get start of week (Monday)
  const weekStart = currentDate.startOf('isoWeek');
  const weekDays = Array.from({ length: 7 }, (_, i) => weekStart.add(i, 'day'));

  // Group lessons by day
  const lessonsByDay = useMemo(() => {
    const grouped: Record<string, Lesson[]> = {};
    weekDays.forEach(day => {
      grouped[day.format('YYYY-MM-DD')] = [];
    });

    lessons.forEach(lesson => {
      const lessonDay = dayjs(lesson.scheduled_at);
      if (lessonDay.isSame(weekStart, 'isoWeek')) {
        const key = lessonDay.format('YYYY-MM-DD');
        if (grouped[key]) {
          grouped[key].push(lesson);
        }
      }
    });

    // Sort lessons by time within each day
    Object.keys(grouped).forEach(key => {
      grouped[key].sort((a, b) => 
        dayjs(a.scheduled_at).valueOf() - dayjs(b.scheduled_at).valueOf()
      );
    });

    return grouped;
  }, [lessons, weekStart]);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 8 }}>
      {weekDays.map(day => {
        const dateKey = day.format('YYYY-MM-DD');
        const dayLessons = lessonsByDay[dateKey] || [];
        const isToday = day.isSame(dayjs(), 'day');

        return (
          <Card
            key={dateKey}
            size="small"
            title={
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 12, fontWeight: 'normal', color: '#999' }}>
                  {day.format('ddd')}
                </div>
                <div style={{ 
                  fontSize: 18,
                  fontWeight: isToday ? 'bold' : 'normal',
                  color: isToday ? '#1890ff' : 'inherit'
                }}>
                  {day.format('D')}
                </div>
              </div>
            }
            style={{ 
              minHeight: 200,
              background: isToday ? '#e6f7ff' : 'white'
            }}
          >
            {dayLessons.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '20px 0', color: '#999' }}>
                <Text type="secondary" style={{ fontSize: 12 }}>Нет уроков</Text>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {dayLessons.map(lesson => {
                  const lessonTime = dayjs(lesson.scheduled_at);
                  const statusColor = STATUS_COLORS[lesson.status];

                  return (
                    <div
                      key={lesson.id}
                      onClick={() => onLessonClick(lesson)}
                      style={{
                        cursor: 'pointer',
                        padding: 8,
                        borderRadius: 4,
                        border: `1px solid ${statusColor}`,
                        background: `${statusColor}10`,
                        transition: 'all 0.2s'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.transform = 'scale(1.02)';
                        e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.transform = 'scale(1)';
                        e.currentTarget.style.boxShadow = 'none';
                      }}
                    >
                      <div style={{ fontWeight: 'bold', fontSize: 14 }}>
                        {lessonTime.format('HH:mm')}
                      </div>
                      <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
                        {lesson.duration_minutes} мин
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
};

export default WeekView;
