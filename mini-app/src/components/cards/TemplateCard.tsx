import React from 'react';
import { Card, Button, Space, Typography } from 'antd';
import { EditOutlined, DeleteOutlined, CopyOutlined, BookOutlined, CalendarOutlined } from '@ant-design/icons';
import { useTheme } from '../../theme/ThemeProvider';
import { spacing } from '../../theme/tokens';

const { Text } = Typography;

interface Template {
  id: number;
  name: string;
  description?: string;
  lesson_count?: number;
  duration_days?: number;
}

interface TemplateCardProps {
  template: Template;
  onEdit: (template: Template) => void;
  onDuplicate: (id: number) => void;
  onDelete: (id: number) => void;
  onClick?: (template: Template) => void;
}

const TemplateCard: React.FC<TemplateCardProps> = ({
  template,
  onEdit,
  onDuplicate,
  onDelete,
  onClick,
}) => {
  const { resolvedTheme } = useTheme();
  const colors = resolvedTheme.colors;

  return (
    <Card
      size="small"
      style={{
        marginBottom: spacing.sm,
        cursor: onClick ? 'pointer' : 'default',
        background: colors.bgSecondary,
        borderColor: colors.borderPrimary,
      }}
      onClick={() => onClick?.(template)}
      actions={[
        <Button
          key="edit"
          type="text"
          icon={<EditOutlined />}
          onClick={(e) => {
            e.stopPropagation();
            onEdit(template);
          }}
        >
          Edit
        </Button>,
        <Button
          key="duplicate"
          type="text"
          icon={<CopyOutlined />}
          onClick={(e) => {
            e.stopPropagation();
            onDuplicate(template.id);
          }}
        >
          Copy
        </Button>,
        <Button
          key="delete"
          type="text"
          danger
          icon={<DeleteOutlined />}
          onClick={(e) => {
            e.stopPropagation();
            onDelete(template.id);
          }}
        >
          Delete
        </Button>,
      ]}
    >
      <Space direction="vertical" size={spacing.xs} style={{ width: '100%' }}>
        <Text strong style={{ fontSize: 16 }}>{template.name}</Text>
        
        {template.description && (
          <Text type="secondary" ellipsis>
            {template.description}
          </Text>
        )}
        
        <Space size={spacing.md}>
          {template.lesson_count !== undefined && (
            <Space size={4}>
              <BookOutlined style={{ color: '#8c8c8c' }} />
              <Text type="secondary">{template.lesson_count} lessons</Text>
            </Space>
          )}
          {template.duration_days !== undefined && (
            <Space size={4}>
              <CalendarOutlined style={{ color: '#8c8c8c' }} />
              <Text type="secondary">{template.duration_days} days</Text>
            </Space>
          )}
        </Space>
      </Space>
    </Card>
  );
};

export default TemplateCard;
