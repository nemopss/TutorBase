import React, { useState } from 'react';
import { Segmented, Spin, Alert, Typography } from 'antd';
import { CalendarOutlined, UnorderedListOutlined, AppstoreOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import MonthCalendar from '../components/common/MonthCalendar';
import WeekCalendar from '../components/common/WeekCalendar';
import ListView from '../components/schedule/ListView';
import LessonDrawer from '../components/schedule/LessonDrawer';
import type { Lesson as ScheduleLesson, ViewMode } from '../components/schedule/types';
import { DEFAULT_TIMEZONE } from '../utils/datetime';
import { fetchAllScheduleLessons } from '../services/scheduleLessons';

const { Title } = Typography;

const Schedule: React.FC = () => {
  const { t } = useTranslation();
  const [viewMode, setViewMode] = useState<ViewMode>('month');
  const [selectedLesson, setSelectedLesson] = useState<ScheduleLesson | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Fetch all lessons for student
  const { data: lessonsData, isLoading, error } = useQuery({
    queryKey: ['lessons', 'schedule'],
    queryFn: fetchAllScheduleLessons,
  });

  const lessons = lessonsData?.items || [];

  // Handler for common calendar components (receives lessonId)
  const handleLessonClickById = (lessonId: number) => {
    const lesson = lessons.find(l => l.id === lessonId);
    if (lesson) {
      // Convert to ScheduleLesson format for drawer
      setSelectedLesson({
        id: lesson.id,
        scheduled_at: lesson.scheduled_at,
        status: lesson.status === 'rescheduled' ? 'scheduled' : lesson.status,
        duration_minutes: lesson.duration_minutes || 60,
      });
      setDrawerOpen(true);
    }
  };

  // Handler for ListView (receives full lesson object)
  const handleLessonClickByObject = (lesson: ScheduleLesson) => {
    setSelectedLesson(lesson);
    setDrawerOpen(true);
  };

  const handleDrawerClose = () => {
    setDrawerOpen(false);
    setTimeout(() => setSelectedLesson(null), 300); // Delay to allow drawer close animation
  };

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '50px' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '24px' }}>
        <Alert
          message={t('errors.loadFailed', { message: '' })}
          description={t('errors.networkError')}
          type="error"
          showIcon
        />
      </div>
    );
  }

  return (
    <div style={{ padding: '16px' }}>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        marginBottom: 24,
        gap: 16,
        flexWrap: 'wrap'
      }}>
        <Title level={2} style={{ margin: 0 }}>
          {t('pages.schedule.title')}
        </Title>
        
        <Segmented
          value={viewMode}
          onChange={(value) => setViewMode(value as ViewMode)}
          options={[
            {
              label: t('pages.schedule.month'),
              value: 'month',
              icon: <CalendarOutlined />,
            },
            {
              label: t('pages.schedule.week'),
              value: 'week',
              icon: <AppstoreOutlined />,
            },
            {
              label: t('pages.schedule.list'),
              value: 'list',
              icon: <UnorderedListOutlined />,
            },
          ]}
        />
      </div>

      {viewMode === 'month' && (
        <MonthCalendar 
          lessons={lessons} 
          timezone={DEFAULT_TIMEZONE}
          onLessonClick={handleLessonClickById}
          // Read-only mode: no edit callbacks
        />
      )}

      {viewMode === 'week' && (
        <WeekCalendar 
          lessons={lessons}
          timezone={DEFAULT_TIMEZONE}
          onLessonClick={handleLessonClickById}
          // Read-only mode: no edit callbacks
        />
      )}

      {viewMode === 'list' && (
        <ListView 
          lessons={lessons.map(l => ({
            id: l.id,
            scheduled_at: l.scheduled_at,
            status: l.status === 'rescheduled' ? 'scheduled' : l.status,
            duration_minutes: l.duration_minutes || 60,
          }))}
          onLessonClick={handleLessonClickByObject}
        />
      )}

      <LessonDrawer
        lesson={selectedLesson}
        open={drawerOpen}
        onClose={handleDrawerClose}
      />
    </div>
  );
};

export default Schedule;
