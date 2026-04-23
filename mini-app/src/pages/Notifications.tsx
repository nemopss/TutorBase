import React, { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  Col,
  Collapse,
  Descriptions,
  Divider,
  Dropdown,
  Drawer,
  Empty,
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
import { MoreOutlined, PlusOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { useTranslation } from 'react-i18next';
import PageHeader from '../components/common/PageHeader';
import ResponsiveDataView from '../components/common/ResponsiveDataView';
import TenantContextRequired from '../components/common/TenantContextRequired';
import { useAuth } from '../auth/AuthProvider';
import api from '../services/api';

type NotificationsTabKey = 'rules' | 'templates' | 'queue' | 'activity' | 'settings';

interface NotificationAssignment {
  scope_type: string;
  scope_id?: number | null;
  is_exclusion: boolean;
}

interface NotificationRule {
  id: number;
  preset_key?: string | null;
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
  provider_chat_id?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  started_at?: string | null;
  sent_at?: string | null;
  finished_at?: string | null;
  created_at?: string | null;
  attempt_no?: number;
  channel?: string;
  provider?: string;
}

interface NotificationInstanceComponent {
  component_id: number;
  rule_id?: number | null;
  category: string;
  template_id?: number | null;
  component_key: string;
  metadata: Record<string, unknown>;
}

interface NotificationInstance {
  id: number;
  rule_id?: number | null;
  category: string;
  event_type: string;
  event_id?: number | null;
  event_key: string;
  recipient_type: string;
  recipient_id: number;
  learner_id?: number | null;
  learner_display_name?: string | null;
  scheduled_for: string;
  effective_scheduled_for: string;
  status: string;
  status_reason?: string | null;
  delivery_enabled: boolean;
  priority: string;
  channel: string;
  dedupe_key: string;
  combination_key?: string | null;
  explanation: Record<string, unknown>;
  components: NotificationInstanceComponent[];
  latest_attempt?: NotificationDeliveryAttempt | null;
  created_at?: string | null;
  updated_at?: string | null;
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
  metadata: Record<string, unknown>;
}

interface NotificationActivityAcknowledgement {
  id: number;
  tenant_id: number;
  activity_type: 'teacher_alert';
  activity_id: number;
  acknowledged_by_user_id?: number | null;
  acknowledged_at: string;
  created_at?: string | null;
  updated_at?: string | null;
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

interface NotificationTaskTriggerResult {
  task_id: string;
  task_name: string;
  tenant_id: number;
  limit: number;
  job_type?: string | null;
  queued: boolean;
}

interface LearnerNotificationMode {
  learner_id: number;
  display_name: string;
  mode_override: string;
  effective_mode: string;
  updated_at?: string | null;
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
  confirm_global_new?: boolean;
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
  preset_key?: 'lesson_confirmation' | 'homework' | 'package_renewal' | 'custom_message';
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

interface NotificationPilotSummary {
  globalMode: string;
  totalLearners: number;
  learnerNewCount: number;
  learnerShadowCount: number;
  plannedCount: number;
  dueDeliveryCount: number;
  attentionAlertCount: number;
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

const ACTIVE_QUEUE_INSTANCE_STATUSES = new Set([
  'shadow',
  'scheduled',
  'processing',
  'skipped',
  'suppressed',
]);

const isQueueInstance = (instance: NotificationInstance): boolean => ACTIVE_QUEUE_INSTANCE_STATUSES.has(instance.status);

const fetchNotificationRules = async (): Promise<NotificationRule[]> => {
  const { data } = await api.get('/notifications/rules', {
    params: { include_archived: true },
  });
  return data;
};

const fetchNotificationTemplates = async (): Promise<NotificationTemplate[]> => {
  const { data } = await api.get('/notifications/templates');
  return data;
};

const fetchNotificationInstances = async (): Promise<NotificationInstance[]> => {
  const { data } = await api.get('/notifications/instances', { params: { limit: 100, queue_only: true } });
  return data;
};

const fetchNotificationInstanceDetail = async (instanceId: number): Promise<NotificationInstance> => {
  const { data } = await api.get(`/notifications/instances/${instanceId}`);
  return data;
};

const fetchNotificationActivity = async (): Promise<NotificationActivity[]> => {
  const { data } = await api.get('/notifications/activity', { params: { limit: 100 } });
  return data;
};

const fetchNotificationActivityAcknowledgements = async (): Promise<NotificationActivityAcknowledgement[]> => {
  try {
    const { data } = await api.get('/notifications/activity-acknowledgements', {
      params: { activity_type: 'teacher_alert' },
    });
    return data;
  } catch (error) {
    const statusCode = (
      error as Error & { response?: { status?: number } }
    ).response?.status;
    if (statusCode === 404) {
      return [];
    }
    throw error;
  }
};

const fetchNotificationSettings = async (): Promise<NotificationSettings> => {
  const { data } = await api.get('/notifications/settings');
  return data;
};

const fetchLearnerNotificationModes = async (): Promise<LearnerNotificationMode[]> => {
  const { data } = await api.get('/notifications/learner-modes');
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

const setRuleStatus = async ({ ruleId, action }: { ruleId: number; action: 'activate' | 'pause' | 'archive' | 'restore' }): Promise<NotificationRule> => {
  const endpointAction = action === 'restore' ? 'pause' : action;
  const { data } = await api.post(`/notifications/rules/${ruleId}/${endpointAction}`);
  return data;
};

const archiveTemplate = async (templateId: number): Promise<NotificationTemplate> => {
  const { data } = await api.post(`/notifications/templates/${templateId}/archive`);
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

const updateLearnerNotificationMode = async ({
  learnerId,
  modeOverride,
}: {
  learnerId: number;
  modeOverride: string;
}): Promise<LearnerNotificationMode> => {
  const { data } = await api.patch(`/notifications/learner-modes/${learnerId}`, {
    mode_override: modeOverride,
  });
  return data;
};

const triggerNotificationJobProcessing = async (): Promise<NotificationTaskTriggerResult> => {
  const { data } = await api.post('/notifications/pilot/process-jobs', {
    limit: 20,
  });
  return data;
};

const triggerNotificationDeliveryTick = async (): Promise<NotificationTaskTriggerResult> => {
  const { data } = await api.post('/notifications/pilot/deliver-now', {
    limit: 100,
  });
  return data;
};

const acknowledgeNotificationActivity = async (activityId: number): Promise<NotificationActivityAcknowledgement> => {
  const { data } = await api.post('/notifications/activity-acknowledgements', {
    activity_type: 'teacher_alert',
    activity_id: activityId,
  });
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

type TranslateFn = (key: string, options?: Record<string, unknown>) => string;

const getWarningLabel = (warning: string, t: TranslateFn): string => {
  switch (warning) {
    case 'quiet_hours_shifted':
      return t('pages.notifications.warningLabels.quietHoursShifted');
    case 'calendar_conflict:active_lessons_same_slot':
      return t('pages.notifications.warningLabels.calendarConflict');
    case 'combined':
      return t('pages.notifications.warningLabels.combined');
    case 'homework_inherited':
      return t('pages.notifications.warningLabels.homeworkInherited');
    default:
      return warning;
  }
};

const getStatusReasonLabel = (reason: string | null | undefined, t: TranslateFn): string => {
  if (!reason) return '—';
  switch (reason) {
    case 'missing_contact':
      return t('pages.notifications.statusReasons.missingContact');
    case 'learner_notifications_disabled':
      return t('pages.notifications.statusReasons.learnerNotificationsDisabled');
    case 'preferences_notifications_disabled':
      return t('pages.notifications.statusReasons.preferencesNotificationsDisabled');
    case 'category_disabled':
      return t('pages.notifications.statusReasons.categoryDisabled');
    case 'package_not_active':
      return t('pages.notifications.statusReasons.packageNotActive');
    case 'lesson_not_schedulable':
      return t('pages.notifications.statusReasons.lessonNotSchedulable');
    case 'lesson_has_no_homework':
      return t('pages.notifications.statusReasons.lessonHasNoHomework');
    case 'manual_cancelled':
      return t('pages.notifications.statusReasons.manualCancelled');
    case 'manual_send_now':
      return t('pages.notifications.statusReasons.manualSendNow');
    case 'cancelled_from_notifications_ui':
      return t('pages.notifications.statusReasons.cancelledFromUi');
    default:
      return reason;
  }
};

const extractInstanceWarnings = (instance: NotificationInstance): string[] => {
  const explanationWarnings = Array.isArray(instance.explanation?.warnings)
    ? (instance.explanation.warnings as string[])
    : [];

  const componentWarnings = Array.isArray(instance.explanation?.component_explanations)
    ? (instance.explanation.component_explanations as Array<Record<string, unknown>>).flatMap((item) => (
      Array.isArray(item.warnings) ? (item.warnings as string[]) : []
    ))
    : [];

  const warnings = [...explanationWarnings, ...componentWarnings];
  if (instance.explanation?.calendar_conflict) {
    warnings.push('calendar_conflict:active_lessons_same_slot');
  }
  if (instance.combination_key) {
    warnings.push('combined');
  }
  return [...new Set(warnings)];
};

const formatDateTime = (value?: string | null): string => (value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '—');

const getActivityTypeLabel = (activityType: string, t: TranslateFn): string => {
  switch (activityType) {
    case 'delivery_attempt':
      return t('pages.notifications.activityTypes.deliveryAttempt');
    case 'response':
      return t('pages.notifications.activityTypes.response');
    case 'teacher_alert':
      return t('pages.notifications.activityTypes.teacherAlert');
    default:
      return activityType;
  }
};

const getInstanceStatusLabel = (status: string, t: TranslateFn): string => {
  switch (status) {
    case 'sent':
    case 'scheduled':
    case 'processing':
    case 'failed':
    case 'cancelled':
    case 'shadow':
    case 'skipped':
    case 'suppressed':
    case 'expired':
      return t(`pages.notifications.instanceStatus.${status}`);
    default:
      return status;
  }
};

const getActivityStatusLabel = (status: string, t: TranslateFn): string => {
  switch (status) {
    case 'handled':
      return t('pages.notifications.activityStatuses.handled');
    case 'requires_attention':
      return t('pages.notifications.activityStatuses.requiresAttention');
    case 'confirmed':
      return t('pages.notifications.activityStatuses.confirmed');
    case 'declined':
      return t('pages.notifications.activityStatuses.declined');
    case 'needs_discussion':
      return t('pages.notifications.activityStatuses.needsDiscussion');
    default:
      return getInstanceStatusLabel(status, t);
  }
};

const getActivityStatusColor = (status: string): string => {
  switch (status) {
    case 'handled':
      return 'green';
    case 'requires_attention':
    case 'declined':
      return 'red';
    case 'confirmed':
    case 'sent':
      return 'green';
    case 'needs_discussion':
      return 'orange';
    case 'failed':
      return 'red';
    default:
      return 'blue';
  }
};

const getActivityDetails = (activity: NotificationActivity, t: TranslateFn): string => {
  if (activity.activity_type === 'teacher_alert') {
    if (activity.metadata?.alert_code === 'package_renewal_needs_discussion') {
      return t('pages.notifications.activityDetails.packageRenewalNeedsDiscussion');
    }
    const responseText = typeof activity.metadata?.response_text === 'string' ? activity.metadata.response_text : null;
    if (responseText) {
      return t('pages.notifications.activityDetails.lessonDeclinedWithReason', { reason: responseText });
    }
    return t('pages.notifications.activityDetails.lessonDeclined');
  }

  if (activity.activity_type === 'response') {
    if (activity.response_value === 'needs_discussion' || activity.action_key === 'discuss_package_renewal') {
      return t('pages.notifications.activityDetails.packageRenewalNeedsDiscussion');
    }
    if (activity.response_value === 'confirmed' && activity.action_key === 'confirm_lesson') {
      return t('pages.notifications.activityDetails.lessonConfirmed');
    }
    if (activity.response_value === 'declined' && activity.action_key === 'decline_lesson') {
      const responseText = typeof activity.metadata?.response_text === 'string' ? activity.metadata.response_text : null;
      if (responseText) {
        return t('pages.notifications.activityDetails.lessonDeclinedWithReason', { reason: responseText });
      }
      return t('pages.notifications.activityDetails.lessonDeclined');
    }
    if (activity.response_value === 'confirmed') {
      return t('pages.notifications.activityDetails.responseConfirmed');
    }
    return t('pages.notifications.activityDetails.responseRecorded');
  }

  if (activity.activity_type === 'delivery_attempt') {
    if (activity.status === 'sent') {
      return t('pages.notifications.activityDetails.deliverySent');
    }
    if (activity.status === 'processing') {
      return t('pages.notifications.activityDetails.deliveryProcessing');
    }
    if (activity.status === 'scheduled') {
      return t('pages.notifications.activityDetails.deliveryScheduled');
    }
    if (activity.status === 'failed') {
      const reason = activity.error_message || activity.error_code;
      return reason
        ? t('pages.notifications.activityDetails.deliveryFailedWithReason', { reason })
        : t('pages.notifications.activityDetails.deliveryFailed');
    }
    return t('pages.notifications.activityDetails.deliveryRecorded');
  }

  return activity.error_message || activity.error_code || '—';
};

const formatRuleTrigger = (rule: NotificationRule, t: TranslateFn): string => {
  const eventLabel = t(`pages.notifications.eventTypes.${rule.event_type}`);
  const triggerConfig = rule.trigger_config ?? {};

  switch (rule.trigger_type) {
    case 'day_offset_at_time':
      return t('pages.notifications.triggerSummary.dayOffsetAtTime', {
        event: eventLabel,
        days: Math.abs(Number(triggerConfig.days ?? 0)),
        time: String(triggerConfig.local_time ?? '—'),
      });
    case 'relative_offset':
      return t('pages.notifications.triggerSummary.relativeOffset', {
        event: eventLabel,
        minutes: Math.abs(Number(triggerConfig.minutes ?? 0)),
      });
    case 'after_event_offset':
      return t('pages.notifications.triggerSummary.afterEventOffset', {
        event: eventLabel,
        minutes: Math.abs(Number(triggerConfig.minutes ?? 0)),
      });
    case 'absolute_datetime':
      return t('pages.notifications.triggerSummary.absoluteDatetime', {
        event: eventLabel,
        datetime: triggerConfig.datetime ? dayjs(String(triggerConfig.datetime)).format('YYYY-MM-DD HH:mm') : '—',
      });
    default:
      return `${eventLabel} · ${t(`pages.notifications.triggerTypes.${rule.trigger_type}`)}`;
  }
};

const formatAudienceSummary = (assignments: NotificationAssignment[], t: TranslateFn): string => {
  const included = assignments.filter((assignment) => !assignment.is_exclusion);
  const excludedCount = assignments.filter((assignment) => assignment.is_exclusion).length;

  if (included.some((assignment) => assignment.scope_type === 'all_learners')) {
    return excludedCount > 0
      ? `${t('pages.notifications.audienceSummary.allLearners')} · ${t('pages.notifications.audienceSummary.exclusions', { count: excludedCount })}`
      : t('pages.notifications.audienceSummary.allLearners');
  }

  const counts = included.reduce<Record<string, number>>((acc, assignment) => {
    acc[assignment.scope_type] = (acc[assignment.scope_type] ?? 0) + 1;
    return acc;
  }, {});

  const parts = [
    counts.learner ? t('pages.notifications.audienceSummary.learners', { count: counts.learner }) : null,
    counts.group ? t('pages.notifications.audienceSummary.groups', { count: counts.group }) : null,
    counts.package ? t('pages.notifications.audienceSummary.packages', { count: counts.package }) : null,
    excludedCount ? t('pages.notifications.audienceSummary.exclusions', { count: excludedCount }) : null,
  ].filter(Boolean);

  return parts.length > 0 ? parts.join(' · ') : '—';
};

const buildNotificationPilotSummary = (
  settings: NotificationSettings | undefined,
  learnerModes: LearnerNotificationMode[],
  instances: NotificationInstance[],
  activity: NotificationActivity[],
  activityAcknowledgements: NotificationActivityAcknowledgement[],
): NotificationPilotSummary => {
  const now = dayjs();
  const plannedInstances = instances.filter(isQueueInstance);
  const acknowledgedActivityKeys = new Set(
    activityAcknowledgements.map((item) => `${item.activity_type}:${item.activity_id}`),
  );

  return {
    globalMode: settings?.mode ?? 'legacy',
    totalLearners: learnerModes.length,
    learnerNewCount: learnerModes.filter((learner) => learner.effective_mode === 'new').length,
    learnerShadowCount: learnerModes.filter((learner) => learner.effective_mode === 'shadow').length,
    plannedCount: plannedInstances.length,
    dueDeliveryCount: plannedInstances.filter((instance) => (
      instance.status === 'scheduled'
      && instance.delivery_enabled
      && !dayjs(instance.effective_scheduled_for).isAfter(now)
    )).length,
    attentionAlertCount: activity.filter((item) => (
      (item.activity_type === 'teacher_alert' || item.status === 'requires_attention')
      && !acknowledgedActivityKeys.has(`${item.activity_type}:${item.activity_id}`)
    )).length,
  };
};

const getPilotNextAction = (
  summary: NotificationPilotSummary,
): { type: 'success' | 'info' | 'warning' | 'error'; translationKey: string } => {
  if (summary.attentionAlertCount > 0) {
    return { type: 'warning', translationKey: 'pages.notifications.rolloutStatus.nextActions.reviewAlerts' };
  }
  if (summary.globalMode === 'legacy' && summary.learnerShadowCount === 0 && summary.learnerNewCount === 0) {
    return { type: 'info', translationKey: 'pages.notifications.rolloutStatus.nextActions.enableTestMode' };
  }
  if (summary.plannedCount === 0) {
    return { type: 'info', translationKey: 'pages.notifications.rolloutStatus.nextActions.refreshPlan' };
  }
  if (summary.learnerNewCount === 0 && summary.globalMode !== 'new') {
    return { type: 'warning', translationKey: 'pages.notifications.rolloutStatus.nextActions.choosePilotLearner' };
  }
  if (summary.dueDeliveryCount === 0) {
    return { type: 'info', translationKey: 'pages.notifications.rolloutStatus.nextActions.waitForDueNotifications' };
  }
  return { type: 'success', translationKey: 'pages.notifications.rolloutStatus.nextActions.readyForControlledSend' };
};

const getPilotChecklistStatus = (
  summary: NotificationPilotSummary,
): Array<{ titleKey: string; status: 'finish' | 'process' | 'wait' }> => [
  {
    titleKey: 'pages.notifications.rolloutChecklist.steps.1',
    status: summary.globalMode === 'new' ? 'wait' : 'finish',
  },
  {
    titleKey: 'pages.notifications.rolloutChecklist.steps.2',
    status: summary.plannedCount > 0 ? 'finish' : 'process',
  },
  {
    titleKey: 'pages.notifications.rolloutChecklist.steps.3',
    status: summary.learnerNewCount > 0 || summary.globalMode === 'new' ? 'finish' : 'process',
  },
  {
    titleKey: 'pages.notifications.rolloutChecklist.steps.4',
    status: summary.globalMode === 'new' ? 'finish' : 'wait',
  },
];

const getQueueSectionKey = (scheduledFor: string): 'past_due' | 'today' | 'tomorrow' | 'later' => {
  const scheduled = dayjs(scheduledFor);
  const now = dayjs();

  if (scheduled.isBefore(now) && !scheduled.isSame(now, 'day')) {
    return 'past_due';
  }
  if (scheduled.isSame(now, 'day')) {
    if (scheduled.isBefore(now)) {
      return 'past_due';
    }
    return 'today';
  }
  if (scheduled.isSame(now.add(1, 'day'), 'day')) {
    return 'tomorrow';
  }
  return 'later';
};

const getQueueSectionOrder: Array<'past_due' | 'today' | 'tomorrow' | 'later'> = ['past_due', 'today', 'tomorrow', 'later'];

const getActivityAcknowledgementKey = (item: Pick<NotificationActivity, 'activity_type' | 'activity_id'>): string => (
  `${item.activity_type}:${item.activity_id}`
);

const isAttentionActivity = (item: NotificationActivity): boolean => (
  item.activity_type === 'teacher_alert' || item.status === 'requires_attention'
);

const isHandleableActivity = (item: NotificationActivity): boolean => item.activity_type === 'teacher_alert';

const getActivitySectionKey = (
  item: NotificationActivity,
  acknowledgedActivityKeys: Set<string>,
): 'attention' | 'recent' => (
  isAttentionActivity(item) && !acknowledgedActivityKeys.has(getActivityAcknowledgementKey(item))
    ? 'attention'
    : 'recent'
);

const getActivityVisibleStatus = (
  item: NotificationActivity,
  acknowledgedActivityKeys: Set<string>,
): string => (
  isHandleableActivity(item) && acknowledgedActivityKeys.has(getActivityAcknowledgementKey(item))
    ? 'handled'
    : item.status
);

const getTemplateSectionKey = (template: NotificationTemplate): 'system' | 'custom' | 'archived' => {
  if (template.archived_at) {
    return 'archived';
  }
  return template.system ? 'system' : 'custom';
};

const getTemplateSectionOrder: Array<'system' | 'custom' | 'archived'> = ['system', 'custom', 'archived'];

const RULE_WIZARD_PRESETS: Record<NonNullable<RuleWizardValues['preset_key']>, Partial<RuleWizardValues>> = {
  lesson_confirmation: {
    category: 'lesson_confirmation',
    event_type: 'lesson',
    trigger_type: 'day_offset_at_time',
    trigger_days: -1,
    trigger_local_time: '10:00',
    priority: 'normal',
    message_mode: 'template',
    audience_scope_type: 'all_learners',
  },
  homework: {
    category: 'homework',
    event_type: 'lesson',
    trigger_type: 'day_offset_at_time',
    trigger_days: -1,
    trigger_local_time: '10:00',
    priority: 'normal',
    message_mode: 'template',
    audience_scope_type: 'all_learners',
  },
  package_renewal: {
    category: 'package_renewal',
    event_type: 'package',
    trigger_type: 'day_offset_at_time',
    trigger_days: -14,
    trigger_local_time: '10:00',
    priority: 'normal',
    message_mode: 'template',
    audience_scope_type: 'all_learners',
  },
  custom_message: {
    category: 'custom',
    event_type: 'custom_date',
    trigger_type: 'absolute_datetime',
    priority: 'normal',
    message_mode: 'inline',
    audience_scope_type: 'learner',
  },
};

const getDefaultTemplateIdForCategory = (
  category: string,
  templates: NotificationTemplate[],
): number | undefined => templates
  .filter((template) => !template.archived_at && template.category === category)
  .sort((left, right) => Number(right.system) - Number(left.system) || left.id - right.id)[0]?.id;

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
    status: 'paused',
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
  const { tenantId, isSuperAdmin } = useAuth();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<NotificationsTabKey>('rules');
  const [templateModalOpen, setTemplateModalOpen] = useState(false);
  const [ruleWizardOpen, setRuleWizardOpen] = useState(false);
  const [ruleWizardStep, setRuleWizardStep] = useState(0);
  const [rulePreview, setRulePreview] = useState<NotificationPreviewResponse | null>(null);
  const [selectedQueueInstanceId, setSelectedQueueInstanceId] = useState<number | null>(null);
  const [templateForm] = Form.useForm<NotificationTemplateFormValues>();
  const [ruleForm] = Form.useForm<RuleWizardValues>();
  const [settingsForm] = Form.useForm<NotificationSettingsFormValues>();
  const requiresTenantContext = tenantId === null;
  const isOwnerDebug = isSuperAdmin;

  useEffect(() => {
    if (!isOwnerDebug && activeTab === 'settings') {
      setActiveTab('rules');
    }
  }, [activeTab, isOwnerDebug]);

  const rulesQuery = useQuery<NotificationRule[], Error>({
    queryKey: ['notificationRules'],
    queryFn: fetchNotificationRules,
    enabled: !requiresTenantContext && activeTab === 'rules',
  });

  const templatesQuery = useQuery<NotificationTemplate[], Error>({
    queryKey: ['notificationTemplates'],
    queryFn: fetchNotificationTemplates,
    enabled: !requiresTenantContext && (activeTab === 'templates' || templateModalOpen || ruleWizardOpen),
  });

  const instancesQuery = useQuery<NotificationInstance[], Error>({
    queryKey: ['notificationInstances'],
    queryFn: fetchNotificationInstances,
    enabled: !requiresTenantContext && (activeTab === 'queue' || (isOwnerDebug && activeTab === 'settings')),
  });

  const instanceDetailQuery = useQuery<NotificationInstance, Error>({
    queryKey: ['notificationInstanceDetail', selectedQueueInstanceId],
    queryFn: () => fetchNotificationInstanceDetail(selectedQueueInstanceId as number),
    enabled: !requiresTenantContext && activeTab === 'queue' && selectedQueueInstanceId !== null,
  });

  const activityQuery = useQuery<NotificationActivity[], Error>({
    queryKey: ['notificationActivity'],
    queryFn: fetchNotificationActivity,
    enabled: !requiresTenantContext && (activeTab === 'activity' || (isOwnerDebug && activeTab === 'settings')),
  });

  const activityAcknowledgementsQuery = useQuery<NotificationActivityAcknowledgement[], Error>({
    queryKey: ['notificationActivityAcknowledgements'],
    queryFn: fetchNotificationActivityAcknowledgements,
    enabled: !requiresTenantContext && (activeTab === 'activity' || (isOwnerDebug && activeTab === 'settings')),
  });

  const settingsQuery = useQuery<NotificationSettings, Error>({
    queryKey: ['notificationSettings'],
    queryFn: fetchNotificationSettings,
    enabled: !requiresTenantContext && activeTab === 'settings',
  });

  const learnerModesQuery = useQuery<LearnerNotificationMode[], Error>({
    queryKey: ['learnerNotificationModes'],
    queryFn: fetchLearnerNotificationModes,
    enabled: !requiresTenantContext && activeTab === 'settings',
  });

  const learnersQuery = useQuery<Learner[], Error>({
    queryKey: ['learnersForNotificationWizard'],
    queryFn: fetchLearners,
    enabled: !requiresTenantContext && ruleWizardOpen,
  });

  const groupsQuery = useQuery<LearnerGroup[], Error>({
    queryKey: ['groupsForNotificationWizard'],
    queryFn: fetchGroups,
    enabled: !requiresTenantContext && ruleWizardOpen,
  });

  const packagesQuery = useQuery<LessonPackage[], Error>({
    queryKey: ['packagesForNotificationWizard'],
    queryFn: fetchActivePackages,
    enabled: !requiresTenantContext && ruleWizardOpen,
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

  const cancelInstanceMutation = useMutation({
    mutationFn: cancelInstance,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notificationInstances'] });
      queryClient.invalidateQueries({ queryKey: ['notificationInstanceDetail'] });
      message.success(t('pages.notifications.instanceCancelled'));
    },
    onError: (error: Error) => message.error(t('errors.updateFailed', { message: formatApiError(error) })),
  });

  const sendNowMutation = useMutation({
    mutationFn: sendInstanceNow,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notificationInstances'] });
      queryClient.invalidateQueries({ queryKey: ['notificationInstanceDetail'] });
      message.success(t('pages.notifications.instanceScheduledNow'));
    },
    onError: (error: Error) => message.error(t('errors.updateFailed', { message: formatApiError(error) })),
  });

  const settingsMutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notificationSettings'] });
      queryClient.invalidateQueries({ queryKey: ['learnerNotificationModes'] });
      queryClient.invalidateQueries({ queryKey: ['notificationInstances'] });
      queryClient.invalidateQueries({ queryKey: ['notificationActivity'] });
      queryClient.invalidateQueries({ queryKey: ['notificationInstanceDetail'] });
      message.success(t('pages.notifications.settingsSaved'));
    },
    onError: (error: Error) => message.error(t('errors.updateFailed', { message: formatApiError(error) })),
  });

  const learnerModeMutation = useMutation({
    mutationFn: updateLearnerNotificationMode,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learnerNotificationModes'] });
      queryClient.invalidateQueries({ queryKey: ['notificationInstances'] });
      queryClient.invalidateQueries({ queryKey: ['notificationActivity'] });
      queryClient.invalidateQueries({ queryKey: ['notificationInstanceDetail'] });
      message.success(t('pages.notifications.learnerModeSaved'));
    },
    onError: (error: Error) => message.error(t('errors.updateFailed', { message: formatApiError(error) })),
  });

  const processJobsMutation = useMutation({
    mutationFn: triggerNotificationJobProcessing,
    onSuccess: (result) => {
      message.success(t('pages.notifications.pilotControls.processJobsQueued', { taskId: result.task_id }));
    },
    onError: (error: Error) => message.error(t('errors.updateFailed', { message: formatApiError(error) })),
  });

  const deliverNowMutation = useMutation({
    mutationFn: triggerNotificationDeliveryTick,
    onSuccess: (result) => {
      message.success(t('pages.notifications.pilotControls.deliveryQueued', { taskId: result.task_id }));
    },
    onError: (error: Error) => message.error(t('errors.updateFailed', { message: formatApiError(error) })),
  });

  const acknowledgeActivityMutation = useMutation({
    mutationFn: acknowledgeNotificationActivity,
    onSuccess: (acknowledgement) => {
      queryClient.setQueryData<NotificationActivityAcknowledgement[]>(
        ['notificationActivityAcknowledgements'],
        (current = []) => {
          const next = current.filter((item) => !(
            item.activity_type === acknowledgement.activity_type
            && item.activity_id === acknowledgement.activity_id
          ));
          return [...next, acknowledgement];
        },
      );
      message.success(t('pages.notifications.activityHandled'));
    },
    onError: (error: Error) => message.error(t('errors.updateFailed', { message: formatApiError(error) })),
  });

  const categoryOptions = useMemo(
    () => CATEGORY_OPTIONS.map((category) => ({ value: category, label: t(`pages.notifications.categories.${category}`) })),
    [t],
  );

  const pilotSummary = useMemo(
    () => buildNotificationPilotSummary(
      settingsQuery.data,
      learnerModesQuery.data ?? [],
      instancesQuery.data ?? [],
      activityQuery.data ?? [],
      activityAcknowledgementsQuery.data ?? [],
    ),
    [
      activityAcknowledgementsQuery.data,
      activityQuery.data,
      instancesQuery.data,
      learnerModesQuery.data,
      settingsQuery.data,
    ],
  );

  const openRuleWizard = () => {
    const preset = RULE_WIZARD_PRESETS.lesson_confirmation;
    const presetCategory = preset.category ?? 'lesson_confirmation';
    setRulePreview(null);
    setRuleWizardStep(0);
    ruleForm.setFieldsValue({
      preset_key: 'lesson_confirmation',
      name: '',
      category: presetCategory,
      event_type: preset.event_type,
      trigger_type: preset.trigger_type,
      trigger_days: preset.trigger_days,
      trigger_local_time: preset.trigger_local_time,
      trigger_minutes: -60,
      audience_scope_type: preset.audience_scope_type,
      audience_scope_ids: [],
      excluded_learner_ids: [],
      priority: preset.priority,
      message_mode: preset.message_mode,
      template_id: getDefaultTemplateIdForCategory(presetCategory, templatesQuery.data ?? []),
      inline_template_body: undefined,
      trigger_absolute_datetime: undefined,
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
          onCreateRule={openRuleWizard}
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
          onOpenDetails={(instanceId) => setSelectedQueueInstanceId(instanceId)}
          selectedInstance={instanceDetailQuery.data ?? null}
          selectedInstanceId={selectedQueueInstanceId}
          detailLoading={instanceDetailQuery.isLoading}
          detailError={instanceDetailQuery.error}
          onCloseDetails={() => setSelectedQueueInstanceId(null)}
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
          acknowledgements={activityAcknowledgementsQuery.data ?? []}
          loading={activityQuery.isLoading}
          error={activityQuery.error ?? activityAcknowledgementsQuery.error ?? null}
          acknowledgingActivityId={acknowledgeActivityMutation.isPending ? acknowledgeActivityMutation.variables ?? null : null}
          onAcknowledge={(activityId) => acknowledgeActivityMutation.mutate(activityId)}
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
          learnerModes={learnerModesQuery.data ?? []}
          learnerModesLoading={learnerModesQuery.isLoading}
          learnerModesError={learnerModesQuery.error}
          learnerModeUpdating={learnerModeMutation.isPending}
          onLearnerModeChange={(learnerId, modeOverride) => learnerModeMutation.mutate({ learnerId, modeOverride })}
          pilotSummary={pilotSummary}
          processingJobs={processJobsMutation.isPending}
          deliveringNow={deliverNowMutation.isPending}
          onProcessJobs={() => processJobsMutation.mutate()}
          onDeliverNow={() => deliverNowMutation.mutate()}
        />
      ),
    },
  ];
  const visibleTabs = isOwnerDebug ? tabs : tabs.filter((tab) => tab.key !== 'settings');

  if (requiresTenantContext) {
    return (
      <div>
        <PageHeader
          title={t('pages.notifications.title')}
          subtitle={t('pages.notifications.subtitle')}
          actions={isOwnerDebug ? <Tag color="green">{t('navigation.newBadge')}</Tag> : undefined}
        />

        <TenantContextRequired sectionLabel={t('pages.notifications.title')} />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title={t('pages.notifications.title')}
        subtitle={t('pages.notifications.subtitle')}
        actions={isOwnerDebug ? <Tag color="green">{t('navigation.newBadge')}</Tag> : undefined}
      />

      {isOwnerDebug && (
        <Alert
          type="info"
          showIcon
          message={t('pages.notifications.pilotNoticeTitle')}
          description={t('pages.notifications.pilotNoticeDescription')}
          style={{ marginBottom: 16 }}
        />
      )}

      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as NotificationsTabKey)}
        items={visibleTabs}
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
  const [selectedPresetKey, setSelectedPresetKey] = useState<NonNullable<RuleWizardValues['preset_key']>>('lesson_confirmation');
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

  useEffect(() => {
    if (!open) {
      return;
    }
    const currentPreset = form.getFieldValue('preset_key') as NonNullable<RuleWizardValues['preset_key']> | undefined;
    setSelectedPresetKey(currentPreset ?? 'lesson_confirmation');
  }, [form, open]);

  const applyPreset = (nextPresetKey: NonNullable<RuleWizardValues['preset_key']>) => {
    const preset = RULE_WIZARD_PRESETS[nextPresetKey];
    const nextCategory = preset.category ?? 'custom';
    const nextMessageMode = preset.message_mode ?? 'template';
    const templateId = nextMessageMode === 'template'
      ? getDefaultTemplateIdForCategory(nextCategory, templates)
      : undefined;

    setSelectedPresetKey(nextPresetKey);
    form.setFieldsValue({
      preset_key: nextPresetKey,
      name: t(`pages.notifications.ruleWizard.presets.${nextPresetKey}.name`),
      category: nextCategory,
      message_mode: nextMessageMode,
      template_id: templateId,
      inline_template_body: nextMessageMode === 'inline' ? '' : undefined,
      event_type: preset.event_type,
      trigger_type: preset.trigger_type,
      trigger_days: preset.trigger_days,
      trigger_local_time: preset.trigger_local_time,
      trigger_minutes: preset.trigger_minutes,
      trigger_absolute_datetime: undefined,
      audience_scope_type: preset.audience_scope_type,
      audience_scope_ids: [],
      excluded_learner_ids: [],
      priority: preset.priority,
      combine_policy_key: nextPresetKey === 'lesson_confirmation' ? 'lesson_confirmation_homework' : undefined,
    });
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
              {t('common.create')}
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
          preset_key: 'lesson_confirmation',
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
            <Form.Item name="preset_key" hidden>
              <Input />
            </Form.Item>
            <Card size="small" title={t('pages.notifications.ruleWizard.presetTitle')}>
              <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
                {t('pages.notifications.ruleWizard.presetDescription')}
              </Typography.Paragraph>
              <Row gutter={[12, 12]}>
                {(Object.keys(RULE_WIZARD_PRESETS) as Array<NonNullable<RuleWizardValues['preset_key']>>).map((key) => (
                  <Col xs={24} md={12} key={key}>
                    <Card
                      data-testid={`rule-wizard-preset-${key}`}
                      data-active={selectedPresetKey === key ? 'true' : 'false'}
                      hoverable
                      size="small"
                      onClick={() => applyPreset(key)}
                      style={selectedPresetKey === key ? { borderColor: '#1677ff', background: '#f0f7ff' } : undefined}
                    >
                      <Space direction="vertical" size={4}>
                        <Typography.Text strong>
                          {t(`pages.notifications.ruleWizard.presets.${key}.title`)}
                        </Typography.Text>
                        <Typography.Text type="secondary">
                          {t(`pages.notifications.ruleWizard.presets.${key}.description`)}
                        </Typography.Text>
                      </Space>
                    </Card>
                  </Col>
                ))}
              </Row>
            </Card>
            <Alert
              type="info"
              showIcon
              message={t('pages.notifications.ruleWizard.stepHelp.messageTitle')}
              description={t('pages.notifications.ruleWizard.stepHelp.messageDescription')}
            />
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
            <Alert
              type="info"
              showIcon
              message={t('pages.notifications.ruleWizard.stepHelp.triggerTitle')}
              description={t('pages.notifications.ruleWizard.stepHelp.triggerDescription')}
            />
            <Row gutter={16}>
              <Col xs={24} md={12}>
                <Form.Item name="event_type" label={t('pages.notifications.ruleWizard.eventTypeTeacher')} rules={[{ required: true }]}>
                  <Select
                    options={[
                      { value: 'lesson', label: t('pages.notifications.eventTypes.lesson') },
                      { value: 'package', label: t('pages.notifications.eventTypes.package') },
                      { value: 'custom_date', label: t('pages.notifications.eventTypes.custom_date') },
                    ]}
                  />
                </Form.Item>
              </Col>
              <Col xs={24} md={12}>
                <Form.Item name="trigger_type" label={t('pages.notifications.ruleWizard.whenToSend')} rules={[{ required: true }]}>
                  <Select
                    options={[
                      { value: 'day_offset_at_time', label: t('pages.notifications.ruleWizard.triggerChoices.day_offset_at_time') },
                      { value: 'relative_offset', label: t('pages.notifications.ruleWizard.triggerChoices.relative_offset') },
                      { value: 'after_event_offset', label: t('pages.notifications.ruleWizard.triggerChoices.after_event_offset') },
                      { value: 'absolute_datetime', label: t('pages.notifications.ruleWizard.triggerChoices.absolute_datetime') },
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

            {eventType === 'custom_date' && triggerType !== 'absolute_datetime' && (
              <Alert type="warning" showIcon message={t('pages.notifications.ruleWizard.customDateNeedsAbsoluteTrigger')} />
            )}

            <Collapse
              size="small"
              items={[
                {
                  key: 'wizard-advanced-trigger',
                  label: t('pages.notifications.ruleWizard.advancedSettings'),
                  children: (
                    <Space direction="vertical" style={{ width: '100%' }} size="middle">
                      <Form.Item name="priority" label={t('pages.notifications.ruleWizard.howImportant')} rules={[{ required: true }]}>
                        <Select
                          options={[
                            { value: 'low', label: t('pages.notifications.priorities.low') },
                            { value: 'normal', label: t('pages.notifications.priorities.normal') },
                            { value: 'high', label: t('pages.notifications.priorities.high') },
                          ]}
                        />
                      </Form.Item>

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
                    </Space>
                  ),
                },
              ]}
            />
          </Space>
        )}

        {step === 2 && (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Alert
              type="info"
              showIcon
              message={t('pages.notifications.ruleWizard.stepHelp.audienceTitle')}
              description={t('pages.notifications.ruleWizard.stepHelp.audienceDescription')}
            />
            <Form.Item name="audience_scope_type" label={t('pages.notifications.ruleWizard.whoGetsIt')} rules={[{ required: true }]}>
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

            <Collapse
              size="small"
              items={[
                {
                  key: 'wizard-advanced-audience',
                  label: t('pages.notifications.ruleWizard.optionalAudienceSettings'),
                  children: (
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
                  ),
                },
              ]}
            />
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
  const learnerCount = useMemo(
    () => new Set((preview?.instances ?? []).map((instance) => instance.learner_id)).size,
    [preview],
  );

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
          description={preview.warnings.map((warning) => getWarningLabel(warning, t)).join(', ')}
        />
      )}
      <Card>
        <Typography.Title level={5}>{t('pages.notifications.ruleWizard.previewSummary')}</Typography.Title>
        <Typography.Paragraph>
          {t('pages.notifications.ruleWizard.previewCount', { count: preview.instances.length })}
        </Typography.Paragraph>
        <Typography.Paragraph type="secondary">
          {t('pages.notifications.ruleWizard.previewLearnersCount', { count: learnerCount })}
        </Typography.Paragraph>
        <Divider />
        <Space direction="vertical" style={{ width: '100%' }}>
          {preview.instances.slice(0, 10).map((instance, index) => (
            <Card key={`${instance.kind}-${instance.rule_id ?? index}-${instance.learner_id}-${instance.event_id ?? index}`} size="small">
              <Space direction="vertical" size={4}>
                <Space wrap>
                  <Tag>{instance.kind === 'combined' ? t('pages.notifications.ruleWizard.previewKinds.combined') : t('pages.notifications.ruleWizard.previewKinds.single')}</Tag>
                  <Tag color={getInstanceStatusColor(instance.status)}>{t(`pages.notifications.instanceStatus.${instance.status}`)}</Tag>
                  {instance.category && <Tag>{t(`pages.notifications.categories.${instance.category}`)}</Tag>}
                </Space>
                <span>
                  {t('pages.notifications.ruleWizard.previewLine', {
                    learnerId: instance.learner_id,
                    scheduledFor: dayjs(instance.effective_scheduled_for).format('YYYY-MM-DD HH:mm'),
                  })}
                </span>
                {instance.warnings.length > 0 && (
                  <Typography.Text type="warning">
                    {instance.warnings.join(', ')}
                  </Typography.Text>
                )}
                {instance.components.length > 0 && (
                  <Typography.Text type="secondary">
                    {t('pages.notifications.ruleWizard.combinedSummary', {
                      components: instance.components.map((component) => t(`pages.notifications.categories.${component.category}`)).join(', '),
                    })}
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
  onSetStatus: (ruleId: number, action: 'activate' | 'pause' | 'archive' | 'restore') => void;
  onCreateRule: () => void;
}

const RulesTab: React.FC<RulesTabProps> = ({
  rules,
  loading,
  error,
  onSetStatus,
  onCreateRule,
}) => {
  const { t } = useTranslation();
  const [rulesView, setRulesView] = useState<'current' | 'archived'>('current');

  const currentRules = useMemo(
    () => rules.filter((rule) => rule.status !== 'archived'),
    [rules],
  );
  const archivedRules = useMemo(
    () => rules.filter((rule) => rule.status === 'archived'),
    [rules],
  );
  const visibleRules = rulesView === 'archived' ? archivedRules : currentRules;

  const renderRuleCard = (rule: NotificationRule) => {
    const displayStatus = getRuleDisplayStatus(rule.status);
    const menuItems = rule.status === 'archived'
      ? [
        {
          key: 'restore',
          label: t('pages.notifications.restore'),
        },
      ]
      : [
        {
          key: 'archive',
          label: t('pages.notifications.archive'),
          danger: true,
        },
      ];

    return (
      <Col xs={24} md={12} xl={8} key={rule.id}>
        <Card
          size="small"
          style={{ height: '100%' }}
          styles={{ body: { height: '100%' } }}
        >
          <Space direction="vertical" style={{ width: '100%', height: '100%', justifyContent: 'space-between' }} size="middle">
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <Space wrap align="start" style={{ justifyContent: 'space-between', width: '100%' }}>
                <Space direction="vertical" size={6} style={{ minWidth: 0 }}>
                  <Typography.Text strong>{rule.name}</Typography.Text>
                  <Space wrap size={[8, 8]}>
                    <Tag>{t(`pages.notifications.categories.${rule.category}`)}</Tag>
                    <Tag color={getRuleStatusColor(displayStatus)}>
                      {t(`pages.notifications.ruleStatus.${displayStatus}`)}
                    </Tag>
                  </Space>
                </Space>
                <Space size="small" align="start">
                  {rule.status !== 'archived' && (
                    <Switch
                      checked={displayStatus === 'active'}
                      onChange={(checked) => onSetStatus(rule.id, checked ? 'activate' : 'pause')}
                    />
                  )}
                  {menuItems.length > 0 && (
                    <Dropdown
                      trigger={['click']}
                      menu={{
                        items: menuItems,
                        onClick: ({ key }) => onSetStatus(rule.id, key as 'archive' | 'restore'),
                      }}
                    >
                      <Button
                        type="text"
                        size="small"
                        icon={<MoreOutlined />}
                        aria-label={t('common.actions')}
                      />
                    </Dropdown>
                  )}
                </Space>
              </Space>

              <Space direction="vertical" size={6} style={{ width: '100%' }}>
                <Typography.Text>{formatRuleTrigger(rule, t)}</Typography.Text>
                <Typography.Text type="secondary">{formatAudienceSummary(rule.assignments, t)}</Typography.Text>
              </Space>
            </Space>
          </Space>
        </Card>
      </Col>
    );
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Space wrap style={{ justifyContent: 'space-between', width: '100%' }}>
        <Tabs
          activeKey={rulesView}
          onChange={(nextKey) => setRulesView(nextKey as 'current' | 'archived')}
          items={[
            {
              key: 'current',
              label: `${t('pages.notifications.rulesTabs.current')} (${currentRules.length})`,
            },
            {
              key: 'archived',
              label: `${t('pages.notifications.rulesTabs.archived')} (${archivedRules.length})`,
            },
          ]}
        />
        <Button type="primary" icon={<PlusOutlined />} onClick={onCreateRule}>
          {t('pages.notifications.createRuleWizard')}
        </Button>
      </Space>
      <NoticeError error={error} />
      {loading ? (
        <Card loading />
      ) : visibleRules.length === 0 ? (
        <Empty
          description={(
            <Space direction="vertical" size={4}>
              <Typography.Text>
                {t(rulesView === 'archived' ? 'pages.notifications.noArchivedRules' : 'pages.notifications.noRules')}
              </Typography.Text>
              <Typography.Text type="secondary">
                {t(rulesView === 'archived' ? 'pages.notifications.noArchivedRulesDescription' : 'pages.notifications.noRulesDescription')}
              </Typography.Text>
            </Space>
          )}
        />
      ) : (
        <Row gutter={[16, 16]}>
          {visibleRules.map(renderRuleCard)}
        </Row>
      )}
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
  const groupedTemplates = useMemo(() => {
    const groups: Record<'system' | 'custom' | 'archived', NotificationTemplate[]> = {
      system: [],
      custom: [],
      archived: [],
    };

    templates.forEach((template) => {
      groups[getTemplateSectionKey(template)].push(template);
    });

    return groups;
  }, [templates]);

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
      <Alert
        type="info"
        showIcon
        message={t('pages.notifications.templatesHelpTitle')}
        description={t('pages.notifications.templatesHelpDescription')}
      />
      <NoticeError error={error} />
      {loading ? (
        <Card loading />
      ) : templates.length === 0 ? (
        <Empty
          description={(
            <Space direction="vertical" size={4}>
              <Typography.Text>{t('pages.notifications.noTemplates')}</Typography.Text>
              <Typography.Text type="secondary">{t('pages.notifications.noTemplatesDescription')}</Typography.Text>
            </Space>
          )}
        />
      ) : (
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          {getTemplateSectionOrder.map((sectionKey) => {
            const sectionTemplates = groupedTemplates[sectionKey];
            if (sectionTemplates.length === 0) {
              return null;
            }

            return (
              <Card
                key={sectionKey}
                title={t(`pages.notifications.templateSections.${sectionKey}`)}
                extra={<Tag>{sectionTemplates.length}</Tag>}
              >
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                  {sectionTemplates.map((template) => (
                    <Card key={template.id} size="small" type="inner">
                      <Space direction="vertical" style={{ width: '100%' }} size="small">
                        <Space wrap style={{ justifyContent: 'space-between', width: '100%' }}>
                          <Space wrap>
                            <Typography.Text strong>{template.name}</Typography.Text>
                            <Tag>{t(`pages.notifications.categories.${template.category}`)}</Tag>
                            <Tag color={template.system ? 'purple' : 'blue'}>
                              {template.system ? t('pages.notifications.systemTemplate') : t('pages.notifications.tenantTemplate')}
                            </Tag>
                          </Space>
                          <Typography.Text type="secondary">
                            v{template.version}
                          </Typography.Text>
                        </Space>
                        <Typography.Paragraph style={{ marginBottom: 0 }}>
                          {template.body}
                        </Typography.Paragraph>
                        {!template.system && !template.archived_at && (
                          <Space wrap>
                            <Button
                              size="small"
                              danger
                              disabled={archiving}
                              onClick={() => onArchive(template.id)}
                            >
                              {t('pages.notifications.archive')}
                            </Button>
                          </Space>
                        )}
                      </Space>
                    </Card>
                  ))}
                </Space>
              </Card>
            );
          })}

          <Collapse
            size="small"
            items={[
              {
                key: 'technical-templates',
                label: t('pages.notifications.technicalList'),
                children: (
                  <ResponsiveDataView<NotificationTemplate>
                    data={templates}
                    loading={false}
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
                ),
              },
            ]}
          />
        </Space>
      )}
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
  onOpenDetails: (instanceId: number) => void;
  selectedInstance: NotificationInstance | null;
  selectedInstanceId: number | null;
  detailLoading: boolean;
  detailError: Error | null;
  onCloseDetails: () => void;
}

const QueueTab: React.FC<QueueTabProps> = ({
  instances,
  loading,
  error,
  actionPending,
  onCancel,
  onSendNow,
  onOpenDetails,
  selectedInstance,
  selectedInstanceId,
  detailLoading,
  detailError,
  onCloseDetails,
}) => {
  const { t } = useTranslation();
  const [pendingSendNowInstance, setPendingSendNowInstance] = useState<NotificationInstance | null>(null);
  const visibleInstances = useMemo(
    () => instances.filter(isQueueInstance),
    [instances],
  );
  const groupedInstances = useMemo(() => {
    const groups: Record<string, NotificationInstance[]> = {
      past_due: [],
      today: [],
      tomorrow: [],
      later: [],
    };

    visibleInstances.forEach((instance) => {
      groups[getQueueSectionKey(instance.effective_scheduled_for)].push(instance);
    });

    return groups;
  }, [visibleInstances]);

  const handleSendNowClick = (instance: NotificationInstance) => {
    setPendingSendNowInstance(instance);
  };

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
      render: (status: string) => <Tag color={getInstanceStatusColor(status)}>{getInstanceStatusLabel(status, t)}</Tag>,
    },
    {
      title: t('pages.notifications.delivery'),
      key: 'delivery',
      render: (_, record) => record.latest_attempt ? (
        <Space direction="vertical" size={0}>
          <span>{getInstanceStatusLabel(record.latest_attempt.status, t)}</span>
          {record.latest_attempt.provider_message_id && (
            <Typography.Text type="secondary">
              {t('pages.notifications.queueDetails.providerMessageId')}: #{record.latest_attempt.provider_message_id}
            </Typography.Text>
          )}
        </Space>
      ) : '-',
    },
    {
      title: t('common.actions'),
      key: 'actions',
      render: (_, record) => (
        <Space wrap>
          <Button type="link" onClick={() => onOpenDetails(record.id)}>
            {t('pages.notifications.viewDetails')}
          </Button>
          <Button
            type="link"
            disabled={['sent', 'processing', 'shadow'].includes(record.status)}
            loading={actionPending}
            onClick={() => handleSendNowClick(record)}
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
      <Alert
        type="info"
        showIcon
        message={t('pages.notifications.queueHelpTitle')}
        description={t('pages.notifications.queueHelpDescription')}
      />
      <NoticeError error={error} />
      {loading ? (
        <Card loading />
      ) : visibleInstances.length === 0 ? (
        <Empty
          description={(
            <Space direction="vertical" size={4}>
              <Typography.Text>{t('pages.notifications.noInstances')}</Typography.Text>
              <Typography.Text type="secondary">{t('pages.notifications.noInstancesDescription')}</Typography.Text>
            </Space>
          )}
        />
      ) : (
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          {getQueueSectionOrder.map((sectionKey) => {
            const sectionItems = groupedInstances[sectionKey];
            if (sectionItems.length === 0) {
              return null;
            }

            return (
              <Card
                key={sectionKey}
                title={t(`pages.notifications.queueSections.${sectionKey}`)}
                extra={<Tag>{sectionItems.length}</Tag>}
              >
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                  {sectionItems.map((instance) => {
                    const warnings = extractInstanceWarnings(instance);
                    const eventTime = (instance.explanation?.event_starts_at as string | undefined) ?? null;
                    return (
                      <Card key={instance.id} size="small" type="inner">
                        <Space direction="vertical" style={{ width: '100%' }} size="small">
                          <Space wrap style={{ justifyContent: 'space-between', width: '100%' }}>
                            <Space wrap>
                              <Typography.Text strong>
                                {instance.learner_display_name || `#${instance.recipient_id}`}
                              </Typography.Text>
                              <Tag>{t(`pages.notifications.categories.${instance.category}`)}</Tag>
                              <Tag color={getInstanceStatusColor(instance.status)}>
                                {t(`pages.notifications.instanceStatus.${instance.status}`)}
                              </Tag>
                            </Space>
                            <Typography.Text>
                              {dayjs(instance.effective_scheduled_for).format('YYYY-MM-DD HH:mm')}
                            </Typography.Text>
                          </Space>

                          <Typography.Text type="secondary">
                            {t('pages.notifications.queueTimeline.deliveryLine', {
                              event: t(`pages.notifications.eventTypes.${instance.event_type}`),
                              eventTime: formatDateTime(eventTime),
                            })}
                          </Typography.Text>

                          {warnings.length > 0 && (
                            <Space wrap>
                              {warnings.map((warning) => (
                                <Tag color="orange" key={`${instance.id}-${warning}`}>
                                  {getWarningLabel(warning, t)}
                                </Tag>
                              ))}
                            </Space>
                          )}

                          <Space wrap>
                            <Button size="small" onClick={() => onOpenDetails(instance.id)}>
                              {t('pages.notifications.viewDetails')}
                            </Button>
                            <Button
                              size="small"
                              disabled={['sent', 'processing', 'shadow'].includes(instance.status)}
                              onClick={() => handleSendNowClick(instance)}
                            >
                              {t('pages.notifications.sendNow')}
                            </Button>
                            <Button
                              size="small"
                              danger
                              disabled={['sent', 'processing'].includes(instance.status)}
                              onClick={() => onCancel(instance.id)}
                            >
                              {t('common.cancel')}
                            </Button>
                          </Space>
                        </Space>
                      </Card>
                    );
                  })}
                </Space>
              </Card>
            );
          })}

          <Collapse
            size="small"
            items={[
              {
                key: 'technical-queue',
                label: t('pages.notifications.technicalList'),
                children: (
                  <ResponsiveDataView<NotificationInstance>
                    data={visibleInstances}
                    loading={false}
                    columns={columns}
                    rowKey="id"
                    emptyText={t('pages.notifications.noInstances')}
                    emptyDescription={t('pages.notifications.noInstancesDescription')}
                    renderCard={(instance) => (
                      <Card key={instance.id} title={instance.learner_display_name || `#${instance.id}`} size="small" style={{ marginBottom: 12 }}>
                        <Space direction="vertical">
                          <span>{dayjs(instance.effective_scheduled_for).format('YYYY-MM-DD HH:mm')}</span>
                          <Tag color={getInstanceStatusColor(instance.status)}>{t(`pages.notifications.instanceStatus.${instance.status}`)}</Tag>
                        </Space>
                      </Card>
                    )}
                    pagination={false}
                  />
                ),
              },
            ]}
          />
        </Space>
      )}
      <NotificationInstanceDrawer
        open={selectedInstanceId !== null}
        instance={selectedInstance}
        loading={detailLoading}
        error={detailError}
        onClose={onCloseDetails}
      />
      <Modal
        open={Boolean(pendingSendNowInstance)}
        title={t('pages.notifications.sendNowConfirmTitle')}
        okText={t('pages.notifications.sendNow')}
        cancelText={t('common.cancel')}
        okButtonProps={{ danger: true, loading: actionPending }}
        onCancel={() => setPendingSendNowInstance(null)}
        onOk={() => {
          if (!pendingSendNowInstance) return;
          onSendNow(pendingSendNowInstance.id);
          setPendingSendNowInstance(null);
        }}
      >
        <Alert
          type="warning"
          showIcon
          message={t('pages.notifications.sendNowConfirmDescription', {
            learner: pendingSendNowInstance?.learner_display_name ?? `#${pendingSendNowInstance?.recipient_id ?? '—'}`,
            category: pendingSendNowInstance ? t(`pages.notifications.categories.${pendingSendNowInstance.category}`) : '',
          })}
        />
      </Modal>
    </Space>
  );
};

interface NotificationInstanceDrawerProps {
  open: boolean;
  instance: NotificationInstance | null;
  loading: boolean;
  error: Error | null;
  onClose: () => void;
}

const NotificationInstanceDrawer: React.FC<NotificationInstanceDrawerProps> = ({
  open,
  instance,
  loading,
  error,
  onClose,
}) => {
  const { t } = useTranslation();

  const warnings = useMemo(
    () => (instance ? extractInstanceWarnings(instance) : []),
    [instance],
  );
  const calendarConflict = instance?.explanation?.calendar_conflict as Record<string, unknown> | undefined;
  const componentExplanations = Array.isArray(instance?.explanation?.component_explanations)
    ? instance?.explanation?.component_explanations as Array<Record<string, unknown>>
    : [];

  return (
    <Drawer
      open={open}
      width={720}
      title={instance ? t('pages.notifications.queueDetails.titleWithId', { id: instance.id }) : t('pages.notifications.queueDetails.title')}
      onClose={onClose}
      destroyOnHidden
    >
      {loading ? (
        <Card loading />
      ) : error ? (
        <Alert
          type="error"
          showIcon
          message={t('errors.loadFailed', { message: formatApiError(error) })}
        />
      ) : !instance ? (
        <Empty description={t('pages.notifications.queueDetails.notFound')} />
      ) : (
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Descriptions bordered column={1} size="small" title={t('pages.notifications.queueDetails.summary')}>
            <Descriptions.Item label={t('pages.notifications.learner')}>
              {instance.learner_display_name || `#${instance.recipient_id}`}
            </Descriptions.Item>
            <Descriptions.Item label={t('pages.notifications.category')}>
              <Tag>{t(`pages.notifications.categories.${instance.category}`)}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label={t('pages.notifications.status')}>
              <Tag color={getInstanceStatusColor(instance.status)}>
                {t(`pages.notifications.instanceStatus.${instance.status}`)}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label={t('pages.notifications.queueDetails.statusReason')}>
              {getStatusReasonLabel(instance.status_reason, t)}
            </Descriptions.Item>
            <Descriptions.Item label={t('pages.notifications.queueDetails.eventTime')}>
              {formatDateTime((instance.explanation?.event_starts_at as string | undefined) ?? null)}
            </Descriptions.Item>
            <Descriptions.Item label={t('pages.notifications.scheduledFor')}>
              {formatDateTime(instance.scheduled_for)}
            </Descriptions.Item>
            <Descriptions.Item label={t('pages.notifications.queueDetails.effectiveScheduledFor')}>
              {formatDateTime(instance.effective_scheduled_for)}
            </Descriptions.Item>
            <Descriptions.Item label={t('pages.notifications.delivery')}>
              {instance.delivery_enabled ? t('pages.notifications.queueDetails.deliveryEnabled') : t('pages.notifications.queueDetails.deliveryDisabled')}
            </Descriptions.Item>
            <Descriptions.Item label={t('pages.notifications.queueDetails.priority')}>
              {t(`pages.notifications.priorities.${instance.priority}`)}
            </Descriptions.Item>
            <Descriptions.Item label={t('pages.notifications.queueDetails.channel')}>
              {instance.channel}
            </Descriptions.Item>
          </Descriptions>

          <Descriptions bordered column={1} size="small" title={t('pages.notifications.queueDetails.source')}>
            <Descriptions.Item label={t('pages.notifications.queueDetails.rule')}>
              {instance.explanation?.rule_name
                ? `${String(instance.explanation.rule_name)}${instance.rule_id ? ` (#${instance.rule_id})` : ''}`
                : instance.rule_id ? `#${instance.rule_id}` : '—'}
            </Descriptions.Item>
            <Descriptions.Item label={t('pages.notifications.queueDetails.event')}>
              {`${t(`pages.notifications.eventTypes.${instance.event_type}`)} #${instance.event_id ?? '—'}`}
            </Descriptions.Item>
            <Descriptions.Item label={t('pages.notifications.queueDetails.combination')}>
              {instance.combination_key || '—'}
            </Descriptions.Item>
          </Descriptions>

          <Card size="small" title={t('pages.notifications.queueDetails.warnings')}>
            {warnings.length === 0 ? (
              <Typography.Text type="secondary">
                {t('pages.notifications.queueDetails.noWarnings')}
              </Typography.Text>
            ) : (
              <Space wrap>
                {warnings.map((warning) => (
                  <Tag color="orange" key={warning}>
                    {getWarningLabel(warning, t)}
                  </Tag>
                ))}
              </Space>
            )}
          </Card>

          {calendarConflict && (
            <Alert
              type="warning"
              showIcon
              message={t('pages.notifications.queueDetails.calendarConflictTitle')}
              description={t('pages.notifications.queueDetails.calendarConflictDescription', {
                count: Number(calendarConflict.count || 0),
                lessonIds: Array.isArray(calendarConflict.lesson_ids) ? (calendarConflict.lesson_ids as Array<number | string>).join(', ') : '—',
                packageIds: Array.isArray(calendarConflict.package_ids) ? (calendarConflict.package_ids as Array<number | string>).join(', ') : '—',
              })}
            />
          )}

          {instance.components.length > 0 && (
            <Card size="small" title={t('pages.notifications.queueDetails.components')}>
              <Space direction="vertical" style={{ width: '100%' }}>
                {instance.components.map((component, index) => {
                  const componentExplanation = componentExplanations[index];
                  const componentWarnings = Array.isArray(componentExplanation?.warnings)
                    ? componentExplanation.warnings as string[]
                    : [];
                  return (
                    <Card key={component.component_id} size="small" type="inner" title={t(`pages.notifications.categories.${component.category}`)}>
                      <Space direction="vertical" size={4}>
                        <Typography.Text>
                          {t('pages.notifications.queueDetails.rule')}: {component.rule_id ? `#${component.rule_id}` : '—'}
                        </Typography.Text>
                        <Typography.Text>
                          {t('pages.notifications.queueDetails.componentKey')}: <Typography.Text code>{component.component_key}</Typography.Text>
                        </Typography.Text>
                        <Typography.Text>
                          {t('pages.notifications.queueDetails.eventTime')}: {formatDateTime((componentExplanation?.event_starts_at as string | undefined) ?? null)}
                        </Typography.Text>
                        {componentWarnings.length > 0 && (
                          <Space wrap>
                            {componentWarnings.map((warning) => (
                              <Tag color="orange" key={`${component.component_id}-${warning}`}>
                                {getWarningLabel(warning, t)}
                              </Tag>
                            ))}
                          </Space>
                        )}
                      </Space>
                    </Card>
                  );
                })}
              </Space>
            </Card>
          )}

          <Descriptions bordered column={1} size="small" title={t('pages.notifications.queueDetails.latestAttempt')}>
            <Descriptions.Item label={t('pages.notifications.status')}>
              {instance.latest_attempt
                ? getInstanceStatusLabel(instance.latest_attempt.status, t)
                : t('pages.notifications.queueDetails.noAttempt')}
            </Descriptions.Item>
            <Descriptions.Item label={t('pages.notifications.queueDetails.providerMessageId')}>
              {instance.latest_attempt?.provider_message_id ? `#${instance.latest_attempt.provider_message_id}` : '—'}
            </Descriptions.Item>
            <Descriptions.Item label={t('pages.notifications.queueDetails.providerChatId')}>
              {instance.latest_attempt?.provider_chat_id || '—'}
            </Descriptions.Item>
            <Descriptions.Item label={t('pages.notifications.queueDetails.error')}>
              {instance.latest_attempt?.error_message || instance.latest_attempt?.error_code || '—'}
            </Descriptions.Item>
            <Descriptions.Item label={t('pages.notifications.queueDetails.sentAt')}>
              {formatDateTime(instance.latest_attempt?.sent_at)}
            </Descriptions.Item>
          </Descriptions>

          <Collapse
            size="small"
            items={[
              {
                key: 'debug',
                label: t('pages.notifications.queueDetails.debug'),
                children: (
                  <Typography.Paragraph
                    copyable={{ text: JSON.stringify({
                      dedupe_key: instance.dedupe_key,
                      explanation: instance.explanation,
                      latest_attempt: instance.latest_attempt,
                    }, null, 2) }}
                    style={{ marginBottom: 0 }}
                  >
                    <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                      {JSON.stringify({
                        dedupe_key: instance.dedupe_key,
                        explanation: instance.explanation,
                        latest_attempt: instance.latest_attempt,
                      }, null, 2)}
                    </pre>
                  </Typography.Paragraph>
                ),
              },
            ]}
          />
        </Space>
      )}
    </Drawer>
  );
};

interface ActivityTabProps {
  activity: NotificationActivity[];
  acknowledgements: NotificationActivityAcknowledgement[];
  loading: boolean;
  error: Error | null;
  acknowledgingActivityId: number | null;
  onAcknowledge: (activityId: number) => void;
}

const ActivityTab: React.FC<ActivityTabProps> = ({
  activity,
  acknowledgements,
  loading,
  error,
  acknowledgingActivityId,
  onAcknowledge,
}) => {
  const { t } = useTranslation();
  const acknowledgedActivityKeys = useMemo(
    () => new Set(acknowledgements.map((item) => `${item.activity_type}:${item.activity_id}`)),
    [acknowledgements],
  );
  const groupedActivity = useMemo(() => {
    const groups: Record<'attention' | 'recent', NotificationActivity[]> = {
      attention: [],
      recent: [],
    };
    activity.forEach((item) => {
      groups[getActivitySectionKey(item, acknowledgedActivityKeys)].push(item);
    });
    return groups;
  }, [acknowledgedActivityKeys, activity]);

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
      render: (value: string) => <Tag>{getActivityTypeLabel(value, t)}</Tag>,
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
      render: (_value: string, record) => {
        const visibleStatus = getActivityVisibleStatus(record, acknowledgedActivityKeys);
        return <Tag color={getActivityStatusColor(visibleStatus)}>{getActivityStatusLabel(visibleStatus, t)}</Tag>;
      },
    },
    {
      title: t('pages.notifications.details'),
      key: 'details',
      render: (_, record) => getActivityDetails(record, t),
    },
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Alert
        type="info"
        showIcon
        message={t('pages.notifications.activityHelpTitle')}
        description={t('pages.notifications.activityHelpDescription')}
      />
      <NoticeError error={error} />
      {loading ? (
        <Card loading />
      ) : activity.length === 0 ? (
        <Empty
          description={(
            <Space direction="vertical" size={4}>
              <Typography.Text>{t('pages.notifications.noActivity')}</Typography.Text>
              <Typography.Text type="secondary">{t('pages.notifications.noActivityDescription')}</Typography.Text>
            </Space>
          )}
        />
      ) : (
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          {(['attention', 'recent'] as const).map((sectionKey) => {
            const items = groupedActivity[sectionKey];
            if (items.length === 0) {
              return null;
            }

            return (
              <Card
                key={sectionKey}
                title={t(`pages.notifications.activitySections.${sectionKey}`)}
                extra={<Tag color={sectionKey === 'attention' ? 'red' : 'blue'}>{items.length}</Tag>}
              >
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                  {items.map((item) => (
                    <Card key={`${item.activity_type}-${item.activity_id}`} size="small" type="inner">
                      <Space direction="vertical" style={{ width: '100%' }} size="small">
                        <Space wrap style={{ justifyContent: 'space-between', width: '100%' }}>
                          <Space wrap>
                            <Typography.Text strong>
                              {item.learner_display_name || t(`pages.notifications.eventTypes.${item.event_type}`)}
                            </Typography.Text>
                            <Tag>{getActivityTypeLabel(item.activity_type, t)}</Tag>
                            <Tag color={getActivityStatusColor(getActivityVisibleStatus(item, acknowledgedActivityKeys))}>
                              {getActivityStatusLabel(getActivityVisibleStatus(item, acknowledgedActivityKeys), t)}
                            </Tag>
                          </Space>
                          <Space wrap size="small">
                            {sectionKey === 'attention' && isHandleableActivity(item) && (
                              <Button
                                size="small"
                                type="text"
                                onClick={() => onAcknowledge(item.activity_id)}
                                loading={acknowledgingActivityId === item.activity_id}
                              >
                                {t('pages.notifications.markHandled')}
                              </Button>
                            )}
                            <Typography.Text>
                              {item.occurred_at ? dayjs(item.occurred_at).format('YYYY-MM-DD HH:mm') : '-'}
                            </Typography.Text>
                          </Space>
                        </Space>
                        <Typography.Text>
                          {getActivityDetails(item, t)}
                        </Typography.Text>
                      </Space>
                    </Card>
                  ))}
                </Space>
              </Card>
            );
          })}

          <Collapse
            size="small"
            items={[
              {
                key: 'technical-activity',
                label: t('pages.notifications.technicalList'),
                children: (
                  <ResponsiveDataView<NotificationActivity>
                    data={activity}
                    loading={false}
                    columns={columns}
                    rowKey={(record) => `${record.activity_type}-${record.activity_id}`}
                    emptyText={t('pages.notifications.noActivity')}
                    emptyDescription={t('pages.notifications.noActivityDescription')}
                    renderCard={(item) => (
                      <Card key={`${item.activity_type}-${item.activity_id}`} title={item.learner_display_name || item.activity_type} size="small" style={{ marginBottom: 12 }}>
                        <Space direction="vertical">
                          <span>{item.occurred_at ? dayjs(item.occurred_at).format('YYYY-MM-DD HH:mm') : '-'}</span>
                          <Tag color={getActivityStatusColor(getActivityVisibleStatus(item, acknowledgedActivityKeys))}>
                            {getActivityStatusLabel(getActivityVisibleStatus(item, acknowledgedActivityKeys), t)}
                          </Tag>
                          <span>{getActivityDetails(item, t)}</span>
                        </Space>
                      </Card>
                    )}
                    pagination={false}
                  />
                ),
              },
            ]}
          />
        </Space>
      )}
    </Space>
  );
};

interface SettingsTabProps {
  form: ReturnType<typeof Form.useForm<NotificationSettingsFormValues>>[0];
  loading: boolean;
  error: Error | null;
  saving: boolean;
  onSubmit: (values: NotificationSettingsFormValues) => void;
  learnerModes: LearnerNotificationMode[];
  learnerModesLoading: boolean;
  learnerModesError: Error | null;
  learnerModeUpdating: boolean;
  onLearnerModeChange: (learnerId: number, modeOverride: string) => void;
  pilotSummary: NotificationPilotSummary;
  processingJobs: boolean;
  deliveringNow: boolean;
  onProcessJobs: () => void;
  onDeliverNow: () => void;
}

const SettingsTab: React.FC<SettingsTabProps> = ({
  form,
  loading,
  error,
  saving,
  onSubmit,
  learnerModes,
  learnerModesLoading,
  learnerModesError,
  learnerModeUpdating,
  onLearnerModeChange,
  pilotSummary,
  processingJobs,
  deliveringNow,
  onProcessJobs,
  onDeliverNow,
}) => {
  const { t } = useTranslation();
  const [pendingGlobalNewValues, setPendingGlobalNewValues] = useState<NotificationSettingsFormValues | null>(null);
  const [confirmDeliverNowOpen, setConfirmDeliverNowOpen] = useState(false);
  const selectedMode = Form.useWatch('mode', form) ?? pilotSummary.globalMode;
  const nextAction = getPilotNextAction(pilotSummary);
  const checklistItems = getPilotChecklistStatus(pilotSummary);
  const currentChecklistIndex = checklistItems.findIndex((item) => item.status === 'process');
  const deliveryBlocked = pilotSummary.dueDeliveryCount === 0;

  const handleSubmit = (values: NotificationSettingsFormValues) => {
    if (values.mode === 'new') {
      setPendingGlobalNewValues(values);
      return;
    }
    onSubmit(values);
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <NoticeError error={error} />
      <Card title={t('pages.notifications.rolloutStatus.title')}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <Typography.Text type="secondary">
              {t('pages.notifications.rolloutStatus.nextActionTitle')}
            </Typography.Text>
            <Alert
              type={nextAction.type}
              showIcon
              message={t(nextAction.translationKey)}
              style={{ marginTop: 8 }}
            />
          </div>
          <Row gutter={[24, 16]}>
            <Col xs={12} sm={8} md={6} xl={4}>
              <Space direction="vertical" size={2}>
                <Typography.Text type="secondary">{t('pages.notifications.rolloutStatus.globalMode')}</Typography.Text>
                <Tag color={pilotSummary.globalMode === 'new' ? 'red' : pilotSummary.globalMode === 'shadow' ? 'blue' : 'default'}>
                  {t(`pages.notifications.modes.${pilotSummary.globalMode}`)}
                </Tag>
              </Space>
            </Col>
            <Col xs={12} sm={8} md={6} xl={4}>
              <Space direction="vertical" size={2}>
                <Typography.Text type="secondary">{t('pages.notifications.rolloutStatus.totalLearners')}</Typography.Text>
                <Typography.Text strong>{pilotSummary.totalLearners}</Typography.Text>
              </Space>
            </Col>
            <Col xs={12} sm={8} md={6} xl={4}>
              <Space direction="vertical" size={2}>
                <Typography.Text type="secondary">{t('pages.notifications.rolloutStatus.learnersInTestMode')}</Typography.Text>
                <Typography.Text strong>{pilotSummary.learnerShadowCount}</Typography.Text>
              </Space>
            </Col>
            <Col xs={12} sm={8} md={6} xl={4}>
              <Space direction="vertical" size={2}>
                <Typography.Text type="secondary">{t('pages.notifications.rolloutStatus.learnersInNew')}</Typography.Text>
                <Typography.Text strong>{pilotSummary.learnerNewCount}</Typography.Text>
              </Space>
            </Col>
            <Col xs={12} sm={8} md={6} xl={4}>
              <Space direction="vertical" size={2}>
                <Typography.Text type="secondary">{t('pages.notifications.rolloutStatus.plannedNotifications')}</Typography.Text>
                <Typography.Text strong>{pilotSummary.plannedCount}</Typography.Text>
              </Space>
            </Col>
            <Col xs={12} sm={8} md={6} xl={4}>
              <Space direction="vertical" size={2}>
                <Typography.Text type="secondary">{t('pages.notifications.rolloutStatus.readyForDelivery')}</Typography.Text>
                <Typography.Text strong>{pilotSummary.dueDeliveryCount}</Typography.Text>
              </Space>
            </Col>
            <Col xs={12} sm={8} md={6} xl={4}>
              <Space direction="vertical" size={2}>
                <Typography.Text type="secondary">{t('pages.notifications.rolloutStatus.attentionAlerts')}</Typography.Text>
                <Typography.Text strong>{pilotSummary.attentionAlertCount}</Typography.Text>
              </Space>
            </Col>
          </Row>
        </Space>
      </Card>

      <Row gutter={[16, 16]} align="stretch">
        <Col xs={24} xl={10}>
          <Card title={t('pages.notifications.pilotControls.title')} style={{ height: '100%' }}>
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                {t('pages.notifications.pilotControls.noticeDescription')}
              </Typography.Paragraph>
              <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                {t('pages.notifications.pilotControls.statusSummary', {
                  planned: pilotSummary.plannedCount,
                  ready: pilotSummary.dueDeliveryCount,
                })}
              </Typography.Paragraph>
              <Space wrap>
                <Button onClick={onProcessJobs} loading={processingJobs}>
                  {t('pages.notifications.pilotControls.processJobs')}
                </Button>
                <Button
                  danger
                  disabled={deliveryBlocked}
                  onClick={() => setConfirmDeliverNowOpen(true)}
                  loading={deliveringNow}
                >
                  {t('pages.notifications.pilotControls.deliverNow')}
                </Button>
              </Space>
              {deliveryBlocked && (
                <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                  {t('pages.notifications.pilotControls.deliveryBlockedHint')}
                </Typography.Paragraph>
              )}
            </Space>
          </Card>
        </Col>
        <Col xs={24} xl={14}>
          <Card title={t('pages.notifications.settingsPanelTitle')} loading={loading} style={{ height: '100%' }}>
            <Typography.Paragraph type="secondary">
              {t('pages.notifications.settingsPanelDescription')}
            </Typography.Paragraph>
            <Form<NotificationSettingsFormValues> form={form} layout="vertical" onFinish={handleSubmit}>
              <Row gutter={16}>
                <Col xs={24} md={12}>
                  <Form.Item name="mode" label={t('pages.notifications.systemMode')} rules={[{ required: true }]}>
                    <Select
                      options={[
                        { value: 'legacy', label: t('pages.notifications.modes.legacy') },
                        { value: 'shadow', label: t('pages.notifications.modes.shadow') },
                        { value: 'new', label: t('pages.notifications.modes.new') },
                      ]}
                    />
                  </Form.Item>
                  <Typography.Paragraph type="secondary" style={{ marginTop: -8 }}>
                    {t(`pages.notifications.modeDescriptions.${selectedMode}`)}
                  </Typography.Paragraph>
                </Col>
              </Row>
              <Collapse
                size="small"
                style={{ marginBottom: 16 }}
                items={[
                  {
                    key: 'advanced-settings',
                    label: t('pages.notifications.advancedSettingsTitle'),
                    children: (
                      <>
                        <Row gutter={16}>
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
                          <Col xs={24} md={8}>
                            <Form.Item name="notifications_enabled" valuePropName="checked" label={t('pages.notifications.notificationsEnabled')}>
                              <Switch />
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
                      </>
                    ),
                  },
                ]}
              />
              <Button type="primary" htmlType="submit" loading={saving}>
                {t('common.save')}
              </Button>
            </Form>
          </Card>
        </Col>
      </Row>

      <LearnerRolloutSettings
        learnerModes={learnerModes}
        loading={learnerModesLoading}
        error={learnerModesError}
        updating={learnerModeUpdating}
        onModeChange={onLearnerModeChange}
      />

      <Collapse
        size="small"
        items={[
          {
            key: 'rollout-checklist',
            label: t('pages.notifications.rolloutChecklist.title'),
            children: (
              <Space direction="vertical" style={{ width: '100%' }} size="middle">
                <Alert
                  type="info"
                  showIcon
                  message={t('pages.notifications.rolloutChecklist.noticeTitle')}
                  description={t('pages.notifications.rolloutChecklist.noticeDescription')}
                />
                <Steps
                  direction="vertical"
                  size="small"
                  current={currentChecklistIndex === -1 ? checklistItems.length - 1 : currentChecklistIndex}
                  items={checklistItems.map((item) => ({
                    status: item.status,
                    title: t(item.titleKey),
                  }))}
                />
              </Space>
            ),
          },
        ]}
      />

      <Modal
        open={Boolean(pendingGlobalNewValues)}
        title={t('pages.notifications.globalNewConfirmTitle')}
        okText={t('pages.notifications.enableGlobalNew')}
        cancelText={t('common.cancel')}
        okButtonProps={{ danger: true, loading: saving }}
        onCancel={() => setPendingGlobalNewValues(null)}
        onOk={() => {
          if (!pendingGlobalNewValues) return;
          onSubmit({
            ...pendingGlobalNewValues,
            confirm_global_new: true,
          });
          setPendingGlobalNewValues(null);
        }}
      >
        <Alert
          type="warning"
          showIcon
          message={t('pages.notifications.globalNewConfirmDescription')}
        />
      </Modal>
      <Modal
        open={confirmDeliverNowOpen}
        title={t('pages.notifications.pilotControls.deliverNowConfirmTitle')}
        okText={t('pages.notifications.pilotControls.deliverNow')}
        cancelText={t('common.cancel')}
        okButtonProps={{ danger: true, loading: deliveringNow }}
        onCancel={() => setConfirmDeliverNowOpen(false)}
        onOk={() => {
          onDeliverNow();
          setConfirmDeliverNowOpen(false);
        }}
      >
        <Alert
          type="warning"
          showIcon
          message={t('pages.notifications.pilotControls.deliverNowConfirmDescription')}
        />
      </Modal>
    </Space>
  );
};

interface LearnerRolloutSettingsProps {
  learnerModes: LearnerNotificationMode[];
  loading: boolean;
  error: Error | null;
  updating: boolean;
  onModeChange: (learnerId: number, modeOverride: string) => void;
}

const LearnerRolloutSettings: React.FC<LearnerRolloutSettingsProps> = ({
  learnerModes,
  loading,
  error,
  updating,
  onModeChange,
}) => {
  const { t } = useTranslation();
  const [pendingNewModeLearner, setPendingNewModeLearner] = useState<LearnerNotificationMode | null>(null);

  const handleModeChange = (learner: LearnerNotificationMode, modeOverride: string) => {
    if (modeOverride !== 'new') {
      onModeChange(learner.learner_id, modeOverride);
      return;
    }

    setPendingNewModeLearner(learner);
  };

  const columns: TableProps<LearnerNotificationMode>['columns'] = [
    {
      title: t('pages.notifications.learner'),
      dataIndex: 'display_name',
      key: 'display_name',
    },
    {
      title: t('pages.notifications.rollout.overrideMode'),
      dataIndex: 'mode_override',
      key: 'mode_override',
      render: (value: string, record) => (
        <Select
          value={value}
          style={{ minWidth: 180 }}
          disabled={updating}
          onChange={(nextMode) => handleModeChange(record, nextMode)}
          options={[
            { value: 'inherit', label: t('pages.notifications.modes.inherit') },
            { value: 'legacy', label: t('pages.notifications.modes.legacy') },
            { value: 'shadow', label: t('pages.notifications.modes.shadow') },
            { value: 'new', label: t('pages.notifications.modes.new') },
          ]}
        />
      ),
    },
    {
      title: t('pages.notifications.rollout.effectiveMode'),
      dataIndex: 'effective_mode',
      key: 'effective_mode',
      render: (value: string) => <Tag color={getModeColor(value)}>{t(`pages.notifications.modes.${value}`)}</Tag>,
    },
    {
      title: t('pages.notifications.rollout.updatedAt'),
      dataIndex: 'updated_at',
      key: 'updated_at',
      render: (value: string | null) => value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '-',
    },
  ];

  return (
    <>
      <Card title={t('pages.notifications.rollout.title')}>
        <Alert
          type="warning"
          showIcon
          message={t('pages.notifications.rollout.noticeTitle')}
          description={t('pages.notifications.rollout.noticeDescription')}
          style={{ marginBottom: 16 }}
        />
        <NoticeError error={error} />
        <ResponsiveDataView<LearnerNotificationMode>
          data={learnerModes}
          loading={loading}
          columns={columns}
          rowKey="learner_id"
          emptyText={t('pages.notifications.rollout.noLearners')}
          emptyDescription={t('pages.notifications.rollout.noLearnersDescription')}
          renderCard={(learner) => (
            <Card key={learner.learner_id} title={learner.display_name} size="small" style={{ marginBottom: 12 }}>
              <Space direction="vertical" style={{ width: '100%' }}>
                <Tag color={getModeColor(learner.effective_mode)}>
                  {t('pages.notifications.rollout.effectiveMode')}: {t(`pages.notifications.modes.${learner.effective_mode}`)}
                </Tag>
                <Select
                  value={learner.mode_override}
                  disabled={updating}
                  onChange={(nextMode) => handleModeChange(learner, nextMode)}
                  options={[
                    { value: 'inherit', label: t('pages.notifications.modes.inherit') },
                    { value: 'legacy', label: t('pages.notifications.modes.legacy') },
                    { value: 'shadow', label: t('pages.notifications.modes.shadow') },
                    { value: 'new', label: t('pages.notifications.modes.new') },
                  ]}
                />
              </Space>
            </Card>
          )}
          pagination={false}
        />
      </Card>

      <Modal
        open={Boolean(pendingNewModeLearner)}
        title={t('pages.notifications.rollout.newConfirmTitle')}
        okText={t('pages.notifications.rollout.enableNewForLearner')}
        cancelText={t('common.cancel')}
        okButtonProps={{ danger: true, loading: updating }}
        onCancel={() => setPendingNewModeLearner(null)}
        onOk={() => {
          if (!pendingNewModeLearner) return;
          onModeChange(pendingNewModeLearner.learner_id, 'new');
          setPendingNewModeLearner(null);
        }}
      >
        <Alert
          type="warning"
          showIcon
          message={t('pages.notifications.rollout.newConfirmDescription', {
            name: pendingNewModeLearner?.display_name ?? '',
          })}
        />
      </Modal>
    </>
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

const getRuleDisplayStatus = (status: string): 'active' | 'paused' | 'archived' => {
  switch (status) {
    case 'active':
      return 'active';
    case 'archived':
      return 'archived';
    case 'paused':
    case 'draft':
    default:
      return 'paused';
  }
};

const getRuleStatusColor = (status: string) => {
  switch (getRuleDisplayStatus(status)) {
    case 'active': return 'green';
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

const getModeColor = (mode: string) => {
  switch (mode) {
    case 'new': return 'green';
    case 'shadow': return 'purple';
    case 'legacy': return 'default';
    case 'inherit': return 'blue';
    default: return 'default';
  }
};

export default Notifications;
