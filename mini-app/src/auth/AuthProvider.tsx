
import React, { createContext, useState, useEffect, useContext } from 'react';
import type { PropsWithChildren } from 'react';
import api from '../services/api';

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

  useEffect(() => {
    const login = async () => {
      try {
        // Initialize Telegram WebApp
        if (window.Telegram?.WebApp) {
          window.Telegram.WebApp.ready();
          window.Telegram.WebApp.expand();
        }

        // Get initData from Telegram WebApp
        const initData = window.Telegram?.WebApp?.initData;

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

        const response = await api.post<AuthResponse>('/auth/login', { init_data: initData });
        
        const { access_token, refresh_token, user } = response.data;

        // Сохраняем токены (например, в localStorage)
        localStorage.setItem('accessToken', access_token);
        localStorage.setItem('refreshToken', refresh_token);

        // Настраиваем заголовок по умолчанию для всех запросов
        api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;

        setUser(user);
        setIsLoading(false);
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
  }, []);

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
