import { useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, theme } from 'antd';
import { useAuth } from './auth/AuthProvider';
import { useTelegram } from './hooks/useTelegram';
import { useThemeMode } from './theme/ThemeProvider';
import AppLayout from './components/layout/AppLayout';
import Dashboard from './pages/Dashboard';
import Packages from './pages/Packages';
import PackageDetail from './pages/PackageDetail';
import Templates from './pages/Templates';
import Reminders from './pages/Reminders';
import Settings from './pages/Settings';
import Analytics from './pages/Analytics';
import Lessons from './pages/Lessons';
import Learners from './pages/Learners';
import Admin from './pages/Admin';
import AccessDenied from './pages/AccessDenied';
import RoleSelectionScreen from './pages/RoleSelectionScreen';
import TutorRegistrationForm from './pages/TutorRegistrationForm';
import StudentRegistrationForm from './pages/StudentRegistrationForm';
import InviteCodes from './pages/InviteCodes';

function App() {
  const { isLoading, isAuthenticated, user } = useAuth();
  const { tg, autoFullscreenEnabled, requestFullscreen } = useTelegram();
  const { resolvedTheme } = useThemeMode();
  const isAdmin = user?.role === 'admin';
  const hasStaffAccess = user?.role === 'admin' || user?.role === 'teacher';

  useEffect(() => {
    if (!tg) return;

    tg.ready();

    tg.BackButton?.hide();

    // Принудительно разворачиваем приложение только для устройств, где это необходимо
    if (autoFullscreenEnabled) {
      requestFullscreen();
    } else if (!tg.isExpanded) {
      tg.expand();
    }

    // Включаем кнопку закрытия для возможности свернуть
    tg.enableClosingConfirmation();

    // Устанавливаем цвет заголовка
    if (tg.setHeaderColor) {
      tg.setHeaderColor(resolvedTheme === 'dark' ? '#191919' : '#ffffff');
    }

    // Устанавливаем цвет фона
    if (tg.setBackgroundColor) {
      tg.setBackgroundColor(resolvedTheme === 'dark' ? '#191919' : '#ffffff');
    }
  }, [tg, resolvedTheme, autoFullscreenEnabled, requestFullscreen]);

  const antdTheme = {
    algorithm: resolvedTheme === 'dark' ? theme.darkAlgorithm : theme.defaultAlgorithm,
    token: {
      colorPrimary: '#2383e2', // Notion blue
      colorSuccess: '#0f7b6c',
      colorWarning: '#e16259',
      colorError: '#eb5757',
      colorInfo: '#2383e2',
      colorTextBase: resolvedTheme === 'dark' ? '#ffffff' : '#37352f',
      colorBgBase: resolvedTheme === 'dark' ? '#191919' : '#ffffff',
      colorBgContainer: resolvedTheme === 'dark' ? '#252525' : '#ffffff',
      colorBorder: resolvedTheme === 'dark' ? '#3a3a3a' : '#e8e8e8',
      borderRadius: 6,
      fontSize: 14,
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, "Apple Color Emoji", Arial, sans-serif, "Segoe UI Emoji", "Segoe UI Symbol"',
    },
    components: {
      Card: {
        borderRadiusLG: 8,
        boxShadowTertiary: resolvedTheme === 'dark' ? 'none' : '0 1px 2px rgba(0, 0, 0, 0.05)',
      },
      Table: {
        borderRadius: 6,
        headerBg: resolvedTheme === 'dark' ? '#2a2a2a' : '#f7f7f5',
      },
      Menu: {
        itemBg: 'transparent',
        itemSelectedBg: resolvedTheme === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.04)',
        itemSelectedColor: resolvedTheme === 'dark' ? '#ffffff' : '#37352f',
        itemColor: resolvedTheme === 'dark' ? 'rgba(255,255,255,0.65)' : 'rgba(55,53,47,0.65)',
        itemHoverBg: resolvedTheme === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.03)',
        itemHoverColor: resolvedTheme === 'dark' ? '#ffffff' : '#37352f',
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

  // If not authenticated, show registration flow
  if (!isAuthenticated) {
    return (
      <ConfigProvider theme={antdTheme}>
        <Routes>
          <Route path="/" element={<RoleSelectionScreen />} />
          <Route path="/register/tutor" element={<TutorRegistrationForm />} />
          <Route path="/register/student" element={<StudentRegistrationForm />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </ConfigProvider>
    );
  }

  if (!hasStaffAccess) {
    return <AccessDenied />;
  }

  return (
    <ConfigProvider theme={antdTheme}>
      <AppLayout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/packages" element={<Packages />} />
          <Route path="/packages/:id" element={<PackageDetail />} />
          <Route path="/lessons" element={<Lessons />} />
          <Route path="/learners" element={<Learners />} />
          <Route path="/templates" element={<Templates />} />
          <Route path="/reminders" element={<Reminders />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/invite-codes" element={<InviteCodes />} />
          <Route path="/settings" element={<Settings />} />
          {isAdmin && <Route path="/admin" element={<Admin />} />}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppLayout>
    </ConfigProvider>
  );
}

export default App;
