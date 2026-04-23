import React, { useEffect } from 'react';
import { Form, DatePicker, InputNumber, Select, Input } from 'antd';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import { useTranslation } from 'react-i18next';
import { appEnv } from '../../env';
import ResponsiveModal from '../common/ResponsiveModal';

dayjs.extend(utc);
dayjs.extend(timezone);

const DEFAULT_TIMEZONE = 'Europe/Moscow';

interface LessonFormProps {
  open: boolean;
  onCancel: () => void;
  onFinish: (values: any) => void;
  isLoading: boolean;
  initialValues?: any; // Объект с начальными значениями для редактирования
  mode?: 'create' | 'edit'; // Явный режим формы
}

const { Option } = Select;

const LessonForm: React.FC<LessonFormProps> = ({ open, onCancel, onFinish, isLoading, initialValues, mode }) => {
  const { t } = useTranslation();
  const [form] = Form.useForm();

  useEffect(() => {
    if (!open) {
      return;
    }

    if (initialValues) {
      const tz = initialValues.timezone || DEFAULT_TIMEZONE;
      form.setFieldsValue({
        ...initialValues,
        scheduled_at: initialValues.scheduled_at ? dayjs(initialValues.scheduled_at).tz(tz) : null,
      });
    } else {
      form.resetFields();
    }
  }, [initialValues, form, open]);

  // Use explicit mode if provided, otherwise infer from initialValues.id
  const isEditing = mode === 'edit' || (mode !== 'create' && !!initialValues?.id);
  const lessonTimezone = initialValues?.timezone || DEFAULT_TIMEZONE;

  return (
    <ResponsiveModal
      open={open}
      title={isEditing ? t('forms.lesson.editTitle') : t('forms.lesson.title')}
      okText={isEditing ? t('common.save') : t('common.create')}
      cancelText={t('common.cancel')}
      onCancel={onCancel}
      onOk={() => {
        form
          .validateFields()
          .then((values) => {
            // Преобразуем scheduled_at в ISO string для backend
            const formattedValues: Record<string, any> = {
              ...values,
              scheduled_at: values.scheduled_at
                ? values.scheduled_at.tz(lessonTimezone).toISOString()
                : undefined,
            };
            
            // При редактировании: не отправляем status если он не изменился
            // Это позволяет backend автоматически установить 'rescheduled' при изменении времени
            if (isEditing && initialValues?.status === values.status) {
              delete formattedValues.status;
            }
            
            // Не сбрасываем поля при редактировании, чтобы не было моргания
            if (!isEditing) {
              form.resetFields();
            }
            onFinish(formattedValues);
          })
          .catch((info) => {
            if (appEnv.isDev) {
              console.log('Validate Failed:', info);
            }
          });
      }}
      confirmLoading={isLoading}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" name="lesson_form">
        <Form.Item
          name="scheduled_at"
          label={t('forms.lesson.dateTimeLabel')}
          rules={[{ required: true, message: t('common.required') }]}
        >
          <DatePicker showTime format="YYYY-MM-DD HH:mm:ss" style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="duration_minutes" label={t('forms.lesson.durationLabel')}>
          <InputNumber min={1} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="status" label={t('forms.lesson.statusLabel')} initialValue={isEditing ? undefined : "scheduled"}>
          <Select>
            <Option value="scheduled">{t('pages.lessons.status.scheduled')}</Option>
            <Option value="rescheduled">{t('pages.lessons.status.rescheduled')}</Option>
            <Option value="completed">{t('pages.lessons.status.completed')}</Option>
            <Option value="cancelled">{t('pages.lessons.status.cancelled')}</Option>
          </Select>
        </Form.Item>
        <Form.Item name="teacher_notes" label={t('forms.lesson.notesLabel')}>
          <Input.TextArea rows={2} />
        </Form.Item>
      </Form>
    </ResponsiveModal>
  );
};

export default LessonForm;
