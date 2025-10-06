import React, { useEffect } from 'react';
import { Layout, Menu } from 'antd';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { HomeOutlined, AppstoreOutlined, ReadOutlined } from '@ant-design/icons';
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
];

interface AppLayoutProps {
  children: React.ReactNode;
}

const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { tg } = useTelegram();

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
      <Sider collapsible>
        <div className="logo" />
        <Menu theme="dark" selectedKeys={[location.pathname]} mode="inline" items={menuItems} />
      </Sider>
      <Layout>
        <Content style={{ margin: '16px', padding: 24, background: 'var(--tg-theme-bg-color, #fff)', borderRadius: '8px' }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
