import React from 'react';
import { Modal, Drawer } from 'antd';
import type { ModalProps } from 'antd';
import { useResponsive } from '../../hooks/useResponsive';
import { spacing } from '../../theme/tokens';

export interface ResponsiveModalProps extends ModalProps {
  /** Use full-screen drawer on very small screens (< 480px). Default: true */
  mobileFullScreen?: boolean;
  /** Children content */
  children?: React.ReactNode;
}

/**
 * Responsive modal that adapts to screen size:
 * - Desktop (≥768px): Standard centered modal
 * - Mobile (< 768px): Full-width modal with 16px margin
 * - Very small (< 480px): Full-screen drawer (if mobileFullScreen is true)
 */
const ResponsiveModal: React.FC<ResponsiveModalProps> = ({
  mobileFullScreen = true,
  children,
  width,
  style,
  ...props
}) => {
  const { isMobile, breakpoint } = useResponsive();
  const isVerySmall = breakpoint === 'xs';

  // Very small screens: use full-screen drawer
  if (isMobile && isVerySmall && mobileFullScreen) {
    // Drawer footer only accepts ReactNode, not function
    const drawerFooter = typeof props.footer === 'function' ? undefined : props.footer;
    
    return (
      <Drawer
        open={props.open}
        onClose={props.onCancel as () => void}
        title={props.title}
        placement="bottom"
        height="100%"
        styles={{
          body: { padding: spacing.md },
          header: { padding: `${spacing.md}px ${spacing.md}px` },
        }}
        footer={drawerFooter}
        destroyOnClose={props.destroyOnClose}
        closable={props.closable}
        maskClosable={props.maskClosable}
      >
        {children}
      </Drawer>
    );
  }

  // Mobile: full-width with margin
  if (isMobile) {
    return (
      <Modal
        {...props}
        width="calc(100% - 32px)"
        style={{
          ...style,
          top: spacing.md,
          maxWidth: '100%',
          margin: '0 auto',
          paddingBottom: 0,
        }}
        styles={{
          ...props.styles,
          body: {
            ...props.styles?.body,
            maxHeight: 'calc(100vh - 200px)',
            overflowY: 'auto',
          },
        }}
      >
        {children}
      </Modal>
    );
  }

  // Desktop: standard modal
  return (
    <Modal
      {...props}
      width={width || 520}
      style={style}
    >
      {children}
    </Modal>
  );
};

export default ResponsiveModal;
