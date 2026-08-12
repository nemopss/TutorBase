import React, { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  Col,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  Steps,
  Switch,
  Tag,
  Typography,
} from 'antd';
import {
  BellOutlined,
  CalendarOutlined,
  ClockCircleOutlined,
  WalletOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import dayjs, { type Dayjs } from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import api from '../../services/api';
import { appEnv } from '../../env';
import { devLog } from '../../utils/safeLogging';
import ResponsiveModal from '../common/ResponsiveModal';
import LessonPreviewCalendar from '../learner/LessonPreviewCalendar';
import './PackageForm.css';

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

export interface PackageSubmitValues {
  id?: number;
  learner_id?: number;
  learner?: { id: number; display_name?: string };
  template_id?: number | null;
  title?: string;
  notes?: string;
  status?: string;
  schedule_mode?: ScheduleMode;
  renewal_enabled?: boolean;
  total_lessons?: number | string;
  price?: number | string | null;
  start_date?: Dayjs | string | null;
  end_date?: Dayjs | string | null;
  scheduled_at?: Dayjs | string | null;
  duration_minutes?: number;
  lesson_dates?: PreviewDate[];
  timezone?: string;
  _creation_kind?: 'one_off';
  [key: string]: unknown;
}

interface PackageFormProps {
  open?: boolean;
  visible?: boolean; // alias for open
  onCancel: () => void;
  onFinish?: (values: PackageSubmitValues) => void;
  onSubmit?: (values: PackageSubmitValues) => void; // alias for onFinish
  isLoading?: boolean;
  loading?: boolean; // alias for isLoading
  initialValues?: PackageSubmitValues;
  mode?: 'create' | 'edit';
  preselectedLearnerId?: number;
}

type ScheduleMode = 'fixed' | 'flexible' | 'one_off';

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
  const scheduleMode = Form.useWatch('schedule_mode', form) as ScheduleMode | undefined;
  const renewalEnabled = Form.useWatch('renewal_enabled', form);
  const priceValue = Form.useWatch('price', form);
  const oneOffDate = Form.useWatch('scheduled_at', form);
  
  // State for preview dates
  const [previewState, setPreviewState] = useState<{ key: string; dates: PreviewDate[] }>({
    key: '',
    dates: [],
  });
  
  // Fetch schedule for selected learner
  const { data: scheduleData } = useQuery<ScheduleData>({
    queryKey: ['learnerSchedule', selectedLearnerId],
    queryFn: async () => {
      const { data } = await api.get(`/learners/${selectedLearnerId}/schedule`);
      return data;
    },
    enabled: !!selectedLearnerId && isCreateWizard && scheduleMode === 'fixed',
  });
  
  const hasSchedule = scheduleData && scheduleData.slots.length > 0;
  
  // Fetch preview dates when learner, start date, and lesson count are set
  const previewRequestKey = [
    selectedLearnerId ?? '',
    startDateValue?.format('YYYY-MM-DD') ?? '',
    totalLessonsValue ?? '',
  ].join(':');
  const { data: previewData, isFetching: isPreviewFetching } = useQuery<PreviewDatesResponse & { requestKey: string }>({
    queryKey: ['previewDates', selectedLearnerId, startDateValue?.format('YYYY-MM-DD'), totalLessonsValue],
    queryFn: async () => {
      const { data } = await api.post('/packages/preview-dates', null, {
        params: {
          learner_id: selectedLearnerId,
          start_date: startDateValue.format('YYYY-MM-DD'),
          lesson_count: parseInt(totalLessonsValue) || 8,
        },
      });
      return { ...data, requestKey: previewRequestKey };
    },
    enabled: !!selectedLearnerId && !!startDateValue && !!totalLessonsValue && hasSchedule && isCreateWizard && scheduleMode === 'fixed',
  });
  
  // Update preview dates when data changes
  useEffect(() => {
    if (previewData?.dates) {
      setPreviewState({ key: previewData.requestKey, dates: previewData.dates });
    }
  }, [previewData]);

  const previewDates = previewState.key === previewRequestKey ? previewState.dates : [];

  useEffect(() => {
    if (!isCreateWizard) {
      return;
    }
    if (
      scheduleMode !== 'fixed'
      || !selectedLearnerId
      || !startDateValue
      || !totalLessonsValue
      || !hasSchedule
    ) {
      setPreviewState({ key: '', dates: [] });
    }
  }, [hasSchedule, isCreateWizard, scheduleMode, selectedLearnerId, startDateValue, totalLessonsValue]);

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
      form.setFieldsValue({
        schedule_mode: undefined,
        renewal_enabled: false,
        duration_minutes: 60,
      });
      setCurrentStep(0);
      setPreviewState({ key: '', dates: [] });
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
    { title: t('forms.packageWizard.steps.mode') },
    { title: t('forms.packageWizard.steps.learner') },
    { title: t('forms.packageWizard.steps.schedule') },
    { title: t('forms.packageWizard.steps.review') },
  ];

  const validateCurrentStep = async () => {
    if (currentStep === 0) {
      await form.validateFields(['schedule_mode']);
    }
    if (currentStep === 1) {
      await form.validateFields([
        'learner_id',
        'title',
        ...(scheduleMode === 'one_off' ? [] : ['total_lessons']),
      ]);
    }
    if (currentStep === 2 && scheduleMode === 'one_off') {
      await form.validateFields(['scheduled_at', 'duration_minutes']);
    }
    if (currentStep === 2 && scheduleMode === 'fixed' && previewDates.length === 0) {
      throw new Error('Fixed package requires scheduled lessons');
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

  const formatCreateValues = (values: PackageSubmitValues, status: 'active' | 'draft') => {
    const startDate = values.start_date;
    const totalLessonsRaw = values.total_lessons;
    const totalLessons =
      totalLessonsRaw === undefined || totalLessonsRaw === null || totalLessonsRaw === ''
        ? undefined
        : Number(totalLessonsRaw);

    const formattedValues: PackageSubmitValues = {
      ...values,
      status,
      timezone: MSK_TZ,
      schedule_mode: scheduleMode,
    };

    if (scheduleMode === 'one_off') {
      const scheduledAt = dayjs(values.scheduled_at);
      return {
        _creation_kind: 'one_off' as const,
        learner_id: values.learner_id,
        title: values.title,
        scheduled_at: scheduledAt.tz(MSK_TZ).toISOString(),
        duration_minutes: Number(values.duration_minutes || 60),
        price: values.price,
        notes: values.notes,
      };
    }

    if (startDate) {
      formattedValues.start_date = dayjs(startDate).tz(MSK_TZ).format('YYYY-MM-DD');
    } else {
      delete formattedValues.start_date;
    }

    if (totalLessons !== undefined) {
      formattedValues.total_lessons = totalLessons;
    }

    if (scheduleMode === 'fixed' && previewDates.length > 0) {
      formattedValues.lesson_dates = previewDates;
    } else {
      delete formattedValues.lesson_dates;
    }

    delete formattedValues.template_id;
    return formattedValues;
  };

  const submitCreateWizard = async (status: 'active' | 'draft') => {
    try {
      const values = await form.validateFields([
        'schedule_mode',
        'learner_id',
        'title',
        ...(scheduleMode === 'one_off'
          ? ['scheduled_at', 'duration_minutes']
          : ['total_lessons']),
      ]);
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
        <Button
          type="primary"
          onClick={goNext}
          loading={currentStep === 2 && scheduleMode === 'fixed' && isPreviewFetching}
          disabled={currentStep === 2 && scheduleMode === 'fixed' && isPreviewFetching}
        >
          {t('forms.packageWizard.next')}
        </Button>
      ) : (
        <Space>
          {scheduleMode !== 'one_off' && (
            <Button onClick={() => submitCreateWizard('draft')} loading={isSubmitting}>
              {t('forms.packageWizard.createDraft')}
            </Button>
          )}
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

            const formattedValues: PackageSubmitValues = {
              ...values,
              timezone: resolvedTimezone,
            };
            if (values.schedule_mode !== 'fixed') {
              formattedValues.renewal_enabled = false;
            }

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
              setPreviewState({ key: '', dates: [] });
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
              <Typography.Title level={4} className="package-wizard__heading">
                {t('forms.packageWizard.modeTitle')}
              </Typography.Title>
              <Text type="secondary" className="package-wizard__intro">
                {t('forms.packageWizard.modeHint')}
              </Text>
              <Form.Item
                name="schedule_mode"
                rules={[{ required: true, message: t('forms.packageWizard.modeRequired') }]}
                className="package-wizard__mode-field"
              >
                <input type="hidden" />
              </Form.Item>
              <Row gutter={[12, 12]}>
                {([
                  ['fixed', <CalendarOutlined />, 'fixedTitle', 'fixedDescription'],
                  ['flexible', <ClockCircleOutlined />, 'flexibleTitle', 'flexibleDescription'],
                  ['one_off', <WalletOutlined />, 'oneOffTitle', 'oneOffDescription'],
                ] as const).map(([value, icon, titleKey, descriptionKey]) => (
                  <Col xs={24} md={8} key={value}>
                    <button
                      type="button"
                      className={`package-mode-card${scheduleMode === value ? ' package-mode-card--selected' : ''}`}
                      onClick={() => {
                        form.setFieldValue('schedule_mode', value);
                        form.setFieldValue('renewal_enabled', false);
                        if (value === 'one_off') {
                          form.setFieldValue('total_lessons', 1);
                        }
                      }}
                      aria-pressed={scheduleMode === value}
                    >
                      <span className="package-mode-card__icon">{icon}</span>
                      <span className="package-mode-card__title">
                        {t(`forms.packageWizard.${titleKey}`)}
                      </span>
                      <span className="package-mode-card__description">
                        {t(`forms.packageWizard.${descriptionKey}`)}
                      </span>
                    </button>
                  </Col>
                ))}
              </Row>
            </div>

            <div style={{ display: currentStep === 1 ? 'block' : 'none' }}>
              <Row gutter={16}>
                <Col xs={24} md={12}>
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
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item
                    name="title"
                    label={t('forms.package.titleLabel')}
                    rules={[{ required: true, message: t('forms.package.titleRequired') }]}
                  >
                    <Input placeholder={t('forms.package.titlePlaceholder')} />
                  </Form.Item>
                </Col>
              </Row>
              {scheduleMode !== 'one_off' && (
                <Form.Item
                  name="total_lessons"
                  label={t('forms.package.totalLessonsLabel')}
                  rules={[{ required: true, message: t('forms.package.totalLessonsRequired') }]}
                >
                  <InputNumber min={1} max={1000} style={{ width: '100%' }} placeholder={t('forms.package.totalLessonsPlaceholder')} />
                </Form.Item>
              )}
              <Form.Item
                name="price"
                label={t('forms.packageWizard.priceLabel')}
                extra={t('forms.packageWizard.priceHint')}
              >
                <InputNumber min={0} precision={2} style={{ width: '100%' }} prefix="₽" />
              </Form.Item>
              <Form.Item name="notes" label={t('forms.package.notesLabel')}>
                <Input.TextArea rows={3} placeholder={t('forms.package.notesPlaceholder')} />
              </Form.Item>
            </div>

            <div style={{ display: currentStep === 2 ? 'block' : 'none' }}>
              {scheduleMode === 'one_off' ? (
                <Card className="package-wizard__panel" bordered={false}>
                  <Form.Item
                    name="scheduled_at"
                    label={t('forms.packageWizard.oneOffDateLabel')}
                    rules={[{ required: true, message: t('forms.packageWizard.oneOffDateRequired') }]}
                  >
                    <DatePicker showTime format="DD.MM.YYYY HH:mm" style={{ width: '100%' }} />
                  </Form.Item>
                  <Form.Item
                    name="duration_minutes"
                    label={t('forms.packageWizard.durationLabel')}
                    rules={[{ required: true }]}
                  >
                    <InputNumber min={15} max={480} step={15} style={{ width: '100%' }} />
                  </Form.Item>
                  <Alert type="success" showIcon message={t('forms.packageWizard.oneOffSafeHint')} />
                </Card>
              ) : scheduleMode === 'flexible' ? (
                <Card className="package-wizard__panel" bordered={false}>
                  <Alert
                    type="success"
                    showIcon
                    message={t('forms.packageWizard.flexibleSafeTitle')}
                    description={t('forms.packageWizard.flexibleSafeDescription')}
                  />
                  <Form.Item name="start_date" label={t('forms.package.startDateLabel')} style={{ marginTop: 16 }}>
                    <DatePicker style={{ width: '100%' }} format="DD.MM.YYYY" />
                  </Form.Item>
                </Card>
              ) : (
                <>
                  <Form.Item name="start_date" label={t('forms.package.startDateLabel')} rules={[{ required: true }]}>
                    <DatePicker style={{ width: '100%' }} format="DD.MM.YYYY" />
                  </Form.Item>
                  {selectedLearnerId && hasSchedule && startDateValue && totalLessonsValue ? (
                <>
                  <Text strong style={{ display: 'block', marginBottom: 8 }}>
                    {t('schedulePreview.title')}
                  </Text>
                  <LessonPreviewCalendar
                    dates={previewDates}
                    onDatesChange={(dates) => setPreviewState({ key: previewRequestKey, dates })}
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
                  <Card className="package-wizard__renewal" size="small">
                    <Space align="start">
                      <BellOutlined className="package-wizard__renewal-icon" />
                      <div className="package-wizard__renewal-copy">
                        <Text strong>{t('forms.packageWizard.renewalTitle')}</Text>
                        <Text type="secondary">{t('forms.packageWizard.renewalDescription')}</Text>
                      </div>
                      <Form.Item name="renewal_enabled" valuePropName="checked" noStyle>
                        <Switch aria-label={t('forms.packageWizard.renewalTitle')} />
                      </Form.Item>
                    </Space>
                  </Card>
                </>
              )}
            </div>

            <div style={{ display: currentStep === 3 ? 'block' : 'none' }}>
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                <div>
                  <Text type="secondary">{t('forms.packageWizard.modeLabel')}</Text>
                  <Text strong style={{ display: 'block' }}>
                    {scheduleMode ? t(`forms.packageWizard.${scheduleMode === 'one_off' ? 'oneOffTitle' : `${scheduleMode}Title`}`) : t('common.noData')}
                  </Text>
                </div>
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
                  <Text strong style={{ display: 'block' }}>{scheduleMode === 'one_off' ? 1 : totalLessonsValue || t('common.noData')}</Text>
                </div>
                <div>
                  <Text type="secondary">{t('forms.package.startDateLabel')}</Text>
                  <Text strong style={{ display: 'block' }}>
                    {scheduleMode === 'one_off'
                      ? oneOffDate?.format('DD.MM.YYYY HH:mm') || t('common.noData')
                      : startDateValue?.format('DD.MM.YYYY') || t('common.noData')}
                  </Text>
                </div>
                <div>
                  <Text type="secondary">{t('forms.packageWizard.lessons')}</Text>
                  <div style={{ marginTop: 4 }}>
                    <Tag color={scheduleMode === 'fixed' && previewDates.length > 0 ? 'green' : 'blue'}>
                      {scheduleMode === 'one_off'
                        ? t('forms.packageWizard.oneLessonWillBeCreated')
                        : previewDates.length > 0
                        ? t('schedulePreview.lessonsWillBeCreated', { count: previewDates.length })
                        : t('forms.packageWizard.noLessonsWillBeCreated')}
                    </Tag>
                  </div>
                </div>
                <div>
                  <Text type="secondary">{t('forms.packageWizard.priceLabel')}</Text>
                  <Text strong style={{ display: 'block' }}>
                    {priceValue !== undefined && priceValue !== null ? `${priceValue} ₽` : t('forms.packageWizard.priceAuto')}
                  </Text>
                </div>
                {scheduleMode === 'fixed' && (
                  <Alert
                    type={renewalEnabled ? 'info' : 'success'}
                    showIcon
                    message={renewalEnabled
                      ? t('forms.packageWizard.renewalOnReview')
                      : t('forms.packageWizard.renewalOffReview')}
                  />
                )}
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

            <Form.Item name="schedule_mode" label={t('forms.packageWizard.modeLabel')}>
              <Select
                disabled={initialValues?.package_type === 'one_off'}
                options={[
                  { value: 'fixed', label: t('forms.packageWizard.fixedTitle') },
                  { value: 'flexible', label: t('forms.packageWizard.flexibleTitle') },
                  ...(initialValues?.package_type === 'one_off'
                    ? [{ value: 'one_off', label: t('forms.packageWizard.oneOffTitle') }]
                    : []),
                ]}
              />
            </Form.Item>

            {scheduleMode === 'fixed' && (
              <Form.Item
                name="renewal_enabled"
                label={t('forms.packageWizard.renewalTitle')}
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
            )}

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

            <Form.Item name="price" label={t('forms.packageWizard.priceLabel')}>
              <InputNumber min={0} precision={2} style={{ width: '100%' }} prefix="₽" />
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
