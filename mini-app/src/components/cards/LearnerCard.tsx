import React from 'react';
import { Card, Tag, Switch, Space, Typography, Tooltip, Button } from 'antd';
import { BellOutlined, BellFilled, IdcardOutlined, DeleteOutlined } from '@ant-design/icons';
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
  isToggling?: boolean;
  onClick?: (learner: Learner) => void;
}

const LearnerCard: React.FC<LearnerCardProps> = ({
  learner,
  onNotificationToggle,
  onDelete,
  isToggling = false,
  onClick,
}) => {
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
      actions={onDelete ? [
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
          Delete
        </Button>,
      ] : undefined}
    >
      <Space direction="vertical" size={spacing.sm} style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <IdcardOutlined />
            <Text strong>{learner.display_name}</Text>
          </Space>
          <Tag color={learner.notifications_enabled ? 'green' : 'red'}>
            {learner.notifications_enabled ? 'Notifications On' : 'Notifications Off'}
          </Tag>
        </div>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Text type="secondary" copyable={learner.chat_id ? { text: String(learner.chat_id) } : false}>
            Chat ID: {learner.chat_id || '—'}
          </Text>
          
          <Tooltip title={learner.notifications_enabled ? 'Disable notifications' : 'Enable notifications'}>
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
