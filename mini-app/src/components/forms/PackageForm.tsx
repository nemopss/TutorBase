import React, { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Form, Input, Select, DatePicker, Alert, Typography, Button, Space, Steps, InputNumber, Tag } from 'antd';
import { useTranslation } from 'react-i18next';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import api from '../../services/api';
import { appEnv } from '../../env';
import { devLog } from '../../utils/safeLogging';
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
  const isCreateWizard = !isEditing;
  const [currentStep, setCurrentStep] = useState(0);

  const { data: learnersData, isLoading: isLoadingLearners } = useQuery<LearnerListResponse, Error>({
    queryKey: ['learners'],
    queryFn: fetchLearners,
  });

  // Watch form values for schedule preview
  const selectedLearnerId = Form.useWatch('learner_id', form);
  const startDateValue = Form.useWatch('start_date', form);
  const totalLessonsValue = Form.useWatch('total_lessons', form);
  const titleValue = Form.useWatch('title', form);
  
  // State for preview dates
  const [previewDates, setPreviewDates] = useState<PreviewDate[]>([]);
  
  // Fetch schedule for selected learner
  const { data: scheduleData } = useQuery<ScheduleData>({
    queryKey: ['learnerSchedule', selectedLearnerId],
    queryFn: async () => {
      const { data } = await api.get(`/learners/${selectedLearnerId}/schedule`);
      return data;
    },
    enabled: !!selectedLearnerId && isCreateWizard,
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
    enabled: !!selectedLearnerId && !!startDateValue && !!totalLessonsValue && hasSchedule && isCreateWizard,
  });
  
  // Update preview dates when data changes
  useEffect(() => {
    if (previewData?.dates) {
      setPreviewDates(previewData.dates);
    }
  }, [previewData]);

  useEffect(() => {
    if (!isCreateWizard) {
      return;
    }
    if (!selectedLearnerId || !startDateValue || !totalLessonsValue || !hasSchedule) {
      setPreviewDates([]);
    }
  }, [hasSchedule, isCreateWizard, selectedLearnerId, startDateValue, totalLessonsValue]);

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
      setCurrentStep(0);
      setPreviewDates([]);
      // Pre-fill learner if provided
      if (preselectedLearnerId) {
        form.setFieldsValue({ learner_id: preselectedLearnerId });
      }
    }
  }, [initialValues, form, isOpen, preselectedLearnerId]);

  const selectedLearnerName = useMemo(() => {
    const learner = learnersData?.items.find((item) => item.id === selectedLearnerId);
    return learner?.display_name ?? '';
  }, [learnersData?.items, selectedLearnerId]);

  const wizardSteps = [
    { title: t('forms.packageWizard.steps.learner') },
    { title: t('forms.packageWizard.steps.package') },
    { title: t('forms.packageWizard.steps.schedule') },
    { title: t('forms.packageWizard.steps.review') },
  ];

  const validateCurrentStep = async () => {
    if (currentStep === 0) {
      await form.validateFields(['learner_id']);
    }
    if (currentStep === 1) {
      await form.validateFields(['title', 'total_lessons']);
    }
  };

  const goNext = async () => {
    try {
      await validateCurrentStep();
      setCurrentStep((step) => Math.min(step + 1, wizardSteps.length - 1));
    } catch (info) {
      if (appEnv.isDev) {
        devLog('Validate Failed:', info);
      }
    }
  };

  const goBack = () => {
    setCurrentStep((step) => Math.max(step - 1, 0));
  };

  const formatCreateValues = (values: any, status: 'active' | 'draft') => {
    const startDate = values.start_date;
    const totalLessonsRaw = values.total_lessons;
    const totalLessons =
      totalLessonsRaw === undefined || totalLessonsRaw === null || totalLessonsRaw === ''
        ? undefined
        : Number(totalLessonsRaw);

    const formattedValues: any = {
      ...values,
      status,
      timezone: MSK_TZ,
    };

    if (startDate) {
      formattedValues.start_date = startDate.tz(MSK_TZ).format('YYYY-MM-DD');
    } else {
      delete formattedValues.start_date;
    }

    if (totalLessons !== undefined) {
      formattedValues.total_lessons = totalLessons;
    }

    if (previewDates.length > 0) {
      formattedValues.lesson_dates = previewDates;
    }

    delete formattedValues.template_id;
    return formattedValues;
  };

  const submitCreateWizard = async (status: 'active' | 'draft') => {
    try {
      const values = await form.validateFields(['learner_id', 'title', 'total_lessons']);
      handleFinish(formatCreateValues({ ...form.getFieldsValue(), ...values }, status));
    } catch (info) {
      if (appEnv.isDev) {
        devLog('Validate Failed:', info);
      }
    }
  };

  const wizardFooter = isCreateWizard ? (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
      <Button onClick={currentStep === 0 ? onCancel : goBack}>
        {currentStep === 0 ? t('common.cancel') : t('common.back')}
      </Button>
      {currentStep < wizardSteps.length - 1 ? (
        <Button type="primary" onClick={goNext}>
          {t('forms.packageWizard.next')}
        </Button>
      ) : (
        <Space>
          <Button onClick={() => submitCreateWizard('draft')} loading={isSubmitting}>
            {t('forms.packageWizard.createDraft')}
          </Button>
          <Button type="primary" onClick={() => submitCreateWizard('active')} loading={isSubmitting}>
            {t('forms.packageWizard.createActive')}
          </Button>
        </Space>
      )}
    </div>
  ) : undefined;

  return (
    <ResponsiveModal
      open={isOpen}
      title={isEditing ? t('forms.package.editTitle') : t('forms.package.title')}
      okText={isEditing ? t('common.save') : t('common.create')}
      cancelText={t('common.cancel')}
      onCancel={onCancel}
      onOk={isEditing ? () => {
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
            if (appEnv.isDev) {
              devLog('Validate Failed:', info);
            }
          });
      } : undefined}
      confirmLoading={isSubmitting}
      destroyOnHidden
      footer={wizardFooter}
      width={isCreateWizard ? 680 : undefined}
    >
      <Form form={form} layout="vertical" name="package_form">
        {isCreateWizard ? (
          <>
            <Steps
              current={currentStep}
              items={wizardSteps}
              size="small"
              responsive
              style={{ marginBottom: 24 }}
            />

            <div style={{ display: currentStep === 0 ? 'block' : 'none' }}>
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
            </div>

            <div style={{ display: currentStep === 1 ? 'block' : 'none' }}>
              <Form.Item
                name="title"
                label={t('forms.package.titleLabel')}
                rules={[{ required: true, message: t('forms.package.titleRequired') }]}
              >
                <Input placeholder={t('forms.package.titlePlaceholder')} />
              </Form.Item>
              <Form.Item
                name="total_lessons"
                label={t('forms.package.totalLessonsLabel')}
                rules={[{ required: true, message: t('forms.package.totalLessonsRequired') }]}
              >
                <InputNumber min={1} max={1000} style={{ width: '100%' }} placeholder={t('forms.package.totalLessonsPlaceholder')} />
              </Form.Item>
              <Form.Item name="start_date" label={t('forms.package.startDateLabel')}>
                <DatePicker
                  style={{ width: '100%' }}
                  format="YYYY-MM-DD"
                  showTime={false}
                />
              </Form.Item>
              <Form.Item name="notes" label={t('forms.package.notesLabel')}>
                <Input.TextArea rows={3} placeholder={t('forms.package.notesPlaceholder')} />
              </Form.Item>
            </div>

            <div style={{ display: currentStep === 2 ? 'block' : 'none' }}>
              {selectedLearnerId && hasSchedule && startDateValue && totalLessonsValue ? (
                <>
                  <Text strong style={{ display: 'block', marginBottom: 8 }}>
                    {t('schedulePreview.title')}
                  </Text>
                  <LessonPreviewCalendar
                    dates={previewDates}
                    onDatesChange={setPreviewDates}
                    startDate={startDateValue}
                    scheduleSlots={scheduleData?.slots}
                  />
                  <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
                    {t('schedulePreview.lessonsWillBeCreated', { count: previewDates.length })}
                  </Text>
                </>
              ) : hasSchedule ? (
                <Alert
                  type="info"
                  message={t('schedulePreview.generateDates')}
                  description={t('forms.package.startDateRequired')}
                  showIcon
                />
              ) : (
                <Alert
                  type="warning"
                  message={t('schedulePreview.noSchedule')}
                  description={t('schedulePreview.noScheduleHint')}
                  showIcon
                />
              )}
            </div>

            <div style={{ display: currentStep === 3 ? 'block' : 'none' }}>
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                <div>
                  <Text type="secondary">{t('forms.package.learnerLabel')}</Text>
                  <Text strong style={{ display: 'block' }}>{selectedLearnerName || t('common.noData')}</Text>
                </div>
                <div>
                  <Text type="secondary">{t('forms.package.titleLabel')}</Text>
                  <Text strong style={{ display: 'block' }}>{titleValue || t('common.noData')}</Text>
                </div>
                <div>
                  <Text type="secondary">{t('forms.package.totalLessonsLabel')}</Text>
                  <Text strong style={{ display: 'block' }}>{totalLessonsValue || t('common.noData')}</Text>
                </div>
                <div>
                  <Text type="secondary">{t('forms.package.startDateLabel')}</Text>
                  <Text strong style={{ display: 'block' }}>
                    {startDateValue ? startDateValue.format('YYYY-MM-DD') : t('common.noData')}
                  </Text>
                </div>
                <div>
                  <Text type="secondary">{t('forms.packageWizard.lessons')}</Text>
                  <div style={{ marginTop: 4 }}>
                    <Tag color={previewDates.length > 0 ? 'green' : 'default'}>
                      {previewDates.length > 0
                        ? t('schedulePreview.lessonsWillBeCreated', { count: previewDates.length })
                        : t('forms.packageWizard.noLessonsWillBeCreated')}
                    </Tag>
                  </div>
                </div>
              </Space>
            </div>
          </>
        ) : (
          <>
            <Form.Item
              name="title"
              label={t('forms.package.titleLabel')}
              rules={[{ required: !isEditing, message: t('forms.package.titleRequired') }]}
            >
              <Input placeholder={t('forms.package.titlePlaceholder')} />
            </Form.Item>

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

            <Form.Item name="notes" label={t('forms.package.notesLabel')} style={{ marginTop: 16 }}>
              <Input.TextArea rows={3} placeholder={t('forms.package.notesPlaceholder')} />
            </Form.Item>
          </>
        )}
      </Form>
    </ResponsiveModal>
  );
};

export default PackageForm;
