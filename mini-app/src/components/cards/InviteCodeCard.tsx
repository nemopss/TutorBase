import React from 'react';
import { Card, Tag, Button, Space, Typography, Tooltip } from 'antd';
import { CopyOutlined, CheckCircleOutlined, ClockCircleOutlined, DeleteOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { useThemeMode } from '../../theme/ThemeProvider';
import { spacing } from '../../theme/tokens';

const { Text } = Typography;

interface InviteToken {
  id: number;
  token: string;
  expires_at: string;
  used_at: string | null;
  created_at: string;
}

interface InviteCodeCardProps {
  inviteCode: InviteToken;
  onCopyToken: (token: string) => void;
  onCopyLink: (token: string) => void;
  onDelete?: (id: number) => void;
  onClick?: (inviteCode: InviteToken) => void;
}

const InviteCodeCard: React.FC<InviteCodeCardProps> = ({
  inviteCode,
  onCopyToken,
  onCopyLink,
  onDelete,
  onClick,
}) => {
  const { resolvedTheme } = useThemeMode();
  const isDark = resolvedTheme === 'dark';

  const isUsed = !!inviteCode.used_at;
  const isExpired = dayjs(inviteCode.expires_at).isBefore(dayjs());
  const isActive = !isUsed && !isExpired;

  const getStatusTag = () => {
    if (isUsed) {
      return (
        <Tag icon={<CheckCircleOutlined />} color="success">
          Used {dayjs(inviteCode.used_at).fromNow()}
        </Tag>
      );
    }
    if (isExpired) {
      return (
        <Tag icon={<ClockCircleOutlined />} color="default">
          Expired
        </Tag>
      );
    }
    return (
      <Tag icon={<ClockCircleOutlined />} color="processing">
        Active
      </Tag>
    );
  };

  return (
    <Card
      size="small"
      style={{
        marginBottom: spacing.sm,
        cursor: onClick ? 'pointer' : 'default',
        background: isDark ? '#1f1f1f' : '#ffffff',
        borderColor: isDark ? '#3a3a3a' : '#e8e8e8',
      }}
      onClick={() => onClick?.(inviteCode)}
      actions={[
        ...(isActive ? [
          <Tooltip key="copy" title="Copy code">
            <Button
              type="text"
              icon={<CopyOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                onCopyToken(inviteCode.token);
              }}
            >
              Copy Code
            </Button>
          </Tooltip>,
          <Button
            key="link"
            type="text"
            onClick={(e) => {
              e.stopPropagation();
              onCopyLink(inviteCode.token);
            }}
          >
            Copy Link
          </Button>,
        ] : []),
        ...(!isUsed && onDelete ? [
          <Button
            key="delete"
            type="text"
            danger
            icon={<DeleteOutlined />}
            onClick={(e) => {
              e.stopPropagation();
              onDelete(inviteCode.id);
            }}
          >
            Delete
          </Button>,
        ] : []),
      ].filter(Boolean)}
    >
      <Space direction="vertical" size={spacing.xs} style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: spacing.xs }}>
          <Text code copyable={{ text: inviteCode.token }}>
            {inviteCode.token.substring(0, 16)}...
          </Text>
          {getStatusTag()}
        </div>
        
        <Space size={spacing.md} wrap>
          <Tooltip title={dayjs(inviteCode.expires_at).format('YYYY-MM-DD HH:mm')}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              Expires {dayjs(inviteCode.expires_at).fromNow()}
            </Text>
          </Tooltip>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Created {dayjs(inviteCode.created_at).format('MMM D, YYYY')}
          </Text>
        </Space>
      </Space>
    </Card>
  );
};

export default InviteCodeCard;
