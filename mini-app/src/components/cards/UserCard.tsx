import React from 'react';
import { Card, Tag, Select, Space, Typography } from 'antd';
import { useTranslation } from 'react-i18next';
import { useTheme } from '../../theme/ThemeProvider';
import { spacing } from '../../theme/tokens';
import i18n from '../../i18n';

const { Text } = Typography;

type UserRole = 'admin' | 'teacher' | 'viewer';

interface UserRecord {
  id: number;
  displayName: string;
  username: string | null;
  telegramId: number | null;
  role: UserRole;
  isPlatformAdmin?: boolean;
  createdAt: string;
  lastLoginAt: string | null;
}

const roleColors: Record<UserRole, string> = {
  admin: 'magenta',
  teacher: 'blue',
  viewer: 'default',
};

const formatDateTime = (value: string | null) => {
  if (!value) return '—';
  try {
    const locale = i18n.language === 'ko' ? 'ko-KR' : i18n.language === 'en' ? 'en-US' : 'ru-RU';
    return new Date(value).toLocaleString(locale, {
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
  const { t } = useTranslation();
  const { resolvedTheme } = useTheme();
  const colors = resolvedTheme.colors;

  const isCurrentUser = user.id === currentUserId;
  
  const roleLabels: Record<UserRole, string> = {
    admin: t('pages.admin.roles.admin'),
    teacher: t('pages.admin.roles.teacher'),
    viewer: t('pages.admin.roles.viewer'),
  };

  const roleOptions = [
    { value: 'viewer', label: roleLabels.viewer },
    { value: 'teacher', label: roleLabels.teacher },
  ];

  return (
    <Card
      size="small"
      style={{
        marginBottom: spacing.sm,
        cursor: onClick ? 'pointer' : 'default',
        background: colors.bgSecondary,
        borderColor: colors.borderPrimary,
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
          <Space size={4} wrap>
            <Tag color={roleColors[user.role]}>{roleLabels[user.role]}</Tag>
            {user.isPlatformAdmin && <Tag color="gold">Владелец</Tag>}
          </Space>
        </div>
        
        <Space direction="vertical" size={2}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {user.username ? `@${user.username}` : '—'}
          </Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Telegram ID: {user.telegramId ?? '—'}
          </Text>
        </Space>
        
        <Space direction="vertical" size={2}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {t('pages.admin.lastLogin')}: {formatDateTime(user.lastLoginAt)}
          </Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {t('pages.admin.created')}: {formatDateTime(user.createdAt)}
          </Text>
        </Space>
        
        <div style={{ paddingTop: spacing.xs }}>
          <Text type="secondary" style={{ fontSize: 12, marginRight: spacing.sm }}>{t('pages.admin.role')}:</Text>
          <Select<UserRole>
            value={user.role}
            options={roleOptions}
            onChange={(value) => onRoleChange(user.id, value)}
            size="middle"
            loading={isUpdating}
            disabled={isUpdating || isCurrentUser || user.isPlatformAdmin}
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
