import React, { useMemo, useState } from 'react';
import { Card, Typography, theme } from 'antd';
import { DownOutlined, RightOutlined } from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';
import { useTranslation } from 'react-i18next';
import type { Lesson } from './types';
import { STATUS_COLORS } from './types';
import { useResponsive } from '../../hooks/useResponsive';
import { spacing } from '../../theme/tokens';

const { Text } = Typography;

interface WeekViewProps {
  lessons: Lesson[];
  currentDate: Dayjs;
  onLessonClick: (lesson: Lesson) => void;
}

const WeekView: React.FC<WeekViewProps> = ({ lessons, currentDate, onLessonClick }) => {
  const { t } = useTranslation();
  const { token } = theme.useToken();
  const { isMobile } = useResponsive();
  const [expandedDays, setExpandedDays] = useState<string[]>([dayjs().format('YYYY-MM-DD')]);
  
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

  const renderLessonItem = (lesson: Lesson) => {
    const lessonTime = dayjs(lesson.scheduled_at);
    const statusColor = STATUS_COLORS[lesson.status];

    return (
      <div
        key={lesson.id}
        onClick={() => onLessonClick(lesson)}
        style={{
          cursor: 'pointer',
          padding: spacing.sm,
          borderRadius: 4,
          border: `1px solid ${statusColor}`,
          background: `${statusColor}10`,
          transition: 'all 0.2s'
        }}
      >
        <div style={{ fontWeight: 'bold', fontSize: 14 }}>
          {lessonTime.format('HH:mm')}
        </div>
        {lesson.duration_minutes && (
          <div style={{ fontSize: 12, color: token.colorTextSecondary, marginTop: 4 }}>
            {lesson.duration_minutes} {t('calendar.min')}
          </div>
        )}
      </div>
    );
  };

  // Mobile: Vertical list with expandable days
  if (isMobile) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
        {weekDays.map(day => {
          const dateKey = day.format('YYYY-MM-DD');
          const dayLessons = lessonsByDay[dateKey] || [];
          const isToday = day.isSame(dayjs(), 'day');
          const isExpanded = expandedDays.includes(dateKey);

          return (
            <Card
              key={dateKey}
              size="small"
              style={{
                background: isToday ? token.colorPrimaryBg : token.colorBgContainer,
              }}
            >
              <div
                onClick={() => {
                  setExpandedDays(prev =>
                    prev.includes(dateKey)
                      ? prev.filter(d => d !== dateKey)
                      : [...prev, dateKey]
                  );
                }}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  cursor: 'pointer',
                  padding: `${spacing.xs}px 0`,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
                  <div style={{
                    fontSize: 16,
                    fontWeight: isToday ? 'bold' : 'normal',
                    color: isToday ? token.colorPrimary : 'inherit',
                  }}>
                    {day.format('ddd, D MMM')}
                  </div>
                  {dayLessons.length > 0 && (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      ({dayLessons.length} {dayLessons.length === 1 ? t('calendar.lesson') : t('calendar.lessons')})
                    </Text>
                  )}
                </div>
                {isExpanded ? <DownOutlined /> : <RightOutlined />}
              </div>

              {isExpanded && (
                <div style={{ marginTop: spacing.sm }}>
                  {dayLessons.length === 0 ? (
                    <Text type="secondary" style={{ fontSize: 12 }}>{t('pages.lessons.noLessons')}</Text>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
                      {dayLessons.map(renderLessonItem)}
                    </div>
                  )}
                </div>
              )}
            </Card>
          );
        })}
      </div>
    );
  }

  // Desktop: 7-column grid
  return (
    <div style={{ 
      display: 'grid', 
      gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', 
      gap: 8
    }}>
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
              background: isToday ? token.colorPrimaryBg : token.colorBgContainer
            }}
          >
            {dayLessons.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '20px 0', color: '#999' }}>
                <Text type="secondary" style={{ fontSize: 12 }}>{t('pages.lessons.noLessons')}</Text>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {dayLessons.map(renderLessonItem)}
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
};

export default WeekView;
