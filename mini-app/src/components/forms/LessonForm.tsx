import React, { useEffect } from 'react';
import { Modal, Form, DatePicker, InputNumber, Select, Input } from 'antd';
import dayjs from 'dayjs';

interface LessonFormProps {
  open: boolean;
  onCancel: () => void;
  onFinish: (values: any) => void;
  isLoading: boolean;
  initialValues?: any; // Объект с начальными значениями для редактирования
}

const { Option } = Select;

const LessonForm: React.FC<LessonFormProps> = ({ open, onCancel, onFinish, isLoading, initialValues }) => {
  const [form] = Form.useForm();

  useEffect(() => {
    if (initialValues) {
      form.setFieldsValue({
        ...initialValues,
        scheduled_at: initialValues.scheduled_at ? dayjs(initialValues.scheduled_at) : null,
      });
    } else {
      form.resetFields();
    }
  }, [initialValues, form, open]);

  const isEditing = !!initialValues;

  return (
    <Modal
      open={open}
      title={isEditing ? "Edit Lesson" : "Add New Lesson"}
      okText={isEditing ? "Save" : "Create"}
      cancelText="Cancel"
      onCancel={onCancel}
      onOk={() => {
        form
          .validateFields()
          .then((values) => {
            // Преобразуем scheduled_at в ISO string для backend
            const formattedValues = {
              ...values,
              scheduled_at: values.scheduled_at ? values.scheduled_at.toISOString() : undefined,
            };
            
            // Не сбрасываем поля при редактировании, чтобы не было моргания
            if (!isEditing) {
              form.resetFields();
            }
            onFinish(formattedValues);
          })
          .catch((info) => {
            console.log('Validate Failed:', info);
          });
      }}
      confirmLoading={isLoading}
      destroyOnClose // Сбрасывать состояние формы при закрытии, если не редактируем
    >
      <Form form={form} layout="vertical" name="lesson_form">
        <Form.Item
          name="scheduled_at"
          label="Scheduled At"
          rules={[{ required: true, message: 'Please select the date and time!' }]}
        >
          <DatePicker showTime format="YYYY-MM-DD HH:mm:ss" style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="duration_minutes" label="Duration (minutes)">
          <InputNumber min={1} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="status" label="Status" initialValue="scheduled">
          <Select>
            <Option value="scheduled">Scheduled</Option>
            <Option value="completed">Completed</Option>
            <Option value="cancelled">Cancelled</Option>
          </Select>
        </Form.Item>
        <Form.Item name="teacher_notes" label="Notes">
          <Input.TextArea rows={2} />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default LessonForm;
