import { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Button, Divider, List, Space, Spin, Tag, Typography, message } from 'antd';
import { ArrowLeftOutlined, GlobalOutlined, LoginOutlined, ReloadOutlined } from '@ant-design/icons';
import { Link } from 'react-router-dom';
import api from '../services/api';
import { useAuth } from '../auth/AuthProvider';
import { useTheme } from '../theme/ThemeProvider';
import Admin from './Admin';

const { Text, Title } = Typography;

interface Tenant {
  id: number;
  name: string;
  slug: string;
  contact_email?: string | null;
  is_active: boolean;
}

interface TenantListResponse {
  items: Tenant[];
  total: number;
}

const PlatformConsole = () => {
  const { tenantId, canSwitchTenant, switchTenant, logout } = useAuth();
  const { resolvedTheme } = useTheme();
  const colors = resolvedTheme.colors;
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [switchingTenantId, setSwitchingTenantId] = useState<number | 'global' | null>(null);

  const activeTenant = useMemo(
    () => tenants.find((tenant) => tenant.id === tenantId) ?? null,
    [tenantId, tenants],
  );

  const fetchTenants = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get<TenantListResponse>('/tenants', {
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

  useEffect(() => {
    fetchTenants();
  }, [fetchTenants]);

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

  return (
    <div style={{
      minHeight: '100vh',
      background: colors.bgPrimary,
      color: colors.textPrimary,
      padding: '24px',
      boxSizing: 'border-box',
    }}>
      <div style={{ maxWidth: 1180, margin: '0 auto' }}>
        <div style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 16,
          marginBottom: 24,
          flexWrap: 'wrap',
        }}>
          <div>
            <Title level={2} style={{ margin: 0 }}>Консоль</Title>
            <Text type="secondary">
              Глобальное управление кабинетами репетиторов и доступами.
            </Text>
          </div>
          <Space wrap>
            <Link to="/">
              <Button icon={<ArrowLeftOutlined />}>В приложение</Button>
            </Link>
            <Button onClick={logout}>Выйти</Button>
          </Space>
        </div>

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

        <section style={{
          background: colors.bgSecondary,
          border: `1px solid ${colors.borderPrimary}`,
          borderRadius: 8,
          padding: 24,
          marginBottom: 24,
        }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            gap: 12,
            alignItems: 'center',
            marginBottom: 16,
            flexWrap: 'wrap',
          }}>
            <div>
              <Title level={3} style={{ margin: 0 }}>Кабинеты</Title>
              <Text type="secondary">Всего: {total}</Text>
            </div>
            <Button icon={<ReloadOutlined />} onClick={fetchTenants} loading={loading}>
              Обновить
            </Button>
          </div>

          {loading ? (
            <div style={{ padding: 48, textAlign: 'center' }}>
              <Spin />
            </div>
          ) : (
            <List
              dataSource={tenants}
              locale={{ emptyText: 'Кабинеты не найдены' }}
              renderItem={(tenant) => (
                <List.Item
                  actions={[
                    <Button
                      key="open"
                      type={tenant.id === tenantId ? 'default' : 'primary'}
                      icon={<LoginOutlined />}
                      disabled={!tenant.is_active || !canSwitchTenant || tenant.id === tenantId}
                      loading={switchingTenantId === tenant.id}
                      onClick={() => handleSwitchTenant(tenant.id)}
                    >
                      {tenant.id === tenantId ? 'Открыт' : 'Открыть кабинет'}
                    </Button>,
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <Space wrap>
                        <Text strong>{tenant.name}</Text>
                        <Tag color={tenant.is_active ? 'green' : 'default'}>
                          {tenant.is_active ? 'Активен' : 'Отключён'}
                        </Tag>
                        {tenant.id === tenantId && <Tag color="blue">Текущий</Tag>}
                      </Space>
                    }
                    description={
                      <Space direction="vertical" size={0}>
                        <Text type="secondary">ID: {tenant.id} · {tenant.slug}</Text>
                        <Text type="secondary">{tenant.contact_email ?? 'Email не указан'}</Text>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          )}
        </section>

        <section style={{
          background: colors.bgSecondary,
          border: `1px solid ${colors.borderPrimary}`,
          borderRadius: 8,
          padding: 24,
        }}>
          <Title level={3} style={{ marginTop: 0 }}>Пользователи</Title>
          <Text type="secondary">
            Доступ владельца платформы выдаётся только через allowlist в конфигурации. Здесь можно менять только роли репетитора и ученика.
          </Text>
          <Divider />
          <Admin />
        </section>
      </div>
    </div>
  );
};

export default PlatformConsole;
