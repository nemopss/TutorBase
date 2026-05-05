import React, { useState } from 'react';
import { Typography, Dropdown, Tooltip, message } from 'antd';
import type { MenuProps } from 'antd';
import {
  BellOutlined,
  UserOutlined,
  MoreOutlined,
  EditOutlined,
  CopyOutlined,
  DeleteOutlined,
  CalendarOutlined,
  DollarOutlined,
  StopOutlined,
  DisconnectOutlined,
  LinkOutlined,
  InboxOutlined,
  RollbackOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useTheme } from '../../theme/ThemeProvider';
import { spacing } from '../../theme/tokens';
import { formatNextLessonDate } from '../../utils/datetime';
import { useResponsive } from '../../hooks/useResponsive';

const { Text } = Typography;

interface Learner {
  id: number;
  display_name: string;
  notifications_enabled: boolean;
  chat_id: number | null;
  lesson_rate?: number | null;
  next_lesson_date?: string | null;
  is_archived?: boolean;
}

interface LearnerCardProps {
  learner: Learner;
  onNotificationToggle: (learnerId: number, currentValue: boolean) => void;
  onEdit?: (learner: Learner) => void;
  onDelete?: (learnerId: number) => void;
  onCreateInvite?: (learner: Learner) => void;
  onUnlinkAccount?: (learner: Learner) => void;
  onArchive?: (learner: Learner) => void;
  onRestore?: (learner: Learner) => void;
  onClick?: (learner: Learner) => void;
  isToggling?: boolean;
  notificationsGloballyAllowed?: boolean;
}

const LearnerCard: React.FC<LearnerCardProps> = ({
  learner,
  onNotificationToggle,
  onEdit,
  onDelete,
  onCreateInvite,
  onUnlinkAccount,
  onArchive,
  onRestore,
  onClick,
  isToggling = false,
  notificationsGloballyAllowed = true,
}) => {
  const { t } = useTranslation();
  const { resolvedTheme } = useTheme();
  const { isMobile } = useResponsive();
  const colors = resolvedTheme.colors;
  const [isHovered, setIsHovered] = useState(false);

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
    ...(!learner.is_archived && !learner.chat_id && onCreateInvite ? [{
      key: 'createInvite',
      icon: <LinkOutlined />,
      label: t('learnerProfile.createInviteAction'),
    }] : []),
    ...(!learner.is_archived && learner.chat_id && onUnlinkAccount ? [{
      key: 'unlinkAccount',
      icon: <DisconnectOutlined />,
      label: t('learnerProfile.unlinkAccountAction'),
      danger: true,
    }] : []),
    ...(!learner.is_archived && onArchive ? [{
      key: 'archive',
      icon: <InboxOutlined />,
      label: t('pages.learners.archiveAction', { defaultValue: 'Архивировать' }),
      danger: true,
    }] : []),
    ...(learner.is_archived && onRestore ? [{
      key: 'restore',
      icon: <RollbackOutlined />,
      label: t('pages.learners.restoreAction', { defaultValue: 'Вернуть из архива' }),
    }] : []),
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
      case 'createInvite':
        if (onCreateInvite) onCreateInvite(learner);
        break;
      case 'unlinkAccount':
        if (onUnlinkAccount) onUnlinkAccount(learner);
        break;
      case 'archive':
        if (onArchive) onArchive(learner);
        break;
      case 'restore':
        if (onRestore) onRestore(learner);
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
    if (!isToggling && !learner.is_archived && notificationsGloballyAllowed) {
      onNotificationToggle(learner.id, learner.notifications_enabled);
    }
  };

  const nextLessonText = formatNextLessonDate(learner.next_lesson_date, t);
  const isDesktopHovered = isHovered && !isMobile;
  const surfaceColor = isDesktopHovered
    ? `color-mix(in srgb, ${colors.bgTertiary} 82%, ${colors.accentPrimary})`
    : colors.bgTertiary;
  const isNotificationDisabled = learner.is_archived || !notificationsGloballyAllowed;
  const formatCurrency = (value: number): string => new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
  const statusPillStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    minHeight: 26,
    padding: '4px 8px',
    borderRadius: 10,
    background: colors.bgSecondary,
    color: colors.textSecondary,
    fontSize: 12,
    lineHeight: 1.2,
    whiteSpace: 'nowrap',
  };

  return (
    <div
      role="button"
      tabIndex={0}
      style={{
        cursor: onClick ? 'pointer' : 'default',
        background: surfaceColor,
        border: 0,
        borderRadius: 10,
        boxShadow: 'none',
        minHeight: 136,
        padding: spacing.md,
        transition: 'background 0.16s ease',
        outline: 'none',
      }}
      onClick={handleCardClick}
      onKeyDown={(event) => {
        if ((event.key === 'Enter' || event.key === ' ') && onClick) {
          event.preventDefault();
          handleCardClick();
        }
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
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
            style={{ fontSize: 16, lineHeight: 1.3 }}
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
          <button
            type="button"
            aria-label={t('packageCard.actions.menu')}
            onClick={(e) => e.stopPropagation()}
            style={{
              width: 28,
              height: 28,
              border: 0,
              cursor: 'pointer',
              borderRadius: 8,
              background: 'transparent',
              color: colors.textSecondary,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <MoreOutlined />
          </button>
        </Dropdown>
      </div>

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

      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: spacing.sm,
        flexWrap: 'wrap',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: spacing.xs, flexWrap: 'wrap', minWidth: 0 }}>
          <span style={statusPillStyle}>
            <LinkOutlined style={{ fontSize: 12 }} />
            {learner.chat_id
              ? t('pages.learners.telegramLinked', { defaultValue: 'Telegram' })
              : t('pages.learners.telegramNotLinked', { defaultValue: 'Без Telegram' })}
          </span>
          {learner.lesson_rate ? (
            <span style={statusPillStyle}>
              <DollarOutlined style={{ fontSize: 12 }} />
              {formatCurrency(learner.lesson_rate)}
            </span>
          ) : null}
          {learner.is_archived ? (
            <span style={statusPillStyle}>
              <InboxOutlined style={{ fontSize: 12 }} />
              {t('pages.learners.archivedTab', { defaultValue: 'Архив' })}
            </span>
          ) : null}
        </div>
        <Tooltip 
          title={learner.is_archived
            ? t('pages.learners.archivedNotificationsOff', { defaultValue: 'У архивного ученика уведомления отключены' })
            : !notificationsGloballyAllowed
            ? t('pages.learners.notificationsBillingDisabled', { defaultValue: 'Уведомления отключены до продления подписки' })
            : learner.notifications_enabled
            ? t('pages.learners.notificationsOn') 
            : t('pages.learners.notificationsOff')
          }
        >
          <div
            onClick={handleNotificationClick}
            style={{
              padding: 6,
              cursor: isToggling ? 'wait' : isNotificationDisabled ? 'not-allowed' : 'pointer',
              borderRadius: 8,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              opacity: isToggling || !notificationsGloballyAllowed ? 0.5 : 1,
              background: colors.bgSecondary,
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
    </div>
  );
};

export default LearnerCard;
