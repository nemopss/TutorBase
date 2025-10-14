
import React, { createContext, useState, useEffect, useContext, useRef } from 'react';
import type { PropsWithChildren } from 'react';
import api from '../services/api';

const DEV_MODE = import.meta.env.VITE_DEV_MODE === 'true';
const DEV_INIT_DATA = import.meta.env.VITE_DEV_INIT_DATA ?? 'dev';

// Decode JWT token to get expiration time
const parseJwt = (token: string): { exp?: number } | null => {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      window.atob(base64).split('').map(c => 
        '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)
      ).join('')
    );
    return JSON.parse(jsonPayload);
  } catch (e) {
    return null;
  }
};

// Предполагаемые типы для данных пользователя и ответа от API
interface User {
  id: number;
  display_name: string;
  role: string;
}

interface AuthResponse {
  access_token: string;
  refresh_token: string;
  user: User;
}

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | null;
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
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const refreshTimerRef = useRef<number | null>(null);

  useEffect(() => {
    const login = async () => {
      try {
        let initData: string | undefined = undefined;

        if (DEV_MODE) {
          initData = DEV_INIT_DATA;
        } else {
          // Initialize Telegram WebApp
          if (window.Telegram?.WebApp) {
            window.Telegram.WebApp.ready();
            window.Telegram.WebApp.expand();
          }

          initData = window.Telegram?.WebApp?.initData;

          if (!initData || initData.length === 0) {
            const debugInfo = [
              '⚠️ Please open this app from Telegram bot.',
              '',
              'Debug Info:',
              `• Telegram object: ${window.Telegram ? 'Found' : 'Not found'}`,
              `• WebApp object: ${window.Telegram?.WebApp ? 'Found' : 'Not found'}`,
              `• InitData: ${initData ? `"${initData.substring(0, 50)}..."` : 'Empty'}`,
              `• InitData length: ${initData?.length || 0}`,
            ].join('\n');

            setError(debugInfo);
            setIsLoading(false);
            return;
          }
        }

        const response = await api.post<AuthResponse>('/auth/login', { init_data: initData });

        const { access_token, refresh_token, user } = response.data;

        // Сохраняем токены (например, в localStorage)
        localStorage.setItem('accessToken', access_token);
        localStorage.setItem('refreshToken', refresh_token);

        // Настраиваем заголовок по умолчанию для всех запросов
        api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;

        setUser(user);
        setIsLoading(false);
        
        // Setup auto-refresh 5 minutes before expiration
        setupTokenRefresh(access_token);
      } catch (err: any) {
        console.error('Authentication failed:', err);
        const errorMsg = err?.response?.data?.detail || err?.message || 'Authentication failed';
        setError('❌ Authentication Error\n\n' + errorMsg);
        setUser(null);
        // Очищаем токены в случае ошибки
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
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
    };
  }, []);
  
  // Auto-refresh token before expiration
  const setupTokenRefresh = (accessToken: string) => {
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
        const refreshToken = localStorage.getItem('refreshToken');
        if (!refreshToken) return;
        
        const response = await api.post<AuthResponse>('/auth/refresh', {
          refresh_token: refreshToken
        });
        
        const { access_token, refresh_token: newRefreshToken, user: updatedUser } = response.data;
        
        localStorage.setItem('accessToken', access_token);
        localStorage.setItem('refreshToken', newRefreshToken);
        api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
        
        setUser(updatedUser);
        
        // Schedule next refresh
        setupTokenRefresh(access_token);
      } catch (err) {
        console.error('Auto-refresh failed:', err);
        // On failure, user will be logged out on next 401
      }
    }, refreshIn * 1000);
  };

  const value = {
    isAuthenticated: !!user,
    isLoading,
    user,
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

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};
