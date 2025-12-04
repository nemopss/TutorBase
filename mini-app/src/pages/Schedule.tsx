import React, { useState } from 'react';
import { Segmented, Spin, Alert, Typography } from 'antd';
import { CalendarOutlined, UnorderedListOutlined, AppstoreOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import dayjs, { Dayjs } from 'dayjs';
import api from '../services/api';
import MonthCalendar from '../components/schedule/MonthCalendar';
import WeekView from '../components/schedule/WeekView';
import ListView from '../components/schedule/ListView';
import LessonDrawer from '../components/schedule/LessonDrawer';
import type { Lesson, ViewMode } from '../components/schedule/types';

const { Title } = Typography;

const Schedule: React.FC = () => {
  const [viewMode, setViewMode] = useState<ViewMode>('month');
  const [selectedLesson, setSelectedLesson] = useState<Lesson | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [currentDate] = useState<Dayjs>(dayjs());

  // Fetch all lessons for student
  const { data: lessonsData, isLoading, error } = useQuery({
    queryKey: ['lessons', 'schedule'],
    queryFn: async () => {
      const { data } = await api.get<{ items: Lesson[], total: number }>('/lessons', {
        params: { 
          limit: 100, // Max allowed by API validation
          sort_by: 'scheduled_at',
          sort_order: 'asc'
        }
      });
      return data;
    },
  });

  const lessons = lessonsData?.items || [];

  const handleLessonClick = (lesson: Lesson) => {
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
          message="Ошибка загрузки"
          description="Не удалось загрузить расписание. Попробуйте обновить страницу."
          type="error"
          showIcon
        />
      </div>
    );
  }

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={2} style={{ margin: 0 }}>
          Расписание
        </Title>
        
        <Segmented
          value={viewMode}
          onChange={(value) => setViewMode(value as ViewMode)}
          options={[
            {
              label: 'Месяц',
              value: 'month',
              icon: <CalendarOutlined />,
            },
            {
              label: 'Неделя',
              value: 'week',
              icon: <AppstoreOutlined />,
            },
            {
              label: 'Список',
              value: 'list',
              icon: <UnorderedListOutlined />,
            },
          ]}
        />
      </div>

      {viewMode === 'month' && (
        <MonthCalendar 
          lessons={lessons} 
          onLessonClick={handleLessonClick}
        />
      )}

      {viewMode === 'week' && (
        <WeekView 
          lessons={lessons}
          currentDate={currentDate}
          onLessonClick={handleLessonClick}
        />
      )}

      {viewMode === 'list' && (
        <ListView 
          lessons={lessons}
          onLessonClick={handleLessonClick}
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
