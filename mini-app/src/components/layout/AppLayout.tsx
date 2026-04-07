import React, { useEffect, useState, useMemo } from 'react';
import { Layout, Menu, Drawer, Button, Space, Tag, type MenuProps } from 'antd';
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
  MailOutlined,
  DollarOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useTheme } from '../../theme/ThemeProvider';
import { useAuth } from '../../auth/AuthProvider';
import TenantSwitcher from '../common/TenantSwitcher';
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
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const hasStaffAccess = user?.role === 'admin' || user?.role === 'teacher';
  const isStudent = user?.role === 'viewer';

  const handleSidebarCollapse = (collapsed: boolean) => {
    setSidebarCollapsed(collapsed);
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(collapsed));
  };

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
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: <Link to="/settings">{t('navigation.settings')}</Link>,
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
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: <Link to="/settings">{t('navigation.settings')}</Link>,
    },
  ], [t]);

  const inviteCodesMenuItem: NonNullable<MenuProps['items']>[number] = useMemo(() => ({
    key: '/invite-codes',
    icon: <MailOutlined />,
    label: <Link to="/invite-codes">{t('navigation.inviteCodes')}</Link>,
  }), [t]);

  const adminMenuItem: NonNullable<MenuProps['items']>[number] = useMemo(() => ({
    key: '/admin',
    icon: <CrownOutlined />,
    label: <Link to="/admin">{t('navigation.admin')}</Link>,
  }), [t]);

  const menuItems = useMemo<NonNullable<MenuProps['items']>>(() => {
    if (isStudent) {
      return studentMenuItems;
    }

    const items = [...baseMenuItems];

    // Add Invite Codes for teachers and admins
    if (hasStaffAccess) {
      const settingsIndex = items.findIndex(item => item?.key === '/settings');
      if (settingsIndex !== -1) {
        items.splice(settingsIndex, 0, inviteCodesMenuItem);
      } else {
        items.push(inviteCodesMenuItem);
      }
    }

    // Add Admin menu for admins only
    if (isAdmin) {
      items.push(adminMenuItem);
    }

    return items;
  }, [isAdmin, hasStaffAccess, isStudent, baseMenuItems, studentMenuItems, inviteCodesMenuItem, adminMenuItem]);

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < 768);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const menuContent = (
    <>
      <div style={{
        padding: sidebarCollapsed ? '20px 8px' : '20px 16px',
        fontSize: sidebarCollapsed ? '16px' : '18px',
        fontWeight: 600,
        color: colors.textPrimary,
        borderBottom: `1px solid ${colors.borderPrimary}`,
        textAlign: 'center',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
      }}>
        {sidebarCollapsed ? '📚' : '📚 TutorBase'}
      </div>

      {/* Tenant Switcher for Super Admins */}
      {isAdmin && (
        <div style={{
          padding: '16px',
          borderBottom: `1px solid ${colors.borderPrimary}`,
        }}>
          <TenantSwitcher />
        </div>
      )}

      <Menu
        selectedKeys={[location.pathname]}
        mode="inline"
        items={menuItems}
        onClick={() => isMobile && setDrawerVisible(false)}
        style={{
          background: 'transparent',
          border: 'none',
          marginTop: '8px',
          fontSize: '14px',
          color: colors.textPrimary,
        }}
      />
    </>
  );

  return (
    <Layout style={{ minHeight: '100vh', background: colors.bgPrimary }}>
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
            borderRight: `1px solid ${colors.borderPrimary}`,
            overflow: 'auto',
            height: '100vh',
            position: 'fixed',
            left: 0,
            top: 0,
            bottom: 0,
            display: 'flex',
            flexDirection: 'column',
          }}
          trigger={
            <div style={{
              padding: '12px',
              textAlign: 'center',
              borderTop: `1px solid ${colors.borderPrimary}`,
              cursor: 'pointer',
              color: colors.textPrimary,
            }}>
              {sidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            </div>
          }
          theme={isDark ? 'dark' : 'light'}
        >
          <div style={{ flex: 1, overflow: 'auto' }}>
            {menuContent}
          </div>
          {/* Tenant Indicator at bottom of sidebar */}
          {isAdmin && !sidebarCollapsed && (
            <div style={{
              padding: '16px',
              borderTop: `1px solid ${colors.borderPrimary}`,
              background: colors.bgTertiary,
            }}>
              <TenantIndicator />
            </div>
          )}
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
            },
          }}
        >
          {menuContent}
          {/* TenantSwitcher in mobile drawer for non-admin staff */}
          {hasStaffAccess && !isAdmin && (
            <div style={{
              padding: '16px',
              borderTop: `1px solid ${colors.borderPrimary}`,
            }}>
              <TenantSwitcher />
            </div>
          )}
        </Drawer>
      )}

      <Layout style={{ marginLeft: isMobile ? 0 : (sidebarCollapsed ? 80 : 240), background: colors.bgPrimary, transition: 'margin-left 0.2s' }}>
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
            <TenantIndicator />
          </div>
        )}

        <Content style={{
          margin: isMobile ? '16px' : '24px',
          padding: isMobile ? '16px' : '32px',
          background: colors.bgSecondary,
          minHeight: isMobile ? 'calc(100vh - 120px)' : 'calc(100vh - 48px)',
          borderRadius: '8px',
          border: `1px solid ${colors.borderPrimary}`,
        }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
