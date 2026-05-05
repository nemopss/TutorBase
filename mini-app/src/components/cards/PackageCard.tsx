import React, { useState } from 'react';
import { Dropdown, Progress, Typography } from 'antd';
import type { MenuProps } from 'antd';
import {
  CalendarOutlined,
  DeleteOutlined,
  DollarOutlined,
  EditOutlined,
  LoginOutlined,
  MoreOutlined,
  PlayCircleOutlined,
  StopOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import dayjs from 'dayjs';
import { useTheme } from '../../theme/ThemeProvider';
import { useResponsive } from '../../hooks/useResponsive';
import { spacing } from '../../theme/tokens';
import type { ThemeColors } from '../../theme/types';

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
  status: 'active' | 'completed' | 'cancelled' | 'draft';
  progress: PackageProgress;
  next_lesson_date?: string | null;
}

interface PackageCardProps {
  package: Package;
  onClick?: () => void;
  onAction?: (action: PackageCardAction, pkg: Package) => void;
  showStatus?: boolean;
}

export type PackageCardAction = 'open' | 'edit' | 'payment' | 'activate' | 'complete' | 'delete';

/**
 * Get badge color for package status
 */
export const getStatusBadgeColor = (status: string): string => {
  switch (status) {
    case 'active': return 'success';
    case 'completed': return 'primary';
    case 'draft': return 'warning';
    case 'cancelled': return 'error';
    default: return '#8c8c8c';
  }
};

const isPackageCardAction = (key: string): key is PackageCardAction => (
  ['open', 'edit', 'payment', 'activate', 'complete', 'delete'].includes(key)
);

const getStatusAccentColor = (status: string, colors: ThemeColors): string => {
  switch (status) {
    case 'active': return colors.accentSuccess;
    case 'completed': return colors.accentPrimary;
    case 'draft': return colors.accentWarning;
    case 'cancelled': return colors.accentError;
    default: return colors.borderPrimary;
  }
};

/**
 * Package card with new layout:
 * - Title + learner name on the left
 * - Progress ring on the right (no percentage)
 * - Lesson count + status badge
 * - Next lesson date (for active packages)
 */
const PackageCard: React.FC<PackageCardProps> = ({
  package: pkg,
  onClick,
  onAction,
  showStatus = false,
}) => {
  const { t } = useTranslation();
  const { resolvedTheme } = useTheme();
  const { isMobile } = useResponsive();
  const colors = resolvedTheme.colors;
  const [isHovered, setIsHovered] = useState(false);

  const progress = pkg.progress || { total: 0, completed: 0, cancelled: 0 };
  const done = progress.completed + progress.cancelled;
  const percent = progress.total > 0
    ? Math.round((done / progress.total) * 100)
    : 0;

  const isActive = pkg.status === 'active';
  const isDesktopHovered = isHovered && !isMobile;
  const statusColor = getStatusAccentColor(pkg.status, colors);
  const surfaceColor = isDesktopHovered
    ? `color-mix(in srgb, ${colors.bgTertiary} 82%, ${statusColor})`
    : colors.bgTertiary;
  const handleAction = (action: PackageCardAction) => {
    if (onAction) {
      onAction(action, pkg);
      return;
    }
    if (action === 'open') {
      onClick?.();
    }
  };

  const menuItems: MenuProps['items'] = [
    {
      key: 'open',
      icon: <LoginOutlined />,
      label: t('packageCard.actions.open'),
    },
    {
      key: 'edit',
      icon: <EditOutlined />,
      label: t('common.edit'),
    },
    {
      key: 'payment',
      icon: <DollarOutlined />,
      label: t('pages.finance.recordPayment'),
    },
    ...(pkg.status === 'active'
      ? [{
          key: 'complete',
          icon: <StopOutlined />,
          label: t('packageCard.actions.complete'),
        } as const]
      : [{
          key: 'activate',
          icon: <PlayCircleOutlined />,
          label: t('packageCard.actions.activate'),
        } as const]),
    {
      type: 'divider',
    },
    {
      key: 'delete',
      icon: <DeleteOutlined />,
      label: t('common.delete'),
      danger: true,
    },
  ];

  // Format lesson count
  const formatLessonCount = (): string => {
    return `${done}/${progress.total} ${t('pages.packages.lessons')}`;
  };

  // Format next lesson date
  const formatNextLessonDate = (dateStr?: string | null): string => {
    if (!dateStr) return t('packageCard.noScheduled');
    
    const formattedDate = dayjs(dateStr).format('D MMM');
    
    return t('packageCard.nextLesson', { date: formattedDate });
  };

  return (
    <div
      role="button"
      tabIndex={0}
      style={{
        cursor: 'pointer',
        background: surfaceColor,
        border: 0,
        borderRadius: 10,
        boxShadow: 'none',
        minHeight: 132,
        padding: spacing.md,
        transition: 'background 0.16s ease',
        outline: 'none',
      }}
      onClick={onClick}
      onKeyDown={(event) => {
        if ((event.key === 'Enter' || event.key === ' ') && onClick) {
          event.preventDefault();
          onClick();
        }
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: spacing.md }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <Text
            strong
            style={{
              fontSize: 16,
              lineHeight: 1.3,
              display: 'block',
            }}
            ellipsis
          >
            {pkg.title}
          </Text>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4, minWidth: 0 }}>
            <UserOutlined style={{ color: colors.textSecondary, fontSize: 12, flex: '0 0 auto' }} />
            <Text
              type="secondary"
              style={{
                fontSize: 12,
                display: 'block',
                minWidth: 0,
              }}
              ellipsis
            >
              {pkg.learner_name}
            </Text>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: spacing.xs, flex: '0 0 auto', paddingTop: 2 }}>
          {showStatus && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: statusColor,
                }}
              />
              <Text type="secondary" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
                {t(`pages.packages.status.${pkg.status}`)}
              </Text>
            </div>
          )}
          <Dropdown
            menu={{
              items: menuItems,
              onClick: ({ key, domEvent }) => {
                domEvent.stopPropagation();
                if (isPackageCardAction(key)) {
                  handleAction(key);
                }
              },
            }}
            trigger={['click']}
            placement="bottomRight"
          >
            <button
              type="button"
              aria-label={t('packageCard.actions.menu')}
              onClick={(event) => event.stopPropagation()}
              style={{
                width: 28,
                height: 28,
                border: 0,
                borderRadius: 8,
                background: 'transparent',
                color: colors.textSecondary,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <MoreOutlined />
            </button>
          </Dropdown>
        </div>
      </div>

      <div style={{ marginTop: spacing.md }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: spacing.sm, marginBottom: 6 }}>
          <Text type="secondary" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
            {t('pages.packages.progress')}
          </Text>
          <Text style={{ fontSize: 12, color: colors.textPrimary, whiteSpace: 'nowrap' }}>
            {formatLessonCount()}
          </Text>
        </div>
        <Progress
          percent={percent}
          showInfo={false}
          size="small"
          strokeColor={colors.accentPrimary}
          trailColor={colors.borderPrimary}
        />
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: spacing.sm, minWidth: 0 }}>
        <CalendarOutlined style={{ color: colors.textSecondary, fontSize: 12, flex: '0 0 auto' }} />
        {isActive ? (
          <Text 
            type="secondary" 
            style={{ fontSize: 12, display: 'block', minWidth: 0 }}
            ellipsis
          >
            {formatNextLessonDate(pkg.next_lesson_date)}
          </Text>
        ) : (
          <Text type="secondary" style={{ fontSize: 12 }}>
            {t('packageCard.noScheduled')}
          </Text>
        )}
      </div>
    </div>
  );
};

export default PackageCard;
