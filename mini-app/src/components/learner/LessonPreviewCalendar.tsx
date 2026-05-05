import React, { useState, useMemo } from 'react';
import { Card, Button, Typography, Modal, Form, TimePicker, InputNumber, Space } from 'antd';
import { LeftOutlined, RightOutlined, DeleteOutlined } from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';
import { useTranslation } from 'react-i18next';
import { useTheme } from '../../theme/ThemeProvider';
import { spacing } from '../../theme/tokens';

const { Text } = Typography;

interface PreviewDate {
  datetime: string;
  duration: number;
}

interface LessonPreviewCalendarProps {
  dates: PreviewDate[];
  onDatesChange: (dates: PreviewDate[]) => void;
  startDate: Dayjs;
  scheduleSlots?: PreviewScheduleSlot[];
}

const WEEKDAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];

interface PreviewScheduleSlot {
  day: number;
  time: string;
  duration: number;
}

interface EditingLessonState {
  day: Dayjs;
  dateIndex: number | null;
}

const LessonPreviewCalendar: React.FC<LessonPreviewCalendarProps> = ({
  dates,
  onDatesChange,
  startDate,
  scheduleSlots = [],
}) => {
  const { t } = useTranslation();
  const { resolvedTheme } = useTheme();
  const colors = resolvedTheme.colors;
  const [form] = Form.useForm();
  
  const [currentMonth, setCurrentMonth] = useState(() => startDate.startOf('month'));
  const [editingLesson, setEditingLesson] = useState<EditingLessonState | null>(null);

  // Get all days in the current month view
  const calendarDays = useMemo(() => {
    const start = currentMonth.startOf('month').startOf('week');
    const end = currentMonth.endOf('month').endOf('week');
    const days: Dayjs[] = [];
    let day = start;
    while (day.isBefore(end) || day.isSame(end, 'day')) {
      days.push(day);
      day = day.add(1, 'day');
    }
    return days;
  }, [currentMonth]);

  // Map dates to day strings for quick lookup
  const dateMap = useMemo(() => {
    const map = new Map<string, Array<{ date: PreviewDate; index: number }>>();
    dates.forEach((d, index) => {
      const key = dayjs(d.datetime).format('YYYY-MM-DD');
      const items = map.get(key) ?? [];
      items.push({ date: d, index });
      map.set(key, items);
    });
    return map;
  }, [dates]);

  const getDefaultValuesForDay = (day: Dayjs) => {
    const scheduleDay = (day.day() + 6) % 7;
    const sameDaySlot = scheduleSlots.find((slot) => slot.day === scheduleDay);
    const fallbackSlot = scheduleSlots[0];
    const slot = sameDaySlot ?? fallbackSlot;
    const [hours, minutes] = (slot?.time ?? '12:00').split(':').map(Number);

    return {
      time: dayjs().hour(hours).minute(minutes).second(0).millisecond(0),
      duration: slot?.duration ?? 60,
    };
  };

  const handleDayClick = (day: Dayjs) => {
    const key = day.format('YYYY-MM-DD');
    const existing = dateMap.get(key)?.[0];

    if (existing) {
      const existingDate = dayjs(existing.date.datetime);
      form.setFieldsValue({
        time: existingDate,
        duration: existing.date.duration,
      });
      setEditingLesson({ day, dateIndex: existing.index });
    } else {
      form.setFieldsValue(getDefaultValuesForDay(day));
      setEditingLesson({ day, dateIndex: null });
    }
  };

  const closeEditor = () => {
    setEditingLesson(null);
    form.resetFields();
  };

  const handleSaveLesson = async () => {
    if (!editingLesson) {
      return;
    }

    const values = await form.validateFields();
    const lessonDate = editingLesson.day
      .hour(values.time.hour())
      .minute(values.time.minute())
      .second(0)
      .millisecond(0);
    const nextDate: PreviewDate = {
      datetime: lessonDate.toISOString(),
      duration: values.duration,
    };

    const nextDates =
      editingLesson.dateIndex === null
        ? [...dates, nextDate]
        : dates.map((date, index) => (index === editingLesson.dateIndex ? nextDate : date));

    onDatesChange(nextDates.sort((a, b) => dayjs(a.datetime).valueOf() - dayjs(b.datetime).valueOf()));
    closeEditor();
  };

  const handleDeleteLesson = () => {
    if (!editingLesson || editingLesson.dateIndex === null) {
      return;
    }

    onDatesChange(dates.filter((_, index) => index !== editingLesson.dateIndex));
    closeEditor();
  };

  const isCurrentMonth = (day: Dayjs) => day.month() === currentMonth.month();
  const isToday = (day: Dayjs) => day.isSame(dayjs(), 'day');
  const getLessonsForDay = (day: Dayjs) => dateMap.get(day.format('YYYY-MM-DD')) ?? [];

  return (
    <>
      <Card
        style={{
          background: colors.bgSecondary,
          borderColor: colors.borderPrimary,
        }}
      >
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          marginBottom: spacing.md,
        }}>
          <Button 
            type="text" 
            icon={<LeftOutlined />} 
            onClick={() => setCurrentMonth(currentMonth.subtract(1, 'month'))}
          />
          <Text strong style={{ fontSize: 16 }}>
            {currentMonth.format('MMMM YYYY')}
          </Text>
          <Button 
            type="text" 
            icon={<RightOutlined />} 
            onClick={() => setCurrentMonth(currentMonth.add(1, 'month'))}
          />
        </div>

        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(7, minmax(0, 1fr))',
          gap: 4,
          marginBottom: spacing.xs,
        }}>
          {WEEKDAYS.map((day) => (
            <div 
              key={day} 
              style={{ 
                textAlign: 'center', 
                padding: spacing.xs,
                color: colors.textSecondary,
                fontSize: 12,
              }}
            >
              {t(`schedule.daysShort.${day}`)}
            </div>
          ))}
        </div>

        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(7, minmax(0, 1fr))',
          gap: 4,
        }}>
          {calendarDays.map((day) => {
            const inMonth = isCurrentMonth(day);
            const today = isToday(day);
            const lessons = getLessonsForDay(day);
            const hasLesson = lessons.length > 0;
            const lessonLabel = lessons.length > 1
              ? t('schedulePreview.multipleLessons', { count: lessons.length })
              : lessons[0]
                ? dayjs(lessons[0].date.datetime).format('HH:mm')
                : null;
            
            return (
              <button
                key={day.format('YYYY-MM-DD')}
                type="button"
                onClick={() => handleDayClick(day)}
                style={{
                  aspectRatio: '1',
                  minWidth: 0,
                  borderRadius: 8,
                  cursor: 'pointer',
                  background: today && !hasLesson ? colors.bgTertiary : 'transparent',
                  color: inMonth ? colors.textPrimary : colors.textTertiary,
                  fontWeight: today || hasLesson ? 600 : 400,
                  fontSize: 13,
                  transition: 'all 0.2s',
                  border: hasLesson
                    ? `2px solid ${colors.accentPrimary}`
                    : today
                      ? `1px solid ${colors.accentPrimary}`
                      : `1px solid ${colors.borderPrimary}`,
                  padding: 4,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 2,
                }}
              >
                <span>{day.date()}</span>
                {lessonLabel && (
                  <span style={{ color: colors.accentPrimary, fontSize: 11, lineHeight: 1.1 }}>
                    {lessonLabel}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        <div style={{ 
          marginTop: spacing.md, 
          textAlign: 'center',
          color: colors.textSecondary,
        }}>
          <Text>
            {dates.length} {t('calendar.lessons')} • {t('schedulePreview.clickToEdit')}
          </Text>
        </div>
      </Card>

      <Modal
        open={!!editingLesson}
        title={editingLesson?.dateIndex === null ? t('schedulePreview.addLesson') : t('schedulePreview.editLesson')}
        onCancel={closeEditor}
        onOk={handleSaveLesson}
        okText={t('common.save')}
        cancelText={t('common.cancel')}
        footer={(_, { OkBtn, CancelBtn }) => (
          <Space style={{ width: '100%', justifyContent: editingLesson?.dateIndex === null ? 'flex-end' : 'space-between' }}>
            {editingLesson?.dateIndex !== null && (
              <Button danger icon={<DeleteOutlined />} onClick={handleDeleteLesson}>
                {t('common.delete')}
              </Button>
            )}
            <Space>
              <CancelBtn />
              <OkBtn />
            </Space>
          </Space>
        )}
      >
        <Form form={form} layout="vertical" initialValues={{ duration: 60 }}>
          <Text type="secondary" style={{ display: 'block', marginBottom: spacing.md }}>
            {editingLesson?.day.format('D MMMM YYYY')}
          </Text>
          <Form.Item
            name="time"
            label={t('schedule.time')}
            rules={[{ required: true, message: t('schedule.timeRequired') }]}
          >
            <TimePicker format="HH:mm" minuteStep={5} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item
            name="duration"
            label={t('schedule.duration')}
            rules={[
              { required: true, message: t('schedule.durationRequired') },
              { type: 'number', min: 15, max: 480, message: t('schedule.durationInvalid') },
            ]}
          >
            <InputNumber min={15} max={480} step={15} style={{ width: '100%' }} addonAfter={t('schedule.min')} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default LessonPreviewCalendar;
