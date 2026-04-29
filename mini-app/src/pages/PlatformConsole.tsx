import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Collapse,
  Divider,
  Form,
  Input,
  InputNumber,
  List,
  Segmented,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  ArrowLeftOutlined,
  CreditCardOutlined,
  EyeOutlined,
  GlobalOutlined,
  LoginOutlined,
  PlusOutlined,
  ReloadOutlined,
  SendOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { Link } from 'react-router-dom';
import api from '../services/api';
import { useAuth } from '../auth/AuthProvider';
import { useTheme } from '../theme/ThemeProvider';
import { useResponsive } from '../hooks/useResponsive';
import PageHeader from '../components/common/PageHeader';
import ResponsiveModal from '../components/common/ResponsiveModal';
import Admin from './Admin';

const { Text, Title } = Typography;

interface Tenant {
  id: number;
  name: string;
  slug: string;
  contact_email?: string | null;
  is_active: boolean;
  access: TenantAccess;
  billing?: BillingSnapshot | null;
}

interface TenantAccess {
  tenant_id: number;
  status: string;
  mode: string;
  access_until?: string | null;
  grace_until?: string | null;
  is_lifetime: boolean;
  reason?: string | null;
  notes?: string | null;
}

interface BillingSnapshot {
  plan_code: string;
  plan_name: string;
  subscription_plan_code?: string | null;
  subscription_status?: string | null;
  provider?: string | null;
  active_learners_limit: number;
  active_learners_count: number;
  monthly_price_rub: number;
  yearly_price_rub?: number | null;
  current_period_start?: string | null;
  current_period_end?: string | null;
  grace_until?: string | null;
  cancel_at_period_end: boolean;
  is_effective_free_plan: boolean;
  is_over_limit: boolean;
  notifications_allowed: boolean;
  can_create_learner: boolean;
  can_restore_learner: boolean;
  billing_restriction_reason?: string | null;
}

interface TenantListResponse {
  items: Tenant[];
  total: number;
}

interface TenantAccessSyncResponse {
  grace_started: number;
  expired: number;
  changed: number;
}

interface BroadcastRecipientPreview {
  bot_user_id: number;
  chat_id: number;
  display_name?: string | null;
  username?: string | null;
}

interface BroadcastPreview {
  audience: string;
  total: number;
  sample: BroadcastRecipientPreview[];
}

