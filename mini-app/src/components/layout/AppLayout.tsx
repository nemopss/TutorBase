import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Layout, Menu, Drawer, Button, Space, Tag, Typography, type MenuProps } from 'antd';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  HomeOutlined,
  AppstoreOutlined,
  BellOutlined,
  BarChartOutlined,
  SettingOutlined,
  CalendarOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  TeamOutlined,
  CrownOutlined,
  DollarOutlined,
  CloseOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useTheme } from '../../theme/ThemeProvider';
import { useAuth } from '../../auth/AuthProvider';
import { useResponsive } from '../../hooks/useResponsive';
import TenantIndicator from '../common/TenantIndicator';
import TenantSwitcher from '../common/TenantSwitcher';

const { Sider, Content } = Layout;
const { Text } = Typography;

interface AppLayoutProps {
  children: React.ReactNode;
}

interface MobileNavItem {
  key: string;
  label: string;
  icon: React.ReactNode;
}

const SIDEBAR_COLLAPSED_KEY = 'tutorbase_sidebar_collapsed';
const MOBILE_NAV_BOTTOM = 'calc(16px + env(safe-area-inset-bottom, 0px))';
const MOBILE_CONTENT_BOTTOM = 'calc(112px + env(safe-area-inset-bottom, 0px))';
const MOBILE_NAV_GAP = 8;
const MOBILE_NAV_PADDING = 10;
const MORE_SHEET_CLOSE_THRESHOLD = 84;
const MORE_BUTTON_WIDTH = 80;
const MORE_SHEET_CLOSE_OFFSET = 220;
const MORE_SHEET_CLOSE_ANIMATION_MS = 260;
const MORE_SHEET_RETURN_ANIMATION_MS = 220;

const isFinanceRoute = (pathname: string) => (
  pathname.startsWith('/finance') || /^\/learners\/[^/]+\/finance$/.test(pathname)
);

const matchesNavItem = (pathname: string, key: string) => {
  switch (key) {
    case '/':
      return pathname === '/';
    case '/lessons':
      return pathname === '/lessons';
    case '/learners':
      return pathname === '/learners' || pathname.startsWith('/learners/');
    case '/finance/dashboard':
      return isFinanceRoute(pathname);
    case '/schedule':
      return pathname === '/schedule';
    case '/settings':
      return pathname === '/settings';
    default:
      return pathname === key || pathname.startsWith(`${key}/`);
  }
};

