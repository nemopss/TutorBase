import React, { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  Col,
  Divider,
  Form,
  Input,
  InputNumber,
  message,
  Modal,
  Row,
  Select,
  Space,
  Steps,
  Switch,
  Tabs,
  Tag,
  Typography,
} from 'antd';
import type { TableProps } from 'antd';
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { useTranslation } from 'react-i18next';
import PageHeader from '../components/common/PageHeader';
import ResponsiveDataView from '../components/common/ResponsiveDataView';
import api from '../services/api';

type NotificationsTabKey = 'rules' | 'templates' | 'queue' | 'activity' | 'settings';

interface NotificationAssignment {
  scope_type: string;
  scope_id?: number | null;
  is_exclusion: boolean;
}

interface NotificationRule {
  id: number;
  name: string;
  category: string;
  event_type: string;
  trigger_type: string;
  trigger_config: Record<string, unknown>;
  priority: string;
  status: string;
  combine_policy_key?: string | null;
  assignments: NotificationAssignment[];
  updated_at?: string | null;
}

interface NotificationTemplate {
  id: number;
  category: string;
  key: string;
  name: string;
  body: string;
  locale: string;
  version: number;
  system: boolean;
  archived_at?: string | null;
}

interface NotificationDeliveryAttempt {
  status: string;
  provider_message_id?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  sent_at?: string | null;
  finished_at?: string | null;
}

interface NotificationInstance {
  id: number;
  rule_id?: number | null;
  category: string;
  event_type: string;
  event_id?: number | null;
  learner_display_name?: string | null;
  scheduled_for: string;
  effective_scheduled_for: string;
  status: string;
  status_reason?: string | null;
  delivery_enabled: boolean;
  priority: string;
  combination_key?: string | null;
  latest_attempt?: NotificationDeliveryAttempt | null;
}

interface NotificationActivity {
  activity_type: string;
  activity_id: number;
  notification_instance_id?: number | null;
  category?: string | null;
  event_type: string;
  learner_display_name?: string | null;
  status: string;
  action_key?: string | null;
  response_value?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  provider_message_id?: string | null;
  occurred_at?: string | null;
}

interface NotificationSettings {
  mode: string;
  notifications_enabled?: boolean | null;
  quiet_hours_start?: string | null;
  quiet_hours_end?: string | null;
  timezone?: string | null;
  daily_cap?: number | null;
  cap_mode?: string | null;
}

interface NotificationTemplateFormValues {
  category: string;
  key: string;
  name: string;
  body: string;
  description?: string;
}

interface NotificationSettingsFormValues {
  mode: string;
  notifications_enabled?: boolean;
  quiet_hours_start?: string;
  quiet_hours_end?: string;
  timezone?: string;
  daily_cap?: number;
  cap_mode?: string;
}

interface Learner {
  id: number;
  display_name: string;
}

interface LearnerListResponse {
  items: Learner[];
}

interface LearnerGroup {
  id: number;
  name: string;
  status: string;
  member_count: number;
}

interface LessonPackage {
  id: number;
  title: string;
  learner_name?: string;
  status: string;
}

interface PackageListResponse {
  items: LessonPackage[];
}

interface RuleWizardValues {
  name: string;
  category: string;
  message_mode: 'template' | 'inline';
  template_id?: number;
  inline_template_body?: string;
  event_type: string;
  trigger_type: string;
  trigger_days?: number;
  trigger_local_time?: string;
  trigger_minutes?: number;
  trigger_absolute_datetime?: string;
  audience_scope_type: 'all_learners' | 'learner' | 'group' | 'package';
  audience_scope_ids?: number[];
  excluded_learner_ids?: number[];
  priority: string;
  combine_policy_key?: string;
}

interface NotificationPreviewComponent {
  rule_id: number | string;
  category: string;
  scheduled_for: string;
  effective_scheduled_for: string;
  warnings: string[];
  explanation: Record<string, unknown>;
}

interface NotificationPreviewInstance {
  kind: string;
  rule_id?: number | string | null;
  learner_id: number;
  event_type: string;
  event_id?: number | null;
  category?: string | null;
  scheduled_for: string;
  effective_scheduled_for: string;
  priority: string;
  status: string;
  reason?: string | null;
  warnings: string[];
  explanation: Record<string, unknown>;
  combination_key?: string | null;
  components: NotificationPreviewComponent[];
}

interface NotificationPreviewResponse {
  instances: NotificationPreviewInstance[];
  warnings: string[];
}

const CATEGORY_OPTIONS = [
  'lesson_confirmation',
  'lesson_reminder',
  'homework',
  'package_renewal',
  'payment',
  'custom',
  'teacher_alert',
];

const fetchNotificationRules = async (): Promise<NotificationRule[]> => {
  const { data } = await api.get('/notifications/rules');
  return data;
};

const fetchNotificationTemplates = async (): Promise<NotificationTemplate[]> => {
  const { data } = await api.get('/notifications/templates');
  return data;
};

const fetchNotificationInstances = async (): Promise<NotificationInstance[]> => {
  const { data } = await api.get('/notifications/instances', { params: { limit: 100 } });
  return data;
};

const fetchNotificationActivity = async (): Promise<NotificationActivity[]> => {
  const { data } = await api.get('/notifications/activity', { params: { limit: 100 } });
  return data;
};

const fetchNotificationSettings = async (): Promise<NotificationSettings> => {
  const { data } = await api.get('/notifications/settings');
  return data;
};

const fetchLearners = async (): Promise<Learner[]> => {
  const { data } = await api.get<LearnerListResponse>('/learners');
  return data.items;
};

const fetchGroups = async (): Promise<LearnerGroup[]> => {
  const { data } = await api.get('/groups');
  return data;
};

const fetchActivePackages = async (): Promise<LessonPackage[]> => {
  const { data } = await api.get<PackageListResponse>('/packages', {
    params: { status_filter: 'active', limit: 100 },
  });
  return data.items;
};

const createNotificationTemplate = async (values: NotificationTemplateFormValues): Promise<NotificationTemplate> => {
  const { data } = await api.post('/notifications/templates', {
    ...values,
    locale: 'ru',
    template_format: 'plain_text',
  });
  return data;
};

const setRuleStatus = async ({ ruleId, action }: { ruleId: number; action: 'activate' | 'pause' | 'archive' }): Promise<NotificationRule> => {
  const { data } = await api.post(`/notifications/rules/${ruleId}/${action}`);
  return data;
};

const archiveTemplate = async (templateId: number): Promise<NotificationTemplate> => {
  const { data } = await api.post(`/notifications/templates/${templateId}/archive`);
  return data;
};

const materializeShadowQueue = async () => {
  const { data } = await api.post('/notifications/materialize-active-rules', {
    horizon_days: 30,
    limit: 100,
    delivery_enabled: false,
    shadow: true,
  });
  return data;
};

