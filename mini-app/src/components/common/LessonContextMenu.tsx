import React, { useEffect, useRef } from 'react';
import { 
  CalendarOutlined, 
  CheckCircleOutlined, 
  CloseCircleOutlined, 
  DeleteOutlined 
} from '@ant-design/icons';
import { useThemeMode } from '../../theme/ThemeProvider';

interface LessonContextMenuProps {
  visible: boolean;
  position: { x: number; y: number };
  lessonId: number;
  onReschedule: () => void;
  onComplete: () => void;
  onCancel: () => void;
  onDelete: () => void;
  onClose: () => void;
}

const MENU_WIDTH = 180;
const MENU_ITEM_HEIGHT = 36;
const MENU_PADDING = 8;

/**
 * Context menu for lesson actions.
 * Triggered by right-click (desktop) or long-press (mobile).
 */
const LessonContextMenu: React.FC<LessonContextMenuProps> = ({
  visible,
  position,
  onReschedule,
  onComplete,
  onCancel,
  onDelete,
  onClose,
}) => {
  const { resolvedTheme } = useThemeMode();
  const isDark = resolvedTheme === 'dark';
  const menuRef = useRef<HTMLDivElement>(null);

  // Calculate adjusted position to keep menu within viewport
  const adjustedPosition = React.useMemo(() => {
    const menuHeight = (4 * MENU_ITEM_HEIGHT) + (2 * MENU_PADDING);
    let x = position.x;
    let y = position.y;

    // Adjust horizontal position
    if (x + MENU_WIDTH > window.innerWidth) {
      x = window.innerWidth - MENU_WIDTH - 8;
    }
    if (x < 8) {
      x = 8;
    }

    // Adjust vertical position
    if (y + menuHeight > window.innerHeight) {
      y = window.innerHeight - menuHeight - 8;
    }
    if (y < 8) {
      y = 8;
    }

    return { x, y };
  }, [position]);

  // Close on outside click
  useEffect(() => {
    if (!visible) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [visible, onClose]);

  if (!visible) return null;

  const menuItems = [
    { 
      icon: <CalendarOutlined />, 
      label: 'Reschedule', 
      onClick: onReschedule,
      color: '#1890ff',
    },
    { 
      icon: <CheckCircleOutlined />, 
      label: 'Mark as Completed', 
      onClick: onComplete,
      color: '#52c41a',
    },
    { 
      icon: <CloseCircleOutlined />, 
      label: 'Cancel Lesson', 
      onClick: onCancel,
      color: '#faad14',
    },
    { 
      icon: <DeleteOutlined />, 
      label: 'Delete', 
      onClick: onDelete,
      color: '#ff4d4f',
      danger: true,
    },
  ];

  return (
    <div
      ref={menuRef}
      style={{
        position: 'fixed',
        top: adjustedPosition.y,
        left: adjustedPosition.x,
        width: MENU_WIDTH,
        background: isDark ? '#1f1f1f' : '#ffffff',
        borderRadius: 8,
        boxShadow: isDark 
          ? '0 6px 16px rgba(0, 0, 0, 0.5)' 
          : '0 6px 16px rgba(0, 0, 0, 0.12)',
        padding: MENU_PADDING,
        zIndex: 1000,
      }}
    >
      {menuItems.map((item, index) => (
        <div
          key={index}
          onClick={() => {
            item.onClick();
            onClose();
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '8px 12px',
            borderRadius: 6,
            cursor: 'pointer',
            color: item.danger 
              ? '#ff4d4f' 
              : (isDark ? 'rgba(255,255,255,0.85)' : 'rgba(0,0,0,0.85)'),
            transition: 'background 0.15s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = isDark 
              ? 'rgba(255,255,255,0.08)' 
              : 'rgba(0,0,0,0.04)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
          }}
        >
          <span style={{ color: item.color, fontSize: 14 }}>
            {item.icon}
          </span>
          <span style={{ fontSize: 13 }}>
            {item.label}
          </span>
        </div>
      ))}
    </div>
  );
};

export default LessonContextMenu;
