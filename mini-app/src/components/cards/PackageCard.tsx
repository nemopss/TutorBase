import React from 'react';
import { Card, Tag, Progress, Button, Space, Typography } from 'antd';
import { EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { useThemeMode } from '../../theme/ThemeProvider';
import { spacing } from '../../theme/tokens';

const { Text } = Typography;

interface PackageProgress {
  total: number;
  completed: number;
  cancelled: number;
}

interface Package {
  id: number;
  title: string;
  learner_name: string;
  status: string;
  progress: PackageProgress;
}

interface PackageCardProps {
  package: Package;
  onEdit: (pkg: Package) => void;
  onDelete: (id: number) => void;
  onClick?: (pkg: Package) => void;
}

const PackageCard: React.FC<PackageCardProps> = ({
  package: pkg,
  onEdit,
  onDelete,
  onClick,
}) => {
  const { resolvedTheme } = useThemeMode();
  const isDark = resolvedTheme === 'dark';

  const progress = pkg.progress || { total: 0, completed: 0, cancelled: 0 };
  const percent = progress.total > 0
    ? Math.round(((progress.completed + progress.cancelled) / progress.total) * 100)
    : 0;

  const statusColor = pkg.status === 'active' ? 'green' : 'volcano';

  return (
    <Card
      size="small"
      style={{
        marginBottom: spacing.sm,
        cursor: onClick ? 'pointer' : 'default',
        background: isDark ? '#1f1f1f' : '#ffffff',
        borderColor: isDark ? '#3a3a3a' : '#e8e8e8',
      }}
      onClick={() => onClick?.(pkg)}
      actions={[
        <Button
          key="edit"
          type="text"
          icon={<EditOutlined />}
          onClick={(e) => {
            e.stopPropagation();
            onEdit(pkg);
          }}
        >
          Edit
        </Button>,
        <Button
          key="delete"
          type="text"
          danger
          icon={<DeleteOutlined />}
          onClick={(e) => {
            e.stopPropagation();
            onDelete(pkg.id);
          }}
        >
          Delete
        </Button>,
      ]}
    >
      <Space direction="vertical" size={spacing.xs} style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Text strong style={{ fontSize: 16 }}>{pkg.title}</Text>
          <Tag color={statusColor}>{pkg.status?.toUpperCase() || 'UNKNOWN'}</Tag>
        </div>
        
        <Text type="secondary">{pkg.learner_name}</Text>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
          <Progress
            percent={percent}
            size="small"
            strokeColor="#0f7b6c"
            style={{ flex: 1, margin: 0 }}
          />
          <Text type="secondary" style={{ fontSize: 12, minWidth: 60 }}>
            {progress.completed}+{progress.cancelled}/{progress.total}
          </Text>
        </div>
      </Space>
    </Card>
  );
};

export default PackageCard;
