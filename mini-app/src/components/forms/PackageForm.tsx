import React, { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Form, Input, Select, DatePicker, Alert, Typography, Divider } from 'antd';
import { useTranslation } from 'react-i18next';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import api from '../../services/api';
import ResponsiveModal from '../common/ResponsiveModal';
import LessonPreviewCalendar from '../learner/LessonPreviewCalendar';

dayjs.extend(utc);
dayjs.extend(timezone);

const { Text } = Typography;

interface Learner {
  id: number;
  display_name: string;
}

interface LearnerListResponse {
  items: Learner[];
}

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

interface PreviewDate {
  datetime: string;
  duration: number;
}

interface PreviewDatesResponse {
  dates: PreviewDate[];
  schedule: ScheduleData;
}

interface PackageFormProps {
  open?: boolean;
  visible?: boolean; // alias for open
  onCancel: () => void;
  onFinish?: (values: any) => void;
  onSubmit?: (values: any) => void; // alias for onFinish
  isLoading?: boolean;
  loading?: boolean; // alias for isLoading
  initialValues?: any;
  mode?: 'create' | 'edit';
  preselectedLearnerId?: number;
}

const fetchLearners = async (): Promise<LearnerListResponse> => {
  const { data } = await api.get('/learners');
  return data;
};

const PackageForm: React.FC<PackageFormProps> = ({ 
  open, 
  visible,
  onCancel, 
  onFinish, 
  onSubmit,
  isLoading, 
  loading,
  initialValues,
  mode,
  preselectedLearnerId,
}) => {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const MSK_TZ = 'Europe/Moscow';
  
  // Support both prop naming conventions
  const isOpen = open ?? visible ?? false;
  const handleFinish = onFinish ?? onSubmit ?? (() => {});
  const isSubmitting = isLoading ?? loading ?? false;
  const isEditing = mode === 'edit' || !!initialValues;

  const { data: learnersData, isLoading: isLoadingLearners } = useQuery<LearnerListResponse, Error>({
    queryKey: ['learners'],
    queryFn: fetchLearners,
  });

  // Watch form values for schedule preview
  const selectedLearnerId = Form.useWatch('learner_id', form);
  const startDateValue = Form.useWatch('start_date', form);
  const totalLessonsValue = Form.useWatch('total_lessons', form);
  
  // State for preview dates
  const [previewDates, setPreviewDates] = useState<PreviewDate[]>([]);
  
  // Fetch schedule for selected learner
  const { data: scheduleData } = useQuery<ScheduleData>({
    queryKey: ['learnerSchedule', selectedLearnerId],
    queryFn: async () => {
      const { data } = await api.get(`/learners/${selectedLearnerId}/schedule`);
      return data;
    },
    enabled: !!selectedLearnerId && !isEditing,
  });
  
  const hasSchedule = scheduleData && scheduleData.slots.length > 0;
  
  // Fetch preview dates when learner, start date, and lesson count are set
  const { data: previewData } = useQuery<PreviewDatesResponse>({
    queryKey: ['previewDates', selectedLearnerId, startDateValue?.format('YYYY-MM-DD'), totalLessonsValue],
    queryFn: async () => {
      const { data } = await api.post('/packages/preview-dates', null, {
        params: {
          learner_id: selectedLearnerId,
          start_date: startDateValue.format('YYYY-MM-DD'),
          lesson_count: parseInt(totalLessonsValue) || 8,
        },
      });
      return data;
    },
    enabled: !!selectedLearnerId && !!startDateValue && !!totalLessonsValue && hasSchedule && !isEditing,
  });
  
  // Update preview dates when data changes
  useEffect(() => {
    if (previewData?.dates) {
      setPreviewDates(previewData.dates);
    }
  }, [previewData]);

  useEffect(() => {
    if (!isOpen) {
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
      // Pre-fill learner if provided
      if (preselectedLearnerId) {
        form.setFieldsValue({ learner_id: preselectedLearnerId });
      }
    }
  }, [initialValues, form, isOpen, preselectedLearnerId]);

  return (
    <ResponsiveModal
      open={isOpen}
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
              // Add preview dates if available
              if (previewDates.length > 0) {
                formattedValues.lesson_dates = previewDates;
              }
            } else {
              delete formattedValues.learner_id;
              delete formattedValues.template_id;
            }

            if (!isEditing) {
              form.resetFields();
              setPreviewDates([]);
            }
            handleFinish(formattedValues);
          })
          .catch((info) => {
            if (import.meta.env.DEV) {
              console.log('Validate Failed:', info);
            }
          });
      }}
      confirmLoading={isSubmitting}
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

        {/* Schedule Preview Section */}
        {!isEditing && selectedLearnerId && (
          <>
            <Divider />
            {hasSchedule ? (
              startDateValue && totalLessonsValue ? (
                <>
                  <Text strong style={{ display: 'block', marginBottom: 8 }}>
                    {t('schedulePreview.title')}
                  </Text>
                  <LessonPreviewCalendar
                    dates={previewDates}
                    onDatesChange={setPreviewDates}
                    startDate={startDateValue}
                  />
                  <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
                    {t('schedulePreview.lessonsWillBeCreated', { count: previewDates.length })}
                  </Text>
                </>
              ) : (
                <Alert
                  type="info"
                  message={t('schedulePreview.generateDates')}
                  description={t('forms.package.startDateRequired')}
                  showIcon
                />
              )
            ) : (
              <Alert
                type="warning"
                message={t('schedulePreview.noSchedule')}
                description={t('schedulePreview.noScheduleHint')}
                showIcon
              />
            )}
          </>
        )}

        <Form.Item name="notes" label={t('forms.package.notesLabel')} style={{ marginTop: 16 }}>
          <Input.TextArea rows={3} placeholder={t('forms.package.notesPlaceholder')} />
        </Form.Item>
      </Form>
    </ResponsiveModal>
  );
};

export default PackageForm;
