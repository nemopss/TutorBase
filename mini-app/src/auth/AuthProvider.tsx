
import React, { createContext, useState, useEffect, useContext, useRef } from 'react';
import type { PropsWithChildren } from 'react';
import api from '../services/api';
import { setBrowserRefreshHandler } from '../services/api';
import { BrowserLoginScreen } from './BrowserLoginScreen';
import {
  loginWithTelegramWidget,
  logoutBrowserSession,
  refreshBrowserSession,
} from './browserSession';
import type { TelegramLoginWidgetPayload } from './browserSession';
import { detectAuthMode, prepareTelegramWebApp } from './modes';
import type { AuthMode } from './modes';
import { parseJwt } from './token';
import { cacheUser, clearCachedUser, readCachedUser } from './userCache';
import { appEnv } from '../env';

const DEV_MODE = appEnv.devMode;
const DEV_INIT_DATA = appEnv.devInitData;
const AUTH_BOOTSTRAP_TIMEOUT_MS = appEnv.isDev
  ? Math.max(appEnv.apiTimeoutMs, 45000)
  : appEnv.apiTimeoutMs;

// Предполагаемые типы для данных пользователя и ответа от API
interface User {
  id: number;
  display_name: string;
  role: string;
  is_platform_admin?: boolean;
  telegram_id?: number;
  tenant_id?: number | null;
  last_login_at?: string;
}

export interface TenantAccess {
  tenant_id: number | null;
  status: string;
  mode: 'full' | 'grace' | 'blocked' | string;
  access_until?: string | null;
  grace_until?: string | null;
  is_lifetime: boolean;
  reason?: string | null;
  notes?: string | null;
  bypass_access_restrictions?: boolean;
}

export interface BillingSnapshot {
  tenant_id: number;
  plan_code: string;
  plan_name: string;
  subscription_plan_code?: string | null;
  subscription_status?: string | null;
  provider?: string | null;
  active_learners_limit: number;
  active_learners_count: number;
  monthly_price_rub: number;
  yearly_price_rub?: number | null;
  current_period_start?: string | null;
  current_period_end?: string | null;
  grace_until?: string | null;
  cancel_at_period_end: boolean;
  is_effective_free_plan: boolean;
  is_over_limit: boolean;
  can_create_learner: boolean;
  can_restore_learner: boolean;
  notifications_allowed: boolean;
  billing_restriction_reason?: string | null;
}

interface AuthResponse {
  access_token: string;
  refresh_token?: string;
  user: User;
  expires_in?: number;
}

interface TutorRegistrationData {
  school_name: string;
  tutor_name?: string;
  offer_accepted: boolean;
  privacy_accepted: boolean;
}

