import React from 'react';
import { Space } from 'antd';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

const PageHeader: React.FC<PageHeaderProps> = ({ title, subtitle, actions }) => {
  return (
    <div style={{ 
      display: 'flex', 
      justifyContent: 'space-between', 
      alignItems: 'flex-start',
      marginBottom: 32,
      paddingBottom: 16,
      borderBottom: '1px solid rgba(0,0,0,0.06)',
    }}>
      <div>
        <h1 style={{ 
          fontSize: 32, 
          fontWeight: 700, 
          margin: 0,
          marginBottom: subtitle ? 4 : 0,
          color: 'var(--ant-color-text)',
          lineHeight: 1.2,
        }}>
          {title}
        </h1>
        {subtitle && (
          <p style={{ 
            fontSize: 14, 
            color: 'rgba(0,0,0,0.45)', 
            margin: 0 
          }}>
            {subtitle}
          </p>
        )}
      </div>
      {actions && <Space>{actions}</Space>}
    </div>
  );
};

export default PageHeader;
