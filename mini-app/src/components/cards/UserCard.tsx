import React from 'react';
import { Card, Tag, Select, Space, Typography } from 'antd';
import { useThemeMode } from '../../theme/ThemeProvider';
import { spacing } from '../../theme/tokens';

const { Text } = Typography;

type UserRole = 'admin' | 'teacher' | 'viewer';

interface UserRecord {
  id: number;
  displayName: string;
  username: string | null;
  telegramId: number | null;
  role: UserRole;
  createdAt: string;
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

const formatDateTime = (value: string | null) => {
  if (!value) return '—';
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

interface UserCardProps {
  user: UserRecord;
  currentUserId?: number;
  onRoleChange: (userId: number, role: UserRole) => void;
  isUpdating?: boolean;
  onClick?: (user: UserRecord) => void;
}

const UserCard: React.FC<UserCardProps> = ({
  user,
  currentUserId,
  onRoleChange,
  isUpdating = false,
  onClick,
}) => {
  const { resolvedTheme } = useThemeMode();
  const isDark = resolvedTheme === 'dark';

  const isCurrentUser = user.id === currentUserId;

  return (
    <Card
      size="small"
      style={{
        marginBottom: spacing.sm,
        cursor: onClick ? 'pointer' : 'default',
        background: isDark ? '#1f1f1f' : '#ffffff',
        borderColor: isDark ? '#3a3a3a' : '#e8e8e8',
      }}
      onClick={() => onClick?.(user)}
    >
      <Space direction="vertical" size={spacing.sm} style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: spacing.xs }}>
          <div>
            <Text strong>{user.displayName}</Text>
            <br />
            <Text type="secondary" style={{ fontSize: 12 }}>ID: {user.id}</Text>
          </div>
          <Tag color={roleColors[user.role]}>{roleLabels[user.role]}</Tag>
        </div>
        
        <Space direction="vertical" size={2}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {user.username ? `@${user.username}` : 'No username'}
          </Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Telegram ID: {user.telegramId ?? '—'}
          </Text>
        </Space>
        
        <Space direction="vertical" size={2}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Последний вход: {formatDateTime(user.lastLoginAt)}
          </Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Создан: {formatDateTime(user.createdAt)}
          </Text>
        </Space>
        
        <div style={{ paddingTop: spacing.xs }}>
          <Text type="secondary" style={{ fontSize: 12, marginRight: spacing.sm }}>Изменить роль:</Text>
          <Select<UserRole>
            value={user.role}
            options={roleOptions}
            onChange={(value) => onRoleChange(user.id, value)}
            size="middle"
            loading={isUpdating}
            disabled={isUpdating || isCurrentUser}
            style={{ minWidth: 140 }}
            dropdownMatchSelectWidth={false}
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      </Space>
    </Card>
  );
};

export default UserCard;
