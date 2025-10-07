import React, { useEffect } from 'react';
import { Layout, Menu } from 'antd';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { HomeOutlined, AppstoreOutlined, ReadOutlined, BellOutlined, BarChartOutlined, SettingOutlined, CalendarOutlined } from '@ant-design/icons';
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
    <Layout style={{ minHeight: '100vh', background: colorScheme === 'dark' ? '#191919' : '#ffffff' }}>
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
          style={{
            background: 'transparent',
            border: 'none',
            marginTop: '8px',
            fontSize: '14px',
            color: colorScheme === 'dark' ? '#ffffff' : '#37352f',
          }}
        />
      </Sider>
      <Layout style={{ marginLeft: 240, background: colorScheme === 'dark' ? '#191919' : '#ffffff' }}>
        <Content style={{ 
          margin: '24px 24px 24px 24px', 
          padding: '32px', 
          background: colorScheme === 'dark' ? '#252525' : '#ffffff',
          minHeight: 'calc(100vh - 48px)',
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
