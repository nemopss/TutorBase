import React, { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Form, Input, Select, DatePicker } from 'antd';
import { useTranslation } from 'react-i18next';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import api from '../../services/api';
import ResponsiveModal from '../common/ResponsiveModal';

dayjs.extend(utc);
dayjs.extend(timezone);

interface Learner {
  id: number;
  display_name: string;
}

interface LearnerListResponse {
  items: Learner[];
}

interface Template {
  id: number;
  name: string;
  description?: string;
  timezone: string;
}

interface TemplateListResponse {
  total: number;
  items: Template[];
}

interface PackageFormProps {
  open: boolean;
  onCancel: () => void;
  onFinish: (values: any) => void;
  isLoading: boolean;
  initialValues?: any;
}

const fetchLearners = async (): Promise<LearnerListResponse> => {
  const { data } = await api.get('/learners');
  return data;
};

const fetchTemplates = async (): Promise<TemplateListResponse> => {
  const { data } = await api.get('/templates');
  return data;
};

const PackageForm: React.FC<PackageFormProps> = ({ open, onCancel, onFinish, isLoading, initialValues }) => {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const MSK_TZ = 'Europe/Moscow';

  const { data: learnersData, isLoading: isLoadingLearners } = useQuery<LearnerListResponse, Error>({
    queryKey: ['learners'],
    queryFn: fetchLearners,
  });

  const { data: templatesData, isLoading: isLoadingTemplates } = useQuery<TemplateListResponse, Error>({
    queryKey: ['templates'],
    queryFn: fetchTemplates,
  });

  useEffect(() => {
    if (!open) {
      return;
    }

    if (initialValues) {
      form.setFieldsValue({
        ...initialValues,
        start_date: initialValues.start_date ? dayjs(initialValues.start_date).tz(MSK_TZ) : null,
        end_date: initialValues.end_date ? dayjs(initialValues.end_date).tz(MSK_TZ) : null,
        learner_id: initialValues.learner_id ?? initialValues.learner?.id,
      });
    } else {
      form.resetFields();
    }
  }, [initialValues, form, open]);

  const isEditing = !!initialValues;
  const selectedTemplateId = Form.useWatch('template_id', form);
  const shouldRequireStartDate = !isEditing && !!selectedTemplateId;

  return (
    <ResponsiveModal
      open={open}
      title={isEditing ? t('forms.package.editTitle') : t('forms.package.title')}
      okText={isEditing ? t('common.save') : t('common.create')}
      cancelText={t('common.cancel')}
      onCancel={onCancel}
      onOk={() => {
        form
          .validateFields()
          .then((values) => {
            const resolvedTimezone = MSK_TZ;

            const startDateValue = values.start_date;
            const endDateValue = values.end_date;
            const totalLessonsRaw = values.total_lessons;
            const totalLessons =
              totalLessonsRaw === undefined || totalLessonsRaw === null || totalLessonsRaw === ''
                ? undefined
                : Number(totalLessonsRaw);

            const formattedValues: any = {
              ...values,
              timezone: resolvedTimezone,
            };

            if (startDateValue) {
              if (isEditing) {
                const originalDate = initialValues?.start_date ? dayjs(initialValues.start_date).tz(MSK_TZ).format('YYYY-MM-DD') : null;
                const newDate = startDateValue.tz(MSK_TZ).format('YYYY-MM-DD');
                if (originalDate !== newDate) {
                  formattedValues.start_date = startDateValue.tz(MSK_TZ).startOf('day').toISOString();
                } else {
                  delete formattedValues.start_date;
                }
              } else {
                formattedValues.start_date = startDateValue.tz(MSK_TZ).format('YYYY-MM-DD');
              }
            } else if (isEditing) {
              formattedValues.start_date = null;
            } else {
              delete formattedValues.start_date;
            }

            if (endDateValue) {
              if (isEditing) {
                const originalDate = initialValues?.end_date ? dayjs(initialValues.end_date).tz(MSK_TZ).format('YYYY-MM-DD') : null;
                const newDate = endDateValue.tz(MSK_TZ).format('YYYY-MM-DD');
                if (originalDate !== newDate) {
                  formattedValues.end_date = endDateValue.tz(MSK_TZ).endOf('day').toISOString();
                } else {
                  delete formattedValues.end_date;
                }
              } else {
                formattedValues.end_date = endDateValue.tz(MSK_TZ).endOf('day').toISOString();
              }
            } else if (isEditing) {
              formattedValues.end_date = null;
            } else {
              delete formattedValues.end_date;
            }
            
            if (totalLessons !== undefined) {
              formattedValues.total_lessons = totalLessons;
            }

            if (!isEditing) {
              if (!formattedValues.template_id) {
                delete formattedValues.template_id;
              }
            } else {
              delete formattedValues.learner_id;
              delete formattedValues.template_id;
            }

            if (!isEditing) form.resetFields();
            onFinish(formattedValues);
          })
          .catch((info) => {
            if (import.meta.env.DEV) {
              console.log('Validate Failed:', info);
            }
          });
      }}
      confirmLoading={isLoading}
      destroyOnClose
    >
      <Form form={form} layout="vertical" name="package_form">
        <Form.Item
          name="title"
          label={t('forms.package.titleLabel')}
          rules={[{ required: !isEditing, message: t('forms.package.titleRequired') }]}
        >
          <Input placeholder={t('forms.package.titlePlaceholder')} />
        </Form.Item>
        
        {!isEditing && (
          <>
            <Form.Item
              name="template_id"
              label={t('forms.package.templateLabel')}
            >
              <Select
                allowClear
                showSearch
                placeholder={t('forms.package.templatePlaceholder')}
                loading={isLoadingTemplates}
                optionFilterProp="label"
                filterOption={(input, option) => String(option?.label ?? '').toLowerCase().includes(input.toLowerCase())}
                options={templatesData?.items.map(template => ({
                  value: template.id,
                  label: template.name,
                }))}
              />
            </Form.Item>
            
            <Form.Item
              name="learner_id"
              label={t('forms.package.learnerLabel')}
              rules={[{ required: true, message: t('forms.package.learnerRequired') }]}
            >
              <Select
                showSearch
                placeholder={t('forms.package.learnerPlaceholder')}
                loading={isLoadingLearners}
                optionFilterProp="children"
                filterOption={(input, option) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())}
                options={learnersData?.items.map(learner => ({ value: learner.id, label: learner.display_name }))}
              />
            </Form.Item>
          </>
        )}

        <Form.Item
          name="status"
          label={t('forms.package.statusLabel')}
          initialValue="draft"
        >
          <Select
            options={[
              { value: 'draft', label: t('pages.packages.status.draft') },
              { value: 'active', label: t('pages.packages.status.active') },
              { value: 'completed', label: t('pages.packages.status.completed') },
              { value: 'cancelled', label: t('pages.packages.status.cancelled') },
            ]}
          />
        </Form.Item>

        <Form.Item
          name="start_date"
          label={t('forms.package.startDateLabel')}
          rules={shouldRequireStartDate ? [{ required: true, message: t('forms.package.startDateRequired') }] : []}
        >
          <DatePicker 
            style={{ width: '100%' }} 
            format="YYYY-MM-DD"
            showTime={false}
          />
        </Form.Item>

        <Form.Item name="total_lessons" label={t('forms.package.totalLessonsLabel')}>
          <Input type="number" min={1} placeholder={t('forms.package.totalLessonsPlaceholder')} />
        </Form.Item>

        <Form.Item name="notes" label={t('forms.package.notesLabel')}>
          <Input.TextArea rows={3} placeholder={t('forms.package.notesPlaceholder')} />
        </Form.Item>
      </Form>
    </ResponsiveModal>
  );
};

export default PackageForm;
