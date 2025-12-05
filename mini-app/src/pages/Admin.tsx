import { useCallback, useEffect, useMemo, useState } from 'react';
import { Card, Typography, Tag, Select, Space, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
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
  createdAt: string;
  updatedAt: string;
  lastLoginAt: string | null;
}

const roleLabels: Record<UserRole, string> = {
  admin: 'Админ',
  teacher: 'Преподаватель',
  viewer: 'Наблюдатель',
};

const roleColors: Record<UserRole, string> = {
  admin: 'magenta',
  teacher: 'blue',
  viewer: 'default',
};

const roleOptions = [
  { value: 'viewer', label: roleLabels.viewer },
  { value: 'teacher', label: roleLabels.teacher },
  { value: 'admin', label: roleLabels.admin },
];

const mapUser = (user: any): UserRecord => ({
  id: user.id,
  displayName: user.display_name,
  username: user.username,
  telegramId: user.telegram_id,
  role: user.role,
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
  const { user } = useAuth();
  const [data, setData] = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [updatingUserId, setUpdatingUserId] = useState<number | null>(null);
  const { isMobile } = useResponsive();

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get('/users');
      setData(response.data.items.map(mapUser));
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      message.error(detail ?? 'Не удалось загрузить список пользователей');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleRoleChange = useCallback(
    async (userId: number, role: UserRole) => {
      setUpdatingUserId(userId);
      try {
        const response = await api.patch(`/users/${userId}/role`, { role });
        const updated = mapUser(response.data);
        setData((prev) => prev.map((item) => (item.id === userId ? updated : item)));
        message.success(`Роль обновлена: ${updated.displayName} теперь ${roleLabels[updated.role]}`);
      } catch (error: any) {
        const detail = error?.response?.data?.detail;
        message.error(detail ?? 'Не удалось обновить роль пользователя');
      } finally {
        setUpdatingUserId(null);
      }
    },
    [],
  );

  const columns: ColumnsType<UserRecord> = useMemo(() => {
    return [
      {
        title: 'Пользователь',
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
                  Последний вход: {formatDateTime(record.lastLoginAt)}
                </Typography.Text>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  Создан: {formatDateTime(record.createdAt)}
                </Typography.Text>
              </>
            )}
          </Space>
        ),
      },
      {
        title: 'Telegram',
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
        title: 'Роль',
        dataIndex: 'role',
        key: 'role',
        render: (role: UserRole, record) => (
          <Space wrap>
            <Tag color={roleColors[role]}>{roleLabels[role]}</Tag>
            <Select<UserRole>
              value={role}
              options={roleOptions}
              onChange={(value) => handleRoleChange(record.id, value)}
              size={isMobile ? 'middle' : 'small'}
              loading={updatingUserId === record.id}
              disabled={updatingUserId === record.id || record.id === user?.id}
              style={{ minWidth: isMobile ? 140 : 160 }}
              dropdownMatchSelectWidth={false}
            />
          </Space>
        ),
      },
      {
        title: 'Последний вход',
        dataIndex: 'lastLoginAt',
        key: 'lastLoginAt',
        responsive: ['md'],
        render: (value: string | null) => formatDateTime(value),
      },
      {
        title: 'Создан',
        dataIndex: 'createdAt',
        key: 'createdAt',
        responsive: ['lg'],
        render: (value: string) => formatDateTime(value),
      },
    ];
  }, [handleRoleChange, isMobile, updatingUserId, user?.id]);

  return (
    <Space direction="vertical" size={24} style={{ width: '100%' }}>
      <div>
        <Typography.Title level={3} style={{ marginBottom: 8 }}>
          Панель администратора
        </Typography.Title>
        <Typography.Paragraph type="secondary" style={{ margin: 0 }}>
          Управляйте доступом к мини-приложению и назначайте роли преподавателей.
        </Typography.Paragraph>
      </div>

      <Card>
        <ResponsiveDataView<UserRecord>
          data={data}
          loading={loading}
          columns={columns}
          rowKey="id"
          emptyText="Нет пользователей"
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
