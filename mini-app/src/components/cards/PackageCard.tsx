import React, { useState } from 'react';
import { Card, Progress, Typography } from 'antd';
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
  progress: PackageProgress;
}

interface PackageCardProps {
  package: Package;
  onClick?: () => void;
}

/**
 * Simplified package card with circular progress.
 * Shows: title (bold), learner name (light), circular progress with percentage.
 * No action buttons - all actions through detail page.
 */
const PackageCard: React.FC<PackageCardProps> = ({
  package: pkg,
  onClick,
}) => {
  const { resolvedTheme } = useThemeMode();
  const isDark = resolvedTheme === 'dark';
  const [isPressed, setIsPressed] = useState(false);

  const progress = pkg.progress || { total: 0, completed: 0, cancelled: 0 };
  const percent = progress.total > 0
    ? Math.round(((progress.completed + progress.cancelled) / progress.total) * 100)
    : 0;

  return (
    <Card
      hoverable
      style={{
        cursor: 'pointer',
        background: isDark ? '#1f1f1f' : '#ffffff',
        borderColor: isDark ? '#3a3a3a' : '#e8e8e8',
        transform: isPressed ? 'scale(0.98)' : 'scale(1)',
        transition: 'transform 0.1s ease-out',
      }}
      bodyStyle={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: spacing.md,
        gap: spacing.sm,
      }}
      onClick={onClick}
      onMouseDown={() => setIsPressed(true)}
      onMouseUp={() => setIsPressed(false)}
      onMouseLeave={() => setIsPressed(false)}
      onTouchStart={() => setIsPressed(true)}
      onTouchEnd={() => setIsPressed(false)}
    >
      <Progress
        type="circle"
        percent={percent}
        size={60}
        strokeColor="#0f7b6c"
        format={(p) => `${p}%`}
      />
      <Text
        strong
        style={{
          fontSize: 16,
          textAlign: 'center',
          lineHeight: 1.3,
        }}
        ellipsis={{ rows: 2 }}
      >
        {pkg.title}
      </Text>
      <Text
        type="secondary"
        style={{
          fontSize: 12,
          fontWeight: 300,
          textAlign: 'center',
        }}
        ellipsis
      >
        {pkg.learner_name}
      </Text>
    </Card>
  );
};

export default PackageCard;
