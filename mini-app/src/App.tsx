import { Routes, Route } from 'react-router-dom';
import { ConfigProvider, theme } from 'antd';
import { useAuth } from './auth/AuthProvider';
import { useTelegram } from './hooks/useTelegram';
import AppLayout from './components/layout/AppLayout';
import Dashboard from './pages/Dashboard';
import Packages from './pages/Packages';
import PackageDetail from './pages/PackageDetail';
import Templates from './pages/Templates';
import Reminders from './pages/Reminders';
import Settings from './pages/Settings';
import Analytics from './pages/Analytics';
import Lessons from './pages/Lessons';

function App() {
  const { isLoading, isAuthenticated } = useAuth();
  const { colorScheme } = useTelegram();

  const antdTheme = {
    algorithm: colorScheme === 'dark' ? theme.darkAlgorithm : theme.defaultAlgorithm,
    token: {
      colorPrimary: colorScheme === 'dark' ? '#5a67d8' : '#667eea',
      colorSuccess: '#52c41a',
      colorWarning: '#faad14',
      colorError: '#ff4d4f',
      colorInfo: '#1890ff',
      borderRadius: 8,
      wireframe: false,
      colorBgContainer: colorScheme === 'dark' ? '#1a1a1a' : '#ffffff',
      colorBgElevated: colorScheme === 'dark' ? '#2a2a2a' : '#ffffff',
    },
    components: {
      Menu: {
        itemBg: 'transparent',
        itemSelectedBg: 'rgba(255,255,255,0.15)',
        itemHoverBg: 'rgba(255,255,255,0.1)',
        itemSelectedColor: '#ffffff',
        itemColor: 'rgba(255,255,255,0.85)',
        itemHoverColor: '#ffffff',
        iconSize: 16,
        itemHeight: 40,
      },
      Layout: {
        siderBg: 'transparent',
        bodyBg: 'var(--tg-theme-bg-color, #f8fafc)',
      },
      Card: {
        borderRadius: 12,
        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
      },
      Button: {
        borderRadius: 8,
        controlHeight: 36,
      },
      Input: {
        borderRadius: 8,
        controlHeight: 36,
      },
      Select: {
        borderRadius: 8,
        controlHeight: 36,
      },
    },
  };

  if (isLoading) {
    return <div>Loading...</div>;
  }

  if (!isAuthenticated) {
    return <div>Authentication Error! Please reload the app.</div>;
  }

  return (
    <ConfigProvider theme={antdTheme}>
      <AppLayout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/packages" element={<Packages />} />
          <Route path="/packages/:id" element={<PackageDetail />} />
          <Route path="/lessons" element={<Lessons />} />
          <Route path="/templates" element={<Templates />} />
          <Route path="/reminders" element={<Reminders />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </AppLayout>
    </ConfigProvider>
  );
}

export default App;
