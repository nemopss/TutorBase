import React from 'react';
import { Form, Input, InputNumber, Switch, Space, Typography, Divider } from 'antd';
import { UserAddOutlined, BellOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
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
    lesson_rate?: number;
  };
  mode?: 'create' | 'edit' | 'edit_notifications';
}

const LearnerForm: React.FC<LearnerFormProps> = ({
  visible,
  onSubmit,
  onCancel,
  loading = false,
  initialValues,
  mode = 'create',
}) => {
  const { t } = useTranslation();
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
          <span>
            {mode === 'create' 
              ? t('forms.learner.title') 
              : mode === 'edit' 
                ? t('forms.learner.editTitle')
                : t('forms.learner.notificationsTitle')
            }
          </span>
        </Space>
      }
      open={visible}
      onOk={handleSubmit}
      onCancel={handleCancel}
      confirmLoading={loading}
      okText={mode === 'create' ? t('forms.learner.createButton') : t('common.save')}
      destroyOnHidden
      cancelText={t('common.cancel')}
      width={500}
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={initialValues || { notifications_enabled: true }}
      >
        {/* Chat ID - only for create mode */}
        {mode === 'create' && (
          <Form.Item
            name="chat_id"
            label={t('forms.learner.chatIdLabel')}
            rules={[
              { 
                transform: (value) => value || undefined,
                pattern: /^-?\d+$/, 
                message: t('forms.learner.chatIdInvalid')
              },
            ]}
            extra={t('forms.learner.chatIdHelp')}
          >
            <Input 
              placeholder={t('forms.learner.chatIdPlaceholder')} 
              type="text"
            />
          </Form.Item>
        )}

        {/* Display name, notes, lesson rate - for create and edit modes */}
        {(mode === 'create' || mode === 'edit') && (
          <>
            <Form.Item
              name="display_name"
              label={t('forms.learner.displayNameLabel')}
              rules={[
                { required: true, message: t('forms.learner.displayNameRequired') },
                { min: 2, message: t('forms.learner.displayNameMinLength') },
              ]}
            >
              <Input placeholder={t('forms.learner.displayNamePlaceholder')} />
            </Form.Item>

            <Form.Item
              name="notes"
              label={t('forms.learner.notesLabel')}
            >
              <Input.TextArea 
                placeholder={t('forms.learner.notesPlaceholder')}
                rows={3}
              />
            </Form.Item>

            <Form.Item
              name="lesson_rate"
              label={t('forms.learner.lessonRateLabel')}
              rules={[
                { type: 'number', min: 0, message: t('forms.learner.lessonRateInvalid') },
              ]}
              extra={t('forms.learner.lessonRateHelp')}
            >
              <InputNumber
                placeholder={t('forms.learner.lessonRatePlaceholder')}
                style={{ width: '100%' }}
                min={0}
                precision={2}
              />
            </Form.Item>

            {mode === 'create' && <Divider />}
          </>
        )}

        {/* Notifications - for create and edit_notifications modes */}
        {(mode === 'create' || mode === 'edit_notifications') && (
          <Form.Item
            name="notifications_enabled"
            label={t('forms.learner.notificationsLabel')}
            valuePropName="checked"
            extra={
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t('forms.learner.notificationsHelp')}
              </Text>
            }
          >
            <Switch 
              checkedChildren={t('pages.learners.enabled')} 
              unCheckedChildren={t('pages.learners.disabled')}
            />
          </Form.Item>
        )}
      </Form>
    </ResponsiveModal>
  );
};

export default LearnerForm;
