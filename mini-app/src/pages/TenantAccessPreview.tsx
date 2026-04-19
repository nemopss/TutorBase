import { Alert, Button, Spin, Typography } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../services/api';
import TenantAccessBlocked from './TenantAccessBlocked';
import type { TenantAccess } from '../auth/AuthProvider';
import { useTheme } from '../theme/ThemeProvider';

const { Text, Title } = Typography;

interface Tenant {
  id: number;
  name: string;
  slug: string;
  access: TenantAccess;
}

const fetchPlatformTenant = async (tenantId: string): Promise<Tenant> => {
  const { data } = await api.get<Tenant>(`/platform/tenants/${tenantId}`);
  return data;
};

const TenantAccessPreview = () => {
  const { tenantId, role } = useParams<{ tenantId: string; role: string }>();
  const navigate = useNavigate();
  const { resolvedTheme } = useTheme();
  const colors = resolvedTheme.colors;
  const previewRole = role === 'student' ? 'viewer' : role === 'teacher' ? 'teacher' : null;

  const {
    data: tenant,
    isLoading,
    isError,
    error,
  } = useQuery<Tenant, Error>({
    queryKey: ['platformTenant', tenantId],
    queryFn: () => fetchPlatformTenant(tenantId!),
    enabled: !!tenantId,
  });

  if (!previewRole) {
    return (
      <div style={{ padding: 24 }}>
        <Alert
          type="error"
          showIcon
          message="Неизвестный preview-режим"
          description="Доступны только роли teacher и student."
          action={<Button onClick={() => navigate('/platform')}>В Консоль</Button>}
        />
      </div>
    );
  }

  if (isLoading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (isError || !tenant) {
    return (
      <div style={{ padding: 24 }}>
        <Alert
          type="error"
          showIcon
          message="Не удалось загрузить кабинет"
          description={error?.message ?? 'Кабинет не найден или недоступен.'}
          action={<Button onClick={() => navigate('/platform')}>В Консоль</Button>}
        />
      </div>
    );
  }

  if (tenant.access.mode !== 'blocked') {
    return (
      <div style={{
        minHeight: '100vh',
        background: colors.bgPrimary,
        color: colors.textPrimary,
        padding: 24,
        boxSizing: 'border-box',
      }}>
        <section style={{
          maxWidth: 680,
          margin: '0 auto',
          background: colors.bgSecondary,
          border: `1px solid ${colors.borderPrimary}`,
          borderRadius: 8,
          padding: 24,
        }}>
          <Title level={3} style={{ marginTop: 0 }}>Экран блокировки не активен</Title>
          <Text type="secondary">
            Кабинет "{tenant.name}" сейчас имеет статус {tenant.access.status} и режим {tenant.access.mode}.
            Отдельный expired/suspended экран показывается только при blocked access.
          </Text>
          <div style={{ marginTop: 20 }}>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/platform')}>
              Вернуться в Консоль
            </Button>
          </div>
        </section>
      </div>
    );
  }

  return (
    <TenantAccessBlocked
      preview={{
        tenantName: tenant.name,
        role: previewRole,
        access: { ...tenant.access, bypass_access_restrictions: false },
      }}
      onExitPreview={() => navigate('/platform')}
    />
  );
};

export default TenantAccessPreview;
