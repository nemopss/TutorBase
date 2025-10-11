import React from 'react';
import { useThemeMode } from '../../theme/ThemeProvider';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

const PageHeader: React.FC<PageHeaderProps> = ({ title, subtitle, actions }) => {
  const { resolvedTheme } = useThemeMode();
  const isDark = resolvedTheme === 'dark';

  const titleColor = isDark ? '#ffffff' : '#000000';
  const subtitleColor = isDark ? '#a0a0a0' : 'rgba(0,0,0,0.45)';
  const borderColor = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.06)';

  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column',
      gap: 16,
      marginBottom: 24,
      paddingBottom: 16,
      borderBottom: `1px solid ${borderColor}`,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <h1 style={{ 
            fontSize: 28, 
            fontWeight: 700, 
            margin: 0,
            marginBottom: subtitle ? 4 : 0,
            color: titleColor,
            lineHeight: 1.2,
          }}>
            {title}
          </h1>
          {subtitle && (
            <p style={{ 
              fontSize: 14, 
              color: subtitleColor, 
              margin: 0 
            }}>
              {subtitle}
            </p>
          )}
        </div>
        {actions && <div style={{ display: 'flex', alignItems: 'center' }}>{actions}</div>}
      </div>
    </div>
  );
};

export default PageHeader;
