import React from 'react';
import { useTheme } from '../../theme/ThemeProvider';
import { useResponsive } from '../../hooks/useResponsive';
import { spacing } from '../../theme/tokens';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  leading?: React.ReactNode;
  variant?: 'section' | 'compact' | 'minimal';
}

const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  subtitle,
  actions,
  leading,
  variant = 'section',
}) => {
  const { resolvedTheme } = useTheme();
  const { isMobile } = useResponsive();
  const isDark = resolvedTheme.colorScheme === 'dark';

  const titleColor = isDark ? '#ffffff' : '#000000';
  const subtitleColor = isDark ? '#a0a0a0' : 'rgba(0,0,0,0.45)';
  const config = {
    section: {
      gap: isMobile ? spacing.sm : spacing.md,
      marginBottom: isMobile ? spacing.lg : spacing.xl,
      titleSize: isMobile ? 26 : 30,
      titleWeight: 700,
      subtitleSize: isMobile ? 13 : 14,
      titleLineHeight: 1.15,
    },
    compact: {
      gap: isMobile ? spacing.xs : spacing.sm,
      marginBottom: isMobile ? spacing.md : spacing.lg,
      titleSize: isMobile ? 22 : 24,
      titleWeight: 700,
      subtitleSize: isMobile ? 13 : 14,
      titleLineHeight: 1.2,
    },
    minimal: {
      gap: isMobile ? spacing.xs : spacing.sm,
      marginBottom: isMobile ? spacing.md : spacing.lg,
      titleSize: isMobile ? 28 : 32,
      titleWeight: 750,
      subtitleSize: isMobile ? 13 : 14,
      titleLineHeight: 1.1,
    },
  }[variant];

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: config.gap,
      marginBottom: config.marginBottom,
    }}>
      <div style={{
        display: 'flex',
        flexDirection: isMobile ? 'column' : 'row',
        justifyContent: 'space-between',
        alignItems: isMobile ? 'stretch' : 'flex-start',
        gap: spacing.sm,
      }}>
        <div style={{
          display: 'flex',
          alignItems: variant === 'compact' ? 'center' : 'flex-start',
          gap: variant === 'compact' ? spacing.sm : 0,
          flex: 1,
          minWidth: 0,
        }}>
          {leading && (
            <div style={{ flex: '0 0 auto', display: 'flex', alignItems: 'center' }}>
              {leading}
            </div>
          )}
          <div style={{ flex: 1, minWidth: 0 }}>
            <h1 style={{
              fontSize: config.titleSize,
              fontWeight: config.titleWeight,
              letterSpacing: variant === 'minimal' ? '-0.03em' : '-0.02em',
              margin: 0,
              marginBottom: subtitle ? 4 : 0,
              color: titleColor,
              lineHeight: config.titleLineHeight,
            }}>
              {title}
            </h1>
            {subtitle && (
              <p style={{
                fontSize: config.subtitleSize,
                color: subtitleColor,
                margin: 0,
                maxWidth: variant === 'section' ? 560 : '100%',
              }}>
                {subtitle}
              </p>
            )}
          </div>
        </div>
        {actions && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: isMobile ? 'stretch' : 'flex-end',
            width: isMobile ? '100%' : 'auto',
            flexWrap: 'wrap',
            gap: spacing.sm,
          }}>
            {actions}
          </div>
        )}
      </div>
    </div>
  );
};

export default PageHeader;