const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const { resolvedTheme } = useTheme();
  const { isMobile } = useResponsive();
  const isDark = resolvedTheme.colorScheme === 'dark';
  const colors = resolvedTheme.colors;
  const [moreSheetOpen, setMoreSheetOpen] = useState(false);
  const [sheetDragOffset, setSheetDragOffset] = useState(0);
  const [isSheetClosing, setIsSheetClosing] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    const saved = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
    return saved === 'true';
  });
  const sheetTouchStartY = useRef<number | null>(null);
  const sheetDragOffsetRef = useRef(0);
  const sheetCloseTimerRef = useRef<number | null>(null);
  const { user, isSuperAdmin, tenantAccess, canSwitchTenant } = useAuth();
  const hasStaffAccess = isSuperAdmin || user?.role === 'teacher';
  const isStudent = user?.role === 'viewer';
  const isTutorDashboardRoute = hasStaffAccess && !isStudent && location.pathname === '/';
  const shellRadius = '10px';
  const accessUntil = tenantAccess?.access_until ? new Date(tenantAccess.access_until) : null;
  const accessDaysLeft = accessUntil
    ? Math.ceil((accessUntil.getTime() - Date.now()) / (1000 * 60 * 60 * 24))
    : null;
  const shouldShowAccessWarning = hasStaffAccess && !isStudent && (
    tenantAccess?.status === 'grace' ||
    ((tenantAccess?.status === 'trial' || tenantAccess?.status === 'active') &&
      accessDaysLeft !== null &&
      accessDaysLeft <= 3)
  );
  const accessWarningMessage = tenantAccess?.status === 'grace'
    ? 'Идёт grace-период доступа'
    : 'Доступ скоро закончится';
  const accessWarningDescription = tenantAccess?.status === 'grace'
    ? 'Можно продолжать важное обслуживание кабинета, но доступ нужно продлить.'
    : accessDaysLeft !== null
      ? `Осталось дней: ${Math.max(accessDaysLeft, 0)}. Продлите доступ заранее.`
      : 'Продлите доступ заранее.';

  const handleSidebarCollapse = (collapsed: boolean) => {
    setSidebarCollapsed(collapsed);
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(collapsed));
  };

  const isSidebarCompact = !isMobile && sidebarCollapsed;
  const sidebarWidth = sidebarCollapsed ? 80 : 240;

  const baseMenuItems: NonNullable<MenuProps['items']> = useMemo(() => [
    {
      key: '/',
      icon: <HomeOutlined />,
      label: <Link to="/">{t('navigation.dashboard')}</Link>,
    },
    {
      key: '/packages',
      icon: <AppstoreOutlined />,
      label: <Link to="/packages">{t('navigation.packages')}</Link>,
    },
    {
      key: '/lessons',
      icon: <CalendarOutlined />,
      label: <Link to="/lessons">{t('navigation.lessons')}</Link>,
    },
    {
      key: '/learners',
      icon: <TeamOutlined />,
      label: <Link to="/learners">{t('navigation.learners')}</Link>,
    },
    {
      key: 'finance',
      icon: <DollarOutlined />,
      label: t('navigation.finance'),
      children: [
        {
          key: '/finance/dashboard',
          label: <Link to="/finance/dashboard">{t('navigation.dashboard')}</Link>,
        },
        {
          key: '/finance/reports',
          label: <Link to="/finance/reports">{t('navigation.analytics')}</Link>,
        },
      ],
    },
    ...(isSuperAdmin ? [{
      key: '/reminders',
      icon: <BellOutlined />,
      label: (
        <Space size={6}>
          <Link to="/reminders">{t('navigation.reminders')}</Link>
          <Tag color="warning" style={{ marginInlineEnd: 0 }}>{t('navigation.legacyBadge')}</Tag>
        </Space>
      ),
    }] : []),
    {
      key: '/notifications',
      icon: <BellOutlined />,
      label: isSuperAdmin ? (
        <Space size={6}>
          <Link to="/notifications">{t('navigation.notifications')}</Link>
          <Tag color="green" style={{ marginInlineEnd: 0 }}>{t('navigation.newBadge')}</Tag>
        </Space>
      ) : <Link to="/notifications">{t('navigation.notifications')}</Link>,
    },
    {
      key: '/groups',
      icon: <TeamOutlined />,
      label: <Link to="/groups">{t('navigation.groups')}</Link>,
    },
    {
      key: '/analytics',
      icon: <BarChartOutlined />,
      label: <Link to="/analytics">{t('navigation.analytics')}</Link>,
    },
  ], [isSuperAdmin, t]);

  const studentMenuItems: NonNullable<MenuProps['items']> = useMemo(() => [
    {
      key: '/',
      icon: <HomeOutlined />,
      label: <Link to="/">{t('navigation.dashboard')}</Link>,
    },
    {
      key: '/schedule',
      icon: <CalendarOutlined />,
      label: <Link to="/schedule">{t('navigation.schedule')}</Link>,
    },
  ], [t]);

  const adminMenuItem: NonNullable<MenuProps['items']>[number] = useMemo(() => ({
    key: '/platform',
    icon: <CrownOutlined />,
    label: (
      <Space size={6}>
        <Link to="/platform">{t('navigation.console', 'Консоль')}</Link>
        <Tag color="gold" style={{ marginInlineEnd: 0 }}>{t('navigation.ndaBadge', 'NDA')}</Tag>
      </Space>
    ),
  }), [t]);

  const settingsMenuItem: NonNullable<MenuProps['items']>[number] = useMemo(() => ({
    key: '/settings',
    icon: <SettingOutlined />,
    label: <Link to="/settings">{t('navigation.settings')}</Link>,
  }), [t]);

  const mainMenuItems = useMemo<NonNullable<MenuProps['items']>>(() => {
    if (isStudent) {
      return studentMenuItems;
    }

    return [...baseMenuItems];
  }, [isStudent, baseMenuItems, studentMenuItems]);

  const footerMenuItems = useMemo<NonNullable<MenuProps['items']>>(() => {
    const items: NonNullable<MenuProps['items']> = [settingsMenuItem];

    if (isSuperAdmin) {
      items.push(adminMenuItem);
    }

    return items;
  }, [isSuperAdmin, settingsMenuItem, adminMenuItem]);

  const mobilePrimaryNavItems = useMemo<MobileNavItem[]>(() => {
    if (isStudent) {
      return [
        { key: '/', label: t('navigation.dashboard'), icon: <HomeOutlined /> },
        { key: '/schedule', label: t('navigation.schedule'), icon: <CalendarOutlined /> },
        { key: '/settings', label: t('navigation.settings'), icon: <SettingOutlined /> },
      ];
    }

    return [
      { key: '/', label: t('navigation.dashboard'), icon: <HomeOutlined /> },
      { key: '/lessons', label: t('navigation.lessons'), icon: <CalendarOutlined /> },
      { key: '/learners', label: t('navigation.learners'), icon: <TeamOutlined /> },
      { key: '/finance/dashboard', label: t('navigation.finance'), icon: <DollarOutlined /> },
    ];
  }, [isStudent, t]);

  const mobileMoreItems = useMemo(() => {
    if (isStudent) {
      return [];
    }

    return [
      {
        key: '/packages',
        label: t('navigation.packages'),
        icon: <AppstoreOutlined />,
      },
      {
        key: '/notifications',
        label: t('navigation.notifications'),
        icon: <BellOutlined />,
        badge: isSuperAdmin ? (
          <Tag color="green" style={{ marginInlineEnd: 0 }}>{t('navigation.newBadge')}</Tag>
        ) : null,
      },
      ...(isSuperAdmin ? [{
        key: '/reminders',
        label: t('navigation.reminders'),
        icon: <BellOutlined />,
        badge: <Tag color="warning" style={{ marginInlineEnd: 0 }}>{t('navigation.legacyBadge')}</Tag>,
      }] : []),
      {
        key: '/groups',
        label: t('navigation.groups'),
        icon: <TeamOutlined />,
      },
      {
        key: '/analytics',
        label: t('navigation.analytics'),
        icon: <BarChartOutlined />,
      },
      {
        key: '/settings',
        label: t('navigation.settings'),
        icon: <SettingOutlined />,
      },
      ...(isSuperAdmin ? [{
        key: '/platform',
        label: t('navigation.console', 'Консоль'),
        icon: <CrownOutlined />,
        badge: <Tag color="gold" style={{ marginInlineEnd: 0 }}>{t('navigation.ndaBadge', 'NDA')}</Tag>,
      }] : []),
    ];
  }, [isSuperAdmin, isStudent, t]);

  const activePrimaryKey = useMemo<string | null>(() => {
    const matchedItem = mobilePrimaryNavItems.find((item) => (
      matchesNavItem(location.pathname, item.key)
    ));

    if (matchedItem) {
      return matchedItem.key;
    }

    return isStudent ? (mobilePrimaryNavItems[0]?.key ?? '/') : null;
  }, [isStudent, location.pathname, mobilePrimaryNavItems]);

  const activePrimaryIndex = useMemo(() => {
    if (activePrimaryKey === null) {
      return -1;
    }

    const index = mobilePrimaryNavItems.findIndex((item) => item.key === activePrimaryKey);
    return index >= 0 ? index : -1;
  }, [activePrimaryKey, mobilePrimaryNavItems]);

  useEffect(() => () => {
    if (sheetCloseTimerRef.current !== null) {
      window.clearTimeout(sheetCloseTimerRef.current);
    }
  }, []);

  const resetMoreSheetState = () => {
    if (sheetCloseTimerRef.current !== null) {
      window.clearTimeout(sheetCloseTimerRef.current);
      sheetCloseTimerRef.current = null;
    }
    sheetTouchStartY.current = null;
    sheetDragOffsetRef.current = 0;
    setIsSheetClosing(false);
    setSheetDragOffset(0);
  };

  const openMoreSheet = () => {
    resetMoreSheetState();
    setMoreSheetOpen(true);
  };

  const closeMoreSheet = () => {
    resetMoreSheetState();
    setMoreSheetOpen(false);
  };

  const triggerMoreSheetCloseAnimation = () => {
    if (isSheetClosing) {
      return;
    }

    sheetTouchStartY.current = null;
    setIsSheetClosing(true);
    const closeOffset = typeof window !== 'undefined'
      ? Math.max(
        window.innerHeight + 32,
        sheetDragOffsetRef.current + 32,
        MORE_SHEET_CLOSE_OFFSET,
      )
      : MORE_SHEET_CLOSE_OFFSET;
    sheetDragOffsetRef.current = closeOffset;
    setSheetDragOffset(closeOffset);
    sheetCloseTimerRef.current = window.setTimeout(() => {
      setMoreSheetOpen(false);
      sheetCloseTimerRef.current = null;
    }, MORE_SHEET_CLOSE_ANIMATION_MS);
  };

  const handleMoreSheetTouchStart = (event: React.TouchEvent<HTMLDivElement>) => {
    if (isSheetClosing) {
      return;
    }

    sheetTouchStartY.current = event.touches[0]?.clientY ?? null;
  };

  const handleMoreSheetTouchMove = (event: React.TouchEvent<HTMLDivElement>) => {
    if (sheetTouchStartY.current === null || isSheetClosing) {
      return;
    }

    const currentY = event.touches[0]?.clientY ?? sheetTouchStartY.current;
    const maxDrag = typeof window !== 'undefined' ? window.innerHeight : Number.MAX_SAFE_INTEGER;
    const nextOffset = Math.max(0, Math.min(currentY - sheetTouchStartY.current, maxDrag));
    sheetDragOffsetRef.current = nextOffset;
    setSheetDragOffset(nextOffset);
  };

  const handleMoreSheetTouchEnd = () => {
    if (isSheetClosing) {
      return;
    }

    const shouldClose = sheetDragOffsetRef.current >= MORE_SHEET_CLOSE_THRESHOLD;
    sheetTouchStartY.current = null;
    if (shouldClose) {
      triggerMoreSheetCloseAnimation();
      return;
    }

    sheetDragOffsetRef.current = 0;
    setSheetDragOffset(0);
  };

  const handleMobilePrimaryAction = (item: MobileNavItem) => {
    closeMoreSheet();
    if (!matchesNavItem(location.pathname, item.key)) {
      navigate(item.key);
    }
  };

  const handleMobileMoreNavigation = (key: string) => {
    closeMoreSheet();

    if (!matchesNavItem(location.pathname, key)) {
      navigate(key);
    }
  };

  const menuContent = (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div style={{
        padding: isSidebarCompact ? '16px 10px' : '16px',
        minHeight: '64px',
        fontWeight: 600,
        color: colors.textPrimary,
        borderBottom: `1px solid ${colors.borderPrimary}`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: isSidebarCompact ? 'center' : 'space-between',
        gap: '8px',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
      }}>
        <span style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: isSidebarCompact ? 'center' : 'flex-start',
          gap: '8px',
          minWidth: 0,
          fontSize: '18px',
        }}>
          <span aria-hidden="true">📚</span>
          {!isSidebarCompact && <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>TutorBase</span>}
        </span>

        {!isMobile && (
          <Button
            type="text"
            size="small"
            aria-label={sidebarCollapsed ? t('navigation.expandSidebar', 'Expand sidebar') : t('navigation.collapseSidebar', 'Collapse sidebar')}
            icon={sidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => handleSidebarCollapse(!sidebarCollapsed)}
            style={{
              flex: '0 0 auto',
              width: 32,
              height: 32,
              minWidth: 32,
              padding: 0,
              color: colors.textSecondary,
            }}
          />
        )}
      </div>

      <div style={{ flex: 1, minHeight: 0, overflow: 'auto', paddingTop: '8px' }}>
        <Menu
          selectedKeys={[location.pathname]}
          mode="inline"
          inlineCollapsed={isSidebarCompact}
          items={mainMenuItems}
          style={{
            background: 'transparent',
            border: 'none',
            fontSize: '14px',
            color: colors.textPrimary,
          }}
        />
      </div>

      <div style={{
        flex: '0 0 auto',
        borderTop: `1px solid ${colors.borderPrimary}`,
        padding: '8px 0',
        background: colors.bgSecondary,
      }}>
        <Menu
          selectedKeys={[location.pathname]}
          mode="inline"
          inlineCollapsed={isSidebarCompact}
          items={footerMenuItems}
          style={{
            background: 'transparent',
            border: 'none',
            fontSize: '14px',
            color: colors.textPrimary,
          }}
        />

        {isSuperAdmin && !isSidebarCompact && (
          <div style={{
            margin: '8px 16px 0',
            paddingTop: '12px',
            borderTop: `1px solid ${colors.borderPrimary}`,
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
          }}>
            <TenantIndicator />
          </div>
        )}
      </div>
    </div>
  );

  const navGlassBackground = isDark ? 'rgba(18, 18, 18, 0.72)' : 'rgba(255, 255, 255, 0.72)';
  const isMoreButtonActive = !isStudent && (moreSheetOpen || activePrimaryKey === null);

  const mobileBottomNav = isMobile ? (
    <div style={{
      position: 'fixed',
      left: 12,
      right: 12,
      bottom: MOBILE_NAV_BOTTOM,
      zIndex: 1200,
      pointerEvents: 'none',
    }}>
      <div style={{
        pointerEvents: 'auto',
        maxWidth: isStudent ? 420 : 640,
        margin: '0 auto',
        display: 'flex',
        alignItems: 'stretch',
        gap: 10,
      }}>
        <div style={{
          flex: 1,
          padding: 10,
          borderRadius: 999,
          background: navGlassBackground,
          border: 'none',
          backdropFilter: 'blur(28px) saturate(1.12)',
          WebkitBackdropFilter: 'blur(28px) saturate(1.12)',
          position: 'relative',
          display: 'grid',
          gridTemplateColumns: `repeat(${mobilePrimaryNavItems.length}, minmax(0, 1fr))`,
          gap: MOBILE_NAV_GAP,
        }}>
          {activePrimaryIndex >= 0 && (
            <div style={{
              position: 'absolute',
              top: MOBILE_NAV_PADDING,
              bottom: MOBILE_NAV_PADDING,
              left: MOBILE_NAV_PADDING,
              width: `calc((100% - ${MOBILE_NAV_PADDING * 2}px - ${(mobilePrimaryNavItems.length - 1) * MOBILE_NAV_GAP}px) / ${mobilePrimaryNavItems.length})`,
              borderRadius: 999,
              background: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(35, 131, 226, 0.12)',
              transform: `translateX(calc(${activePrimaryIndex} * (100% + ${MOBILE_NAV_GAP}px)))`,
              transition: 'transform 520ms cubic-bezier(0.22, 1, 0.36, 1)',
              pointerEvents: 'none',
            }} />
          )}
          {mobilePrimaryNavItems.map((item) => {
            const isActive = activePrimaryKey === item.key;

            return (
              <button
                key={item.key}
                type="button"
                onClick={() => handleMobilePrimaryAction(item)}
                style={{
                  all: 'unset',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 6,
                  minHeight: 60,
                  borderRadius: 999,
                  cursor: 'pointer',
                  background: 'transparent',
                  color: isActive ? colors.textPrimary : colors.textSecondary,
                  transform: isActive ? 'translateY(-1px)' : 'translateY(0)',
                  transition: [
                    'color 320ms cubic-bezier(0.22, 1, 0.36, 1)',
                    'transform 420ms cubic-bezier(0.22, 1, 0.36, 1)',
                  ].join(', '),
                  position: 'relative',
                  zIndex: 1,
                }}
              >
                <span style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 18,
                  transform: isActive ? 'scale(1.06)' : 'scale(1)',
                  transition: 'transform 420ms cubic-bezier(0.22, 1, 0.36, 1)',
                }}>
                  {item.icon}
                </span>
                <span style={{
                  fontSize: 11,
                  lineHeight: 1,
                  fontWeight: isActive ? 600 : 500,
                  letterSpacing: '-0.01em',
                  transition: 'font-weight 320ms cubic-bezier(0.22, 1, 0.36, 1)',
                }}>
                  {item.label}
                </span>
              </button>
            );
          })}
        </div>

        {!isStudent && (
          <button
            type="button"
            onClick={openMoreSheet}
            style={{
              all: 'unset',
              width: MORE_BUTTON_WIDTH,
              flex: `0 0 ${MORE_BUTTON_WIDTH}px`,
              borderRadius: 999,
              background: navGlassBackground,
              border: 'none',
              backdropFilter: 'blur(28px) saturate(1.12)',
              WebkitBackdropFilter: 'blur(28px) saturate(1.12)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
              minHeight: 80,
              cursor: 'pointer',
              color: isMoreButtonActive ? colors.textPrimary : colors.textSecondary,
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            <div style={{
              position: 'absolute',
              inset: 8,
              borderRadius: 999,
              background: isMoreButtonActive
                ? (isDark ? 'rgba(255,255,255,0.1)' : 'rgba(35, 131, 226, 0.12)')
                : 'transparent',
              transition: 'background-color 420ms cubic-bezier(0.22, 1, 0.36, 1)',
            }} />
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 18,
              position: 'relative',
              zIndex: 1,
            }}>
              <AppstoreOutlined />
            </span>
            <span style={{
              fontSize: 11,
              lineHeight: 1,
              fontWeight: 600,
              letterSpacing: '-0.01em',
              position: 'relative',
              zIndex: 1,
            }}>
              {t('navigation.more', 'Ещё')}
            </span>
          </button>
        )}
      </div>
    </div>
  ) : null;

  return (
    <>
      <Layout style={{
        minHeight: '100vh',
        height: isMobile ? undefined : '100vh',
        background: colors.bgPrimary,
        padding: isMobile ? 0 : '24px',
        boxSizing: 'border-box',
        overflow: isMobile ? undefined : 'hidden',
        display: 'flex',
        flexDirection: isMobile ? 'column' : 'row',
        gap: isMobile ? 0 : '24px',
      }}>
        {!isMobile && (
          <Sider
            collapsible
            collapsed={sidebarCollapsed}
            onCollapse={handleSidebarCollapse}
            width={240}
            collapsedWidth={80}
            style={{
              background: colors.bgSecondary,
              borderRadius: shellRadius,
              overflow: 'hidden',
              height: '100%',
              flex: `0 0 ${sidebarWidth}px`,
              minWidth: sidebarWidth,
              maxWidth: sidebarWidth,
              boxSizing: 'border-box',
            }}
            trigger={null}
            theme={isDark ? 'dark' : 'light'}
          >
            {menuContent}
          </Sider>
        )}

        <Layout style={{
          flex: 1,
          minWidth: 0,
          height: isMobile ? undefined : '100%',
          background: colors.bgPrimary,
          transition: 'all 0.2s',
        }}>
          <Content style={{
            margin: isMobile ? '16px 16px 0' : 0,
            padding: isMobile ? 0 : (isTutorDashboardRoute ? 0 : '32px'),
            paddingBottom: isMobile ? MOBILE_CONTENT_BOTTOM : undefined,
            background: isMobile
              ? 'transparent'
              : (isTutorDashboardRoute ? 'transparent' : colors.bgSecondary),
            minHeight: isMobile ? 'calc(100dvh - 140px)' : 0,
            height: isMobile ? undefined : '100%',
            borderRadius: isMobile ? 0 : (isTutorDashboardRoute ? 0 : shellRadius),
            overflow: isMobile ? 'visible' : 'auto',
            boxSizing: 'border-box',
          }}>
            {shouldShowAccessWarning && (
              <Alert
                type={tenantAccess?.status === 'grace' ? 'warning' : 'info'}
                showIcon
                message={accessWarningMessage}
                description={accessWarningDescription}
                style={{ marginBottom: 16 }}
              />
            )}
            {children}
          </Content>
        </Layout>
      </Layout>

      {mobileBottomNav}

      {isMobile && !isStudent && (
        <Drawer
          placement="bottom"
          open={moreSheetOpen}
          onClose={closeMoreSheet}
          afterOpenChange={(open) => {
            if (!open) {
              resetMoreSheetState();
            }
          }}
          height="calc(100dvh - 24px)"
          closable={false}
          styles={{
            wrapper: {
              transform: `translateY(${sheetDragOffset}px)`,
              transition: isSheetClosing
                ? `transform ${MORE_SHEET_CLOSE_ANIMATION_MS}ms cubic-bezier(0.22, 0.61, 0.36, 1)`
                : sheetTouchStartY.current === null
                  ? `transform ${MORE_SHEET_RETURN_ANIMATION_MS}ms cubic-bezier(0.22, 0.61, 0.36, 1)`
                  : 'none',
            },
            content: {
              borderRadius: '28px 28px 0 0',
              overflow: 'hidden',
              background: colors.bgPrimary,
            },
            body: {
              padding: 0,
              background: colors.bgPrimary,
            },
          }}
        >
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            height: '100%',
          }}>
            <div
              onTouchStart={handleMoreSheetTouchStart}
              onTouchMove={handleMoreSheetTouchMove}
              onTouchEnd={handleMoreSheetTouchEnd}
              onTouchCancel={handleMoreSheetTouchEnd}
              style={{ touchAction: 'none' }}
            >
              <div style={{ paddingTop: 12, display: 'flex', justifyContent: 'center' }}>
                <div style={{
                  width: 44,
                  height: 5,
                  borderRadius: 999,
                  background: isDark ? 'rgba(255,255,255,0.18)' : 'rgba(0,0,0,0.12)',
                  transform: sheetDragOffset > 0 ? `scaleX(${1 + Math.min(sheetDragOffset / 280, 0.12)})` : 'scaleX(1)',
                  transition: isSheetClosing
                    ? `transform ${MORE_SHEET_CLOSE_ANIMATION_MS}ms cubic-bezier(0.22, 0.61, 0.36, 1)`
                    : 'none',
                }} />
              </div>

              <div style={{
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                gap: 16,
                padding: '20px 20px 16px',
              }}>
                <div>
                  <div style={{
                    fontSize: 30,
                    fontWeight: 750,
                    letterSpacing: '-0.03em',
                    color: colors.textPrimary,
                    lineHeight: 1.05,
                    marginBottom: 6,
                  }}>
                    {t('navigation.more', 'Ещё')}
                  </div>
                  <Text type="secondary">
                    Остальные разделы и настройки кабинета.
                  </Text>
                </div>
                <Button
                  type="text"
                  icon={<CloseOutlined />}
                  onClick={closeMoreSheet}
                  style={{ color: colors.textSecondary }}
                />
              </div>
            </div>

            <div style={{
              flex: 1,
              overflow: 'auto',
              padding: '0 20px 24px',
            }}>
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
              }}>
                {mobileMoreItems.map((item) => {
                  const isActive = matchesNavItem(location.pathname, item.key);

                  return (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => handleMobileMoreNavigation(item.key)}
                      style={{
                        all: 'unset',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: 16,
                        padding: '16px 18px',
                        borderRadius: 22,
                        cursor: 'pointer',
                        background: isActive
                          ? (isDark ? 'rgba(255,255,255,0.08)' : 'rgba(35, 131, 226, 0.08)')
                          : colors.bgSecondary,
                        color: colors.textPrimary,
                        boxShadow: isDark
                          ? '0 10px 24px rgba(0, 0, 0, 0.18)'
                          : '0 10px 24px rgba(20, 26, 40, 0.06)',
                      }}
                    >
                      <span style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 14,
                        minWidth: 0,
                      }}>
                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          width: 42,
                          height: 42,
                          borderRadius: 14,
                          background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.9)',
                          color: isActive ? colors.accentPrimary : colors.textSecondary,
                          fontSize: 18,
                          flex: '0 0 auto',
                        }}>
                          {item.icon}
                        </span>
                        <span style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          minWidth: 0,
                          flexWrap: 'wrap',
                        }}>
                          <span style={{ fontSize: 15, fontWeight: 600 }}>
                            {item.label}
                          </span>
                          {item.badge}
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>

              {canSwitchTenant && (
                <div style={{
                  marginTop: 24,
                  padding: 20,
                  borderRadius: 24,
                  background: colors.bgSecondary,
                  boxShadow: isDark
                    ? '0 10px 24px rgba(0, 0, 0, 0.18)'
                    : '0 10px 24px rgba(20, 26, 40, 0.06)',
                }}>
                  <div style={{
                    fontSize: 16,
                    fontWeight: 650,
                    color: colors.textPrimary,
                    marginBottom: 6,
                  }}>
                    Контекст владельца
                  </div>
                  <Text type="secondary">
                    Выберите школу только для поддержки или проверки.
                  </Text>
                  <div style={{ marginTop: 16 }}>
                    <TenantSwitcher fullWidth />
                  </div>
                </div>
              )}
            </div>
          </div>
        </Drawer>
      )}
    </>
  );
};

export default AppLayout;
