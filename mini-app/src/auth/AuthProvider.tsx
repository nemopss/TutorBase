
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

  useEffect(() => {
    const login = async () => {
      try {
        // В реальном приложении initData берется из window.Telegram.WebApp.initData
        // Для разработки можно использовать моковые данные
        const initData = window.Telegram?.WebApp?.initData || 'hash=8aeaa09ed7637cfb1a756d804e26c83ddb05017d54c89582589b9e81090f5968&query_id=AAAAA_BBBB&user=%7B%22id%22%3A352019235%2C%22username%22%3A%22nemopss%22%2C%22first_name%22%3A%22%5Cu0410%5Cu043b%5Cu0435%5Cu043a%5Cu0441%5Cu0435%5Cu0439%22%7D&auth_date=1759771465';

        if (!initData) {
          throw new Error('Telegram initData not found.');
        }

        const response = await api.post<AuthResponse>('/auth/login', { init_data: initData });
        
        const { access_token, refresh_token, user } = response.data;

        // Сохраняем токены (например, в localStorage)
        localStorage.setItem('accessToken', access_token);
        localStorage.setItem('refreshToken', refresh_token);

        // Настраиваем заголовок по умолчанию для всех запросов
        api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;

        setUser(user);
      } catch (error) {
        console.error('Authentication failed:', error);
        setUser(null);
        // Очищаем токены в случае ошибки
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
        delete api.defaults.headers.common['Authorization'];
      } finally {
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

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};
