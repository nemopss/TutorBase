import React, { useEffect, useState } from 'react';
import { Layout, Menu, Drawer, Button } from 'antd';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { HomeOutlined, AppstoreOutlined, ReadOutlined, BellOutlined, BarChartOutlined, SettingOutlined, CalendarOutlined, MenuOutlined } from '@ant-design/icons';
import { useTelegram } from '../../hooks/useTelegram';

const { Sider, Content } = Layout;

const menuItems = [
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

interface AppLayoutProps {
  children: React.ReactNode;
}

const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { tg, colorScheme } = useTelegram();
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < 768);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    const handleBackButtonClick = () => {
      navigate(-1);
    };

    if (location.pathname !== '/') {
      tg?.BackButton.show();
      tg?.onEvent('backButtonClicked', handleBackButtonClick);
    } else {
      tg?.BackButton.hide();
      tg?.offEvent('backButtonClicked', handleBackButtonClick);
    }

    return () => {
      tg?.offEvent('backButtonClicked', handleBackButtonClick);
      tg?.BackButton.hide();
    };
  }, [location, navigate, tg]);

  const menuContent = (
    <>
      <div style={{ 
        padding: '20px 16px', 
        fontSize: '18px', 
        fontWeight: 600,
        color: colorScheme === 'dark' ? '#ffffff' : '#37352f',
        borderBottom: colorScheme === 'dark' ? '1px solid #3a3a3a' : '1px solid #e8e8e8',
      }}>
        📚 KSU App
      </div>
      
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
          color: colorScheme === 'dark' ? '#ffffff' : '#37352f',
        }}
      />
    </>
  );

  return (
    <Layout style={{ minHeight: '100vh', background: colorScheme === 'dark' ? '#191919' : '#ffffff' }}>
      {/* Desktop Sidebar */}
      {!isMobile && (
        <Sider 
          collapsible
          width={240}
          collapsedWidth={80}
          style={{
            background: colorScheme === 'dark' ? '#252525' : '#f7f7f5',
            borderRight: colorScheme === 'dark' ? '1px solid #3a3a3a' : '1px solid #e8e8e8',
            overflow: 'auto',
            height: '100vh',
            position: 'fixed',
            left: 0,
            top: 0,
            bottom: 0,
          }}
          trigger={null}
          theme={colorScheme === 'dark' ? 'dark' : 'light'}
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
              background: colorScheme === 'dark' ? '#252525' : '#f7f7f5',
            },
          }}
        >
          {menuContent}
        </Drawer>
      )}

      <Layout style={{ marginLeft: isMobile ? 0 : 240, background: colorScheme === 'dark' ? '#191919' : '#ffffff' }}>
        {/* Mobile Header with Hamburger */}
        {isMobile && (
          <div style={{
            padding: '12px 16px',
            background: colorScheme === 'dark' ? '#252525' : '#ffffff',
            borderBottom: colorScheme === 'dark' ? '1px solid #3a3a3a' : '1px solid #e8e8e8',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}>
            <Button
              type="text"
              icon={<MenuOutlined />}
              onClick={() => setDrawerVisible(true)}
              style={{ fontSize: '18px' }}
            />
            <span style={{ fontSize: '18px', fontWeight: 600 }}>📚 KSU App</span>
          </div>
        )}

        <Content style={{ 
          margin: isMobile ? '16px' : '24px', 
          padding: isMobile ? '16px' : '32px', 
          background: colorScheme === 'dark' ? '#252525' : '#ffffff',
          minHeight: isMobile ? 'calc(100vh - 120px)' : 'calc(100vh - 48px)',
          borderRadius: '8px',
          border: colorScheme === 'dark' ? '1px solid #3a3a3a' : '1px solid #e8e8e8',
        }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
