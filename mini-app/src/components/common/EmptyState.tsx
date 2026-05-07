import React from 'react';
import { Empty, Button } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useTheme } from '../../theme/ThemeProvider';
import { useResponsive } from '../../hooks/useResponsive';
import { spacing } from '../../theme/tokens';

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
  const { resolvedTheme } = useTheme();
  const { isMobile } = useResponsive();
  const isDark = resolvedTheme.colorScheme === 'dark';
  const titleColor = isDark ? '#ffffff' : '#37352f';
  const descColor = isDark ? '#a0a0a0' : '#8c8c8c';

  return (
    <div style={{ 
      display: 'flex', 
      justifyContent: 'center', 
      alignItems: 'center', 
      minHeight: isMobile ? 250 : 400,
      padding: isMobile ? `${spacing.lg}px ${spacing.md}px` : '40px 20px',
    }}>
      <Empty
        image={icon || Empty.PRESENTED_IMAGE_SIMPLE}
        styles={{
          image: {
            height: isMobile ? 80 : 120,
          },
        }}
        description={
          <div>
            <div style={{ fontSize: isMobile ? 14 : 16, fontWeight: 500, marginBottom: 8, color: titleColor }}>
              {title}
            </div>
            {description && (
              <div style={{ fontSize: isMobile ? 12 : 14, color: descColor }}>
                {description}
              </div>
            )}
          </div>
        }
      >
        {actionText && onAction && (
          <Button type="primary" icon={<PlusOutlined />} onClick={onAction} size={isMobile ? 'middle' : 'large'}>
            {actionText}
          </Button>
        )}
      </Empty>
    </div>
  );
};

export default EmptyState;
