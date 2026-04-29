import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './auth/AuthProvider';
import { ThemeProvider } from './theme/ThemeProvider';
import App from './App';
import LandingPage from './pages/LandingPage';
import { OfferPage, PrivacyPage } from './pages/LegalPages';
import { appEnv } from './env';

// Initialize i18n before rendering
import './i18n';

import './index.css';
import './styles/mobile.css';
import './styles/safe-area.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2 * 60 * 1000,
      gcTime: 15 * 60 * 1000,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
      retry: 1,
    },
  },
});

const isLandingRequest = () => {
  if (typeof window === 'undefined') {
    return false;
  }

  const { hostname, pathname } = window.location;
  if (pathname === '/landing') {
    return true;
  }

  if (pathname === '/offer' || pathname === '/privacy') {
    return true;
  }

  const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';
  if (isLocalhost) {
    return false;
  }

  return !hostname.startsWith('app.');
};

const publicTree = () => {
  const pathname = typeof window === 'undefined' ? '/' : window.location.pathname;

  if (pathname === '/offer') {
    return <OfferPage />;
  }

  if (pathname === '/privacy') {
    return <PrivacyPage />;
  }

  return <LandingPage />;
};

const appTree = isLandingRequest() ? (
  <BrowserRouter>
    <ThemeProvider>
      {publicTree()}
    </ThemeProvider>
  </BrowserRouter>
) : (
  <BrowserRouter>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ThemeProvider>
          <App />
        </ThemeProvider>
      </AuthProvider>
    </QueryClientProvider>
  </BrowserRouter>
);

createRoot(document.getElementById('root')!).render(
  appEnv.isDev ? appTree : <StrictMode>{appTree}</StrictMode>
);