const cancelInstance = async (instanceId: number): Promise<NotificationInstance> => {
  const { data } = await api.post(`/notifications/instances/${instanceId}/cancel`, {
    reason: 'cancelled_from_notifications_ui',
  });
  return data;
};

const sendInstanceNow = async (instanceId: number): Promise<NotificationInstance> => {
  const { data } = await api.post(`/notifications/instances/${instanceId}/send-now`);
  return data;
};

const updateSettings = async (values: NotificationSettingsFormValues): Promise<NotificationSettings> => {
  const { data } = await api.patch('/notifications/settings', values);
  return data;
};

const formatApiError = (error: Error): string => {
  const responseData = (error as Error & { response?: { data?: { detail?: unknown } } }).response?.data;
  const detail = responseData?.detail;

  if (Array.isArray(detail)) {
    return detail.map((item) => {
      if (typeof item === 'object' && item !== null && 'msg' in item) {
        const loc = 'loc' in item && Array.isArray(item.loc) ? item.loc.join('.') : '';
        return `${loc ? `${loc}: ` : ''}${String(item.msg)}`;
      }
      return String(item);
    }).join('; ');
  }

  if (typeof detail === 'string') {
    return detail;
  }

  return error.message;
};

const buildTriggerConfig = (values: RuleWizardValues): Record<string, unknown> => {
  switch (values.trigger_type) {
    case 'day_offset_at_time':
      return {
        days: values.trigger_days ?? -1,
        local_time: values.trigger_local_time || '10:00',
      };
    case 'relative_offset':
    case 'after_event_offset':
      return {
        minutes: values.trigger_minutes ?? (values.trigger_type === 'relative_offset' ? -60 : 120),
      };
    case 'absolute_datetime':
      return {
        datetime: values.trigger_absolute_datetime,
      };
    default:
      return {};
  }
};

const buildAssignments = (values: RuleWizardValues) => {
  const includes = values.audience_scope_type === 'all_learners'
    ? [{ scope_type: 'all_learners', scope_id: null, is_exclusion: false }]
    : (values.audience_scope_ids ?? []).map((scopeId) => ({
      scope_type: values.audience_scope_type,
      scope_id: scopeId,
      is_exclusion: false,
    }));

  const exclusions = (values.excluded_learner_ids ?? []).map((learnerId) => ({
    scope_type: 'learner',
    scope_id: learnerId,
    is_exclusion: true,
  }));

  return [...includes, ...exclusions];
};

const createNotificationRule = async (values: RuleWizardValues): Promise<NotificationRule> => {
  const { data } = await api.post('/notifications/rules', {
    category: values.category,
    name: values.name,
    event_type: values.event_type,
    trigger_type: values.trigger_type,
    trigger_config: buildTriggerConfig(values),
    template_id: values.message_mode === 'template' ? values.template_id : null,
    inline_template_body: values.message_mode === 'inline' ? values.inline_template_body : null,
    inline_template_format: 'plain_text',
    priority: values.priority,
    status: 'draft',
    combine_policy_key: values.combine_policy_key || null,
    delivery_channel: 'telegram',
    cap_mode: 'warn_only',
    quiet_hours_mode: 'shift',
    bypass_quiet_hours: false,
    assignments: buildAssignments(values),
  });
  return data;
};

const previewNotificationRule = async (
  values: RuleWizardValues,
  templates: NotificationTemplate[],
): Promise<NotificationPreviewResponse> => {
  const selectedTemplate = values.template_id
    ? templates.find((template) => template.id === values.template_id)
    : undefined;
  const templateBody = values.message_mode === 'template'
    ? selectedTemplate?.body
    : values.inline_template_body;

  const { data } = await api.post('/notifications/rules/preview', {
    horizon_days: 30,
    limit: 20,
    rule: {
      rule_id: 'wizard',
      name: values.name,
      category: values.category,
      event_type: values.event_type,
      trigger_type: values.trigger_type,
      trigger_config: buildTriggerConfig(values),
      priority: values.priority,
      template_body: templateBody,
      template_key: selectedTemplate?.key ?? null,
      combine_policy_key: values.combine_policy_key || null,
      assignments: buildAssignments(values),
    },
  });
  return data;
};

const getRuleWizardValidation = (values: RuleWizardValues): { step: number; translationKey: string } | null => {
  if (!values.name?.trim()) {
    return { step: 0, translationKey: 'pages.notifications.ruleWizard.validation.nameRequired' };
  }
  if (!values.category) {
    return { step: 0, translationKey: 'pages.notifications.ruleWizard.validation.categoryRequired' };
  }
  if (values.message_mode === 'template' && !values.template_id) {
    return { step: 0, translationKey: 'pages.notifications.ruleWizard.validation.templateRequired' };
  }
  if (values.message_mode === 'inline' && !values.inline_template_body?.trim()) {
    return { step: 0, translationKey: 'pages.notifications.ruleWizard.validation.messageRequired' };
  }
  if (!values.event_type || !values.trigger_type || !values.priority) {
    return { step: 1, translationKey: 'pages.notifications.ruleWizard.validation.triggerRequired' };
  }
  if (values.trigger_type === 'day_offset_at_time' && (values.trigger_days === undefined || !values.trigger_local_time)) {
    return { step: 1, translationKey: 'pages.notifications.ruleWizard.validation.dayTriggerRequired' };
  }
  if ((values.trigger_type === 'relative_offset' || values.trigger_type === 'after_event_offset') && values.trigger_minutes === undefined) {
    return { step: 1, translationKey: 'pages.notifications.ruleWizard.validation.minutesRequired' };
  }
  if (values.trigger_type === 'absolute_datetime' && !values.trigger_absolute_datetime) {
    return { step: 1, translationKey: 'pages.notifications.ruleWizard.validation.absoluteDatetimeRequired' };
  }
  if (values.audience_scope_type !== 'all_learners' && (values.audience_scope_ids ?? []).length === 0) {
    return { step: 2, translationKey: 'pages.notifications.ruleWizard.validation.audienceRequired' };
  }
  return null;
};

