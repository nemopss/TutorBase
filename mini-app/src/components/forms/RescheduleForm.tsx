import React from 'react';
import { Modal, Form, DatePicker, TimePicker, InputNumber, Typography } from 'antd';
import dayjs from 'dayjs';

const { Text } = Typography;

interface RescheduleFormProps {
  open: boolean;
  onCancel: () => void;
  onFinish: (values: { date: dayjs.Dayjs; time: dayjs.Dayjs; duration_minutes?: number }) => void;
  isLoading: boolean;
  currentDateTime?: string;
  currentDuration?: number;
}

/**
 * Modal form for rescheduling a lesson.
 * Pre-fills with current lesson date/time/duration.
 */
const RescheduleForm: React.FC<RescheduleFormProps> = ({
  open,
  onCancel,
  onFinish,
  isLoading,
  currentDateTime,
  currentDuration,
}) => {
  const [form] = Form.useForm();

  React.useEffect(() => {
    if (open) {
      const dt = currentDateTime ? dayjs(currentDateTime) : dayjs();
      form.setFieldsValue({
        date: dt,
        time: dt,
        duration_minutes: currentDuration || 60,
      });
    }
  }, [open, currentDateTime, currentDuration, form]);

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      onFinish(values);
    } catch {
      // Validation error
    }
  };

  return (
    <Modal
      title="Reschedule Lesson"
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      confirmLoading={isLoading}
      okText="Reschedule"
      cancelText="Cancel"
      destroyOnClose
    >
      {currentDateTime && (
        <div style={{ marginBottom: 16, padding: '8px 12px', background: 'rgba(0,0,0,0.02)', borderRadius: 8 }}>
          <Text type="secondary" style={{ fontSize: 13 }}>
            Current: {dayjs(currentDateTime).format('ddd, MMM D, YYYY • HH:mm')}
            {currentDuration && ` (${currentDuration} min)`}
          </Text>
        </div>
      )}
      <Form form={form} layout="vertical">
        <Form.Item
          name="date"
          label="New Date"
          rules={[{ required: true, message: 'Please select a date' }]}
        >
          <DatePicker style={{ width: '100%' }} format="DD.MM.YYYY" />
        </Form.Item>
        <Form.Item
          name="time"
          label="New Time"
          rules={[{ required: true, message: 'Please select a time' }]}
        >
          <TimePicker style={{ width: '100%' }} format="HH:mm" minuteStep={5} />
        </Form.Item>
        <Form.Item
          name="duration_minutes"
          label="Duration (minutes)"
          rules={[{ required: true, message: 'Please enter duration' }]}
        >
          <InputNumber 
            style={{ width: '100%' }} 
            min={15} 
            max={240} 
            step={15}
            placeholder="60"
          />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default RescheduleForm;
