import React, { useState } from 'react';
import { Tag, Typography, Dropdown, Button } from 'antd';
import type { MenuProps } from 'antd';
import {
  MoreOutlined,
  ClockCircleOutlined,
  CalendarOutlined,
  CheckOutlined,
  CloseOutlined,
  DeleteOutlined,
  VideoCameraOutlined,
  BookOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import { useTranslation } from 'react-i18next';
import { useThemeMode } from '../../theme/ThemeProvider';
import { spacing } from '../../theme/tokens';

dayjs.extend(utc);
dayjs.extend(timezone);

const { Text } = Typography;

type LessonStatus = 'scheduled' | 'rescheduled' | 'completed' | 'cancelled';

interface Lesson {
  id: number;
  scheduled_at: string;
  status: LessonStatus;
  duration_minutes?: number;
  // Future fields
  meeting_link?: string;
  topic?: string;
  notes?: string;
}

interface LessonCardProps {
  lesson: Lesson;
  timezone: string;
  onReschedule: (lessonId: number) => void;
  onComplete: (lessonId: number) => void;
  onCancel: (lessonId: number) => void;
  onDelete: (lessonId: number) => void;
  onClick?: (lessonId: number) => void;
}

/** Status colors */
const statusColors: Record<LessonStatus, { bg: string; bgDark: string; border: string; tag: string }> = {
  scheduled: {
    bg: 'rgba(24, 144, 255, 0.08)',
    bgDark: 'rgba(24, 144, 255, 0.15)',
    border: 'rgba(24, 144, 255, 0.3)',
    tag: 'blue',
  },
  rescheduled: {
    bg: 'rgba(250, 173, 20, 0.08)',
    bgDark: 'rgba(250, 173, 20, 0.15)',
    border: 'rgba(250, 173, 20, 0.3)',
    tag: 'gold',
  },
  completed: {
    bg: 'rgba(82, 196, 26, 0.08)',
    bgDark: 'rgba(82, 196, 26, 0.15)',
    border: 'rgba(82, 196, 26, 0.3)',
    tag: 'green',
  },
  cancelled: {
    bg: 'rgba(255, 77, 79, 0.08)',
    bgDark: 'rgba(255, 77, 79, 0.15)',
    border: 'rgba(255, 77, 79, 0.3)',
    tag: 'red',
  },
};

/**
 * Lesson card with colored background indicating status.
 * Designed for future expansion (location, meeting links, topics, etc.)
 */
const LessonCard: React.FC<LessonCardProps> = ({
  lesson,
  timezone: tz,
  onReschedule,
  onComplete,
  onCancel,
  onDelete,
  onClick,
}) => {
  const { t } = useTranslation();
  const { resolvedTheme } = useThemeMode();
  const isDark = resolvedTheme === 'dark';
  const [isHovered, setIsHovered] = useState(false);

  const colors = statusColors[lesson.status];
  const date = dayjs(lesson.scheduled_at).tz(tz);
  const endTime = lesson.duration_minutes 
    ? date.add(lesson.duration_minutes, 'minute') 
    : null;

  const menuItems: MenuProps['items'] = [
    {
      key: 'reschedule',
      icon: <CalendarOutlined />,
      label: t('pages.lessons.reschedule'),
      onClick: (e) => {
        e.domEvent.stopPropagation();
        onReschedule(lesson.id);
      },
    },
    {
      key: 'complete',
      icon: <CheckOutlined />,
      label: t('pages.lessons.markCompleted'),
      onClick: (e) => {
        e.domEvent.stopPropagation();
        onComplete(lesson.id);
      },
    },
    {
      key: 'cancel',
      icon: <CloseOutlined />,
      label: t('common.cancel'),
      onClick: (e) => {
        e.domEvent.stopPropagation();
        onCancel(lesson.id);
      },
    },
    { type: 'divider' },
    {
      key: 'delete',
      icon: <DeleteOutlined />,
      label: t('common.delete'),
      danger: true,
      onClick: (e) => {
        e.domEvent.stopPropagation();
        onDelete(lesson.id);
      },
    },
  ];

  const handleCardClick = () => {
    if (onClick) {
      onClick(lesson.id);
    }
  };

  // Check if we have any extra info to show
  const hasExtraInfo = lesson.meeting_link || lesson.topic;

  return (
    <div
      onClick={handleCardClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        background: isDark ? colors.bgDark : colors.bg,
        border: `1px solid ${colors.border}`,
        borderRadius: 12,
        padding: spacing.md,
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        transform: isHovered ? 'translateY(-2px)' : 'translateY(0)',
        boxShadow: isHovered 
          ? (isDark ? '0 4px 12px rgba(0,0,0,0.3)' : '0 4px 12px rgba(0,0,0,0.1)')
          : 'none',
      }}
    >
      {/* Header row: Date + Status + Menu */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'flex-start',
        marginBottom: spacing.xs,
      }}>
        <div style={{ flex: 1 }}>
          <Text strong style={{ fontSize: 15, display: 'block' }}>
            {date.format('ddd, MMM D, YYYY')}
          </Text>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: spacing.xs }}>
          <Tag color={colors.tag} style={{ margin: 0 }}>
            {t(`pages.lessons.status.${lesson.status}`)}
          </Tag>
          <Dropdown menu={{ items: menuItems }} trigger={['click']} placement="bottomRight">
            <Button
              type="text"
              icon={<MoreOutlined />}
              size="small"
              onClick={(e) => e.stopPropagation()}
              style={{ 
                color: isDark ? 'rgba(255,255,255,0.65)' : 'rgba(0,0,0,0.45)',
              }}
            />
          </Dropdown>
        </div>
      </div>

      {/* Time row */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: spacing.xs,
        marginBottom: hasExtraInfo ? spacing.xs : 0,
      }}>
        <ClockCircleOutlined style={{ fontSize: 14, color: isDark ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.45)' }} />
        <Text type="secondary" style={{ fontSize: 14 }}>
          {date.format('HH:mm')}
          {endTime && ` – ${endTime.format('HH:mm')}`}
          {lesson.duration_minutes && ` (${lesson.duration_minutes} ${t('pages.lessons.minutes')})`}
        </Text>
      </div>

      {/* Extra info row: Topic, Location, Meeting link */}
      {hasExtraInfo && (
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: spacing.md,
          flexWrap: 'wrap',
        }}>
          {lesson.topic && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <BookOutlined style={{ fontSize: 13, color: isDark ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.45)' }} />
              <Text type="secondary" style={{ fontSize: 13 }}>{lesson.topic}</Text>
            </div>
          )}

          {lesson.meeting_link && (
            <a 
              href={lesson.meeting_link} 
              target="_blank" 
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 13 }}
            >
              <VideoCameraOutlined />
              {t('lessonCard.join')}
            </a>
          )}
        </div>
      )}
    </div>
  );
};

export default LessonCard;