interface BroadcastCampaign {
  id: number;
  title: string;
  message_text: string;
  audience: string;
  status: string;
  recipient_count: number;
  sent_count: number;
  failed_count: number;
  skipped_count: number;
  rate_limit_per_second: number;
  last_task_id?: string | null;
  created_at: string;
  queued_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

interface BroadcastRecipient {
  id: number;
  chat_id: number;
  display_name?: string | null;
  username?: string | null;
  status: string;
  error_message?: string | null;
  sent_at?: string | null;
}

interface BroadcastAudienceUser {
  bot_user_id: number;
  chat_id: number;
  display_name?: string | null;
  username?: string | null;
  is_platform_admin: boolean;
}

interface BroadcastListResponse {
  items: BroadcastCampaign[];
  total: number;
}

interface BroadcastAudienceUsersResponse {
  items: BroadcastAudienceUser[];
  total: number;
}

interface BroadcastRecipientListResponse {
  items: BroadcastRecipient[];
  total: number;
}

interface BroadcastFormValues {
  title: string;
  message_text: string;
  audience: 'platform_admins' | 'selected_bot_users' | 'all_bot_users';
  bot_user_ids?: number[];
  rate_limit_per_second: number;
}

interface BillingGrantFormValues {
  plan_code: string;
  scenario: string;
  status: string;
  period_end_offset_days: number;
  notes?: string;
}

interface PlatformTenantEvent {
  id: number;
  domain: 'access' | 'billing' | string;
  action: string;
  actor_user_id?: number | null;
  notes?: string | null;
  created_at: string;
}

interface PlatformTenantEventsResponse {
  items: PlatformTenantEvent[];
}

interface TenantActionConfig {
  key: string;
  label: string;
  icon?: React.ReactNode;
  type?: 'primary' | 'default';
  danger?: boolean;
  disabled?: boolean;
  loading?: boolean;
  href?: string;
  onClick?: () => void;
}

type ConsoleSection = 'broadcasts' | 'tenants' | 'users';

const BILLING_PLAN_OPTIONS = [
  { value: 'start', label: 'Старт · 0-3 ученика' },
  { value: 'basic', label: 'Базовый · 4-10 учеников' },
  { value: 'pro', label: 'Про · 11-20 учеников' },
  { value: 'studio', label: 'Бизнес · 21+ учеников' },
];

const BILLING_STATUS_OPTIONS = [
  { value: 'manual', label: 'manual · ручная подписка' },
  { value: 'active', label: 'active · активная подписка' },
  { value: 'canceled', label: 'canceled · действует до конца периода' },
  { value: 'past_due', label: 'past_due · льготный период' },
  { value: 'suspended', label: 'suspended · отключена' },
];

const BILLING_SCENARIO_OPTIONS = [
  { value: 'active_custom', label: 'Активна до выбранной даты' },
  { value: 'lifetime', label: 'Бессрочная подписка' },
  { value: 'expired_yesterday', label: 'Уже закончилась вчера' },
  { value: 'ends_today', label: 'Закончится сегодня' },
  { value: 'canceled_at_period_end', label: 'Отменена, доступ до конца периода' },
  { value: 'past_due', label: 'Past due / grace' },
  { value: 'suspended', label: 'Заблокирована' },
];

const PlatformConsole = () => {
  const { tenantId, canSwitchTenant, switchTenant, logout } = useAuth();
  const { resolvedTheme } = useTheme();
  const { isMobile } = useResponsive();
  const colors = resolvedTheme.colors;
  const isDark = resolvedTheme.colorScheme === 'dark';
  const [broadcastForm] = Form.useForm<BroadcastFormValues>();
  const [billingForm] = Form.useForm<BillingGrantFormValues>();
  const selectedBroadcastAudience = Form.useWatch('audience', broadcastForm) ?? 'platform_admins';
  const billingFormValues = Form.useWatch([], billingForm) as Partial<BillingGrantFormValues> | undefined;
  const [activeSection, setActiveSection] = useState<ConsoleSection>('broadcasts');
  const [isBroadcastComposerOpen, setIsBroadcastComposerOpen] = useState(false);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [switchingTenantId, setSwitchingTenantId] = useState<number | 'global' | null>(null);
  const [accessActionKey, setAccessActionKey] = useState<string | null>(null);
  const [billingActionKey, setBillingActionKey] = useState<string | null>(null);
  const [managingTenantId, setManagingTenantId] = useState<number | null>(null);
  const [isSyncingAccess, setIsSyncingAccess] = useState(false);
  const [broadcastPreview, setBroadcastPreview] = useState<BroadcastPreview | null>(null);
  const [broadcasts, setBroadcasts] = useState<BroadcastCampaign[]>([]);
  const [broadcastTotal, setBroadcastTotal] = useState(0);
  const [isPreviewingBroadcast, setIsPreviewingBroadcast] = useState(false);
  const [isCreatingBroadcast, setIsCreatingBroadcast] = useState(false);
  const [isLoadingBroadcasts, setIsLoadingBroadcasts] = useState(false);
  const [sendingBroadcastId, setSendingBroadcastId] = useState<number | null>(null);
  const [sendConfirmation, setSendConfirmation] = useState('');
  const [recipientModalCampaign, setRecipientModalCampaign] = useState<BroadcastCampaign | null>(null);
  const [broadcastRecipients, setBroadcastRecipients] = useState<BroadcastRecipient[]>([]);
  const [broadcastRecipientTotal, setBroadcastRecipientTotal] = useState(0);
  const [isLoadingRecipients, setIsLoadingRecipients] = useState(false);
  const [broadcastAudienceUsers, setBroadcastAudienceUsers] = useState<BroadcastAudienceUser[]>([]);
  const [isLoadingAudienceUsers, setIsLoadingAudienceUsers] = useState(false);
  const [tenantEvents, setTenantEvents] = useState<PlatformTenantEvent[]>([]);
  const [isLoadingTenantEvents, setIsLoadingTenantEvents] = useState(false);
  const activeTenant = useMemo(
    () => tenants.find((tenant) => tenant.id === tenantId) ?? null,
    [tenantId, tenants],
  );
  const managingTenant = useMemo(
    () => tenants.find((tenant) => tenant.id === managingTenantId) ?? null,
    [managingTenantId, tenants],
  );

  const inferBillingScenario = (billing?: BillingSnapshot | null) => {
    if (!billing || billing.plan_code === 'start') return 'active_custom';
    if (billing.subscription_status === 'suspended') return 'suspended';
    if (billing.subscription_status === 'past_due') return 'past_due';
    if (billing.subscription_status === 'canceled') return 'canceled_at_period_end';
    if (!billing.current_period_end) return 'lifetime';

    const daysLeft = Math.ceil((new Date(billing.current_period_end).getTime() - Date.now()) / (1000 * 60 * 60 * 24));
    if (daysLeft < 0) return 'expired_yesterday';
    if (daysLeft === 0) return 'ends_today';
    return 'active_custom';
  };

  useEffect(() => {
    if (!managingTenant) return;
    const periodEnd = managingTenant.billing?.current_period_end
      ? new Date(managingTenant.billing.current_period_end)
      : null;
    const periodEndOffsetDays = periodEnd
      ? Math.ceil((periodEnd.getTime() - Date.now()) / (1000 * 60 * 60 * 24))
      : 30;
    billingForm.setFieldsValue({
      plan_code: managingTenant.billing?.subscription_plan_code ?? managingTenant.billing?.plan_code ?? 'basic',
      scenario: inferBillingScenario(managingTenant.billing),
      status: managingTenant.billing?.subscription_status ?? 'manual',
      period_end_offset_days: periodEndOffsetDays,
      notes: '',
    });
  }, [billingForm, managingTenant]);

  const surfaceStyle = {
    background: colors.bgSecondary,
    borderRadius: isMobile ? 24 : 16,
    padding: isMobile ? 18 : 24,
    marginBottom: 24,
    boxShadow: isDark
      ? '0 18px 40px rgba(0, 0, 0, 0.2)'
      : '0 18px 40px rgba(20, 26, 40, 0.06)',
  } as const;

  const itemCardStyle = {
    borderRadius: 20,
    border: 'none',
    background: isDark ? 'rgba(255,255,255,0.04)' : '#ffffff',
    boxShadow: isDark
      ? '0 12px 28px rgba(0, 0, 0, 0.16)'
      : '0 12px 28px rgba(20, 26, 40, 0.05)',
  } as const;

  const fetchTenants = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get<TenantListResponse>('/platform/tenants', {
        params: { limit: 100, offset: 0 },
      });
      setTenants(response.data.items);
      setTotal(response.data.total);
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      message.error(detail ?? 'Не удалось загрузить кабинеты');
    } finally {
      setLoading(false);
    }
  }, []);

  const replaceTenant = useCallback((tenant: Tenant) => {
    setTenants((items) => items.map((item) => (
      item.id === tenant.id ? tenant : item
    )));
  }, []);

  const fetchTenant = useCallback(async (tenantIdToFetch: number) => {
    const response = await api.get<Tenant>(`/platform/tenants/${tenantIdToFetch}`);
    replaceTenant(response.data);
    return response.data;
  }, [replaceTenant]);

  const fetchTenantEvents = useCallback(async (tenantIdToFetch: number) => {
    setIsLoadingTenantEvents(true);
    try {
      const response = await api.get<PlatformTenantEventsResponse>(
        `/platform/tenants/${tenantIdToFetch}/events`,
        { params: { limit: 8 } },
      );
      setTenantEvents(response.data.items);
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      message.error(typeof detail === 'string' ? detail : 'Не удалось загрузить историю кабинета');
    } finally {
      setIsLoadingTenantEvents(false);
    }
  }, []);

  const fetchBroadcasts = useCallback(async () => {
    setIsLoadingBroadcasts(true);
    try {
      const response = await api.get<BroadcastListResponse>('/platform/broadcasts', {
        params: { limit: 10, offset: 0 },
      });
      setBroadcasts(response.data.items);
      setBroadcastTotal(response.data.total);
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      message.error(typeof detail === 'string' ? detail : 'Не удалось загрузить рассылки');
    } finally {
      setIsLoadingBroadcasts(false);
    }
  }, []);

  const fetchBroadcastAudienceUsers = useCallback(async () => {
    setIsLoadingAudienceUsers(true);
    try {
      const response = await api.get<BroadcastAudienceUsersResponse>('/platform/broadcasts/audience/users', {
        params: { limit: 100, offset: 0 },
      });
      setBroadcastAudienceUsers(response.data.items);
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      message.error(typeof detail === 'string' ? detail : 'Не удалось загрузить пользователей бота');
    } finally {
      setIsLoadingAudienceUsers(false);
    }
  }, []);

  useEffect(() => {
    fetchTenants();
    fetchBroadcasts();
    fetchBroadcastAudienceUsers();
  }, [fetchTenants, fetchBroadcasts, fetchBroadcastAudienceUsers]);

  useEffect(() => {
    if (managingTenantId === null) {
      setTenantEvents([]);
      return;
    }
    fetchTenantEvents(managingTenantId);
  }, [fetchTenantEvents, managingTenantId]);

  const handleSwitchTenant = async (targetTenantId: number | null) => {
    const switchKey = targetTenantId ?? 'global';
    setSwitchingTenantId(switchKey);
    try {
      await switchTenant(targetTenantId);
      message.success(targetTenantId === null ? 'Контекст сброшен' : 'Контекст кабинета изменён');
      setSwitchingTenantId(null);
    } catch (error: any) {
      message.error(error?.message ?? 'Не удалось сменить контекст');
      setSwitchingTenantId(null);
    }
  };

  const formatAccessDate = (value?: string | null) => {
    if (!value) return null;
    return new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    }).format(new Date(value));
  };

  const formatDateTime = (value?: string | null) => {
    if (!value) return '—';
    return new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value));
  };

  const accessTag = (access: TenantAccess) => {
    const statusMap: Record<string, { label: string; color: string }> = {
      trial: { label: 'Legacy trial', color: 'blue' },
      active: { label: 'Доступ активен', color: 'green' },
      grace: { label: 'Grace', color: 'gold' },
      expired: { label: 'Истёк', color: 'red' },
      lifetime: { label: 'Открыт', color: 'purple' },
      suspended: { label: 'Suspended', color: 'volcano' },
    };
    const item = statusMap[access.status] ?? { label: access.status, color: 'default' };
    return <Tag color={item.color}>{item.label}</Tag>;
  };

  const accessText = (access: TenantAccess) => {
    if (access.is_lifetime) return 'без даты окончания';
    const accessUntil = formatAccessDate(access.access_until);
    const graceUntil = formatAccessDate(access.grace_until);
    if (access.status === 'expired') return accessUntil ? `истёк ${accessUntil}` : 'истёк';
    if (access.status === 'grace') return graceUntil ? `grace до ${graceUntil}` : 'grace';
    if (access.status === 'suspended') return 'приостановлен вручную';
    return accessUntil ? `до ${accessUntil}` : 'срок не указан';
  };

  const billingTag = (billing?: BillingSnapshot | null) => {
    if (!billing) return null;
    return (
      <Tag color={billing.notifications_allowed ? 'green' : 'gold'}>
        {billing.plan_name} {billing.active_learners_count}/{billing.active_learners_limit}
      </Tag>
    );
  };

  const billingPreview = useMemo(() => {
    if (!managingTenant) return null;
    const values = billingFormValues ?? {};
    const planCode = values.plan_code ?? managingTenant.billing?.subscription_plan_code ?? managingTenant.billing?.plan_code ?? 'basic';
    const planOption = BILLING_PLAN_OPTIONS.find((plan) => plan.value === planCode);
    const scenario = values.scenario ?? 'active_custom';
    const offsetDays = Number(values.period_end_offset_days ?? 30);
    const isLifetime = scenario === 'lifetime';
    const status = scenario === 'canceled_at_period_end' ? 'canceled'
      : scenario === 'past_due' ? 'past_due'
        : scenario === 'suspended' ? 'suspended'
          : isLifetime ? 'manual'
          : scenario === 'active_custom' ? (values.status ?? 'manual')
            : 'manual';
    const periodEnd = new Date();
    periodEnd.setDate(periodEnd.getDate() + offsetDays);
    const willUsePaidPlan = planCode !== 'start' && status !== 'suspended' && (offsetDays >= 0 || status === 'past_due');
    return {
      planLabel: planOption?.label ?? planCode,
      status,
      offsetDays,
      periodEnd,
      isLifetime,
      effectiveText: willUsePaidPlan
        ? `Лимиты будут от тарифа ${planOption?.label.split(' · ')[0] ?? planCode}`
        : 'Эффективно будет бесплатный Старт / ограничения',
    };
  }, [billingFormValues, managingTenant]);

  const eventDomainTag = (domain: string) => (
    <Tag color={domain === 'billing' ? 'blue' : 'purple'}>
      {domain === 'billing' ? 'billing' : 'access'}
    </Tag>
  );

  const broadcastStatusTag = (statusValue: string) => {
    const statusMap: Record<string, { label: string; color: string }> = {
      draft: { label: 'Черновик', color: 'default' },
      queued: { label: 'В очереди', color: 'blue' },
      sending: { label: 'Отправляется', color: 'processing' },
      completed: { label: 'Завершена', color: 'green' },
      failed: { label: 'Ошибка', color: 'red' },
      cancelled: { label: 'Отменена', color: 'default' },
    };
    const item = statusMap[statusValue] ?? { label: statusValue, color: 'default' };
    return <Tag color={item.color}>{item.label}</Tag>;
  };

  const recipientStatusTag = (statusValue: string) => {
    const statusMap: Record<string, { label: string; color: string }> = {
      pending: { label: 'Ожидает', color: 'default' },
      sent: { label: 'Отправлено', color: 'green' },
      failed: { label: 'Ошибка', color: 'red' },
      skipped: { label: 'Пропущено', color: 'gold' },
    };
    const item = statusMap[statusValue] ?? { label: statusValue, color: 'default' };
    return <Tag color={item.color}>{item.label}</Tag>;
  };

  const recipientLabel = (recipient: BroadcastRecipientPreview | BroadcastRecipient) => {
    if (recipient.display_name) return recipient.display_name;
    if (recipient.username) return `@${recipient.username}`;
    return `chat ${recipient.chat_id}`;
  };

  const audienceUserLabel = (user: BroadcastAudienceUser) => {
    const name = user.display_name || (user.username ? `@${user.username}` : `chat ${user.chat_id}`);
    return `${name} · ${user.chat_id}`;
  };

  const audienceText = (audience: string) => {
    const labels: Record<string, string> = {
      platform_admins: 'Тест: platform admins',
      selected_bot_users: 'Выбранные люди',
      all_bot_users: 'Все пользователи бота',
    };
    return labels[audience] ?? audience;
  };

  const handleAccessAction = async (
    tenant: Tenant,
    action: 'grant' | 'lifetime' | 'suspend' | 'resume',
  ) => {
    const key = `${tenant.id}:${action}`;
    setAccessActionKey(key);
    try {
      const payload = action === 'grant'
        ? { days: 30 }
        : {};
      const response = await api.post<TenantAccess>(
        `/platform/tenants/${tenant.id}/access/${action}`,
        payload,
      );
      setTenants((items) => items.map((item) => (
        item.id === tenant.id ? { ...item, access: response.data } : item
      )));
      fetchTenantEvents(tenant.id);
      message.success('Доступ обновлён');
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      message.error(typeof detail === 'string' ? detail : 'Не удалось обновить доступ');
    } finally {
      setAccessActionKey(null);
    }
  };

  const applyBillingScenario = (scenario: string) => {
    const updates: Partial<BillingGrantFormValues> = { scenario };
    if (scenario === 'expired_yesterday') {
      updates.status = 'manual';
      updates.period_end_offset_days = -1;
    } else if (scenario === 'ends_today') {
      updates.status = 'manual';
      updates.period_end_offset_days = 0;
    } else if (scenario === 'lifetime') {
      updates.status = 'manual';
      updates.period_end_offset_days = 30;
    } else if (scenario === 'canceled_at_period_end') {
      updates.status = 'canceled';
      updates.period_end_offset_days = Math.max(billingForm.getFieldValue('period_end_offset_days') ?? 30, 1);
    } else if (scenario === 'past_due') {
      updates.status = 'past_due';
      updates.period_end_offset_days = -1;
    } else if (scenario === 'suspended') {
      updates.status = 'suspended';
    } else {
      updates.status = 'manual';
      updates.period_end_offset_days = Math.max(billingForm.getFieldValue('period_end_offset_days') ?? 30, 1);
    }
    billingForm.setFieldsValue(updates);
  };

  const handleRefreshTenant = async (tenant: Tenant) => {
    try {
      await Promise.all([
        fetchTenant(tenant.id),
        fetchTenantEvents(tenant.id),
      ]);
      message.success('Снимок кабинета обновлён');
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      message.error(typeof detail === 'string' ? detail : 'Не удалось обновить кабинет');
    }
  };

  const handleGrantBilling = async (tenant: Tenant) => {
    const values = await billingForm.validateFields();
    const key = `${tenant.id}:billing-grant`;
    setBillingActionKey(key);
    try {
      const now = new Date();
      const isStartPlan = values.plan_code === 'start';
      const isLifetimeSubscription = !isStartPlan && values.scenario === 'lifetime';
      const status = values.scenario === 'active_custom' ? values.status : (
        values.scenario === 'lifetime' ? 'manual'
          : values.scenario === 'canceled_at_period_end' ? 'canceled'
          : values.scenario === 'past_due' ? 'past_due'
            : values.scenario === 'suspended' ? 'suspended'
              : 'manual'
      );
      const periodEnd = new Date(now);
      periodEnd.setDate(periodEnd.getDate() + values.period_end_offset_days);
      const periodStart = new Date(periodEnd);
      periodStart.setDate(periodStart.getDate() - 30);
      const graceUntil = new Date(periodEnd);
      graceUntil.setDate(graceUntil.getDate() + 7);
      const response = await api.post<BillingSnapshot>(
        `/platform/tenants/${tenant.id}/billing/grant`,
        {
          plan_code: values.plan_code,
          status: isStartPlan ? 'active' : status,
          current_period_start: isStartPlan ? null : (isLifetimeSubscription ? now.toISOString() : periodStart.toISOString()),
          current_period_end: isStartPlan || isLifetimeSubscription ? null : periodEnd.toISOString(),
          grace_until: !isStartPlan && status === 'past_due' ? graceUntil.toISOString() : null,
          notes: values.notes || null,
        },
      );
      setTenants((items) => items.map((item) => (
        item.id === tenant.id ? { ...item, billing: response.data } : item
      )));
      fetchTenantEvents(tenant.id);
      message.success('Подписка обновлена');
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      message.error(typeof detail === 'string' ? detail : 'Не удалось обновить подписку');
    } finally {
      setBillingActionKey(null);
    }
  };

  const handleCancelBilling = async (tenant: Tenant) => {
    const key = `${tenant.id}:billing-cancel`;
    setBillingActionKey(key);
    try {
      const response = await api.post<BillingSnapshot>(
        `/platform/tenants/${tenant.id}/billing/cancel`,
        { notes: 'Cancelled from platform console' },
      );
      setTenants((items) => items.map((item) => (
        item.id === tenant.id ? { ...item, billing: response.data } : item
      )));
      fetchTenantEvents(tenant.id);
      message.success('Автопродление отключено');
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      message.error(typeof detail === 'string' ? detail : 'Не удалось отменить подписку');
    } finally {
      setBillingActionKey(null);
    }
  };

  const handleSyncAccess = async () => {
    setIsSyncingAccess(true);
    try {
      const response = await api.post<TenantAccessSyncResponse>('/platform/access/sync');
      await fetchTenants();
      const { changed, grace_started, expired } = response.data;
      message.success(`Синхронизация завершена: ${changed} изменений, grace: ${grace_started}, expired: ${expired}`);
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      message.error(typeof detail === 'string' ? detail : 'Не удалось синхронизировать доступы');
    } finally {
      setIsSyncingAccess(false);
    }
  };

  const handlePreviewBroadcast = async () => {
    const values = broadcastForm.getFieldsValue();
    setIsPreviewingBroadcast(true);
    try {
      const response = await api.post<BroadcastPreview>('/platform/broadcasts/preview', {
        audience: values.audience ?? 'platform_admins',
        bot_user_ids: values.bot_user_ids ?? [],
        sample_limit: 10,
      });
      setBroadcastPreview(response.data);
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      message.error(typeof detail === 'string' ? detail : 'Не удалось проверить аудиторию');
    } finally {
      setIsPreviewingBroadcast(false);
    }
  };

  const handleCreateBroadcast = async () => {
    const values = await broadcastForm.validateFields();
    setIsCreatingBroadcast(true);
    try {
      const response = await api.post<BroadcastCampaign>('/platform/broadcasts', {
        title: values.title,
        message_text: values.message_text,
        audience: values.audience ?? 'platform_admins',
        bot_user_ids: values.bot_user_ids ?? [],
        rate_limit_per_second: values.rate_limit_per_second ?? 10,
      });
      setBroadcasts((items) => [response.data, ...items].slice(0, 10));
      setBroadcastTotal((value) => value + 1);
      broadcastForm.resetFields();
      setBroadcastPreview(null);
      setIsBroadcastComposerOpen(false);
      message.success('Черновик рассылки создан');
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      message.error(typeof detail === 'string' ? detail : 'Не удалось создать рассылку');
    } finally {
      setIsCreatingBroadcast(false);
    }
  };

  const handleSendBroadcast = async () => {
    if (sendingBroadcastId === null) return;
    try {
      const response = await api.post<BroadcastCampaign>(
        `/platform/broadcasts/${sendingBroadcastId}/send`,
        { confirmation_text: sendConfirmation },
      );
      setBroadcasts((items) => items.map((item) => (
        item.id === response.data.id ? response.data : item
      )));
      setSendingBroadcastId(null);
      setSendConfirmation('');
      message.success('Рассылка поставлена в очередь');
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      message.error(typeof detail === 'string' ? detail : 'Не удалось поставить рассылку в очередь');
    }
  };

  const handleOpenRecipients = async (campaign: BroadcastCampaign) => {
    setRecipientModalCampaign(campaign);
    setBroadcastRecipients([]);
    setBroadcastRecipientTotal(0);
    setIsLoadingRecipients(true);
    try {
      const response = await api.get<BroadcastRecipientListResponse>(
        `/platform/broadcasts/${campaign.id}/recipients`,
        { params: { limit: 50, offset: 0 } },
      );
      setBroadcastRecipients(response.data.items);
      setBroadcastRecipientTotal(response.data.total);
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      message.error(typeof detail === 'string' ? detail : 'Не удалось загрузить получателей');
    } finally {
      setIsLoadingRecipients(false);
    }
  };

  const tenantActions = useCallback((tenant: Tenant): TenantActionConfig[] => {
    return [
      {
        key: 'open',
        label: tenant.id === tenantId ? 'Открыт' : 'Открыть',
        icon: <LoginOutlined />,
        type: tenant.id === tenantId ? 'default' : 'primary',
        disabled: !tenant.is_active || !canSwitchTenant || tenant.id === tenantId,
        loading: switchingTenantId === tenant.id,
        onClick: () => handleSwitchTenant(tenant.id),
      },
      {
        key: 'manage',
        label: 'Управлять',
        icon: <SettingOutlined />,
        onClick: () => setManagingTenantId(tenant.id),
      },
    ];
  }, [canSwitchTenant, switchingTenantId, tenantId]);

  const activeBroadcasts = useMemo(
    () => broadcasts.filter((campaign) => campaign.status !== 'completed'),
    [broadcasts],
  );
  const completedBroadcasts = useMemo(
    () => broadcasts.filter((campaign) => campaign.status === 'completed'),
    [broadcasts],
  );

  const broadcastComposer = (
    <>
      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 16 }}
        message="Отправка только после подтверждения"
        description="Создание черновика не отправляет сообщение. Для запуска нужно открыть черновик и ввести SEND."
      />

      <Form<BroadcastFormValues>
        form={broadcastForm}
        layout="vertical"
        initialValues={{ audience: 'platform_admins', rate_limit_per_second: 10 }}
      >
        <Form.Item
          name="audience"
          label="Кому отправить"
          rules={[{ required: true, message: 'Выберите аудиторию' }]}
        >
          <Select
            options={[
              { value: 'platform_admins', label: 'Тест: platform admins' },
              { value: 'selected_bot_users', label: 'Выбранные люди' },
              { value: 'all_bot_users', label: 'Все пользователи бота' },
            ]}
            onChange={() => {
              broadcastForm.setFieldValue('bot_user_ids', []);
              setBroadcastPreview(null);
            }}
          />
        </Form.Item>
        {selectedBroadcastAudience === 'selected_bot_users' && (
          <Form.Item
            name="bot_user_ids"
            label="Получатели"
            rules={[{ required: true, message: 'Выберите хотя бы одного получателя' }]}
          >
            <Select
              mode="multiple"
              loading={isLoadingAudienceUsers}
              placeholder="Выберите пользователей Telegram"
              optionFilterProp="label"
              options={broadcastAudienceUsers.map((user) => ({
                value: user.bot_user_id,
                label: audienceUserLabel(user),
              }))}
            />
          </Form.Item>
        )}
        {selectedBroadcastAudience === 'platform_admins' && (
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            message="Тестовая аудитория"
            description="Получателями будут только BotUser, чей chat_id есть в allowlist platform admins."
          />
        )}
        {selectedBroadcastAudience === 'all_bot_users' && (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 16 }}
            message="Массовая аудитория"
            description="Эта аудитория собирает всех не-bot пользователей текущего Telegram-бота."
          />
        )}
        <Form.Item
          name="title"
          label="Название"
          rules={[{ required: true, message: 'Введите название рассылки' }]}
        >
          <Input placeholder="Например: Переименование бота" />
        </Form.Item>
        <Form.Item
          name="message_text"
          label="Текст сообщения"
          rules={[{ required: true, message: 'Введите текст сообщения' }]}
        >
          <Input.TextArea rows={5} maxLength={4000} showCount />
        </Form.Item>
        <Form.Item name="rate_limit_per_second" label="Скорость отправки">
          <InputNumber min={1} max={20} addonAfter="сообщ./сек" style={{ width: '100%' }} />
        </Form.Item>
        <Space wrap style={{ marginBottom: 16 }}>
          <Button onClick={handlePreviewBroadcast} loading={isPreviewingBroadcast}>
            Проверить аудиторию
          </Button>
          <Button type="primary" onClick={handleCreateBroadcast} loading={isCreatingBroadcast}>
            Создать черновик
          </Button>
        </Space>
      </Form>

      {broadcastPreview && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message={`Получателей: ${broadcastPreview.total}`}
          description={
            broadcastPreview.sample.length > 0
              ? `Пример: ${broadcastPreview.sample.map(recipientLabel).join(', ')}`
              : 'Подходящих пользователей пока нет.'
          }
        />
      )}
    </>
  );

  const renderBroadcastList = (items: BroadcastCampaign[]) => {
    if (isLoadingBroadcasts) {
      return (
        <div style={{ padding: 32, textAlign: 'center' }}>
          <Spin />
        </div>
      );
    }

    if (items.length === 0) {
      return <Text type="secondary">Рассылок пока нет</Text>;
    }

    if (isMobile) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {items.map((campaign) => (
            <Card key={campaign.id} style={itemCardStyle} styles={{ body: { padding: 18 } }}>
              <Space direction="vertical" size={10} style={{ width: '100%' }}>
                <div>
                  <Space wrap size={8}>
                    <Text strong style={{ fontSize: 16 }}>{campaign.title}</Text>
                    {broadcastStatusTag(campaign.status)}
                  </Space>
                  <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <Text type="secondary">Аудитория: {audienceText(campaign.audience)}</Text>
                    <Text type="secondary">
                      Получателей: {campaign.recipient_count} · отправлено: {campaign.sent_count} · ошибок: {campaign.failed_count}
                    </Text>
                    <Text type="secondary">Создано: {formatDateTime(campaign.created_at)}</Text>
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}>
                  <Button onClick={() => handleOpenRecipients(campaign)}>
                    Получатели
                  </Button>
                  <Button
                    type="primary"
                    danger
                    icon={<SendOutlined />}
                    disabled={campaign.status !== 'draft'}
                    onClick={() => setSendingBroadcastId(campaign.id)}
                  >
                    Отправить
                  </Button>
                </div>
              </Space>
            </Card>
          ))}
        </div>
      );
    }

    return (
      <List
        dataSource={items}
        locale={{ emptyText: 'Рассылок пока нет' }}
        renderItem={(campaign) => (
          <List.Item
            actions={[
              <Button key="recipients" onClick={() => handleOpenRecipients(campaign)}>
                Получатели
              </Button>,
              <Button
                key="send"
                type="primary"
                danger
                icon={<SendOutlined />}
                disabled={campaign.status !== 'draft'}
                onClick={() => setSendingBroadcastId(campaign.id)}
              >
                Отправить
              </Button>,
            ]}
          >
            <List.Item.Meta
              title={(
                <Space wrap>
                  <Text strong>{campaign.title}</Text>
                  {broadcastStatusTag(campaign.status)}
                </Space>
              )}
              description={(
                <Space direction="vertical" size={2}>
                  <Text type="secondary">Аудитория: {audienceText(campaign.audience)}</Text>
                  <Text type="secondary">
                    Получателей: {campaign.recipient_count} · отправлено: {campaign.sent_count} · ошибок: {campaign.failed_count}
                  </Text>
                  <Text type="secondary">Создано: {formatDateTime(campaign.created_at)}</Text>
                </Space>
              )}
            />
          </List.Item>
        )}
      />
    );
  };

  const renderTenantList = () => {
    if (loading) {
      return (
        <div style={{ padding: 48, textAlign: 'center' }}>
          <Spin />
        </div>
      );
    }

    if (isMobile) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {tenants.map((tenant) => (
            <Card key={tenant.id} style={itemCardStyle} styles={{ body: { padding: 18 } }}>
              <Space direction="vertical" size={14} style={{ width: '100%' }}>
                <div>
                  <Space wrap size={8}>
                    <Text strong style={{ fontSize: 16 }}>{tenant.name}</Text>
                    <Tag color={tenant.is_active ? 'green' : 'default'}>
                      {tenant.is_active ? 'Активен' : 'Отключён'}
                    </Tag>
                    {accessTag(tenant.access)}
                    {billingTag(tenant.billing)}
                    {tenant.id === tenantId && <Tag color="blue">Текущий</Tag>}
                  </Space>
                  <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <Text type="secondary">ID: {tenant.id} · {tenant.slug}</Text>
                    <Text type="secondary">Доступ: {accessText(tenant.access)}</Text>
                    {tenant.billing && !tenant.billing.notifications_allowed && (
                      <Text type="warning">Уведомления отключены биллингом</Text>
                    )}
                    <Text type="secondary">{tenant.contact_email ?? 'Email не указан'}</Text>
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}>
                  {tenantActions(tenant).map((action) => (
                    action.href ? (
                      <Link key={action.key} to={action.href} style={{ display: 'block' }}>
                        <Button icon={action.icon} style={{ width: '100%' }}>
                          {action.label}
                        </Button>
                      </Link>
                    ) : (
                      <Button
                        key={action.key}
                        type={action.type}
                        danger={action.danger}
                        icon={action.icon}
                        disabled={action.disabled}
                        loading={action.loading}
                        onClick={action.onClick}
                        style={{ width: '100%' }}
                      >
                        {action.label}
                      </Button>
                    )
                  ))}
                </div>
              </Space>
            </Card>
          ))}
        </div>
      );
    }

    return (
      <List
        dataSource={tenants}
        locale={{ emptyText: 'Кабинеты не найдены' }}
        renderItem={(tenant) => (
          <List.Item
            actions={tenantActions(tenant).map((action) => (
              action.href ? (
                <Link key={action.key} to={action.href}>
                  <Button icon={action.icon}>{action.label}</Button>
                </Link>
              ) : (
                <Button
                  key={action.key}
                  type={action.type}
                  danger={action.danger}
                  icon={action.icon}
                  disabled={action.disabled}
                  loading={action.loading}
                  onClick={action.onClick}
                >
                  {action.label}
                </Button>
              )
            ))}
          >
            <List.Item.Meta
              title={(
                <Space wrap>
                  <Text strong>{tenant.name}</Text>
                  <Tag color={tenant.is_active ? 'green' : 'default'}>
                    {tenant.is_active ? 'Активен' : 'Отключён'}
                  </Tag>
                  {accessTag(tenant.access)}
                  {billingTag(tenant.billing)}
                  {tenant.id === tenantId && <Tag color="blue">Текущий</Tag>}
                </Space>
              )}
              description={(
                <Space direction="vertical" size={0}>
                  <Text type="secondary">ID: {tenant.id} · {tenant.slug}</Text>
                  <Text type="secondary">Доступ: {accessText(tenant.access)}</Text>
                  {tenant.billing && !tenant.billing.notifications_allowed && (
                    <Text type="warning">Уведомления отключены биллингом</Text>
                  )}
                  <Text type="secondary">{tenant.contact_email ?? 'Email не указан'}</Text>
                </Space>
              )}
            />
          </List.Item>
        )}
      />
    );
  };

  const broadcastsSection = (
    <section style={surfaceStyle}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        gap: 12,
        alignItems: 'center',
        marginBottom: 16,
        flexWrap: 'wrap',
      }}>
        <div>
          <Title level={isMobile ? 4 : 3} style={{ margin: 0 }}>Рассылки</Title>
          <Text type="secondary">Системные сообщения всем пользователям текущего Telegram-бота.</Text>
        </div>
        <Space wrap>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setIsBroadcastComposerOpen((open) => (isMobile ? true : !open))}
          >
            {isMobile ? 'Новая рассылка' : (isBroadcastComposerOpen ? 'Скрыть форму' : 'Новая рассылка')}
          </Button>
          <Button icon={<ReloadOutlined />} onClick={fetchBroadcasts} loading={isLoadingBroadcasts}>
            Обновить
          </Button>
        </Space>
      </div>

      {!isMobile && isBroadcastComposerOpen && (
        <>
          {broadcastComposer}
          <Divider />
        </>
      )}

      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        gap: 12,
        alignItems: 'center',
        marginBottom: 12,
        flexWrap: 'wrap',
      }}>
        <Text strong>Последние кампании</Text>
        <Text type="secondary">Всего: {broadcastTotal}</Text>
      </div>

      {renderBroadcastList(activeBroadcasts)}

      {completedBroadcasts.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <Collapse
            ghost
            items={[
              {
                key: 'completed',
                label: `Завершённые (${completedBroadcasts.length})`,
                children: <div style={{ paddingTop: 8 }}>{renderBroadcastList(completedBroadcasts)}</div>,
              },
            ]}
          />
        </div>
      )}
    </section>
  );

  const tenantsSection = (
    <section style={surfaceStyle}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        gap: 12,
        alignItems: 'center',
        marginBottom: 16,
        flexWrap: 'wrap',
      }}>
        <div>
          <Title level={isMobile ? 4 : 3} style={{ margin: 0 }}>Кабинеты</Title>
          <Text type="secondary">Всего: {total}</Text>
        </div>
        <Space wrap>
          <Button onClick={handleSyncAccess} loading={isSyncingAccess}>
            Синхронизировать статусы
          </Button>
          <Button icon={<ReloadOutlined />} onClick={fetchTenants} loading={loading}>
            Обновить
          </Button>
        </Space>
      </div>

      {renderTenantList()}
    </section>
  );

  const usersSection = (
    <section style={{ marginBottom: 24 }}>
      <Admin />
    </section>
  );

  return (
    <div style={{
      minHeight: '100vh',
      background: colors.bgPrimary,
      color: colors.textPrimary,
      padding: isMobile ? '16px 16px 32px' : '24px',
      boxSizing: 'border-box',
    }}>
      <div style={{ maxWidth: 1180, margin: '0 auto' }}>
        <PageHeader
          title="Консоль"
          subtitle="Глобальное управление кабинетами репетиторов и доступами."
          actions={(
            <Space wrap>
              <Link to="/">
                <Button icon={<ArrowLeftOutlined />}>В приложение</Button>
              </Link>
              <Button onClick={logout}>Выйти</Button>
            </Space>
          )}
        />

        <Alert
          type={tenantId === null ? 'info' : 'warning'}
          showIcon
          style={{ marginBottom: 24 }}
          message={tenantId === null ? 'Глобальный режим' : 'Открыт кабинет репетитора'}
          description={
            tenantId === null
              ? 'Данные обычных разделов не привязаны к конкретному кабинету. Выберите кабинет только для поддержки или проверки.'
              : `Сейчас активен контекст: ${activeTenant?.name ?? `кабинет #${tenantId}`}. Возврат в глобальный режим нужен перед системными действиями.`
          }
          action={
            tenantId !== null ? (
              <Button
                size="small"
                icon={<GlobalOutlined />}
                loading={switchingTenantId === 'global'}
                disabled={!canSwitchTenant}
                onClick={() => handleSwitchTenant(null)}
              >
                Глобальный режим
              </Button>
            ) : null
          }
        />

        {!canSwitchTenant && (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 24 }}
            message="Переключение кабинетов недоступно"
            description="В браузерном входе пока можно смотреть консоль, но нельзя менять tenant-контекст."
          />
        )}

        {isMobile && (
          <div style={{ ...surfaceStyle, padding: 8, marginBottom: 20 }}>
            <Segmented
              block
              value={activeSection}
              onChange={(value) => setActiveSection(value as ConsoleSection)}
              options={[
                { value: 'broadcasts', label: 'Рассылки' },
                { value: 'tenants', label: 'Кабинеты' },
                { value: 'users', label: 'Пользователи' },
              ]}
            />
          </div>
        )}

        {(!isMobile || activeSection === 'broadcasts') && broadcastsSection}
        {(!isMobile || activeSection === 'tenants') && tenantsSection}
        {(!isMobile || activeSection === 'users') && usersSection}
      </div>

      {isMobile && (
        <ResponsiveModal
          title="Новая рассылка"
          open={isBroadcastComposerOpen}
          onCancel={() => setIsBroadcastComposerOpen(false)}
          footer={null}
        >
          {broadcastComposer}
        </ResponsiveModal>
      )}

      <ResponsiveModal
        title="Подтверждение рассылки"
        open={sendingBroadcastId !== null}
        okText="Поставить в очередь"
        okButtonProps={{
          danger: true,
          disabled: sendConfirmation !== 'SEND',
        }}
        onOk={handleSendBroadcast}
        onCancel={() => {
          setSendingBroadcastId(null);
          setSendConfirmation('');
        }}
      >
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="Сообщение будет отправлено всем получателям из сохранённого снимка."
          description="Введите SEND, чтобы подтвердить запуск."
        />
        <Input
          value={sendConfirmation}
          onChange={(event) => setSendConfirmation(event.target.value)}
          placeholder="SEND"
        />
      </ResponsiveModal>

      <ResponsiveModal
        title={recipientModalCampaign ? `Получатели: ${recipientModalCampaign.title}` : 'Получатели'}
        open={recipientModalCampaign !== null}
        footer={null}
        onCancel={() => {
          setRecipientModalCampaign(null);
          setBroadcastRecipients([]);
          setBroadcastRecipientTotal(0);
        }}
      >
        {isLoadingRecipients ? (
          <div style={{ padding: 32, textAlign: 'center' }}>
            <Spin />
          </div>
        ) : (
          <>
            <Text type="secondary">Показано {broadcastRecipients.length} из {broadcastRecipientTotal}</Text>
            <List
              dataSource={broadcastRecipients}
              locale={{ emptyText: 'Получатели не найдены' }}
              renderItem={(recipient) => (
                <List.Item>
                  <List.Item.Meta
                    title={(
                      <Space wrap>
                        <Text>{recipientLabel(recipient)}</Text>
                        {recipientStatusTag(recipient.status)}
                      </Space>
                    )}
                    description={(
                      <Space direction="vertical" size={0}>
                        <Text type="secondary">chat_id: {recipient.chat_id}</Text>
                        {recipient.error_message && (
                          <Text type="danger">{recipient.error_message}</Text>
                        )}
                      </Space>
                    )}
                  />
                </List.Item>
              )}
            />
          </>
        )}
      </ResponsiveModal>

      <ResponsiveModal
        title={managingTenant ? `Кабинет: ${managingTenant.name}` : 'Кабинет'}
        open={managingTenant !== null}
        footer={null}
        onCancel={() => setManagingTenantId(null)}
      >
        {managingTenant && (
          <Space direction="vertical" size={18} style={{ width: '100%' }}>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: 12,
            }}>
              <div style={{
                padding: 14,
                borderRadius: 12,
                background: colors.bgSecondary,
                border: `1px solid ${colors.borderPrimary}`,
              }}>
                <Text type="secondary" style={{ display: 'block' }}>Кабинет</Text>
                <Text strong style={{ display: 'block' }}>{managingTenant.slug}</Text>
                <Text type="secondary">{managingTenant.contact_email ?? 'Email не указан'}</Text>
              </div>
              <div style={{
                padding: 14,
                borderRadius: 12,
                background: colors.bgSecondary,
                border: `1px solid ${colors.borderPrimary}`,
              }}>
                <Text type="secondary" style={{ display: 'block' }}>Доступ</Text>
                <Space wrap size={6}>
                  {accessTag(managingTenant.access)}
                  <Text>{accessText(managingTenant.access)}</Text>
                </Space>
              </div>
              <div style={{
                padding: 14,
                borderRadius: 12,
                background: colors.bgSecondary,
                border: `1px solid ${colors.borderPrimary}`,
              }}>
                <Text type="secondary" style={{ display: 'block' }}>Тариф</Text>
                {billingTag(managingTenant.billing)}
                {managingTenant.billing && (
                  <Text type="secondary" style={{ display: 'block', marginTop: 4 }}>
                    {managingTenant.billing.current_period_end
                      ? `До ${formatDateTime(managingTenant.billing.current_period_end)}`
                      : 'Бессрочно'}
                  </Text>
                )}
              </div>
            </div>

            {managingTenant.billing && !managingTenant.billing.notifications_allowed && (
              <Alert
                type="warning"
                showIcon
                message="Уведомления отключены биллингом"
                description="Активных учеников больше бесплатного лимита, а платная подписка не действует."
              />
            )}

            <Space wrap>
              <Button
                icon={<ReloadOutlined />}
                onClick={() => handleRefreshTenant(managingTenant)}
              >
                Обновить снимок
              </Button>
              {managingTenant.access.mode === 'blocked' && (
                <>
                  <Link to={`/platform/tenants/${managingTenant.id}/access-preview/teacher`}>
                    <Button icon={<EyeOutlined />}>Экран репетитора</Button>
                  </Link>
                  <Link to={`/platform/tenants/${managingTenant.id}/access-preview/student`}>
                    <Button icon={<EyeOutlined />}>Экран ученика</Button>
                  </Link>
                </>
              )}
            </Space>

            <div>
              <Title level={5} style={{ marginTop: 0 }}>Тариф и подписка</Title>
              <Form<BillingGrantFormValues>
                form={billingForm}
                layout="vertical"
                initialValues={{ plan_code: 'basic', scenario: 'active_custom', status: 'manual', period_end_offset_days: 30 }}
              >
                <Form.Item
                  name="plan_code"
                  label="Тариф"
                  rules={[{ required: true, message: 'Выберите тариф' }]}
                >
                  <Select options={BILLING_PLAN_OPTIONS} />
                </Form.Item>
                <Form.Item
                  name="scenario"
                  label="Сценарий"
                  rules={[{ required: true, message: 'Выберите сценарий' }]}
                >
                  <Select options={BILLING_SCENARIO_OPTIONS} onChange={applyBillingScenario} />
                </Form.Item>
                <Form.Item
                  name="period_end_offset_days"
                  label="Когда закончится"
                  extra="10 = через 10 дней, 0 = сегодня, -1 = уже закончилась вчера."
                  rules={billingFormValues?.scenario === 'lifetime' ? [] : [{ required: true, message: 'Укажите дату окончания относительно сегодня' }]}
                  hidden={billingFormValues?.scenario === 'lifetime'}
                >
                  <InputNumber min={-3650} max={3650} addonAfter="дней от сегодня" style={{ width: '100%' }} />
                </Form.Item>
                {billingFormValues?.scenario !== 'lifetime' && (
                <Space wrap size={6} style={{ marginTop: -12, marginBottom: 16 }}>
                  {[
                    { label: 'Вчера', value: -1 },
                    { label: 'Сегодня', value: 0 },
                    { label: '+10 дней', value: 10 },
                    { label: '+15 дней', value: 15 },
                    { label: '+30 дней', value: 30 },
                  ].map((preset) => (
                    <Button
                      key={preset.value}
                      size="small"
                      onClick={() => billingForm.setFieldsValue({ period_end_offset_days: preset.value })}
                    >
                      {preset.label}
                    </Button>
                  ))}
                </Space>
                )}
                <Collapse
                  ghost
                  size="small"
                  items={[
                    {
                      key: 'advanced-billing',
                      label: 'Advanced: raw billing status',
                      children: (
                        <Form.Item
                          name="status"
                          label="Статус записи"
                          rules={[{ required: true, message: 'Выберите статус' }]}
                        >
                          <Select options={BILLING_STATUS_OPTIONS} />
                        </Form.Item>
                      ),
                    },
                  ]}
                />
                {billingPreview && (
                  <div style={{
                    padding: 14,
                    borderRadius: 12,
                    background: colors.bgSecondary,
                    marginBottom: 16,
                  }}>
                    <Text type="secondary" style={{ display: 'block' }}>После сохранения</Text>
                    <Text strong style={{ display: 'block', color: colors.textPrimary }}>
                      {billingPreview.planLabel} · {billingPreview.status}
                    </Text>
                    <Text type="secondary" style={{ display: 'block' }}>
                      {billingPreview.isLifetime
                        ? 'Окончание: бессрочно'
                        : `Окончание: ${formatDateTime(billingPreview.periodEnd.toISOString())} (${billingPreview.offsetDays} дней от сегодня)`}
                    </Text>
                    <Text type="secondary" style={{ display: 'block' }}>
                      {billingPreview.effectiveText}
                    </Text>
                  </div>
                )}
                <Form.Item name="notes" label="Комментарий">
                  <Input.TextArea rows={2} maxLength={1000} />
                </Form.Item>
                <Space wrap>
                  <Button
                    type="primary"
                    icon={<CreditCardOutlined />}
                    loading={billingActionKey === `${managingTenant.id}:billing-grant`}
                    onClick={() => handleGrantBilling(managingTenant)}
                  >
                    Выдать подписку
                  </Button>
                  <Button
                    danger
                    loading={billingActionKey === `${managingTenant.id}:billing-cancel`}
                    onClick={() => handleCancelBilling(managingTenant)}
                  >
                    {managingTenant.billing?.current_period_end ? 'Отменить продление' : 'Отменить подписку'}
                  </Button>
                </Space>
              </Form>
            </div>

            <Divider style={{ margin: 0 }} />

            <div>
              <Title level={5} style={{ marginTop: 0 }}>Доступ к сервису</Title>
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <div style={{
                  padding: 14,
                  borderRadius: 12,
                  background: colors.bgSecondary,
                }}>
                  <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                    Доступ управляет только ручной блокировкой кабинета. Срок платного тарифа задаётся в блоке «Тариф и подписка».
                  </Text>
                </div>
                <Space wrap>
                {managingTenant.access.status === 'suspended' ? (
                  <Button
                    onClick={() => handleAccessAction(managingTenant, 'resume')}
                    loading={accessActionKey === `${managingTenant.id}:resume`}
                  >
                    Возобновить
                  </Button>
                ) : (
                  <Button
                    danger
                    onClick={() => handleAccessAction(managingTenant, 'suspend')}
                    loading={accessActionKey === `${managingTenant.id}:suspend`}
                  >
                    Приостановить
                  </Button>
                )}
                </Space>
              </Space>
              <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
                Возобновление после приостановки не меняет тариф и не продлевает оплаченный период.
              </Text>
            </div>

            <Divider style={{ margin: 0 }} />

            <div>
              <Title level={5} style={{ marginTop: 0 }}>История изменений</Title>
              {isLoadingTenantEvents ? (
                <div style={{ padding: 18, textAlign: 'center' }}>
                  <Spin />
                </div>
              ) : (
                <List
                  dataSource={tenantEvents}
                  rowKey={(event) => `${event.domain}-${event.id}`}
                  locale={{ emptyText: 'Событий пока нет' }}
                  renderItem={(event) => (
                    <List.Item style={{ paddingLeft: 0, paddingRight: 0 }}>
                      <List.Item.Meta
                        title={(
                          <Space wrap size={6}>
                            {eventDomainTag(event.domain)}
                            <Text>{event.action}</Text>
                            <Text type="secondary">{formatDateTime(event.created_at)}</Text>
                          </Space>
                        )}
                        description={(
                          <Space direction="vertical" size={0}>
                            {event.actor_user_id && (
                              <Text type="secondary">actor #{event.actor_user_id}</Text>
                            )}
                            {event.notes && (
                              <Text type="secondary">{event.notes}</Text>
                            )}
                          </Space>
                        )}
                      />
                    </List.Item>
                  )}
                />
              )}
            </div>
          </Space>
        )}
      </ResponsiveModal>
    </div>
  );
};

export default PlatformConsole;
