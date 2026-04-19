import { Alert, Button, Space, Typography } from 'antd';
import { LockOutlined, ReloadOutlined } from '@ant-design/icons';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import type { TenantAccess } from '../auth/AuthProvider';
import { useTheme } from '../theme/ThemeProvider';

const { Paragraph, Text, Title } = Typography;

type PreviewRole = 'teacher' | 'viewer';

interface TenantAccessBlockedProps {
  preview?: {
    access: TenantAccess;
    role: PreviewRole;
    tenantName?: string;
  };
  onExitPreview?: () => void;
}

const formatDate = (value?: string | null) => {
  if (!value) return null;
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  }).format(new Date(value));
};

const TenantAccessBlocked = ({ preview, onExitPreview }: TenantAccessBlockedProps) => {
  const { user, tenantAccess, isSuperAdmin, logout, refreshTenantAccess } = useAuth();
  const { resolvedTheme } = useTheme();
  const colors = resolvedTheme.colors;
  const effectiveAccess = preview?.access ?? tenantAccess;
  const effectiveRole = preview?.role ?? user?.role;
  const isPreview = !!preview;
  const isStudent = effectiveRole === 'viewer';
  const isSuspended = effectiveAccess?.status === 'suspended';
  const accessUntil = formatDate(effectiveAccess?.access_until);
  const graceUntil = formatDate(effectiveAccess?.grace_until);

  const title = isStudent
    ? 'Кабинет временно недоступен'
    : isSuspended
      ? 'Доступ к кабинету приостановлен'
      : 'Доступ к кабинету истёк';

  const description = isStudent
    ? 'Свяжитесь с преподавателем, чтобы уточнить детали.'
    : isSuspended
      ? 'Кабинет заблокирован вручную. Для восстановления доступа напишите владельцу сервиса.'
      : 'Чтобы снова пользоваться TutorBase, продлите доступ или напишите владельцу сервиса.';

  return (
    <div style={{
      minHeight: '100vh',
      background: colors.bgPrimary,
      color: colors.textPrimary,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 24,
      boxSizing: 'border-box',
    }}>
      <section style={{
        width: '100%',
        maxWidth: 520,
        background: colors.bgSecondary,
        border: `1px solid ${colors.borderPrimary}`,
        borderRadius: 8,
        padding: 28,
        textAlign: 'center',
      }}>
        <LockOutlined style={{ fontSize: 44, color: '#fa8c16' }} />
        <Title level={3} style={{ marginTop: 16, marginBottom: 8 }}>
          {title}
        </Title>
        <Paragraph type="secondary" style={{ marginBottom: 20 }}>
          {description}
        </Paragraph>

        {isPreview && (
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 20, textAlign: 'left' }}
            message="Preview экрана доступа"
            description={`Кабинет: ${preview.tenantName ?? `#${preview.access.tenant_id}`}. Роль: ${isStudent ? 'ученик' : 'репетитор'}. Это debug-preview, реальный owner-доступ не меняется.`}
          />
        )}

        {!isStudent && (
          <Space direction="vertical" size={8} style={{ width: '100%', marginBottom: 20 }}>
            {accessUntil && (
              <Text type="secondary">Доступ был активен до {accessUntil}</Text>
            )}
            {graceUntil && (
              <Text type="secondary">Grace-период закончился {graceUntil}</Text>
            )}
          </Space>
        )}

        {!isPreview && isSuperAdmin && tenantAccess?.bypass_access_restrictions && (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 20, textAlign: 'left' }}
            message="Открыт support context"
            description="Вы видите этот кабинет как владелец платформы. Обычный репетитор будет видеть экран блокировки."
          />
        )}

        <Space direction="vertical" style={{ width: '100%' }}>
          {isPreview ? (
            <Button type="primary" onClick={onExitPreview} block>
              Вернуться в Консоль
            </Button>
          ) : (
            <>
              <Button
                type="primary"
                icon={<ReloadOutlined />}
                onClick={refreshTenantAccess}
                block
              >
                Проверить доступ
              </Button>
              {isSuperAdmin && (
                <Link to="/platform">
                  <Button block>Открыть Консоль</Button>
                </Link>
              )}
              <Button onClick={logout} block>
                Выйти
              </Button>
            </>
          )}
        </Space>
      </section>
    </div>
  );
};

export default TenantAccessBlocked;