const Notifications: React.FC = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<NotificationsTabKey>('rules');
  const [templateModalOpen, setTemplateModalOpen] = useState(false);
  const [ruleWizardOpen, setRuleWizardOpen] = useState(false);
  const [ruleWizardStep, setRuleWizardStep] = useState(0);
  const [rulePreview, setRulePreview] = useState<NotificationPreviewResponse | null>(null);
  const [templateForm] = Form.useForm<NotificationTemplateFormValues>();
  const [ruleForm] = Form.useForm<RuleWizardValues>();
  const [settingsForm] = Form.useForm<NotificationSettingsFormValues>();

  const rulesQuery = useQuery<NotificationRule[], Error>({
    queryKey: ['notificationRules'],
    queryFn: fetchNotificationRules,
    enabled: activeTab === 'rules',
  });

  const templatesQuery = useQuery<NotificationTemplate[], Error>({
    queryKey: ['notificationTemplates'],
    queryFn: fetchNotificationTemplates,
    enabled: activeTab === 'templates' || templateModalOpen || ruleWizardOpen,
  });

  const instancesQuery = useQuery<NotificationInstance[], Error>({
    queryKey: ['notificationInstances'],
    queryFn: fetchNotificationInstances,
    enabled: activeTab === 'queue',
  });

  const activityQuery = useQuery<NotificationActivity[], Error>({
    queryKey: ['notificationActivity'],
    queryFn: fetchNotificationActivity,
    enabled: activeTab === 'activity',
  });

  const settingsQuery = useQuery<NotificationSettings, Error>({
    queryKey: ['notificationSettings'],
    queryFn: fetchNotificationSettings,
    enabled: activeTab === 'settings',
  });

  const learnersQuery = useQuery<Learner[], Error>({
    queryKey: ['learnersForNotificationWizard'],
    queryFn: fetchLearners,
    enabled: ruleWizardOpen,
  });

  const groupsQuery = useQuery<LearnerGroup[], Error>({
    queryKey: ['groupsForNotificationWizard'],
    queryFn: fetchGroups,
    enabled: ruleWizardOpen,
  });

  const packagesQuery = useQuery<LessonPackage[], Error>({
    queryKey: ['packagesForNotificationWizard'],
    queryFn: fetchActivePackages,
    enabled: ruleWizardOpen,
  });

  useEffect(() => {
    if (!settingsQuery.data) return;
    settingsForm.setFieldsValue({
      mode: settingsQuery.data.mode,
      notifications_enabled: settingsQuery.data.notifications_enabled ?? true,
      quiet_hours_start: settingsQuery.data.quiet_hours_start ?? undefined,
      quiet_hours_end: settingsQuery.data.quiet_hours_end ?? undefined,
      timezone: settingsQuery.data.timezone ?? 'Europe/Moscow',
      daily_cap: settingsQuery.data.daily_cap ?? 3,
      cap_mode: settingsQuery.data.cap_mode ?? 'warn_only',
    });
  }, [settingsForm, settingsQuery.data]);

  const createTemplateMutation = useMutation({
    mutationFn: createNotificationTemplate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notificationTemplates'] });
      message.success(t('pages.notifications.templateCreated'));
      templateForm.resetFields();
      setTemplateModalOpen(false);
    },
    onError: (error: Error) => message.error(t('errors.createFailed', { message: formatApiError(error) })),
  });

  const ruleStatusMutation = useMutation({
    mutationFn: setRuleStatus,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notificationRules'] });
      message.success(t('pages.notifications.ruleUpdated'));
    },
    onError: (error: Error) => message.error(t('errors.updateFailed', { message: formatApiError(error) })),
  });

  const createRuleMutation = useMutation({
    mutationFn: createNotificationRule,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notificationRules'] });
      queryClient.invalidateQueries({ queryKey: ['notificationAudit'] });
      message.success(t('pages.notifications.ruleCreated'));
      ruleForm.resetFields();
      setRulePreview(null);
      setRuleWizardStep(0);
      setRuleWizardOpen(false);
    },
    onError: (error: Error) => message.error(t('errors.createFailed', { message: formatApiError(error) })),
  });

  const previewRuleMutation = useMutation({
    mutationFn: (values: RuleWizardValues) => previewNotificationRule(values, templatesQuery.data ?? []),
    onSuccess: (preview) => {
      setRulePreview(preview);
      setRuleWizardStep(3);
    },
    onError: (error: Error) => message.error(t('errors.updateFailed', { message: formatApiError(error) })),
  });

  const archiveTemplateMutation = useMutation({
    mutationFn: archiveTemplate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notificationTemplates'] });
      message.success(t('pages.notifications.templateArchived'));
    },
    onError: (error: Error) => message.error(t('errors.updateFailed', { message: formatApiError(error) })),
  });

  const materializeMutation = useMutation({
    mutationFn: materializeShadowQueue,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notificationInstances'] });
      message.success(t('pages.notifications.materializeQueued'));
    },
    onError: (error: Error) => message.error(t('errors.updateFailed', { message: formatApiError(error) })),
  });

  const cancelInstanceMutation = useMutation({
    mutationFn: cancelInstance,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notificationInstances'] });
      message.success(t('pages.notifications.instanceCancelled'));
    },
    onError: (error: Error) => message.error(t('errors.updateFailed', { message: formatApiError(error) })),
  });

  const sendNowMutation = useMutation({
    mutationFn: sendInstanceNow,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notificationInstances'] });
      message.success(t('pages.notifications.instanceScheduledNow'));
    },
    onError: (error: Error) => message.error(t('errors.updateFailed', { message: formatApiError(error) })),
  });

  const settingsMutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notificationSettings'] });
      message.success(t('pages.notifications.settingsSaved'));
    },
    onError: (error: Error) => message.error(t('errors.updateFailed', { message: formatApiError(error) })),
  });

  const categoryOptions = useMemo(
    () => CATEGORY_OPTIONS.map((category) => ({ value: category, label: t(`pages.notifications.categories.${category}`) })),
    [t],
  );

  const openRuleWizard = () => {
    setRulePreview(null);
    setRuleWizardStep(0);
    ruleForm.setFieldsValue({
      category: 'lesson_confirmation',
      event_type: 'lesson',
      trigger_type: 'day_offset_at_time',
      trigger_days: -1,
      trigger_local_time: '10:00',
      trigger_minutes: -60,
      audience_scope_type: 'all_learners',
      priority: 'normal',
      message_mode: 'template',
    });
    setRuleWizardOpen(true);
  };

  const closeRuleWizard = () => {
    setRuleWizardOpen(false);
    setRulePreview(null);
    setRuleWizardStep(0);
  };

  const collectValidatedRuleWizardValues = async (): Promise<RuleWizardValues | null> => {
    await ruleForm.validateFields();
    const values = ruleForm.getFieldsValue(true) as RuleWizardValues;
    const validation = getRuleWizardValidation(values);
    if (validation) {
      setRuleWizardStep(validation.step);
      message.warning(t(validation.translationKey));
      return null;
    }
    return values;
  };

  const previewRuleFromWizard = async () => {
    const values = await collectValidatedRuleWizardValues();
    if (!values) return;
    previewRuleMutation.mutate(values);
  };

  const saveRuleFromWizard = async () => {
    const values = await collectValidatedRuleWizardValues();
    if (!values) return;
    createRuleMutation.mutate(values);
  };

  const tabs = [
    {
      key: 'rules',
      label: t('pages.notifications.tabs.rules'),
      children: (
        <RulesTab
          rules={rulesQuery.data ?? []}
          loading={rulesQuery.isLoading}
          error={rulesQuery.error}
          onSetStatus={(ruleId, action) => ruleStatusMutation.mutate({ ruleId, action })}
          onMaterializeShadow={() => materializeMutation.mutate()}
          onCreateRule={openRuleWizard}
          materializing={materializeMutation.isPending}
        />
      ),
    },
    {
      key: 'templates',
      label: t('pages.notifications.tabs.templates'),
      children: (
        <TemplatesTab
          templates={templatesQuery.data ?? []}
          loading={templatesQuery.isLoading}
          error={templatesQuery.error}
          onCreate={() => setTemplateModalOpen(true)}
          onArchive={(templateId) => archiveTemplateMutation.mutate(templateId)}
          archiving={archiveTemplateMutation.isPending}
        />
      ),
    },
    {
      key: 'queue',
      label: t('pages.notifications.tabs.queue'),
      children: (
        <QueueTab
          instances={instancesQuery.data ?? []}
          loading={instancesQuery.isLoading}
          error={instancesQuery.error}
          onCancel={(instanceId) => cancelInstanceMutation.mutate(instanceId)}
          onSendNow={(instanceId) => sendNowMutation.mutate(instanceId)}
          actionPending={cancelInstanceMutation.isPending || sendNowMutation.isPending}
        />
      ),
    },
    {
      key: 'activity',
      label: t('pages.notifications.tabs.activity'),
      children: (
        <ActivityTab
          activity={activityQuery.data ?? []}
          loading={activityQuery.isLoading}
          error={activityQuery.error}
        />
      ),
    },
    {
      key: 'settings',
      label: t('pages.notifications.tabs.settings'),
      children: (
        <SettingsTab
          form={settingsForm}
          loading={settingsQuery.isLoading}
          error={settingsQuery.error}
          saving={settingsMutation.isPending}
          onSubmit={(values) => settingsMutation.mutate(values)}
        />
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title={t('pages.notifications.title')}
        subtitle={t('pages.notifications.subtitle')}
        actions={<Tag color="green">{t('navigation.newBadge')}</Tag>}
      />

      <Alert
        type="info"
        showIcon
        message={t('pages.notifications.pilotNoticeTitle')}
        description={t('pages.notifications.pilotNoticeDescription')}
        style={{ marginBottom: 16 }}
      />

      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as NotificationsTabKey)}
        items={tabs}
      />

      <Modal
        open={templateModalOpen}
        title={t('pages.notifications.createTemplate')}
        okText={t('common.create')}
        cancelText={t('common.cancel')}
        confirmLoading={createTemplateMutation.isPending}
        onCancel={() => setTemplateModalOpen(false)}
        onOk={() => templateForm.submit()}
        destroyOnHidden
      >
        <Form<NotificationTemplateFormValues>
          form={templateForm}
          layout="vertical"
          initialValues={{ category: 'custom' }}
          onFinish={(values) => createTemplateMutation.mutate(values)}
        >
          <Form.Item name="category" label={t('pages.notifications.category')} rules={[{ required: true }]}>
            <Select options={categoryOptions} />
          </Form.Item>
          <Form.Item name="key" label={t('pages.notifications.templateKey')} rules={[{ required: true }]}>
            <Input placeholder="vika_vocabulary_reminder" />
          </Form.Item>
          <Form.Item name="name" label={t('pages.notifications.name')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label={t('pages.notifications.description')}>
            <Input />
          </Form.Item>
          <Form.Item name="body" label={t('pages.notifications.templateBody')} rules={[{ required: true }]}>
            <Input.TextArea rows={6} placeholder={t('pages.notifications.templateBodyPlaceholder')} />
          </Form.Item>
        </Form>
      </Modal>

      <RuleWizardModal
        open={ruleWizardOpen}
        step={ruleWizardStep}
        form={ruleForm}
        templates={templatesQuery.data ?? []}
        learners={learnersQuery.data ?? []}
        groups={groupsQuery.data ?? []}
        packages={packagesQuery.data ?? []}
        categoryOptions={categoryOptions}
        preview={rulePreview}
        loadingLookups={templatesQuery.isLoading || learnersQuery.isLoading || groupsQuery.isLoading || packagesQuery.isLoading}
        previewing={previewRuleMutation.isPending}
        saving={createRuleMutation.isPending}
        onStepChange={setRuleWizardStep}
        onCancel={closeRuleWizard}
        onPreview={previewRuleFromWizard}
        onSave={saveRuleFromWizard}
      />
    </div>
  );
};

