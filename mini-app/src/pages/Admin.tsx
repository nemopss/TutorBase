import { useCallback, useEffect, useMemo, useState } from 'react';
import { Card, Typography, Tag, Select, Space, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { isAxiosError } from 'axios';
import { useTranslation } from 'react-i18next';
import api from '../services/api';
import { useAuth } from '../auth/AuthProvider';
import { useResponsive } from '../hooks/useResponsive';
import ResponsiveDataView from '../components/common/ResponsiveDataView';
import UserCard from '../components/cards/UserCard';

type UserRole = 'admin' | 'teacher' | 'viewer';

interface UserRecord {
  id: number;
  displayName: string;
  username: string | null;
  telegramId: number | null;
  role: UserRole;
  isPlatformAdmin: boolean;
  createdAt: string;
  updatedAt: string;
  lastLoginAt: string | null;
}

interface ApiUser {
  id: number;
  display_name: string;
  username: string | null;
  telegram_id: number | null;
  role: UserRole;
  is_platform_admin?: boolean;
  created_at: string;
  updated_at: string;
  last_login_at: string | null;
}

interface UserListResponse {
  items: ApiUser[];
}

const roleColors: Record<UserRole, string> = {
  admin: 'magenta',
  teacher: 'blue',
  viewer: 'default',
};

const getApiErrorDetail = (error: unknown): string | null => {
  if (!isAxiosError<{ detail?: unknown }>(error)) {
    return null;
  }
  const detail = error.response?.data?.detail;
  return typeof detail === 'string' ? detail : null;
};

const mapUser = (user: ApiUser): UserRecord => ({
  id: user.id,
  displayName: user.display_name,
  username: user.username,
  telegramId: user.telegram_id,
  role: user.role,
  isPlatformAdmin: !!user.is_platform_admin,
  createdAt: user.created_at,
  updatedAt: user.updated_at,
  lastLoginAt: user.last_login_at,
});

const formatDateTime = (value: string | null) => {
  if (!value) {
    return '—';
  }
  try {
    return new Date(value).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return value;
  }
};

const Admin = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [data, setData] = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [updatingUserId, setUpdatingUserId] = useState<number | null>(null);
  const { isMobile } = useResponsive();
  
  const roleLabels: Record<UserRole, string> = useMemo(() => ({
    admin: t('pages.admin.roles.admin'),
    teacher: t('pages.admin.roles.teacher'),
    viewer: t('pages.admin.roles.viewer'),
  }), [t]);

  const roleOptions = useMemo(() => [
    { value: 'viewer', label: roleLabels.viewer },
    { value: 'teacher', label: roleLabels.teacher },
  ], [roleLabels]);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get<UserListResponse>('/users');
      setData(response.data.items.map(mapUser));
    } catch (error: unknown) {
      message.error(getApiErrorDetail(error) ?? t('pages.admin.loadError'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleRoleChange = useCallback(
    async (userId: number, role: UserRole) => {
      setUpdatingUserId(userId);
      try {
        const response = await api.patch<ApiUser>(`/users/${userId}/role`, { role });
        const updated = mapUser(response.data);
        setData((prev) => prev.map((item) => (item.id === userId ? updated : item)));
        message.success(t('pages.admin.roleUpdated', { name: updated.displayName, role: roleLabels[updated.role] }));
      } catch (error: unknown) {
        message.error(getApiErrorDetail(error) ?? t('pages.admin.roleUpdateError'));
      } finally {
        setUpdatingUserId(null);
      }
    },
    [roleLabels, t],
  );

  const columns: ColumnsType<UserRecord> = useMemo(() => {
    return [
      {
        title: t('pages.admin.user'),
        dataIndex: 'displayName',
        key: 'displayName',
        render: (text: string, record) => (
          <Space direction="vertical" size={0}>
            <Typography.Text strong>{text}</Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              ID: {record.id}
            </Typography.Text>
            {isMobile && (
              <>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {record.username ? `@${record.username}` : '—'}
                </Typography.Text>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  Telegram ID: {record.telegramId ?? '—'}
                </Typography.Text>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {t('pages.admin.lastLogin')}: {formatDateTime(record.lastLoginAt)}
                </Typography.Text>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {t('pages.admin.created')}: {formatDateTime(record.createdAt)}
                </Typography.Text>
              </>
            )}
          </Space>
        ),
      },
      {
        title: t('pages.admin.telegram'),
        dataIndex: 'username',
        key: 'username',
        responsive: ['md'],
        render: (_: unknown, record) => (
          <Space direction="vertical" size={0}>
            <Typography.Text>{record.username ? `@${record.username}` : '—'}</Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {record.telegramId ?? '—'}
            </Typography.Text>
          </Space>
        ),
      },
      {
        title: t('pages.admin.role'),
        dataIndex: 'role',
        key: 'role',
        render: (role: UserRole, record) => (
          <Space wrap>
            <Tag color={roleColors[role]}>{roleLabels[role]}</Tag>
            {record.isPlatformAdmin && <Tag color="gold">Владелец</Tag>}
            <Select<UserRole>
              value={role}
              options={roleOptions}
              onChange={(value) => handleRoleChange(record.id, value)}
              size={isMobile ? 'middle' : 'small'}
              loading={updatingUserId === record.id}
              disabled={updatingUserId === record.id || record.id === user?.id || record.isPlatformAdmin}
              style={{ minWidth: isMobile ? 140 : 160 }}
              popupMatchSelectWidth={false}
            />
          </Space>
        ),
      },
      {
        title: t('pages.admin.lastLogin'),
        dataIndex: 'lastLoginAt',
        key: 'lastLoginAt',
        responsive: ['md'],
        render: (value: string | null) => formatDateTime(value),
      },
      {
        title: t('pages.admin.created'),
        dataIndex: 'createdAt',
        key: 'createdAt',
        responsive: ['lg'],
        render: (value: string) => formatDateTime(value),
      },
    ];
  }, [handleRoleChange, isMobile, updatingUserId, user?.id, t, roleLabels, roleOptions]);

  return (
    <Space direction="vertical" size={24} style={{ width: '100%' }}>
      <div>
        <Typography.Title level={3} style={{ marginBottom: 8 }}>
          {t('pages.admin.title')}
        </Typography.Title>
        <Typography.Paragraph type="secondary" style={{ margin: 0 }}>
          {t('pages.admin.subtitle')}
        </Typography.Paragraph>
      </div>

      <Card>
        <ResponsiveDataView<UserRecord>
          data={data}
          loading={loading}
          columns={columns}
          rowKey="id"
          emptyText={t('pages.admin.noUsers')}
          renderCard={(userRecord) => (
            <UserCard
              key={userRecord.id}
              user={userRecord}
              currentUserId={user?.id}
              onRoleChange={handleRoleChange}
              isUpdating={updatingUserId === userRecord.id}
            />
          )}
          tableProps={{
            size: isMobile ? 'small' : 'middle',
            scroll: { x: 720 },
          }}
          pagination={false}
        />
      </Card>
    </Space>
  );
};

export default Admin;
