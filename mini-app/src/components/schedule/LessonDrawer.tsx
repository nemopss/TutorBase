import React from 'react';
import { Drawer, Descriptions, Badge, Typography } from 'antd';
import dayjs from 'dayjs';
import { useTranslation } from 'react-i18next';
import type { Lesson } from './types';
import { STATUS_COLORS } from './types';
const { Title } = Typography;

interface LessonDrawerProps {
  lesson: Lesson | null;
  open: boolean;
  onClose: () => void;
}

const LessonDrawer: React.FC<LessonDrawerProps> = ({ lesson, open, onClose }) => {
  const { t } = useTranslation();
  
  if (!lesson) return null;

  const lessonDate = dayjs(lesson.scheduled_at);
  const statusColor = STATUS_COLORS[lesson.status];

  return (
    <Drawer
      title={t('lessonDrawer.title')}
      placement="right"
      onClose={onClose}
      open={open}
      width={400}
    >
      <Title level={4}>
        {lessonDate.format('D MMMM YYYY')}
      </Title>
      
      <Descriptions column={1} bordered>
        <Descriptions.Item label={t('lessonDrawer.time')}>
          {lessonDate.format('HH:mm')}
        </Descriptions.Item>
        
        <Descriptions.Item label={t('pages.lessons.duration')}>
          {lesson.duration_minutes} {t('pages.lessons.minutes')}
        </Descriptions.Item>
        
        <Descriptions.Item label={t('common.status')}>
          <Badge color={statusColor} text={t(`pages.lessons.status.${lesson.status}`)} />
        </Descriptions.Item>
      </Descriptions>
    </Drawer>
  );
};

export default LessonDrawer;