interface RuleWizardModalProps {
  open: boolean;
  step: number;
  form: ReturnType<typeof Form.useForm<RuleWizardValues>>[0];
  templates: NotificationTemplate[];
  learners: Learner[];
  groups: LearnerGroup[];
  packages: LessonPackage[];
  categoryOptions: { value: string; label: string }[];
  preview: NotificationPreviewResponse | null;
  loadingLookups: boolean;
  previewing: boolean;
  saving: boolean;
  onStepChange: (step: number) => void;
  onCancel: () => void;
  onPreview: () => void;
  onSave: () => void;
}

const RuleWizardModal: React.FC<RuleWizardModalProps> = ({
  open,
  step,
  form,
  templates,
  learners,
  groups,
  packages,
  categoryOptions,
  preview,
  loadingLookups,
  previewing,
  saving,
  onStepChange,
  onCancel,
  onPreview,
  onSave,
}) => {
  const { t } = useTranslation();
  const category = Form.useWatch('category', form) ?? 'lesson_confirmation';
  const messageMode = Form.useWatch('message_mode', form) ?? 'template';
  const triggerType = Form.useWatch('trigger_type', form) ?? 'day_offset_at_time';
  const eventType = Form.useWatch('event_type', form) ?? 'lesson';
  const audienceScopeType = Form.useWatch('audience_scope_type', form) ?? 'all_learners';
  const filteredTemplates = templates.filter((template) => !template.archived_at && template.category === category);

  const learnerOptions = learners.map((learner) => ({ value: learner.id, label: learner.display_name }));
  const groupOptions = groups
    .filter((group) => group.status === 'active')
    .map((group) => ({ value: group.id, label: `${group.name} (${group.member_count})` }));
  const packageOptions = packages.map((pkg) => ({
    value: pkg.id,
    label: `${pkg.title}${pkg.learner_name ? ` · ${pkg.learner_name}` : ''}`,
  }));

  const templateOptions = filteredTemplates.map((template) => ({
    value: template.id,
    label: `${template.name}${template.system ? ` · ${t('pages.notifications.systemTemplate')}` : ''}`,
  }));

  const insertVariable = (variable: string) => {
    const current = form.getFieldValue('inline_template_body') || '';
    form.setFieldValue('inline_template_body', `${current}${current.endsWith(' ') || current.length === 0 ? '' : ' '}{${variable}}`);
  };

  const validateCurrentStep = async () => {
    const messageFields: Array<keyof RuleWizardValues> = [
      'name',
      'category',
      'message_mode',
      messageMode === 'template' ? 'template_id' : 'inline_template_body',
    ];
    const audienceFields: Array<keyof RuleWizardValues> = audienceScopeType === 'all_learners'
      ? ['audience_scope_type']
      : ['audience_scope_type', 'audience_scope_ids'];
    const triggerFields: Array<keyof RuleWizardValues> = triggerType === 'day_offset_at_time'
      ? ['event_type', 'trigger_type', 'trigger_days', 'trigger_local_time', 'priority']
      : triggerType === 'absolute_datetime'
        ? ['event_type', 'trigger_type', 'trigger_absolute_datetime', 'priority']
        : ['event_type', 'trigger_type', 'trigger_minutes', 'priority'];
    const stepFields: Array<Array<keyof RuleWizardValues>> = [
      messageFields,
      triggerFields,
      audienceFields,
    ];
    await form.validateFields(stepFields[step] ?? []);
    onStepChange(Math.min(step + 1, 3));
  };

  return (
    <Modal
      open={open}
      title={t('pages.notifications.ruleWizard.title')}
      width={920}
      destroyOnHidden
      onCancel={onCancel}
      footer={(
        <Space>
          <Button onClick={onCancel}>{t('common.cancel')}</Button>
          {step > 0 && (
            <Button onClick={() => onStepChange(step - 1)}>
              {t('pages.notifications.ruleWizard.back')}
            </Button>
          )}
          {step < 3 && (
            <Button type="primary" onClick={step === 2 ? onPreview : validateCurrentStep} loading={previewing}>
              {step === 2 ? t('pages.notifications.ruleWizard.preview') : t('pages.notifications.ruleWizard.next')}
            </Button>
          )}
          {step === 3 && (
            <Button type="primary" onClick={onSave} loading={saving}>
              {t('pages.notifications.ruleWizard.saveDraft')}
            </Button>
          )}
        </Space>
      )}
    >
      <Steps
        current={step}
        onChange={(nextStep) => {
          if (nextStep <= step) {
            onStepChange(nextStep);
          }
        }}
        style={{ marginBottom: 24 }}
        items={[
          { title: t('pages.notifications.ruleWizard.steps.message') },
          { title: t('pages.notifications.ruleWizard.steps.trigger') },
          { title: t('pages.notifications.ruleWizard.steps.audience') },
          { title: t('pages.notifications.ruleWizard.steps.preview') },
        ]}
      />

      <Form<RuleWizardValues>
        form={form}
        layout="vertical"
        initialValues={{
          category: 'lesson_confirmation',
          event_type: 'lesson',
          trigger_type: 'day_offset_at_time',
          trigger_days: -1,
          trigger_local_time: '10:00',
          trigger_minutes: -60,
          audience_scope_type: 'all_learners',
          priority: 'normal',
          message_mode: 'template',
        }}
      >
        {step === 0 && (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Row gutter={16}>
              <Col xs={24} md={12}>
                <Form.Item name="name" label={t('pages.notifications.name')} rules={[{ required: true }]}>
                  <Input placeholder={t('pages.notifications.ruleWizard.namePlaceholder')} />
                </Form.Item>
              </Col>
              <Col xs={24} md={12}>
                <Form.Item name="category" label={t('pages.notifications.category')} rules={[{ required: true }]}>
                  <Select options={categoryOptions} onChange={() => form.setFieldValue('template_id', undefined)} />
                </Form.Item>
              </Col>
            </Row>

            <Form.Item name="message_mode" label={t('pages.notifications.ruleWizard.messageSource')} rules={[{ required: true }]}>
              <Select
                options={[
                  { value: 'template', label: t('pages.notifications.ruleWizard.useTemplate') },
                  { value: 'inline', label: t('pages.notifications.ruleWizard.writeCustom') },
                ]}
              />
            </Form.Item>

            {messageMode === 'template' ? (
              <Form.Item name="template_id" label={t('pages.notifications.ruleWizard.template')} rules={[{ required: true }]}>
                <Select
                  loading={loadingLookups}
                  options={templateOptions}
                  placeholder={t('pages.notifications.ruleWizard.templatePlaceholder')}
                  showSearch
                  optionFilterProp="label"
                />
              </Form.Item>
            ) : (
              <>
                <VariableButtons onInsert={insertVariable} />
                <Form.Item name="inline_template_body" label={t('pages.notifications.templateBody')} rules={[{ required: true }]}>
                  <Input.TextArea rows={6} placeholder={t('pages.notifications.templateBodyPlaceholder')} />
                </Form.Item>
              </>
            )}
          </Space>
        )}

        {step === 1 && (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Row gutter={16}>
              <Col xs={24} md={8}>
                <Form.Item name="event_type" label={t('pages.notifications.ruleWizard.eventType')} rules={[{ required: true }]}>
                  <Select
                    options={[
                      { value: 'lesson', label: t('pages.notifications.eventTypes.lesson') },
                      { value: 'package', label: t('pages.notifications.eventTypes.package') },
                      { value: 'custom_date', label: t('pages.notifications.eventTypes.custom_date') },
                    ]}
                  />
                </Form.Item>
              </Col>
              <Col xs={24} md={8}>
                <Form.Item name="trigger_type" label={t('pages.notifications.trigger')} rules={[{ required: true }]}>
                  <Select
                    options={[
                      { value: 'day_offset_at_time', label: t('pages.notifications.triggerTypes.day_offset_at_time') },
                      { value: 'relative_offset', label: t('pages.notifications.triggerTypes.relative_offset') },
                      { value: 'after_event_offset', label: t('pages.notifications.triggerTypes.after_event_offset') },
                      { value: 'absolute_datetime', label: t('pages.notifications.triggerTypes.absolute_datetime') },
                    ]}
                  />
                </Form.Item>
              </Col>
              <Col xs={24} md={8}>
                <Form.Item name="priority" label={t('pages.notifications.ruleWizard.priority')} rules={[{ required: true }]}>
                  <Select
                    options={[
                      { value: 'low', label: t('pages.notifications.priorities.low') },
                      { value: 'normal', label: t('pages.notifications.priorities.normal') },
                      { value: 'high', label: t('pages.notifications.priorities.high') },
                    ]}
                  />
                </Form.Item>
              </Col>
            </Row>

            {triggerType === 'day_offset_at_time' && (
              <Row gutter={16}>
                <Col xs={24} md={12}>
                  <Form.Item name="trigger_days" label={t('pages.notifications.ruleWizard.dayOffset')} rules={[{ required: true }]}>
                    <InputNumber min={-30} max={30} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item name="trigger_local_time" label={t('pages.notifications.ruleWizard.localTime')} rules={[{ required: true }]}>
                    <Input placeholder="10:00" />
                  </Form.Item>
                </Col>
              </Row>
            )}

            {(triggerType === 'relative_offset' || triggerType === 'after_event_offset') && (
              <Form.Item name="trigger_minutes" label={t('pages.notifications.ruleWizard.minutesOffset')} rules={[{ required: true }]}>
                <InputNumber min={-10080} max={10080} style={{ width: '100%' }} />
              </Form.Item>
            )}

            {triggerType === 'absolute_datetime' && (
              <Form.Item name="trigger_absolute_datetime" label={t('pages.notifications.ruleWizard.absoluteDatetime')} rules={[{ required: true }]}>
                <Input placeholder="2026-04-10T18:00:00+03:00" />
              </Form.Item>
            )}

            {category === 'lesson_confirmation' && (
              <Form.Item name="combine_policy_key" label={t('pages.notifications.ruleWizard.combinePolicy')}>
                <Select
                  allowClear
                  options={[
                    { value: 'lesson_confirmation_homework', label: t('pages.notifications.ruleWizard.combineLessonHomework') },
                  ]}
                />
              </Form.Item>
            )}

            {eventType === 'custom_date' && triggerType !== 'absolute_datetime' && (
              <Alert type="warning" showIcon message={t('pages.notifications.ruleWizard.customDateNeedsAbsoluteTrigger')} />
            )}
          </Space>
        )}

        {step === 2 && (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Form.Item name="audience_scope_type" label={t('pages.notifications.ruleWizard.audienceScope')} rules={[{ required: true }]}>
              <Select
                options={[
                  { value: 'all_learners', label: t('pages.notifications.audienceScopes.all_learners') },
                  { value: 'learner', label: t('pages.notifications.audienceScopes.learner') },
                  { value: 'group', label: t('pages.notifications.audienceScopes.group') },
                  { value: 'package', label: t('pages.notifications.audienceScopes.package') },
                ]}
                onChange={() => form.setFieldValue('audience_scope_ids', [])}
              />
            </Form.Item>

            {audienceScopeType !== 'all_learners' && (
              <Form.Item name="audience_scope_ids" label={t('pages.notifications.ruleWizard.audienceItems')} rules={[{ required: true }]}>
                <Select
                  mode="multiple"
                  loading={loadingLookups}
                  showSearch
                  optionFilterProp="label"
                  options={audienceScopeType === 'learner' ? learnerOptions : audienceScopeType === 'group' ? groupOptions : packageOptions}
                />
              </Form.Item>
            )}

            <Form.Item name="excluded_learner_ids" label={t('pages.notifications.ruleWizard.excludedLearners')}>
              <Select
                mode="multiple"
                loading={loadingLookups}
                showSearch
                optionFilterProp="label"
                options={learnerOptions}
                placeholder={t('pages.notifications.ruleWizard.excludedLearnersPlaceholder')}
              />
            </Form.Item>
          </Space>
        )}

        {step === 3 && (
          <PreviewStep preview={preview} loading={previewing} />
        )}
      </Form>
    </Modal>
  );
};

