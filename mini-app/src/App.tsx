import { Routes, Route } from 'react-router-dom';
import { ConfigProvider, theme } from 'antd';
import { useAuth } from './auth/AuthProvider';
import { useTelegram } from './hooks/useTelegram';
import AppLayout from './components/layout/AppLayout';
import Dashboard from './pages/Dashboard';
import Packages from './pages/Packages';
import PackageDetail from './pages/PackageDetail';
import Templates from './pages/Templates';

function App() {
  const { isLoading, isAuthenticated } = useAuth();
  const { colorScheme } = useTelegram();

  const antdTheme = {
    algorithm: colorScheme === 'dark' ? theme.darkAlgorithm : theme.defaultAlgorithm,
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
          <Route path="/templates" element={<Templates />} />
          {/* Другие маршруты будут здесь */}
        </Routes>
      </AppLayout>
    </ConfigProvider>
  );
}

export default App;
