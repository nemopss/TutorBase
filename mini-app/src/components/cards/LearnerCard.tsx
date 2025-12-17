import React, { useState } from 'react';
import { Card, Typography, Dropdown, Tooltip, message } from 'antd';
import type { MenuProps } from 'antd';
import {
  BellOutlined,
  UserOutlined,
  MoreOutlined,
  EditOutlined,
  CopyOutlined,
  DeleteOutlined,
  CalendarOutlined,
  StopOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useTheme } from '../../theme/ThemeProvider';
import { spacing } from '../../theme/tokens';
import { formatNextLessonDate } from '../../utils/datetime';

const { Text } = Typography;

interface Learner {
  id: number;
  display_name: string;
  notifications_enabled: boolean;
  chat_id: number | null;
  next_lesson_date?: string | null;
}

interface LearnerCardProps {
  learner: Learner;
  onNotificationToggle: (learnerId: number, currentValue: boolean) => void;
  onEdit?: (learner: Learner) => void;
  onDelete?: (learnerId: number) => void;
  onClick?: (learner: Learner) => void;
  isToggling?: boolean;
}

const LearnerCard: React.FC<LearnerCardProps> = ({
  learner,
  onNotificationToggle,
  onEdit,
  onDelete,
  onClick,
  isToggling = false,
}) => {
  const { t } = useTranslation();
  const { resolvedTheme } = useTheme();
  const colors = resolvedTheme.colors;
  const [isPressed, setIsPressed] = useState(false);

  const handleCopyChatId = () => {
    if (learner.chat_id) {
      navigator.clipboard.writeText(String(learner.chat_id));
      message.success(t('common.chatIdCopied'));
    }
  };

  const menuItems: MenuProps['items'] = [
    ...(onEdit ? [{
      key: 'edit',
      icon: <EditOutlined />,
      label: t('common.edit'),
    }] : []),
    {
      key: 'copy',
      icon: <CopyOutlined />,
      label: t('common.copyChatId'),
      disabled: !learner.chat_id,
    },
    ...(onDelete ? [{
      key: 'delete',
      icon: <DeleteOutlined />,
      label: t('common.delete'),
      danger: true,
    }] : []),
  ];

  const handleMenuClick: MenuProps['onClick'] = (info) => {
    info.domEvent.stopPropagation();
    switch (info.key) {
      case 'edit':
        if (onEdit) onEdit(learner);
        break;
      case 'copy':
        handleCopyChatId();
        break;
      case 'delete':
        if (onDelete) onDelete(learner.id);
        break;
    }
  };

  const handleCardClick = () => {
    if (onClick) {
      onClick(learner);
    }
  };

  const handleNotificationClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!isToggling) {
      onNotificationToggle(learner.id, learner.notifications_enabled);
    }
  };

  const nextLessonText = formatNextLessonDate(learner.next_lesson_date, t);

  return (
    <Card
      hoverable
      style={{
        cursor: onClick ? 'pointer' : 'default',
        background: colors.bgSecondary,
        borderColor: colors.borderPrimary,
        transform: isPressed ? 'scale(0.98)' : 'scale(1)',
        transition: 'transform 0.1s ease-out',
      }}
      bodyStyle={{
        padding: spacing.md,
      }}
      onClick={handleCardClick}
      onMouseDown={() => setIsPressed(true)}
      onMouseUp={() => setIsPressed(false)}
      onMouseLeave={() => setIsPressed(false)}
      onTouchStart={() => setIsPressed(true)}
      onTouchEnd={() => setIsPressed(false)}
    >
      {/* Row 1: Name + Menu */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'flex-start',
        marginBottom: spacing.xs,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: spacing.xs, flex: 1, minWidth: 0 }}>
          <UserOutlined style={{ color: colors.textSecondary, fontSize: 16 }} />
          <Text
            strong
            style={{ fontSize: 15 }}
            ellipsis
          >
            {learner.display_name}
          </Text>
        </div>
        
        <Dropdown
          menu={{ items: menuItems, onClick: handleMenuClick }}
          trigger={['click']}
          placement="bottomRight"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              padding: 4,
              cursor: 'pointer',
              borderRadius: 4,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <MoreOutlined style={{ fontSize: 18, color: colors.textSecondary }} />
          </div>
        </Dropdown>
      </div>

      {/* Row 2: Next lesson date */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: spacing.xs,
        marginBottom: spacing.sm,
      }}>
        <CalendarOutlined style={{ color: colors.textTertiary, fontSize: 13 }} />
        <Text type="secondary" style={{ fontSize: 13 }}>
          {nextLessonText}
        </Text>
      </div>

      {/* Row 3: Notification toggle */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'flex-end',
        alignItems: 'center',
      }}>
        <Tooltip 
          title={learner.notifications_enabled 
            ? t('pages.learners.notificationsOn') 
            : t('pages.learners.notificationsOff')
          }
        >
          <div
            onClick={handleNotificationClick}
            style={{
              padding: 6,
              cursor: isToggling ? 'wait' : 'pointer',
              borderRadius: 4,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              opacity: isToggling ? 0.5 : 1,
            }}
          >
            {learner.notifications_enabled ? (
              <BellOutlined style={{ fontSize: 18, color: colors.textSecondary }} />
            ) : (
              <span style={{ position: 'relative', display: 'inline-flex' }}>
                <BellOutlined style={{ fontSize: 18, color: colors.textTertiary }} />
                <StopOutlined 
                  style={{ 
                    fontSize: 10, 
                    color: colors.textTertiary,
                    position: 'absolute',
                    bottom: -2,
                    right: -2,
                  }} 
                />
              </span>
            )}
          </div>
        </Tooltip>
      </div>
    </Card>
  );
};

export default LearnerCard;
