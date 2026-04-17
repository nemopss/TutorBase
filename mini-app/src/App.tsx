import { useEffect, lazy, Suspense } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { ConfigProvider, Spin } from 'antd';
import { useTranslation } from 'react-i18next';
import ruRU from 'antd/locale/ru_RU';
import enUS from 'antd/locale/en_US';
import koKR from 'antd/locale/ko_KR';
import { useAuth } from './auth/AuthProvider';
import { useTelegram } from './hooks/useTelegram';
import { useTheme } from './theme/ThemeProvider';
import { generateAntdTheme } from './theme/antdTokens';
import type { SupportedLanguage } from './i18n';

const antdLocales = {
  ru: ruRU,
  en: enUS,
  ko: koKR,
};

// Layout - loaded immediately
import AppLayout from './components/layout/AppLayout';

// Lazy-loaded pages for code-splitting
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Packages = lazy(() => import('./pages/Packages'));
const PackageDetail = lazy(() => import('./pages/PackageDetail'));
const Reminders = lazy(() => import('./pages/Reminders'));
const Notifications = lazy(() => import('./pages/Notifications'));
const Groups = lazy(() => import('./pages/Groups'));
const Settings = lazy(() => import('./pages/Settings'));
const Analytics = lazy(() => import('./pages/Analytics'));
const Lessons = lazy(() => import('./pages/Lessons'));
const Learners = lazy(() => import('./pages/Learners'));
const PlatformConsole = lazy(() => import('./pages/PlatformConsole'));
const AccessDenied = lazy(() => import('./pages/AccessDenied'));
const RoleSelectionScreen = lazy(() => import('./pages/RoleSelectionScreen'));
const TutorRegistrationForm = lazy(() => import('./pages/TutorRegistrationForm'));
const StudentRegistrationForm = lazy(() => import('./pages/StudentRegistrationForm'));
const StudentDashboard = lazy(() => import('./pages/StudentDashboard'));
const Schedule = lazy(() => import('./pages/Schedule'));
const InviteCodes = lazy(() => import('./pages/InviteCodes'));
const FinanceDashboard = lazy(() => import('./pages/FinanceDashboard'));
const IncomeReports = lazy(() => import('./pages/IncomeReports'));
const LearnerFinance = lazy(() => import('./pages/LearnerFinance'));
const LearnerProfile = lazy(() => import('./pages/LearnerProfile'));

// Loading fallback component
const PageLoader = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
    <Spin size="large" />
  </div>
);

function App() {
  const { isLoading, isAuthenticated, user } = useAuth();
  const location = useLocation();
  const { tg, autoFullscreenEnabled, requestFullscreen } = useTelegram();
  const { resolvedTheme } = useTheme();
  const { i18n } = useTranslation();
  const isPlatformAdmin = !!user?.is_platform_admin;
  const hasStaffAccess = isPlatformAdmin || user?.role === 'teacher';
  const currentLocale = antdLocales[i18n.language as SupportedLanguage] || ruRU;

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
      tg.setHeaderColor(resolvedTheme.colors.bgPrimary);
    }

    // Устанавливаем цвет фона
    if (tg.setBackgroundColor) {
      tg.setBackgroundColor(resolvedTheme.colors.bgPrimary);
    }
  }, [tg, resolvedTheme, autoFullscreenEnabled, requestFullscreen]);

  const antdTheme = generateAntdTheme(resolvedTheme);

  if (isLoading) {
    return <PageLoader />;
  }

  // If not authenticated, show registration flow
  if (!isAuthenticated) {
    return (
      <ConfigProvider theme={antdTheme} locale={currentLocale}>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/" element={<RoleSelectionScreen />} />
            <Route path="/register/tutor" element={<TutorRegistrationForm />} />
            <Route path="/register/student" element={<StudentRegistrationForm />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </ConfigProvider>
    );
  }

  const isStudent = user?.role === 'viewer';
  const hasAccess = hasStaffAccess || isStudent;

  if (!hasAccess) {
    return <AccessDenied />;
  }

  if (location.pathname.startsWith('/platform')) {
    return (
      <ConfigProvider theme={antdTheme} locale={currentLocale}>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            {isPlatformAdmin ? (
              <Route path="/platform" element={<PlatformConsole />} />
            ) : (
              <Route path="/platform" element={<AccessDenied />} />
            )}
            <Route path="*" element={<Navigate to="/platform" replace />} />
          </Routes>
        </Suspense>
      </ConfigProvider>
    );
  }

  return (
    <ConfigProvider theme={antdTheme} locale={currentLocale}>
      <AppLayout>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            {isStudent ? (
              <>
                <Route path="/" element={<StudentDashboard />} />
                <Route path="/schedule" element={<Schedule />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </>
            ) : (
              <>
                <Route path="/" element={<Dashboard />} />
                <Route path="/packages" element={<Packages />} />
                <Route path="/packages/:id" element={<PackageDetail />} />
                <Route path="/lessons" element={<Lessons />} />
                <Route path="/learners" element={<Learners />} />
                <Route path="/learners/:id" element={<LearnerProfile />} />
                <Route path="/learners/:id/finance" element={<LearnerFinance />} />
                <Route path="/finance/dashboard" element={<FinanceDashboard />} />
                <Route path="/finance/reports" element={<IncomeReports />} />
                <Route path="/notifications" element={<Notifications />} />
                <Route path="/reminders" element={<Reminders />} />
                <Route path="/groups" element={<Groups />} />
                <Route path="/analytics" element={<Analytics />} />
                <Route path="/invite-codes" element={<InviteCodes />} />
                <Route path="/settings" element={<Settings />} />
                {isPlatformAdmin && <Route path="/admin" element={<Navigate to="/platform" replace />} />}
                <Route path="*" element={<Navigate to="/" replace />} />
              </>
            )}
          </Routes>
        </Suspense>
      </AppLayout>
    </ConfigProvider>
  );
}

export default App;