interface StudentRegistrationData {
  invite_token: string;
  student_name?: string;
  offer_accepted: boolean;
  privacy_accepted: boolean;
}

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | null;
  tenantAccess: TenantAccess | null;
  billing: BillingSnapshot | null;
  tenantId: number | null;
  isSuperAdmin: boolean;
  canSwitchTenant: boolean;
  isTenantAccessLoading: boolean;
  isBillingLoading: boolean;
  refreshTenantAccess: () => Promise<void>;
  refreshBilling: () => Promise<void>;
  switchTenant: (tenantId: number | null) => Promise<void>;
  registerTutor: (data: TutorRegistrationData) => Promise<void>;
  registerStudent: (data: StudentRegistrationData) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Хук для доступа к контексту
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider: React.FC<PropsWithChildren<{}>> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [tenantId, setTenantId] = useState<number | null>(null);
  const [tenantAccess, setTenantAccess] = useState<TenantAccess | null>(null);
  const [billing, setBilling] = useState<BillingSnapshot | null>(null);
  const [isTenantAccessLoading, setIsTenantAccessLoading] = useState(false);
  const [isBillingLoading, setIsBillingLoading] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [browserLoginError, setBrowserLoginError] = useState<string | null>(null);
  const [isBrowserLoginLoading, setIsBrowserLoginLoading] = useState(false);
  const [authMode, setAuthMode] = useState<AuthMode>(() => detectAuthMode());
  const refreshTimerRef = useRef<number | null>(null);

  const clearAuthState = () => {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    clearCachedUser();
    delete api.defaults.headers.common['Authorization'];
    setUser(null);
    setTenantId(null);
    setTenantAccess(null);
    setBilling(null);
    setIsTenantAccessLoading(false);
    setIsBillingLoading(false);
  };

  const loadTenantAccess = async (nextTenantId: number | null) => {
    setTenantAccess(null);
    setBilling(null);

    if (nextTenantId === null) {
      setIsTenantAccessLoading(false);
      setIsBillingLoading(false);
      return;
    }

    setIsTenantAccessLoading(true);
    setIsBillingLoading(true);
    try {
      const response = await api.get<TenantAccess>('/tenant-access/current');
      setTenantAccess(response.data);
    } catch (error) {
      console.error('[AuthProvider] Failed to load tenant access state:', error);
    } finally {
      setIsTenantAccessLoading(false);
    }

    try {
      const response = await api.get<BillingSnapshot>('/billing/current');
      setBilling(response.data);
    } catch {
      setBilling(null);
    } finally {
      setIsBillingLoading(false);
    }
  };

  const refreshTenantAccess = async () => {
    await loadTenantAccess(tenantId);
  };

  const refreshBilling = async () => {
    if (tenantId === null) {
      setBilling(null);
      return;
    }
    setIsBillingLoading(true);
    try {
      const response = await api.get<BillingSnapshot>('/billing/current');
      setBilling(response.data);
    } catch {
      setBilling(null);
    } finally {
      setIsBillingLoading(false);
    }
  };

  const applyAuthenticatedSession = (
    authResponse: AuthResponse,
    mode: AuthMode,
    options: { persistLegacyTokens: boolean }
  ) => {
    const { access_token, refresh_token, user: nextUser } = authResponse;

    if (options.persistLegacyTokens && refresh_token) {
      localStorage.setItem('accessToken', access_token);
      localStorage.setItem('refreshToken', refresh_token);
    }
    cacheUser(nextUser, mode);

    api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;

    const payload = parseJwt(access_token);
    const extractedTenantId = payload?.tenant_id !== undefined ? payload.tenant_id : null;

    console.log('[AuthProvider] Session applied:', {
      user: nextUser.display_name,
      role: nextUser.role,
      tenant_id: extractedTenantId,
      mode,
    });

    setUser(nextUser);
    setTenantId(extractedTenantId);
    void loadTenantAccess(extractedTenantId);
    setIsLoading(false);
    setupTokenRefresh(access_token, mode);
  };

  useEffect(() => {
    const login = async () => {
      const currentAuthMode = detectAuthMode();
      setAuthMode(currentAuthMode);

      try {
        if (currentAuthMode === 'browser') {
          setBrowserRefreshHandler(async () => {
            const refreshed = await refreshBrowserSession();
            applyAuthenticatedSession(refreshed, 'browser', { persistLegacyTokens: false });
            return refreshed.access_token;
          });

          try {
            const browserSession = await refreshBrowserSession();
            applyAuthenticatedSession(browserSession, 'browser', { persistLegacyTokens: false });
          } catch {
            clearAuthState();
            setIsLoading(false);
          }
          return;
        }

        setBrowserRefreshHandler(null);

        // Check if we already have a valid token in localStorage
        const existingToken = localStorage.getItem('accessToken');
        const existingRefreshToken = localStorage.getItem('refreshToken');

        if (existingToken && existingRefreshToken) {
          console.log('[AuthProvider] Found existing token, checking validity...');

          // Try to decode and check expiration
          const payload = parseJwt(existingToken);
          const now = Math.floor(Date.now() / 1000);

          if (payload?.exp && payload.exp > now) {
            // Token is still valid, use it
            console.log('[AuthProvider] Using existing valid token:', {
              tenant_id: payload.tenant_id,
              role: payload.role,
              expires_in: payload.exp - now
            });

            // Set up API with existing token
            api.defaults.headers.common['Authorization'] = `Bearer ${existingToken}`;
            const extractedTenantId = payload?.tenant_id !== undefined ? payload.tenant_id : null;
            const cachedUser = readCachedUser<User>(currentAuthMode);

            if (cachedUser) {
              console.log('[AuthProvider] Restoring session from cached user');
              setUser(cachedUser);
              setTenantId(extractedTenantId);
              void loadTenantAccess(extractedTenantId);
              setIsLoading(false);
              setupTokenRefresh(existingToken, currentAuthMode);

              void api.get<User>('/users/me', {
                timeout: AUTH_BOOTSTRAP_TIMEOUT_MS,
              }).then((userResponse) => {
                cacheUser(userResponse.data, currentAuthMode);
                setUser(userResponse.data);
              }).catch((err) => {
                console.log('[AuthProvider] Background user refresh failed:', err);
              });
              return;
            }

            // We need to get user info - try to fetch from API or decode from token
            // For now, we'll fetch the current user
            try {
              const userResponse = await api.get<User>('/users/me', {
                timeout: AUTH_BOOTSTRAP_TIMEOUT_MS,
              });
              const user = userResponse.data;
              cacheUser(user, currentAuthMode);

              console.log('[AuthProvider] Restored session:', {
                user: user.display_name,
                role: user.role,
                tenant_id: extractedTenantId
              });

              setUser(user);
              setTenantId(extractedTenantId);
              void loadTenantAccess(extractedTenantId);
              setIsLoading(false);

              // Setup auto-refresh
              setupTokenRefresh(existingToken, currentAuthMode);
              return;
            } catch (err) {
              console.log('[AuthProvider] Failed to restore session, will re-login:', err);
              // Token might be invalid, continue with normal login
              localStorage.removeItem('accessToken');
              localStorage.removeItem('refreshToken');
              clearCachedUser();
            }
          } else {
            console.log('[AuthProvider] Existing token expired, will re-login');
            localStorage.removeItem('accessToken');
            localStorage.removeItem('refreshToken');
            clearCachedUser();
          }
        }

        // No valid token, proceed with normal login
        let initData: string | undefined = undefined;

        if (currentAuthMode === 'dev') {
          initData = DEV_INIT_DATA;
        } else {
          prepareTelegramWebApp();

          initData = window.Telegram?.WebApp?.initData;

          if (!initData || initData.length === 0) {
            const debugInfo = [
              '⚠️ Please open this app from Telegram bot.',
              '',
              'Debug Info:',
              `• Telegram object: ${window.Telegram ? 'Found' : 'Not found'}`,
              `• WebApp object: ${window.Telegram?.WebApp ? 'Found' : 'Not found'}`,
              `• InitData length: ${initData?.length || 0}`,
            ].join('\n');

            setError(debugInfo);
            setIsLoading(false);
            return;
          }
        }

        const response = await api.post<AuthResponse>('/auth/login', { init_data: initData }, {
          timeout: AUTH_BOOTSTRAP_TIMEOUT_MS,
        });

        const { access_token, refresh_token, user } = response.data;

        // Сохраняем токены (например, в localStorage)
        localStorage.setItem('accessToken', access_token);
        if (refresh_token) {
          localStorage.setItem('refreshToken', refresh_token);
        }
        cacheUser(user, currentAuthMode);

        // Настраиваем заголовок по умолчанию для всех запросов
        api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;

        // Extract tenant_id from JWT
        const payload = parseJwt(access_token);
        const extractedTenantId = payload?.tenant_id !== undefined ? payload.tenant_id : null;

        console.log('[AuthProvider] Login successful:', {
          user: user.display_name,
          role: user.role,
          tenant_id: extractedTenantId,
          jwt_payload: payload
        });

        setUser(user);
        setTenantId(extractedTenantId);
        void loadTenantAccess(extractedTenantId);
        setIsLoading(false);

        // Setup auto-refresh 5 minutes before expiration
        setupTokenRefresh(access_token, currentAuthMode);
      } catch (err: any) {
        console.error('Authentication failed:', err);

        // Check if this is a "user not registered" error (404)
        if (err?.response?.status === 404) {
          console.log('[AuthProvider] User not registered, showing registration flow');
          // User needs to register - don't show error, just set loading to false
          setUser(null);
          setIsLoading(false);
          return;
        }

        // For other errors, show error message
        const errorMsg = err?.response?.data?.detail || err?.message || 'Authentication failed';
        setError('❌ Authentication Error\n\n' + errorMsg);
        setUser(null);
        // Очищаем токены в случае ошибки
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
        clearCachedUser();
        delete api.defaults.headers.common['Authorization'];
        setIsLoading(false);
      }
    };

    login();

    // Cleanup timer on unmount
    return () => {
      if (refreshTimerRef.current) {
        window.clearTimeout(refreshTimerRef.current);
      }
      setBrowserRefreshHandler(null);
    };
  }, []);

  // Auto-refresh token before expiration
  const setupTokenRefresh = (accessToken: string, mode: AuthMode = authMode) => {
    const payload = parseJwt(accessToken);
    if (!payload?.exp) return;

    const now = Math.floor(Date.now() / 1000);
    const expiresIn = payload.exp - now;

    // Refresh 5 minutes (300 seconds) before expiration
    const refreshIn = Math.max(0, expiresIn - 300);

    if (refreshTimerRef.current) {
      window.clearTimeout(refreshTimerRef.current);
    }

    refreshTimerRef.current = window.setTimeout(async () => {
      try {
        if (mode === 'browser') {
          const refreshed = await refreshBrowserSession();
          applyAuthenticatedSession(refreshed, 'browser', { persistLegacyTokens: false });
          return;
        }

        const refreshToken = localStorage.getItem('refreshToken');
        if (!refreshToken) return;

        const response = await api.post<AuthResponse>('/auth/refresh', {
          refresh_token: refreshToken
        });

        const { access_token, refresh_token: newRefreshToken, user: updatedUser } = response.data;

        localStorage.setItem('accessToken', access_token);
        if (newRefreshToken) {
          localStorage.setItem('refreshToken', newRefreshToken);
        }
        cacheUser(updatedUser, mode);
        api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;

        // Extract tenant_id from new JWT
        const payload = parseJwt(access_token);
        const extractedTenantId = payload?.tenant_id !== undefined ? payload.tenant_id : null;

        console.log('[AuthProvider] Token refreshed:', {
          user: updatedUser.display_name,
          tenant_id: extractedTenantId,
          jwt_payload: payload
        });

        setUser(updatedUser);
        setTenantId(extractedTenantId);
        void loadTenantAccess(extractedTenantId);

        // Schedule next refresh
        setupTokenRefresh(access_token, mode);
      } catch (err) {
        console.error('Auto-refresh failed:', err);
        // On failure, user will be logged out on next 401
      }
    }, refreshIn * 1000);
  };

  // Switch tenant context (super-admin only)
  const switchTenant = async (targetTenantId: number | null) => {
    console.log('[AuthProvider] Switching tenant:', { from: tenantId, to: targetTenantId });

    if (authMode === 'browser') {
      throw new Error('Tenant switching is not available in browser mode yet');
    }

    try {
      const response = await api.post<AuthResponse>('/auth/switch-tenant', {
        tenant_id: targetTenantId
      });

      const { access_token, refresh_token: newRefreshToken, user: updatedUser } = response.data;

      // Extract tenant_id from new JWT BEFORE updating state
      const payload = parseJwt(access_token);
      const extractedTenantId = payload?.tenant_id !== undefined ? payload.tenant_id : null;

      console.log('[AuthProvider] Tenant switch successful:', {
        requested: targetTenantId,
        jwt_tenant_id: extractedTenantId,
        jwt_payload: payload,
        user: updatedUser.display_name
      });

      // Update tokens
      localStorage.setItem('accessToken', access_token);
      if (newRefreshToken) {
        localStorage.setItem('refreshToken', newRefreshToken);
      }
      cacheUser(updatedUser, authMode);
      api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;

      setUser(updatedUser);
      setTenantId(extractedTenantId);
      void loadTenantAccess(extractedTenantId);

      // Setup new refresh timer
      setupTokenRefresh(access_token, authMode);

      // Reload the page to refresh all data
      console.log('[AuthProvider] Reloading page to apply new tenant context...');
      window.location.reload();
    } catch (err: any) {
      console.error('[AuthProvider] Tenant switch failed:', err);
      throw new Error(err?.response?.data?.detail || 'Failed to switch tenant');
    }
  };

  // Register tutor (creates new school)
  const registerTutor = async (data: TutorRegistrationData) => {
    console.log('[AuthProvider] Registering tutor:', { school_name: data.school_name });

    // Get Telegram init data
    let initData: string | undefined = undefined;

    if (DEV_MODE) {
      initData = DEV_INIT_DATA;
    } else {
      initData = window.Telegram?.WebApp?.initData;
      if (!initData || initData.length === 0) {
        throw new Error('Telegram init data not available');
      }
    }

    try {
      const response = await api.post<AuthResponse>('/auth/register-tutor', data, {
        headers: {
          'X-Telegram-Init-Data': initData,
        },
      });

      const { access_token, refresh_token, user: registeredUser } = response.data;

      // Save tokens
      localStorage.setItem('accessToken', access_token);
      if (refresh_token) {
        localStorage.setItem('refreshToken', refresh_token);
      }
      cacheUser(registeredUser, authMode);
      api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;

      // Extract tenant_id from JWT
      const payload = parseJwt(access_token);
      const extractedTenantId = payload?.tenant_id !== undefined ? payload.tenant_id : null;

      console.log('[AuthProvider] Tutor registration successful:', {
        user: registeredUser.display_name,
        role: registeredUser.role,
        tenant_id: extractedTenantId,
      });

      setUser(registeredUser);
      setTenantId(extractedTenantId);
      void loadTenantAccess(extractedTenantId);

      // Setup auto-refresh
      setupTokenRefresh(access_token, authMode);

      // Reload to apply new context
      window.location.href = '/';
    } catch (error: any) {
      console.error('[AuthProvider] Tutor registration failed:', error);
      throw error;
    }
  };

  // Register student (joins existing school with invite code)
  const registerStudent = async (data: StudentRegistrationData) => {
    console.log('[AuthProvider] Registering student with invite token');

    // Get Telegram init data
    let initData: string | undefined = undefined;

    if (DEV_MODE) {
      initData = DEV_INIT_DATA;
    } else {
      initData = window.Telegram?.WebApp?.initData;
      if (!initData || initData.length === 0) {
        throw new Error('Telegram init data not available');
      }
    }

    try {
      const response = await api.post<AuthResponse>('/auth/register-student', data, {
        headers: {
          'X-Telegram-Init-Data': initData,
        },
      });

      const { access_token, refresh_token, user: registeredUser } = response.data;

      // Save tokens
      localStorage.setItem('accessToken', access_token);
      if (refresh_token) {
        localStorage.setItem('refreshToken', refresh_token);
      }
      cacheUser(registeredUser, authMode);
      api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;

      // Extract tenant_id from JWT
      const payload = parseJwt(access_token);
      const extractedTenantId = payload?.tenant_id !== undefined ? payload.tenant_id : null;

      console.log('[AuthProvider] Student registration successful:', {
        user: registeredUser.display_name,
        role: registeredUser.role,
        tenant_id: extractedTenantId,
      });

      setUser(registeredUser);
      setTenantId(extractedTenantId);
      void loadTenantAccess(extractedTenantId);

      // Setup auto-refresh
      setupTokenRefresh(access_token, authMode);

      // Reload to apply new context
      window.location.href = '/';
    } catch (error: any) {
      console.error('[AuthProvider] Student registration failed:', error);
      throw error;
    }
  };

  const getBrowserErrorMessage = (err: any): string => {
    const detail = err?.response?.data?.detail;
    if (detail?.code === 'USER_NOT_REGISTERED') {
      return 'Пользователь не зарегистрирован. Сначала откройте Mini App в Telegram и завершите регистрацию.';
    }
    if (detail?.code === 'BROWSER_ACCESS_NOT_ALLOWED') {
      return 'Браузерный кабинет пока доступен только преподавателям и администраторам.';
    }
    if (typeof detail === 'string') {
      return detail;
    }
    return err?.message || 'Не удалось войти через Telegram';
  };

  const handleBrowserTelegramAuth = async (payload: TelegramLoginWidgetPayload) => {
    setBrowserLoginError(null);
    setIsBrowserLoginLoading(true);

    try {
      const authResponse = await loginWithTelegramWidget(payload);
      applyAuthenticatedSession(authResponse, 'browser', { persistLegacyTokens: false });
    } catch (err: any) {
      console.error('[AuthProvider] Browser Telegram login failed:', err);
      setBrowserLoginError(getBrowserErrorMessage(err));
      clearAuthState();
    } finally {
      setIsBrowserLoginLoading(false);
    }
  };

  // Logout function
  const logout = () => {
    console.log('[AuthProvider] Logging out');

    // Clear refresh timer
    if (refreshTimerRef.current) {
      window.clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }

    const finishLogout = () => {
      clearAuthState();
      setBrowserRefreshHandler(null);
      window.location.href = '/';
    };

    if (authMode === 'browser') {
      logoutBrowserSession().finally(finishLogout);
      return;
    }

    finishLogout();
  };

  const isSuperAdmin = !!user?.is_platform_admin;
  const canSwitchTenant = isSuperAdmin && authMode !== 'browser';

  const value = {
    isAuthenticated: !!user,
    isLoading,
    user,
    tenantAccess,
    billing,
    tenantId,
    isSuperAdmin,
    canSwitchTenant,
    isTenantAccessLoading,
    isBillingLoading,
    refreshTenantAccess,
    refreshBilling,
    switchTenant,
    registerTutor,
    registerStudent,
    logout,
  };

  if (error) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        padding: '20px',
        textAlign: 'center',
        backgroundColor: '#f5f5f5'
      }}>
        <div style={{
          backgroundColor: 'white',
          padding: '30px',
          borderRadius: '12px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
          maxWidth: '400px'
        }}>
          <pre style={{
            whiteSpace: 'pre-wrap',
            fontSize: '14px',
            lineHeight: '1.6',
            color: '#333',
            margin: 0,
            fontFamily: 'monospace'
          }}>{error}</pre>
          <button
            onClick={() => window.location.reload()}
            style={{
              marginTop: '20px',
              padding: '10px 20px',
              backgroundColor: '#1890ff',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '16px',
              fontWeight: '500'
            }}
          >
            🔄 Reload
          </button>
        </div>
      </div>
    );
  }

  if (authMode === 'browser' && !user && !isLoading) {
    return (
      <BrowserLoginScreen
        error={browserLoginError}
        isSubmitting={isBrowserLoginLoading}
        onTelegramAuth={handleBrowserTelegramAuth}
      />
    );
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};
