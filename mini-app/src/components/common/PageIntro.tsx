import React from 'react';
import { Typography } from 'antd';
import { useResponsive } from '../../hooks/useResponsive';
import { useResponsiveStyles } from '../../hooks/useResponsiveStyles';
import { spacing } from '../../theme/tokens';

const { Title, Text } = Typography;

interface PageIntroProps {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  action?: React.ReactNode;
  marginBottom?: number;
}

const PageIntro: React.FC<PageIntroProps> = ({
  title,
  subtitle,
  action,
  marginBottom = spacing.lg,
}) => {
  const { isMobile } = useResponsive();
  const { subtitleColor } = useResponsiveStyles();

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: isMobile ? 'column' : 'row',
        alignItems: isMobile ? 'stretch' : 'flex-start',
        justifyContent: 'space-between',
        gap: spacing.md,
        marginBottom,
      }}
    >
      <div style={{ minWidth: 0 }}>
        <Title level={3} style={{ margin: 0 }}>
          {title}
        </Title>
        {subtitle ? (
          <Text style={{ color: subtitleColor, display: 'block', marginTop: spacing.xs }}>
            {subtitle}
          </Text>
        ) : null}
      </div>
      {action ? <div style={{ flexShrink: 0 }}>{action}</div> : null}
    </div>
  );
};

export default PageIntro;
