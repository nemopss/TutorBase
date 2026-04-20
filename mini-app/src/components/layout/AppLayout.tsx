import React, { useEffect, useState, useMemo } from 'react';
import { Alert, Layout, Menu, Drawer, Button, Space, Tag, type MenuProps } from 'antd';
import { Link, useLocation } from 'react-router-dom';
import {
  HomeOutlined,
  AppstoreOutlined,
  BellOutlined,
  BarChartOutlined,
  SettingOutlined,
  CalendarOutlined,
  MenuOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  TeamOutlined,
  CrownOutlined,
  DollarOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useTheme } from '../../theme/ThemeProvider';
import { useAuth } from '../../auth/AuthProvider';
import TenantIndicator from '../common/TenantIndicator';

const { Sider, Content } = Layout;

interface AppLayoutProps {
  children: React.ReactNode;
}

const SIDEBAR_COLLAPSED_KEY = 'tutorbase_sidebar_collapsed';

const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const { t } = useTranslation();
  const location = useLocation();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme.colorScheme === 'dark';
  const colors = resolvedTheme.colors;
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    const saved = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
    return saved === 'true';
  });
  const { user, isSuperAdmin, tenantAccess } = useAuth();
  const hasStaffAccess = isSuperAdmin || user?.role === 'teacher';
  const isStudent = user?.role === 'viewer';
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

  // Build menu items with translations
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
    {
      key: '/reminders',
      icon: <BellOutlined />,
      label: (
        <Space size={6}>
          <Link to="/reminders">{t('navigation.reminders')}</Link>
          <Tag color="warning" style={{ marginInlineEnd: 0 }}>{t('navigation.legacyBadge')}</Tag>
        </Space>
      ),
    },
    {
      key: '/notifications',
      icon: <BellOutlined />,
      label: (
        <Space size={6}>
          <Link to="/notifications">{t('navigation.notifications')}</Link>
          <Tag color="green" style={{ marginInlineEnd: 0 }}>{t('navigation.newBadge')}</Tag>
        </Space>
      ),
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
  ], [t]);

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
    label: <Link to="/platform">{t('navigation.console', 'Консоль')}</Link>,
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

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < 768);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

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
          fontSize: isSidebarCompact ? '18px' : '18px',
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
          onClick={() => isMobile && setDrawerVisible(false)}
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
          onClick={() => isMobile && setDrawerVisible(false)}
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
          }}>
            <TenantIndicator />
          </div>
        )}
      </div>
    </div>
  );

  return (
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
      {/* Desktop Sidebar */}
      {!isMobile && (
        <Sider
          collapsible
          collapsed={sidebarCollapsed}
          onCollapse={handleSidebarCollapse}
          width={240}
          collapsedWidth={80}
          style={{
            background: colors.bgSecondary,
            border: `1px solid ${colors.borderPrimary}`,
            borderRadius: '8px',
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

      {/* Mobile Drawer */}
      {isMobile && (
        <Drawer
          placement="left"
          onClose={() => setDrawerVisible(false)}
          open={drawerVisible}
          width={240}
          styles={{
            body: {
              padding: 0,
              background: colors.bgSecondary,
              height: '100%',
            },
          }}
        >
          {menuContent}
        </Drawer>
      )}

      <Layout style={{
        flex: 1,
        minWidth: 0,
        height: isMobile ? undefined : '100%',
        background: colors.bgPrimary,
        transition: 'all 0.2s',
      }}>
        {/* Mobile Header with Hamburger */}
        {isMobile && (
          <div style={{
            padding: '12px 16px',
            background: colors.bgSecondary,
            borderBottom: `1px solid ${colors.borderPrimary}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
          }}>
            <Space>
              <Button
                type="text"
                icon={<MenuOutlined />}
                onClick={() => setDrawerVisible(true)}
                style={{ fontSize: '18px' }}
              />
              <span style={{ fontSize: '18px', fontWeight: 600 }}>TutorBase</span>
            </Space>
            {isSuperAdmin && <TenantIndicator />}
          </div>
        )}

        <Content style={{
          margin: isMobile ? '16px' : 0,
          padding: isMobile ? '16px' : '32px',
          background: colors.bgSecondary,
          minHeight: isMobile ? 'calc(100vh - 120px)' : 0,
          height: isMobile ? undefined : '100%',
          borderRadius: '8px',
          border: `1px solid ${colors.borderPrimary}`,
          overflow: isMobile ? undefined : 'auto',
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
  );
};

export default AppLayout;
