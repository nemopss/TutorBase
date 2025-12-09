import React from 'react';
import { Button } from 'antd';
import { useThemeMode } from '../../theme/ThemeProvider';

interface FloatingActionButtonProps {
  /** Icon to display in the button */
  icon: React.ReactNode;
  /** Click handler */
  onClick: () => void;
  /** Position of the FAB (default: bottom-right) */
  position?: 'bottom-right' | 'bottom-left';
}

/**
 * Floating Action Button component.
 * Fixed position button for primary actions.
 */
const FloatingActionButton: React.FC<FloatingActionButtonProps> = ({
  icon,
  onClick,
  position = 'bottom-right',
}) => {
  const { resolvedTheme } = useThemeMode();
  const isDark = resolvedTheme === 'dark';

  const positionStyles = position === 'bottom-right'
    ? { right: 24, left: 'auto' }
    : { left: 24, right: 'auto' };

  return (
    <Button
      type="primary"
      shape="circle"
      icon={icon}
      onClick={onClick}
      style={{
        position: 'fixed',
        bottom: 24,
        ...positionStyles,
        width: 56,
        height: 56,
        fontSize: 24,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        boxShadow: isDark
          ? '0 4px 12px rgba(0, 0, 0, 0.5)'
          : '0 4px 12px rgba(0, 0, 0, 0.15)',
      }}
    />
  );
};

export default FloatingActionButton;