const VariableButtons: React.FC<{ onInsert: (variable: string) => void }> = ({ onInsert }) => {
  const { t } = useTranslation();
  const variables = [
    ['student_name', t('pages.notifications.variables.student_name')],
    ['lesson_date', t('pages.notifications.variables.lesson_date')],
    ['lesson_time', t('pages.notifications.variables.lesson_time')],
    ['lesson_datetime', t('pages.notifications.variables.lesson_datetime')],
    ['package_title', t('pages.notifications.variables.package_title')],
    ['teacher_name', t('pages.notifications.variables.teacher_name')],
  ];

  return (
    <Space wrap>
      <Typography.Text type="secondary">{t('pages.notifications.ruleWizard.insertVariable')}</Typography.Text>
      {variables.map(([variable, label]) => (
        <Button key={variable} size="small" onClick={() => onInsert(variable)}>
          {label}
        </Button>
      ))}
    </Space>
  );
};

const PreviewStep: React.FC<{ preview: NotificationPreviewResponse | null; loading: boolean }> = ({ preview, loading }) => {
  const { t } = useTranslation();

  if (loading) {
    return <Card loading />;
  }

  if (!preview) {
    return <Alert type="info" showIcon message={t('pages.notifications.ruleWizard.previewEmpty')} />;
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      {preview.warnings.length > 0 && (
        <Alert
          type="warning"
          showIcon
          message={t('pages.notifications.ruleWizard.previewWarnings')}
          description={preview.warnings.join(', ')}
        />
      )}
      <Card>
        <Typography.Title level={5}>{t('pages.notifications.ruleWizard.previewSummary')}</Typography.Title>
        <Typography.Paragraph>
          {t('pages.notifications.ruleWizard.previewCount', { count: preview.instances.length })}
        </Typography.Paragraph>
        <Divider />
        <Space direction="vertical" style={{ width: '100%' }}>
          {preview.instances.slice(0, 10).map((instance, index) => (
            <Card key={`${instance.kind}-${instance.rule_id ?? index}-${instance.learner_id}-${instance.event_id ?? index}`} size="small">
              <Space direction="vertical" size={4}>
                <Space wrap>
                  <Tag>{instance.kind}</Tag>
                  <Tag color={getInstanceStatusColor(instance.status)}>{t(`pages.notifications.instanceStatus.${instance.status}`)}</Tag>
                  {instance.category && <Tag>{t(`pages.notifications.categories.${instance.category}`)}</Tag>}
                </Space>
                <span>
                  {t('pages.notifications.learner')} #{instance.learner_id} · {dayjs(instance.effective_scheduled_for).format('YYYY-MM-DD HH:mm')}
                </span>
                {instance.warnings.length > 0 && (
                  <Typography.Text type="warning">
                    {instance.warnings.join(', ')}
                  </Typography.Text>
                )}
                {instance.components.length > 0 && (
                  <Typography.Text type="secondary">
                    {t('pages.notifications.ruleWizard.components')}: {instance.components.map((component) => t(`pages.notifications.categories.${component.category}`)).join(', ')}
                  </Typography.Text>
                )}
              </Space>
            </Card>
          ))}
        </Space>
      </Card>
    </Space>
  );
};

