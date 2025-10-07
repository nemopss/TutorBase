import React from 'react';
import { Empty, Button } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useTelegram } from '../../hooks/useTelegram';

interface EmptyStateProps {
  title?: string;
  description?: string;
  actionText?: string;
  onAction?: () => void;
  icon?: React.ReactNode;
}

const EmptyState: React.FC<EmptyStateProps> = ({ 
  title = 'No data', 
  description, 
  actionText, 
  onAction,
  icon 
}) => {
  const { colorScheme } = useTelegram();
  const titleColor = colorScheme === 'dark' ? '#ffffff' : '#37352f';
  const descColor = colorScheme === 'dark' ? '#a0a0a0' : '#8c8c8c';

  return (
    <div style={{ 
      display: 'flex', 
      justifyContent: 'center', 
      alignItems: 'center', 
      minHeight: '400px',
      padding: '40px 20px'
    }}>
      <Empty
        image={icon || Empty.PRESENTED_IMAGE_SIMPLE}
        imageStyle={{
          height: 120,
        }}
        description={
          <div>
            <div style={{ fontSize: 16, fontWeight: 500, marginBottom: 8, color: titleColor }}>
              {title}
            </div>
            {description && (
              <div style={{ fontSize: 14, color: descColor }}>
                {description}
              </div>
            )}
          </div>
        }
      >
        {actionText && onAction && (
          <Button type="primary" icon={<PlusOutlined />} onClick={onAction}>
            {actionText}
          </Button>
        )}
      </Empty>
    </div>
  );
};

export default EmptyState;
