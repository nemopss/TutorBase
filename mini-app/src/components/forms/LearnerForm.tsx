import React from 'react';
import { Form, Input, Switch, Space, Typography, Divider } from 'antd';
import { UserAddOutlined, BellOutlined } from '@ant-design/icons';
import ResponsiveModal from '../common/ResponsiveModal';

const { Text } = Typography;

interface LearnerFormProps {
  visible: boolean;
  onSubmit: (values: any) => Promise<void>;
  onCancel: () => void;
  loading?: boolean;
  initialValues?: {
    chat_id?: number;
    display_name?: string;
    notes?: string;
    notifications_enabled?: boolean;
  };
  mode?: 'create' | 'edit_notifications';
}

const LearnerForm: React.FC<LearnerFormProps> = ({
  visible,
  onSubmit,
  onCancel,
  loading = false,
  initialValues,
  mode = 'create',
}) => {
  const [form] = Form.useForm();

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      await onSubmit(values);
      form.resetFields();
    } catch (error) {
      console.error('Form validation failed:', error);
    }
  };

  const handleCancel = () => {
    form.resetFields();
    onCancel();
  };

  React.useEffect(() => {
    if (visible && initialValues) {
      form.setFieldsValue(initialValues);
    }
  }, [visible, initialValues, form]);

  return (
    <ResponsiveModal
      title={
        <Space>
          {mode === 'create' ? <UserAddOutlined /> : <BellOutlined />}
          <span>{mode === 'create' ? 'Add New Learner' : 'Manage Notifications'}</span>
        </Space>
      }
      open={visible}
      onOk={handleSubmit}
      onCancel={handleCancel}
      confirmLoading={loading}
      okText={mode === 'create' ? 'Create Learner' : 'Save'}
      cancelText="Cancel"
      width={500}
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={initialValues || { notifications_enabled: true }}
      >
        {mode === 'create' && (
          <>
            <Form.Item
              name="chat_id"
              label="Telegram Chat ID"
              rules={[
                { required: true, message: 'Please enter chat ID' },
                { 
                  pattern: /^-?\d+$/, 
                  message: 'Chat ID must be a number' 
                },
              ]}
              extra="Enter the learner's Telegram chat ID (numeric)"
            >
              <Input 
                placeholder="e.g., 123456789" 
                type="text"
              />
            </Form.Item>

            <Form.Item
              name="display_name"
              label="Display Name"
              rules={[
                { required: true, message: 'Please enter display name' },
                { min: 2, message: 'Name must be at least 2 characters' },
              ]}
            >
              <Input placeholder="e.g., John Doe" />
            </Form.Item>

            <Form.Item
              name="notes"
              label="Notes (Optional)"
            >
              <Input.TextArea 
                placeholder="Any additional information about this learner..."
                rows={3}
              />
            </Form.Item>

            <Divider />
          </>
        )}

        <Form.Item
          name="notifications_enabled"
          label="Enable Notifications"
          valuePropName="checked"
          extra={
            <Text type="secondary" style={{ fontSize: 12 }}>
              When disabled, this learner will not receive any lesson reminders or notifications via Telegram
            </Text>
          }
        >
          <Switch 
            checkedChildren="Enabled" 
            unCheckedChildren="Disabled"
          />
        </Form.Item>
      </Form>
    </ResponsiveModal>
  );
};

export default LearnerForm;
