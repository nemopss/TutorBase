import React from 'react';
import { Empty, Button } from 'antd';
import { PlusOutlined } from '@ant-design/icons';

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
            <div style={{ fontSize: 16, fontWeight: 500, marginBottom: 8, color: '#37352f' }}>
              {title}
            </div>
            {description && (
              <div style={{ fontSize: 14, color: '#8c8c8c' }}>
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
