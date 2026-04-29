import React, { useEffect } from 'react';
import { Form, Input, InputNumber, Select, Button, Space, TimePicker } from 'antd';
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import dayjs from 'dayjs';
import { appEnv } from '../../env';
import { devLog } from '../../utils/safeLogging';
import ResponsiveModal from '../common/ResponsiveModal';

interface TemplateFormProps {
  open: boolean;
  onCancel: () => void;
  onFinish: (values: any) => void;
  isLoading: boolean;
  initialValues?: any;
}

const TemplateForm: React.FC<TemplateFormProps> = ({ open, onCancel, onFinish, isLoading, initialValues }) => {
  const { t } = useTranslation();
  const [form] = Form.useForm();

  const WEEKDAY_OPTIONS = [
    { label: t('calendar.days.mon'), value: 0 },
    { label: t('calendar.days.tue'), value: 1 },
    { label: t('calendar.days.wed'), value: 2 },
    { label: t('calendar.days.thu'), value: 3 },
    { label: t('calendar.days.fri'), value: 4 },
    { label: t('calendar.days.sat'), value: 5 },
    { label: t('calendar.days.sun'), value: 6 },
  ];

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
    <ResponsiveModal
      open={open}
      title={isEditing ? t('forms.template.editTitle') : t('forms.template.title')}
      okText={isEditing ? t('common.save') : t('common.create')}
      cancelText={t('common.cancel')}
      onCancel={onCancel}
      onOk={() => form.validateFields().then(handleFinish).catch(info => {
        if (appEnv.isDev) {
          devLog('Validate Failed:', info);
        }
      })}
      confirmLoading={isLoading}
      destroyOnHidden
      width={600}
    >
      <Form form={form} layout="vertical" name="template_form" autoComplete="off">
        <Form.Item
          name="name"
          label={t('forms.template.nameLabel')}
          rules={[{ required: true, message: t('forms.template.nameRequired') }]}
        >
          <Input placeholder={t('forms.template.namePlaceholder')} />
        </Form.Item>
        <Form.Item name="description" label={t('forms.template.descriptionLabel')}>
          <Input.TextArea rows={2} placeholder={t('forms.template.descriptionPlaceholder')} />
        </Form.Item>
        <Form.Item name="lesson_count" label={t('forms.template.lessonCountLabel')}>
          <InputNumber min={1} style={{ width: '100%' }} placeholder={t('forms.template.lessonCountPlaceholder')} />
        </Form.Item>

        <p>{t('forms.template.weeklySchedule')}</p>
        <Form.List name="weekly_schedule">
          {(fields, { add, remove }) => (
            <>
              {fields.map(({ key, name, ...restField }) => (
                <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                  <Form.Item
                    {...restField}
                    name={[name, 'day']}
                    rules={[{ required: true, message: t('forms.template.dayRequired') }]}
                  >
                    <Select options={WEEKDAY_OPTIONS} placeholder={t('forms.template.dayPlaceholder')} style={{ width: 150 }} />
                  </Form.Item>
                  <Form.Item
                    {...restField}
                    name={[name, 'time']}
                    rules={[{ required: true, message: t('forms.template.timeRequired') }]}
                  >
                    <TimePicker format="HH:mm" placeholder={t('forms.template.timePlaceholder')} />
                  </Form.Item>
                  <MinusCircleOutlined onClick={() => remove(name)} />
                </Space>
              ))}
              <Form.Item>
                <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
                  {t('forms.template.addScheduleRule')}
                </Button>
              </Form.Item>
            </>
          )}
        </Form.List>
      </Form>
    </ResponsiveModal>
  );
};

export default TemplateForm;
