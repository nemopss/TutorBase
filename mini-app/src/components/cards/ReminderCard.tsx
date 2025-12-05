import React from 'react';
import { Card, Tag, Button, Space, Typography } from 'antd';
import { EditOutlined, ClockCircleOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { useThemeMode } from '../../theme/ThemeProvider';
import { spacing } from '../../theme/tokens';

const { Text } = Typography;

interface Reminder {
  id: number;
  package_id: number;
  reminder_type?: string;
  scheduled_for: string;
  status: string;
  active: boolean;
  last_response?: string;
}

interface ReminderCardProps {
  reminder: Reminder;
  packageInfo?: { title: string; learner_name: string };
  onEdit: (reminder: Reminder) => void;
  onClick?: (reminder: Reminder) => void;
}

const getStatusColor = (status: string) => {
  switch (status) {
    case 'scheduled': return 'default';
    case 'sent': return 'processing';
    case 'responded': return 'success';
    case 'failed': return 'error';
    case 'cancelled': return 'warning';
    default: return 'default';
  }
};

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'scheduled':
    case 'sent':
      return <ClockCircleOutlined />;
    case 'responded':
      return <CheckCircleOutlined />;
    case 'failed':
    case 'cancelled':
      return <CloseCircleOutlined />;
    default:
      return null;
  }
};

const ReminderCard: React.FC<ReminderCardProps> = ({
  reminder,
  packageInfo,
  onEdit,
  onClick,
}) => {
  const { resolvedTheme } = useThemeMode();
  const isDark = resolvedTheme === 'dark';

  const packageLabel = packageInfo
    ? `${packageInfo.title} (${packageInfo.learner_name})`
    : `Package ${reminder.package_id}`;

  return (
    <Card
      size="small"
      style={{
        marginBottom: spacing.sm,
        cursor: onClick ? 'pointer' : 'default',
        background: isDark ? '#1f1f1f' : '#ffffff',
        borderColor: isDark ? '#3a3a3a' : '#e8e8e8',
      }}
      onClick={() => onClick?.(reminder)}
      actions={[
        <Button
          key="edit"
          type="text"
          icon={<EditOutlined />}
          onClick={(e) => {
            e.stopPropagation();
            onEdit(reminder);
          }}
        >
          Edit
        </Button>,
      ]}
    >
      <Space direction="vertical" size={spacing.xs} style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: spacing.xs }}>
          <Text strong>{dayjs(reminder.scheduled_for).format('YYYY-MM-DD HH:mm')}</Text>
          <Space size={4}>
            <Tag color={getStatusColor(reminder.status)} icon={getStatusIcon(reminder.status)}>
              {reminder.status.toUpperCase()}
            </Tag>
            <Tag color={reminder.active ? 'green' : 'red'}>
              {reminder.active ? 'Active' : 'Inactive'}
            </Tag>
          </Space>
        </div>
        
        <Text type="secondary">{packageLabel}</Text>
        
        {reminder.reminder_type && (
          <Tag>{reminder.reminder_type.replace('_', ' ').toUpperCase()}</Tag>
        )}
        
        {reminder.last_response && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            Response: {reminder.last_response}
          </Text>
        )}
      </Space>
    </Card>
  );
};

export default ReminderCard;
