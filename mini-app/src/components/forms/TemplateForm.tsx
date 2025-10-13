import React, { useEffect } from 'react';
import { Modal, Form, Input, InputNumber, Select, Button, Space, TimePicker } from 'antd';
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';

interface TemplateFormProps {
  open: boolean;
  onCancel: () => void;
  onFinish: (values: any) => void;
  isLoading: boolean;
  initialValues?: any;
}

const WEEKDAY_OPTIONS = [
  { label: 'Monday', value: 0 },
  { label: 'Tuesday', value: 1 },
  { label: 'Wednesday', value: 2 },
  { label: 'Thursday', value: 3 },
  { label: 'Friday', value: 4 },
  { label: 'Saturday', value: 5 },
  { label: 'Sunday', value: 6 },
];

const TemplateForm: React.FC<TemplateFormProps> = ({ open, onCancel, onFinish, isLoading, initialValues }) => {
  const [form] = Form.useForm();

  useEffect(() => {
    if (open) {
      if (initialValues) {
        const schedule = initialValues.default_config?.weekly_schedule || [];
        const formattedSchedule = schedule.map((item: any) => ({
          ...item,
          time: item.time ? dayjs(item.time, 'HH:mm') : null,
        }));
        form.setFieldsValue({ ...initialValues, weekly_schedule: formattedSchedule });
      } else {
        form.resetFields();
      }
    }
  }, [initialValues, form, open]);

  const isEditing = !!initialValues;

  const handleFinish = (values: any) => {
    const schedule = values.weekly_schedule?.map((item: any) => ({
      ...item,
      time: item.time ? item.time.format('HH:mm') : null,
    })) || [];
    const finalValues = {
      ...values,
      default_config: { weekly_schedule: schedule },
    };
    delete finalValues.weekly_schedule;
    onFinish(finalValues);
  };

  return (
    <Modal
      open={open}
      title={isEditing ? "Edit Template" : "Create New Template"}
      okText={isEditing ? "Save" : "Create"}
      cancelText="Cancel"
      onCancel={onCancel}
      onOk={() => form.validateFields().then(handleFinish).catch(info => {
        if (import.meta.env.DEV) {
          console.log('Validate Failed:', info);
        }
      })}
      confirmLoading={isLoading}
      destroyOnHidden
      width={600}
    >
      <Form form={form} layout="vertical" name="template_form" autoComplete="off">
        <Form.Item
          name="name"
          label="Template Name"
          rules={[{ required: true, message: 'Please enter the template name!' }]}
        >
          <Input />
        </Form.Item>
        <Form.Item name="description" label="Description">
          <Input.TextArea rows={2} />
        </Form.Item>
        <Form.Item name="lesson_count" label="Number of Lessons to Generate">
          <InputNumber min={1} style={{ width: '100%' }} />
        </Form.Item>

        <p>Weekly Schedule</p>
        <Form.List name="weekly_schedule">
          {(fields, { add, remove }) => (
            <>
              {fields.map(({ key, name, ...restField }) => (
                <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                  <Form.Item
                    {...restField}
                    name={[name, 'day']}
                    rules={[{ required: true, message: 'Missing day' }]}
                  >
                    <Select options={WEEKDAY_OPTIONS} placeholder="Day" style={{ width: 150 }} />
                  </Form.Item>
                  <Form.Item
                    {...restField}
                    name={[name, 'time']}
                    rules={[{ required: true, message: 'Missing time' }]}
                  >
                    <TimePicker format="HH:mm" />
                  </Form.Item>
                  <MinusCircleOutlined onClick={() => remove(name)} />
                </Space>
              ))}
              <Form.Item>
                <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
                  Add Schedule Rule
                </Button>
              </Form.Item>
            </>
          )}
        </Form.List>
      </Form>
    </Modal>
  );
};

export default TemplateForm;
