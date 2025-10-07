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
      colorPrimary: '#2383e2', // Notion blue
      colorSuccess: '#0f7b6c',
      colorWarning: '#e16259',
      colorError: '#eb5757',
      colorInfo: '#2383e2',
      colorTextBase: colorScheme === 'dark' ? '#ffffff' : '#37352f',
      colorBgBase: colorScheme === 'dark' ? '#191919' : '#ffffff',
      colorBgContainer: colorScheme === 'dark' ? '#252525' : '#ffffff',
      colorBorder: colorScheme === 'dark' ? '#3a3a3a' : '#e8e8e8',
      borderRadius: 6,
      fontSize: 14,
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, "Apple Color Emoji", Arial, sans-serif, "Segoe UI Emoji", "Segoe UI Symbol"',
    },
    components: {
      Card: {
        borderRadiusLG: 8,
        boxShadowTertiary: colorScheme === 'dark' ? 'none' : '0 1px 2px rgba(0, 0, 0, 0.05)',
      },
      Table: {
        borderRadius: 6,
        headerBg: colorScheme === 'dark' ? '#2a2a2a' : '#f7f7f5',
      },
      Menu: {
        itemBg: 'transparent',
        itemSelectedBg: colorScheme === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.04)',
        itemSelectedColor: colorScheme === 'dark' ? '#ffffff' : '#37352f',
        itemColor: colorScheme === 'dark' ? 'rgba(255,255,255,0.65)' : 'rgba(55,53,47,0.65)',
        itemHoverBg: colorScheme === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.03)',
        itemHoverColor: colorScheme === 'dark' ? '#ffffff' : '#37352f',
        iconSize: 18,
        itemHeight: 36,
        itemMarginInline: 4,
        itemBorderRadius: 4,
      },
      Layout: {
        siderBg: 'transparent',
        bodyBg: 'var(--tg-theme-bg-color, #f8fafc)',
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
