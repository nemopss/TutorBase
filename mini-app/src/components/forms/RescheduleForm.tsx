import React from 'react';
import { Modal, Form, DatePicker, TimePicker } from 'antd';
import dayjs from 'dayjs';

interface RescheduleFormProps {
  open: boolean;
  onCancel: () => void;
  onFinish: (values: { date: dayjs.Dayjs; time: dayjs.Dayjs }) => void;
  isLoading: boolean;
  currentDateTime?: string;
}

/**
 * Modal form for rescheduling a lesson.
 * Pre-fills with current lesson date/time.
 */
const RescheduleForm: React.FC<RescheduleFormProps> = ({
  open,
  onCancel,
  onFinish,
  isLoading,
  currentDateTime,
}) => {
  const [form] = Form.useForm();

  React.useEffect(() => {
    if (open && currentDateTime) {
      const dt = dayjs(currentDateTime);
      form.setFieldsValue({
        date: dt,
        time: dt,
      });
    }
  }, [open, currentDateTime, form]);

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
    >
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
      </Form>
    </Modal>
  );
};

export default RescheduleForm;
