import React, { useEffect, useState, useMemo } from 'react';
import { Layout, Menu, Drawer, Button, Space, type MenuProps } from 'antd';
import { Link, useLocation } from 'react-router-dom';
import {
  HomeOutlined,
  AppstoreOutlined,
  ReadOutlined,
  BellOutlined,
  BarChartOutlined,
  SettingOutlined,
  CalendarOutlined,
  MenuOutlined,
  TeamOutlined,
  CrownOutlined,
  MailOutlined
} from '@ant-design/icons';
import { useThemeMode } from '../../theme/ThemeProvider';
import { useAuth } from '../../auth/AuthProvider';
import TenantSwitcher from '../common/TenantSwitcher';
import TenantIndicator from '../common/TenantIndicator';

const { Sider, Content } = Layout;

const baseMenuItems: NonNullable<MenuProps['items']> = [
  {
    key: '/',
    icon: <HomeOutlined />,
    label: <Link to="/">Dashboard</Link>,
  },
  {
    key: '/packages',
    icon: <AppstoreOutlined />,
    label: <Link to="/packages">Packages</Link>,
  },
  {
    key: '/lessons',
    icon: <CalendarOutlined />,
    label: <Link to="/lessons">Lessons</Link>,
  },
  {
    key: '/learners',
    icon: <TeamOutlined />,
    label: <Link to="/learners">Learners</Link>,
  },
  {
    key: '/templates',
    icon: <ReadOutlined />,
    label: <Link to="/templates">Templates</Link>,
  },
  {
    key: '/reminders',
    icon: <BellOutlined />,
    label: <Link to="/reminders">Reminders</Link>,
  },
  {
    key: '/analytics',
    icon: <BarChartOutlined />,
    label: <Link to="/analytics">Analytics</Link>,
  },
  {
    key: '/settings',
    icon: <SettingOutlined />,
    label: <Link to="/settings">Settings</Link>,
  },
];

const inviteCodesMenuItem: NonNullable<MenuProps['items']>[number] = {
  key: '/invite-codes',
  icon: <MailOutlined />,
  label: <Link to="/invite-codes">Invite Codes</Link>,
};

const adminMenuItem: NonNullable<MenuProps['items']>[number] = {
  key: '/admin',
  icon: <CrownOutlined />,
  label: <Link to="/admin">Admin</Link>,
};

interface AppLayoutProps {
  children: React.ReactNode;
}

const studentMenuItems: NonNullable<MenuProps['items']> = [
  {
    key: '/',
    icon: <HomeOutlined />,
    label: <Link to="/">Dashboard</Link>,
  },
  {
    key: '/schedule',
    icon: <CalendarOutlined />,
    label: <Link to="/schedule">Расписание</Link>,
  },
  {
    key: '/settings',
    icon: <SettingOutlined />,
    label: <Link to="/settings">Settings</Link>,
  },
];

const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const location = useLocation();
  const { resolvedTheme } = useThemeMode();
  const isDark = resolvedTheme === 'dark';
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const hasStaffAccess = user?.role === 'admin' || user?.role === 'teacher';
  const isStudent = user?.role === 'viewer';

  const menuItems = useMemo<NonNullable<MenuProps['items']>>(() => {
    if (isStudent) {
      return studentMenuItems;
    }

    const items = [...baseMenuItems];

    // Add Invite Codes for teachers and admins
    if (hasStaffAccess) {
      // Insert before Settings
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
  }, [isAdmin, hasStaffAccess, isStudent]);

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
        padding: '20px 16px',
        fontSize: '18px',
        fontWeight: 600,
        color: isDark ? '#ffffff' : '#37352f',
        borderBottom: isDark ? '1px solid #3a3a3a' : '1px solid #e8e8e8',
      }}>
        📚 TutorBase
      </div>

      {/* Tenant Switcher for Super Admins */}
      {isAdmin && (
        <div style={{
          padding: '16px',
          borderBottom: isDark ? '1px solid #3a3a3a' : '1px solid #e8e8e8',
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
          color: isDark ? '#ffffff' : '#37352f',
        }}
      />
    </>
  );

  return (
    <Layout style={{ minHeight: '100vh', background: isDark ? '#191919' : '#ffffff' }}>
      {/* Desktop Sidebar */}
      {!isMobile && (
        <Sider
          collapsible
          width={240}
          collapsedWidth={80}
          style={{
            background: isDark ? '#252525' : '#f7f7f5',
            borderRight: isDark ? '1px solid #3a3a3a' : '1px solid #e8e8e8',
            overflow: 'auto',
            height: '100vh',
            position: 'fixed',
            left: 0,
            top: 0,
            bottom: 0,
            display: 'flex',
            flexDirection: 'column',
          }}
          trigger={null}
          theme={isDark ? 'dark' : 'light'}
        >
          <div style={{ flex: 1, overflow: 'auto' }}>
            {menuContent}
          </div>
          {/* Tenant Indicator at bottom of sidebar */}
          {isAdmin && (
            <div style={{
              padding: '16px',
              borderTop: isDark ? '1px solid #3a3a3a' : '1px solid #e8e8e8',
              background: isDark ? '#1f1f1f' : '#fafafa',
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
              background: isDark ? '#252525' : '#f7f7f5',
            },
          }}
        >
          {menuContent}
        </Drawer>
      )}

      <Layout style={{ marginLeft: isMobile ? 0 : 240, background: isDark ? '#191919' : '#ffffff' }}>
        {/* Mobile Header with Hamburger */}
        {isMobile && (
          <div style={{
            padding: '12px 16px',
            background: isDark ? '#252525' : '#ffffff',
            borderBottom: isDark ? '1px solid #3a3a3a' : '1px solid #e8e8e8',
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
          background: isDark ? '#252525' : '#ffffff',
          minHeight: isMobile ? 'calc(100vh - 120px)' : 'calc(100vh - 48px)',
          borderRadius: '8px',
          border: isDark ? '1px solid #3a3a3a' : '1px solid #e8e8e8',
        }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;