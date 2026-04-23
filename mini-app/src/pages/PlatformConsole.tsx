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
  EyeOutlined,
  GlobalOutlined,
  LoginOutlined,
  PlusOutlined,
  ReloadOutlined,
  SendOutlined,
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

const PlatformConsole = () => {
  const { tenantId, canSwitchTenant, switchTenant, logout } = useAuth();
  const { resolvedTheme } = useTheme();
  const { isMobile } = useResponsive();
  const colors = resolvedTheme.colors;
  const isDark = resolvedTheme.colorScheme === 'dark';
  const [broadcastForm] = Form.useForm<BroadcastFormValues>();
  const selectedBroadcastAudience = Form.useWatch('audience', broadcastForm) ?? 'platform_admins';
  const [activeSection, setActiveSection] = useState<ConsoleSection>('broadcasts');
  const [isBroadcastComposerOpen, setIsBroadcastComposerOpen] = useState(false);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [switchingTenantId, setSwitchingTenantId] = useState<number | 'global' | null>(null);
  const [accessActionKey, setAccessActionKey] = useState<string | null>(null);
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

  const activeTenant = useMemo(
    () => tenants.find((tenant) => tenant.id === tenantId) ?? null,
    [tenantId, tenants],
  );

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

  const handleSwitchTenant = async (targetTenantId: number | null) => {
    const switchKey = targetTenantId ?? 'global';
    setSwitchingTenantId(switchKey);
    try {
      await switchTenant(targetTenantId);
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
      trial: { label: 'Триал', color: 'blue' },
      active: { label: 'Оплачен', color: 'green' },
      grace: { label: 'Grace', color: 'gold' },
      expired: { label: 'Истёк', color: 'red' },
      lifetime: { label: 'Вечный', color: 'purple' },
      suspended: { label: 'Suspended', color: 'volcano' },
    };
    const item = statusMap[access.status] ?? { label: access.status, color: 'default' };
    return <Tag color={item.color}>{item.label}</Tag>;
  };

  const accessText = (access: TenantAccess) => {
    if (access.is_lifetime) return 'без срока';
    const accessUntil = formatAccessDate(access.access_until);
    const graceUntil = formatAccessDate(access.grace_until);
    if (access.status === 'expired') return accessUntil ? `истёк ${accessUntil}` : 'истёк';
    if (access.status === 'grace') return graceUntil ? `grace до ${graceUntil}` : 'grace';
    if (access.status === 'suspended') return 'приостановлен вручную';
    return accessUntil ? `до ${accessUntil}` : 'срок не указан';
  };

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
      const payload = action === 'grant' || action === 'resume'
        ? { days: 30 }
        : {};
      const response = await api.post<TenantAccess>(
        `/platform/tenants/${tenant.id}/access/${action}`,
        payload,
      );
      setTenants((items) => items.map((item) => (
        item.id === tenant.id ? { ...item, access: response.data } : item
      )));
      message.success('Доступ обновлён');
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      message.error(typeof detail === 'string' ? detail : 'Не удалось обновить доступ');
    } finally {
      setAccessActionKey(null);
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
    const actions: TenantActionConfig[] = [];

    if (tenant.access.mode === 'blocked') {
      actions.push(
        {
          key: 'preview-teacher',
          label: 'Экран репетитора',
          icon: <EyeOutlined />,
          href: `/platform/tenants/${tenant.id}/access-preview/teacher`,
        },
        {
          key: 'preview-student',
          label: 'Экран ученика',
          icon: <EyeOutlined />,
          href: `/platform/tenants/${tenant.id}/access-preview/student`,
        },
      );
    }

    actions.push(
      {
        key: 'open',
        label: tenant.id === tenantId ? 'Открыт' : 'Открыть кабинет',
        icon: <LoginOutlined />,
        type: tenant.id === tenantId ? 'default' : 'primary',
        disabled: !tenant.is_active || !canSwitchTenant || tenant.id === tenantId,
        loading: switchingTenantId === tenant.id,
        onClick: () => handleSwitchTenant(tenant.id),
      },
      {
        key: 'grant',
        label: '+30 дней',
        loading: accessActionKey === `${tenant.id}:grant`,
        onClick: () => handleAccessAction(tenant, 'grant'),
      },
      {
        key: 'lifetime',
        label: 'Вечный',
        disabled: tenant.access.is_lifetime,
        loading: accessActionKey === `${tenant.id}:lifetime`,
        onClick: () => handleAccessAction(tenant, 'lifetime'),
      },
      tenant.access.status === 'suspended' ? {
        key: 'resume',
        label: 'Resume',
        loading: accessActionKey === `${tenant.id}:resume`,
        onClick: () => handleAccessAction(tenant, 'resume'),
      } : {
        key: 'suspend',
        label: 'Suspend',
        danger: true,
        loading: accessActionKey === `${tenant.id}:suspend`,
        onClick: () => handleAccessAction(tenant, 'suspend'),
      },
    );

    return actions;
  }, [accessActionKey, canSwitchTenant, switchingTenantId, tenantId]);

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
                    {tenant.id === tenantId && <Tag color="blue">Текущий</Tag>}
                  </Space>
                  <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <Text type="secondary">ID: {tenant.id} · {tenant.slug}</Text>
                    <Text type="secondary">Доступ: {accessText(tenant.access)}</Text>
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
                  {tenant.id === tenantId && <Tag color="blue">Текущий</Tag>}
                </Space>
              )}
              description={(
                <Space direction="vertical" size={0}>
                  <Text type="secondary">ID: {tenant.id} · {tenant.slug}</Text>
                  <Text type="secondary">Доступ: {accessText(tenant.access)}</Text>
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
    </div>
  );
};

export default PlatformConsole;
