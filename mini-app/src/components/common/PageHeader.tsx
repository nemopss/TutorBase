import React from 'react';
import { useThemeMode } from '../../theme/ThemeProvider';
import { useResponsive } from '../../hooks/useResponsive';
import { spacing } from '../../theme/tokens';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

const PageHeader: React.FC<PageHeaderProps> = ({ title, subtitle, actions }) => {
  const { resolvedTheme } = useThemeMode();
  const { isMobile } = useResponsive();
  const isDark = resolvedTheme === 'dark';

  const titleColor = isDark ? '#ffffff' : '#000000';
  const subtitleColor = isDark ? '#a0a0a0' : 'rgba(0,0,0,0.45)';
  const borderColor = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.06)';

  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column',
      gap: isMobile ? spacing.sm : spacing.md,
      marginBottom: isMobile ? spacing.md : spacing.lg,
      paddingBottom: spacing.md,
      borderBottom: `1px solid ${borderColor}`,
    }}>
      <div style={{ 
        display: 'flex', 
        flexDirection: isMobile ? 'column' : 'row',
        justifyContent: 'space-between', 
        alignItems: isMobile ? 'stretch' : 'flex-start', 
        gap: spacing.sm,
      }}>
        <div style={{ flex: 1, minWidth: isMobile ? 'auto' : 200 }}>
          <h1 style={{ 
            fontSize: isMobile ? 22 : 28, 
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
              fontSize: isMobile ? 13 : 14, 
              color: subtitleColor, 
              margin: 0 
            }}>
              {subtitle}
            </p>
          )}
        </div>
        {actions && (
          <div style={{ 
            display: 'flex', 
            alignItems: 'center',
            width: isMobile ? '100%' : 'auto',
          }}>
            {actions}
          </div>
        )}
      </div>
    </div>
  );
};

export default PageHeader;