interface RulesTabProps {
  rules: NotificationRule[];
  loading: boolean;
  error: Error | null;
  materializing: boolean;
  onSetStatus: (ruleId: number, action: 'activate' | 'pause' | 'archive') => void;
  onMaterializeShadow: () => void;
  onCreateRule: () => void;
}

const RulesTab: React.FC<RulesTabProps> = ({
  rules,
  loading,
  error,
  materializing,
  onSetStatus,
  onMaterializeShadow,
  onCreateRule,
}) => {
  const { t } = useTranslation();

  const columns: TableProps<NotificationRule>['columns'] = [
    {
      title: t('pages.notifications.name'),
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: t('pages.notifications.category'),
      dataIndex: 'category',
      key: 'category',
      render: (category: string) => <Tag>{t(`pages.notifications.categories.${category}`)}</Tag>,
    },
    {
      title: t('pages.notifications.status'),
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => <Tag color={getRuleStatusColor(status)}>{t(`pages.notifications.ruleStatus.${status}`)}</Tag>,
    },
    {
      title: t('pages.notifications.trigger'),
      key: 'trigger',
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <span>{t(`pages.notifications.eventTypes.${record.event_type}`)}</span>
          <span style={{ color: '#8c8c8c' }}>{t(`pages.notifications.triggerTypes.${record.trigger_type}`)}</span>
        </Space>
      ),
    },
    {
      title: t('pages.notifications.audience'),
      key: 'assignments',
      render: (_, record) => record.assignments.length ? (
        <Space wrap>
          {record.assignments.map((assignment, index) => (
            <Tag key={`${assignment.scope_type}-${assignment.scope_id ?? 'all'}-${index}`} color={assignment.is_exclusion ? 'red' : 'blue'}>
              {assignment.is_exclusion ? '-' : '+'} {assignment.scope_type}{assignment.scope_id ? ` #${assignment.scope_id}` : ''}
            </Tag>
          ))}
        </Space>
      ) : '-',
    },
    {
      title: t('common.actions'),
      key: 'actions',
      render: (_, record) => (
        <Space wrap>
          {record.status !== 'active' && record.status !== 'archived' && (
            <Button type="link" onClick={() => onSetStatus(record.id, 'activate')}>
              {t('pages.notifications.activate')}
            </Button>
          )}
          {record.status === 'active' && (
            <Button type="link" onClick={() => onSetStatus(record.id, 'pause')}>
              {t('pages.notifications.pause')}
            </Button>
          )}
          {record.status !== 'archived' && (
            <Button type="link" danger onClick={() => onSetStatus(record.id, 'archive')}>
              {t('pages.notifications.archive')}
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Space wrap>
        <Button icon={<ReloadOutlined />} onClick={onMaterializeShadow} loading={materializing}>
          {t('pages.notifications.materializeShadow')}
        </Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={onCreateRule}>
          {t('pages.notifications.createRuleWizard')}
        </Button>
      </Space>
      <NoticeError error={error} />
      <ResponsiveDataView<NotificationRule>
        data={rules}
        loading={loading}
        columns={columns}
        rowKey="id"
        emptyText={t('pages.notifications.noRules')}
        emptyDescription={t('pages.notifications.noRulesDescription')}
        renderCard={(rule) => (
          <Card key={rule.id} title={rule.name} size="small" style={{ marginBottom: 12 }}>
            <Space direction="vertical">
              <Tag color={getRuleStatusColor(rule.status)}>{t(`pages.notifications.ruleStatus.${rule.status}`)}</Tag>
              <span>{t(`pages.notifications.categories.${rule.category}`)}</span>
              <Space wrap>
                {rule.status !== 'active' && rule.status !== 'archived' && (
                  <Button size="small" onClick={() => onSetStatus(rule.id, 'activate')}>{t('pages.notifications.activate')}</Button>
                )}
                {rule.status === 'active' && (
                  <Button size="small" onClick={() => onSetStatus(rule.id, 'pause')}>{t('pages.notifications.pause')}</Button>
                )}
              </Space>
            </Space>
          </Card>
        )}
        pagination={false}
      />
    </Space>
  );
};

interface TemplatesTabProps {
  templates: NotificationTemplate[];
  loading: boolean;
  error: Error | null;
  archiving: boolean;
  onCreate: () => void;
  onArchive: (templateId: number) => void;
}

const TemplatesTab: React.FC<TemplatesTabProps> = ({ templates, loading, error, archiving, onCreate, onArchive }) => {
  const { t } = useTranslation();

  const columns: TableProps<NotificationTemplate>['columns'] = [
    {
      title: t('pages.notifications.name'),
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: t('pages.notifications.category'),
      dataIndex: 'category',
      key: 'category',
      render: (category: string) => <Tag>{t(`pages.notifications.categories.${category}`)}</Tag>,
    },
    {
      title: t('pages.notifications.version'),
      dataIndex: 'version',
      key: 'version',
    },
    {
      title: t('pages.notifications.source'),
      key: 'system',
      render: (_, record) => (
        <Tag color={record.system ? 'purple' : 'blue'}>
          {record.system ? t('pages.notifications.systemTemplate') : t('pages.notifications.tenantTemplate')}
        </Tag>
      ),
    },
    {
      title: t('common.actions'),
      key: 'actions',
      render: (_, record) => (
        <Button
          type="link"
          danger
          disabled={record.system || Boolean(record.archived_at)}
          loading={archiving}
          onClick={() => onArchive(record.id)}
        >
          {t('pages.notifications.archive')}
        </Button>
      ),
    },
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Button type="primary" icon={<PlusOutlined />} onClick={onCreate}>
        {t('pages.notifications.createTemplate')}
      </Button>
      <NoticeError error={error} />
      <ResponsiveDataView<NotificationTemplate>
        data={templates}
        loading={loading}
        columns={columns}
        rowKey="id"
        emptyText={t('pages.notifications.noTemplates')}
        emptyDescription={t('pages.notifications.noTemplatesDescription')}
        renderCard={(template) => (
          <Card key={template.id} title={template.name} size="small" style={{ marginBottom: 12 }}>
            <Space direction="vertical">
              <Tag>{t(`pages.notifications.categories.${template.category}`)}</Tag>
              <span>{template.body}</span>
            </Space>
          </Card>
        )}
        pagination={false}
      />
    </Space>
  );
};

interface QueueTabProps {
  instances: NotificationInstance[];
  loading: boolean;
  error: Error | null;
  actionPending: boolean;
  onCancel: (instanceId: number) => void;
  onSendNow: (instanceId: number) => void;
}

const QueueTab: React.FC<QueueTabProps> = ({ instances, loading, error, actionPending, onCancel, onSendNow }) => {
  const { t } = useTranslation();

  const columns: TableProps<NotificationInstance>['columns'] = [
    {
      title: t('pages.notifications.scheduledFor'),
      dataIndex: 'effective_scheduled_for',
      key: 'effective_scheduled_for',
      render: (value: string) => dayjs(value).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: t('pages.notifications.learner'),
      dataIndex: 'learner_display_name',
      key: 'learner_display_name',
      render: (value: string | null) => value || '-',
    },
    {
      title: t('pages.notifications.category'),
      dataIndex: 'category',
      key: 'category',
      render: (category: string) => <Tag>{t(`pages.notifications.categories.${category}`)}</Tag>,
    },
    {
      title: t('pages.notifications.status'),
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => <Tag color={getInstanceStatusColor(status)}>{t(`pages.notifications.instanceStatus.${status}`)}</Tag>,
    },
    {
      title: t('pages.notifications.delivery'),
      key: 'delivery',
      render: (_, record) => record.latest_attempt ? (
        <Space direction="vertical" size={0}>
          <span>{record.latest_attempt.status}</span>
          {record.latest_attempt.provider_message_id && <span>#{record.latest_attempt.provider_message_id}</span>}
        </Space>
      ) : '-',
    },
    {
      title: t('common.actions'),
      key: 'actions',
      render: (_, record) => (
        <Space wrap>
          <Button
            type="link"
            disabled={['sent', 'processing', 'shadow'].includes(record.status)}
            loading={actionPending}
            onClick={() => onSendNow(record.id)}
          >
            {t('pages.notifications.sendNow')}
          </Button>
          <Button
            type="link"
            danger
            disabled={['sent', 'processing'].includes(record.status)}
            loading={actionPending}
            onClick={() => onCancel(record.id)}
          >
            {t('common.cancel')}
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <NoticeError error={error} />
      <ResponsiveDataView<NotificationInstance>
        data={instances}
        loading={loading}
        columns={columns}
        rowKey="id"
        emptyText={t('pages.notifications.noInstances')}
        emptyDescription={t('pages.notifications.noInstancesDescription')}
        renderCard={(instance) => (
          <Card key={instance.id} title={instance.learner_display_name || `#${instance.id}`} size="small" style={{ marginBottom: 12 }}>
            <Space direction="vertical">
              <span>{dayjs(instance.effective_scheduled_for).format('YYYY-MM-DD HH:mm')}</span>
              <Tag color={getInstanceStatusColor(instance.status)}>{t(`pages.notifications.instanceStatus.${instance.status}`)}</Tag>
              <Space wrap>
                <Button size="small" disabled={['sent', 'processing', 'shadow'].includes(instance.status)} onClick={() => onSendNow(instance.id)}>
                  {t('pages.notifications.sendNow')}
                </Button>
                <Button size="small" danger disabled={['sent', 'processing'].includes(instance.status)} onClick={() => onCancel(instance.id)}>
                  {t('common.cancel')}
                </Button>
              </Space>
            </Space>
          </Card>
        )}
        pagination={false}
      />
    </Space>
  );
};

interface ActivityTabProps {
  activity: NotificationActivity[];
  loading: boolean;
  error: Error | null;
}

const ActivityTab: React.FC<ActivityTabProps> = ({ activity, loading, error }) => {
  const { t } = useTranslation();

  const columns: TableProps<NotificationActivity>['columns'] = [
    {
      title: t('pages.notifications.occurredAt'),
      dataIndex: 'occurred_at',
      key: 'occurred_at',
      render: (value: string | null) => value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '-',
    },
    {
      title: t('pages.notifications.activityType'),
      dataIndex: 'activity_type',
      key: 'activity_type',
      render: (value: string) => <Tag>{value}</Tag>,
    },
    {
      title: t('pages.notifications.learner'),
      dataIndex: 'learner_display_name',
      key: 'learner_display_name',
      render: (value: string | null) => value || '-',
    },
    {
      title: t('pages.notifications.status'),
      dataIndex: 'status',
      key: 'status',
    },
    {
      title: t('pages.notifications.details'),
      key: 'details',
      render: (_, record) => record.error_message || record.response_value || record.provider_message_id || '-',
    },
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <NoticeError error={error} />
      <ResponsiveDataView<NotificationActivity>
        data={activity}
        loading={loading}
        columns={columns}
        rowKey={(record) => `${record.activity_type}-${record.activity_id}`}
        emptyText={t('pages.notifications.noActivity')}
        emptyDescription={t('pages.notifications.noActivityDescription')}
        renderCard={(item) => (
          <Card key={`${item.activity_type}-${item.activity_id}`} title={item.learner_display_name || item.activity_type} size="small" style={{ marginBottom: 12 }}>
            <Space direction="vertical">
              <span>{item.occurred_at ? dayjs(item.occurred_at).format('YYYY-MM-DD HH:mm') : '-'}</span>
              <span>{item.status}</span>
              <span>{item.error_message || item.response_value || item.provider_message_id || '-'}</span>
            </Space>
          </Card>
        )}
        pagination={false}
      />
    </Space>
  );
};

interface SettingsTabProps {
  form: ReturnType<typeof Form.useForm<NotificationSettingsFormValues>>[0];
  loading: boolean;
  error: Error | null;
  saving: boolean;
  onSubmit: (values: NotificationSettingsFormValues) => void;
}

const SettingsTab: React.FC<SettingsTabProps> = ({ form, loading, error, saving, onSubmit }) => {
  const { t } = useTranslation();

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <NoticeError error={error} />
      <Card loading={loading}>
        <Form<NotificationSettingsFormValues> form={form} layout="vertical" onFinish={onSubmit}>
          <Row gutter={16}>
            <Col xs={24} md={8}>
              <Form.Item name="mode" label={t('pages.notifications.systemMode')} rules={[{ required: true }]}>
                <Select
                  options={[
                    { value: 'legacy', label: t('pages.notifications.modes.legacy') },
                    { value: 'shadow', label: t('pages.notifications.modes.shadow') },
                    { value: 'new', label: t('pages.notifications.modes.new') },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item name="daily_cap" label={t('pages.notifications.dailyCap')}>
                <InputNumber min={0} max={50} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item name="cap_mode" label={t('pages.notifications.capMode')}>
                <Select
                  options={[
                    { value: 'warn_only', label: t('pages.notifications.capModes.warn_only') },
                    { value: 'enforce', label: t('pages.notifications.capModes.enforce') },
                  ]}
                />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col xs={24} md={8}>
              <Form.Item name="quiet_hours_start" label={t('pages.notifications.quietHoursStart')}>
                <Input placeholder="21:00" />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item name="quiet_hours_end" label={t('pages.notifications.quietHoursEnd')}>
                <Input placeholder="09:00" />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item name="timezone" label={t('pages.notifications.timezone')}>
                <Input placeholder="Europe/Moscow" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="notifications_enabled" valuePropName="checked" label={t('pages.notifications.notificationsEnabled')}>
            <Switch />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={saving}>
            {t('common.save')}
          </Button>
        </Form>
      </Card>
    </Space>
  );
};

const NoticeError: React.FC<{ error: Error | null }> = ({ error }) => {
  const { t } = useTranslation();

  if (!error) {
    return null;
  }

  return (
    <Alert
      type="error"
      showIcon
      message={t('errors.loadFailed', { message: '' })}
      description={error.message}
    />
  );
};

const getRuleStatusColor = (status: string) => {
  switch (status) {
    case 'active': return 'green';
    case 'draft': return 'default';
    case 'paused': return 'orange';
    case 'archived': return 'red';
    default: return 'default';
  }
};

const getInstanceStatusColor = (status: string) => {
  switch (status) {
    case 'sent': return 'green';
    case 'scheduled': return 'blue';
    case 'processing': return 'processing';
    case 'failed': return 'red';
    case 'cancelled': return 'orange';
    case 'shadow': return 'purple';
    case 'skipped': return 'default';
    case 'suppressed': return 'default';
    case 'expired': return 'default';
    default: return 'default';
  }
};

export default Notifications;
