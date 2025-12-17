import React, { useMemo } from 'react';
import { Modal, Button, Typography, Empty, Space } from 'antd';
import {
  PlusOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import { useTranslation } from 'react-i18next';
import type { Lesson } from './calendar-types';
import { statusColors, DEFAULT_DURATION } from './calendar-types';
import { useResponsive } from '../../hooks/useResponsive';
import { useTheme } from '../../theme/ThemeProvider';
import { spacing } from '../../theme/tokens';

const { Text, Title } = Typography;

interface DayLessonsModalProps {
  open: boolean;
  date: Dayjs | null;
  lessons: Lesson[];
  timezone: string;
  onClose: () => void;
  onLessonClick: (lessonId: number) => void;
  onAddLesson?: (date: string) => void;
  onReschedule?: (lessonId: number) => void;
  onComplete?: (lessonId: number) => void;
  onCancel?: (lessonId: number) => void;
  onDelete?: (lessonId: number) => void;
}

const DayLessonsModal: React.FC<DayLessonsModalProps> = ({
  open,
  date,
  lessons,
  timezone,
  onClose,
  onLessonClick,
  onAddLesson,
  onReschedule,
  onComplete,
  onCancel,
  onDelete,
}) => {
  const { t } = useTranslation();
  const { isMobile } = useResponsive();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme.colorScheme === 'dark';

  // Sort lessons by time
  const sortedLessons = useMemo(() => {
    return [...lessons].sort((a, b) => 
      dayjs(a.scheduled_at).valueOf() - dayjs(b.scheduled_at).valueOf()
    );
  }, [lessons]);

  // Format title
  const title = date ? date.format('dddd, D MMMM YYYY') : '';

  // Calculate total duration
  const totalMinutes = useMemo(() => {
    return lessons.reduce((sum, l) => sum + (l.duration_minutes || DEFAULT_DURATION), 0);
  }, [lessons]);

  const handleAddLesson = () => {
    if (onAddLesson && date) {
      onAddLesson(date.format('YYYY-MM-DD'));
      onClose();
    }
  };

  const renderLessonItem = (lesson: Lesson) => {
    const colors = statusColors[lesson.status];
    const time = dayjs(lesson.scheduled_at).tz(timezone);
    const duration = lesson.duration_minutes || DEFAULT_DURATION;
    const endTime = time.add(duration, 'minute');
    const statusLabel = t(`calendar.status.${lesson.status}`);

    return (
      <div
        key={lesson.id}
        onClick={() => {
          onLessonClick(lesson.id);
          onClose();
        }}
        style={{
          background: isDark ? colors.bgDark : colors.bg,
          borderLeft: `4px solid ${colors.border}`,
          borderRadius: 8,
          padding: spacing.sm,
          marginBottom: spacing.sm,
          cursor: 'pointer',
        }}
      >
        {/* Time and status row */}
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          marginBottom: spacing.xs,
        }}>
          <div>
            <Text strong style={{ fontSize: 16, color: isDark ? '#fff' : colors.text }}>
              {time.format('HH:mm')} – {endTime.format('HH:mm')}
            </Text>
            {lesson.learner_name && (
              <Text style={{ fontSize: 14, marginLeft: 8, color: isDark ? 'rgba(255,255,255,0.65)' : 'rgba(0,0,0,0.65)' }}>
                {lesson.learner_name}
              </Text>
            )}
          </div>
          <Text 
            style={{ 
              fontSize: 12, 
              color: colors.text,
              background: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.05)',
              padding: '2px 8px',
              borderRadius: 4,
            }}
          >
            {statusLabel}
          </Text>
        </div>

        {/* Duration */}
        <Text type="secondary" style={{ fontSize: 13, display: 'block', marginBottom: spacing.sm }}>
          {duration} {t('calendar.min')}
        </Text>

        {/* Action buttons - only show if any action callback is provided */}
        {(onReschedule || onComplete || onCancel || onDelete) && (
          <Space size="small" wrap>
            {onReschedule && (
              <Button
                size="small"
                icon={<CalendarOutlined />}
                onClick={(e) => {
                  e.stopPropagation();
                  onReschedule(lesson.id);
                  onClose();
                }}
              >
                {t('calendar.reschedule')}
              </Button>
            )}
            {onComplete && lesson.status !== 'completed' && (
              <Button
                size="small"
                icon={<CheckCircleOutlined />}
                onClick={(e) => {
                  e.stopPropagation();
                  onComplete(lesson.id);
                  onClose();
                }}
              >
                {t('calendar.complete')}
              </Button>
            )}
            {onCancel && lesson.status !== 'cancelled' && (
              <Button
                size="small"
                icon={<CloseCircleOutlined />}
                onClick={(e) => {
                  e.stopPropagation();
                  onCancel(lesson.id);
                  onClose();
                }}
              >
                {t('calendar.cancel')}
              </Button>
            )}
            {onDelete && (
              <Button
                size="small"
                danger
                icon={<DeleteOutlined />}
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(lesson.id);
                  onClose();
                }}
              >
                {t('common.delete')}
              </Button>
            )}
          </Space>
        )}
      </div>
    );
  };

  return (
    <Modal
      open={open}
      title={
        <div>
          <Title level={5} style={{ margin: 0 }}>{title}</Title>
          {lessons.length > 0 && (
            <Text type="secondary" style={{ fontSize: 13 }}>
              {lessons.length} {lessons.length === 1 ? t('calendar.lesson') : t('calendar.lessons')} • {Math.round(totalMinutes / 60 * 10) / 10}{t('calendar.hours')}
            </Text>
          )}
        </div>
      }
      onCancel={onClose}
      footer={
        onAddLesson ? (
          <Button 
            type="primary" 
            icon={<PlusOutlined />} 
            onClick={handleAddLesson}
            block={isMobile}
          >
            {t('calendar.addLesson')}
          </Button>
        ) : null
      }
      width={isMobile ? '100%' : 480}
      style={isMobile ? { top: 20 } : undefined}
    >
      {sortedLessons.length === 0 ? (
        <Empty 
          description={t('calendar.noLessonsToday')}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      ) : (
        <div style={{ maxHeight: 400, overflowY: 'auto' }}>
          {sortedLessons.map(renderLessonItem)}
        </div>
      )}
    </Modal>
  );
};

export default DayLessonsModal;
