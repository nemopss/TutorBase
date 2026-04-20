import React from 'react';
import { Card, Tag, Button, Space, Typography, Tooltip } from 'antd';
import { CopyOutlined, CheckCircleOutlined, ClockCircleOutlined, DeleteOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { useTranslation } from 'react-i18next';
import { useTheme } from '../../theme/ThemeProvider';
import { spacing } from '../../theme/tokens';

const { Text } = Typography;

interface InviteToken {
  id: number;
  token: string;
  expires_at: string;
  created_at: string;
  is_used: boolean;
  is_expired: boolean;
  is_valid: boolean;
  learner_id?: number | null;
  learner_name?: string | null;
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
  const { t } = useTranslation();
  const { resolvedTheme } = useTheme();
  const colors = resolvedTheme.colors;

  const isUsed = inviteCode.is_used;
  const isExpired = inviteCode.is_expired || dayjs(inviteCode.expires_at).isBefore(dayjs());
  const isActive = !isUsed && !isExpired;
  const formatInviteDate = (value: string) => dayjs(value).format('D MMM YYYY HH:mm');

  const getStatusTag = () => {
    if (isUsed) {
      return (
        <Tag icon={<CheckCircleOutlined />} color="success">
          {t('pages.inviteCodes.status.used')}
        </Tag>
      );
    }
    if (isExpired) {
      return (
        <Tag icon={<ClockCircleOutlined />} color="default">
          {t('pages.inviteCodes.status.expired')}
        </Tag>
      );
    }
    return (
      <Tag icon={<ClockCircleOutlined />} color="processing">
        {t('pages.inviteCodes.status.active')}
      </Tag>
    );
  };

  return (
    <Card
      size="small"
      style={{
        marginBottom: spacing.sm,
        cursor: onClick ? 'pointer' : 'default',
        background: colors.bgSecondary,
        borderColor: colors.borderPrimary,
      }}
      onClick={() => onClick?.(inviteCode)}
      actions={[
        ...(isActive ? [
          <Tooltip key="copy" title={t('pages.inviteCodes.copyCode')}>
            <Button
              type="text"
              icon={<CopyOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                onCopyToken(inviteCode.token);
              }}
            >
              {t('pages.inviteCodes.copyCode')}
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
            {t('pages.inviteCodes.copyLink')}
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
            {t('common.delete')}
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
          <Tooltip title={formatInviteDate(inviteCode.expires_at)}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {t('pages.inviteCodes.expires')}: {formatInviteDate(inviteCode.expires_at)}
            </Text>
          </Tooltip>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {t('pages.inviteCodes.created')}: {formatInviteDate(inviteCode.created_at)}
          </Text>
        </Space>
      </Space>
    </Card>
  );
};

export default InviteCodeCard;
