import React, { useEffect } from 'react';
import { Layout, Menu } from 'antd';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { HomeOutlined, AppstoreOutlined, ReadOutlined, BellOutlined, BarChartOutlined, SettingOutlined } from '@ant-design/icons';
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

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider 
        collapsible
        style={{
          background: colorScheme === 'dark' 
            ? 'var(--tg-theme-bg-color, #f8fafc)' 
            : 'var(--tg-theme-bg-color, #1a1a1a)',
          boxShadow: colorScheme === 'dark' 
            ? '2px 0 8px rgba(0,0,0,0.3)' 
            : '2px 0 8px rgba(0,0,0,0.1)'
        }}
      >
       
        <Menu 
          theme="dark" 
          selectedKeys={[location.pathname]} 
          mode="inline" 
          items={menuItems}
          style={{
            background: 'transparent',
            border: 'none'
          }}
        />
      </Sider>
      <Layout>
        <Content style={{ 
          margin: '16px', 
          padding: 24, 
          background: colorScheme === 'dark' 
            ? 'var(--tg-theme-bg-color, #1a1a1a)' 
            : 'var(--tg-theme-bg-color, #f8fafc)', 
          borderRadius: '12px',
          boxShadow: colorScheme === 'dark' 
            ? '0 2px 8px rgba(0,0,0,0.3)' 
            : '0 2px 8px rgba(0,0,0,0.06)',
          border: colorScheme === 'dark' 
            ? '1px solid rgba(255,255,255,0.1)' 
            : '1px solid rgba(0,0,0,0.05)'
        }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
