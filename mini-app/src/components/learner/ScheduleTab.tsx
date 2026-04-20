import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card,
  Button,
  List,
  Space,
  Typography,
  message,
  Spin,
  Form,
  TimePicker,
  InputNumber,
  Checkbox,
  Row,
  Col,
  Alert,
} from 'antd';
import { PlusOutlined, DeleteOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import api from '../../services/api';
import EmptyState from '../common/EmptyState';
import { useTheme } from '../../theme/ThemeProvider';
import { spacing } from '../../theme/tokens';
import { useAuth } from '../../auth/AuthProvider';

const { Text } = Typography;

interface ScheduleSlot {
  day: number;
  time: string;
  duration: number;
}

interface ScheduleData {
  learner_id: number;
  slots: ScheduleSlot[];
  timezone: string;
}

interface ScheduleTabProps {
  learnerId: number;
}

const DAYS = [
  { value: 0, labelKey: 'schedule.days.mon' },
  { value: 1, labelKey: 'schedule.days.tue' },
  { value: 2, labelKey: 'schedule.days.wed' },
  { value: 3, labelKey: 'schedule.days.thu' },
  { value: 4, labelKey: 'schedule.days.fri' },
  { value: 5, labelKey: 'schedule.days.sat' },
  { value: 6, labelKey: 'schedule.days.sun' },
];

const ScheduleTab: React.FC<ScheduleTabProps> = ({ learnerId }) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { resolvedTheme } = useTheme();
  const { tenantAccess } = useAuth();
  const colors = resolvedTheme.colors;
  const canUseFullActions = !tenantAccess || tenantAccess.mode === 'full' || tenantAccess.bypass_access_restrictions;
  const [form] = Form.useForm();
  const [showForm, setShowForm] = useState(false);

  // Fetch schedule
  const { data: schedule, isLoading } = useQuery<ScheduleData>({
    queryKey: ['learnerSchedule', learnerId],
    queryFn: async () => {
      const { data } = await api.get(`/learners/${learnerId}/schedule`);
      return data;
    },
  });

  // Add slots mutation
  const addSlotsMutation = useMutation({
    mutationFn: async (values: { days: number[]; time: string; duration: number }) => {
      const { data } = await api.post(`/learners/${learnerId}/schedule/slots`, values);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learnerSchedule', learnerId] });
      message.success(t('schedule.slotAdded'));
      form.resetFields();
      setShowForm(false);
    },
    onError: (err: Error) => {
      message.error(t('errors.createFailed', { message: err.message }));
    },
  });

  // Delete slot mutation
  const deleteSlotMutation = useMutation({
    mutationFn: async (slotIndex: number) => {
      const { data } = await api.delete(`/learners/${learnerId}/schedule/slots/${slotIndex}`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learnerSchedule', learnerId] });
      message.success(t('schedule.slotDeleted'));
    },
    onError: (err: Error) => {
      message.error(t('errors.deleteFailed', { message: err.message }));
    },
  });

  const handleAddSlots = async () => {
    if (!canUseFullActions) {
      message.warning('Изменение шаблона расписания недоступно в grace-периоде.');
      return;
    }
    try {
      const values = await form.validateFields();
      const timeStr = values.time.format('HH:mm');
      await addSlotsMutation.mutateAsync({
        days: values.days,
        time: timeStr,
        duration: values.duration,
      });
    } catch (error) {
      // Validation error
    }
  };

  const getDayLabel = (day: number): string => {
    const dayInfo = DAYS.find((d) => d.value === day);
    return dayInfo ? t(dayInfo.labelKey) : '';
  };

  const formatSlot = (slot: ScheduleSlot): string => {
    return `${getDayLabel(slot.day)} — ${slot.time} (${slot.duration} ${t('schedule.min')})`;
  };

  const cardStyle = {
    background: colors.bgSecondary,
    borderColor: colors.borderPrimary,
    marginBottom: spacing.md,
  };

  if (isLoading) {
    return <Spin style={{ display: 'block', margin: '40px auto' }} />;
  }

  const slots = schedule?.slots || [];

  return (
    <div>
      {!canUseFullActions && (
        <Alert
          type="warning"
          showIcon
          message="Grace-период"
          description="Шаблон расписания временно нельзя менять. Переносите уже созданные уроки на странице занятий."
          style={{ marginBottom: spacing.md }}
        />
      )}

      <Alert
        type="info"
        showIcon
        message={t('schedule.templateInfoTitle')}
        description={t('schedule.templateInfoDescription')}
        style={{ marginBottom: spacing.md }}
      />

      {/* Current Schedule */}
      <Card style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.md }}>
          <Text strong>{t('schedule.currentSchedule')}</Text>
          {!showForm && (
            <Button
              type="primary"
              icon={<PlusOutlined />}
              disabled={!canUseFullActions}
              onClick={() => setShowForm(true)}
              size="small"
            >
              {t('schedule.addSlot')}
            </Button>
          )}
        </div>

        {slots.length === 0 && !showForm ? (
          <EmptyState
            title={t('schedule.noSlots')}
            description={t('schedule.noSlotsDescription')}
            actionText={canUseFullActions ? t('schedule.addSlot') : undefined}
            onAction={canUseFullActions ? () => setShowForm(true) : undefined}
          />
        ) : (
          <List
            dataSource={slots}
            renderItem={(slot, index) => (
              <List.Item
                style={{
                  padding: `${spacing.sm}px ${spacing.md}px`,
                  background: colors.bgPrimary,
                  borderRadius: 8,
                  marginBottom: spacing.xs,
                }}
                actions={[
                  <Button
                    key="delete"
                    type="text"
                    danger
                    icon={<DeleteOutlined />}
                    disabled={!canUseFullActions}
                    onClick={() => deleteSlotMutation.mutate(index)}
                    loading={deleteSlotMutation.isPending}
                  />,
                ]}
              >
                <Space>
                  <ClockCircleOutlined style={{ color: colors.accentPrimary }} />
                  <Text>{formatSlot(slot)}</Text>
                </Space>
              </List.Item>
            )}
          />
        )}
      </Card>

      {/* Add Slot Form */}
      {showForm && (
        <Card style={cardStyle} title={t('schedule.addSlotTitle')}>
          <Form
            form={form}
            layout="vertical"
            initialValues={{ duration: 60 }}
          >
            <Form.Item
              name="days"
              label={t('schedule.selectDays')}
              rules={[{ required: true, message: t('schedule.daysRequired') }]}
            >
              <Checkbox.Group style={{ width: '100%' }}>
                <Row gutter={[8, 8]}>
                  {DAYS.map((day) => (
                    <Col key={day.value} xs={12} sm={8} md={6}>
                      <Checkbox value={day.value}>{t(day.labelKey)}</Checkbox>
                    </Col>
                  ))}
                </Row>
              </Checkbox.Group>
            </Form.Item>

            <Row gutter={16}>
              <Col xs={12}>
                <Form.Item
                  name="time"
                  label={t('schedule.time')}
                  rules={[{ required: true, message: t('schedule.timeRequired') }]}
                >
                  <TimePicker
                    format="HH:mm"
                    minuteStep={5}
                    style={{ width: '100%' }}
                    placeholder={t('schedule.timePlaceholder')}
                  />
                </Form.Item>
              </Col>
              <Col xs={12}>
                <Form.Item
                  name="duration"
                  label={t('schedule.duration')}
                  rules={[
                    { required: true, message: t('schedule.durationRequired') },
                    { type: 'number', min: 15, max: 480, message: t('schedule.durationInvalid') },
                  ]}
                >
                  <InputNumber
                    min={15}
                    max={480}
                    step={15}
                    style={{ width: '100%' }}
                    addonAfter={t('schedule.min')}
                  />
                </Form.Item>
              </Col>
            </Row>

            <Space>
              <Button
                type="primary"
                onClick={handleAddSlots}
                loading={addSlotsMutation.isPending}
              >
                {t('common.add')}
              </Button>
              <Button onClick={() => { setShowForm(false); form.resetFields(); }}>
                {t('common.cancel')}
              </Button>
            </Space>
          </Form>
        </Card>
      )}
    </div>
  );
};

export default ScheduleTab;
