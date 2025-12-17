import React from 'react';
import { Card, Tag, Switch, Space, Typography, Tooltip, Button } from 'antd';
import { BellOutlined, BellFilled, IdcardOutlined, DeleteOutlined, DollarOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useThemeMode } from '../../theme/ThemeProvider';
import { spacing } from '../../theme/tokens';

const { Text } = Typography;

interface Learner {
  id: number;
  display_name: string;
  notifications_enabled: boolean;
  chat_id: number | null;
}

interface LearnerCardProps {
  learner: Learner;
  onNotificationToggle: (learnerId: number, currentValue: boolean) => void;
  onDelete?: (learnerId: number) => void;
  onFinance?: (learnerId: number) => void;
  isToggling?: boolean;
  onClick?: (learner: Learner) => void;
}

const LearnerCard: React.FC<LearnerCardProps> = ({
  learner,
  onNotificationToggle,
  onDelete,
  onFinance,
  isToggling = false,
  onClick,
}) => {
  const { t } = useTranslation();
  const { resolvedTheme } = useThemeMode();
  const isDark = resolvedTheme === 'dark';

  return (
    <Card
      size="small"
      style={{
        marginBottom: spacing.sm,
        cursor: onClick ? 'pointer' : 'default',
        background: isDark ? '#1f1f1f' : '#ffffff',
        borderColor: isDark ? '#3a3a3a' : '#e8e8e8',
      }}
      onClick={() => onClick?.(learner)}
      actions={[
        ...(onFinance ? [
          <Button
            key="finance"
            type="text"
            icon={<DollarOutlined />}
            onClick={(e) => {
              e.stopPropagation();
              onFinance(learner.id);
            }}
          >
            {t('pages.learners.finance')}
          </Button>,
        ] : []),
        ...(onDelete ? [
          <Button
            key="delete"
            type="text"
            danger
            icon={<DeleteOutlined />}
            onClick={(e) => {
              e.stopPropagation();
              onDelete(learner.id);
            }}
          >
            {t('common.delete')}
          </Button>,
        ] : []),
      ]}
    >
      <Space direction="vertical" size={spacing.sm} style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <IdcardOutlined />
            <Text strong>{learner.display_name}</Text>
          </Space>
          <Tag color={learner.notifications_enabled ? 'green' : 'red'}>
            {learner.notifications_enabled ? t('pages.learners.notificationsOn') : t('pages.learners.notificationsOff')}
          </Tag>
        </div>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Text type="secondary" copyable={learner.chat_id ? { text: String(learner.chat_id) } : false}>
            {t('pages.learners.chatId')}: {learner.chat_id || '—'}
          </Text>
          
          <Tooltip title={learner.notifications_enabled ? t('pages.learners.notificationsOff') : t('pages.learners.notificationsOn')}>
            <Switch
              checked={learner.notifications_enabled}
              onChange={() => {
                onNotificationToggle(learner.id, learner.notifications_enabled);
              }}
              onClick={(_, e) => e.stopPropagation()}
              loading={isToggling}
              checkedChildren={<BellFilled />}
              unCheckedChildren={<BellOutlined />}
            />
          </Tooltip>
        </div>
      </Space>
    </Card>
  );
};

export default LearnerCard;
