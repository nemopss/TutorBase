import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from '../AuthProvider';

// Mock the api module
jest.mock('../../services/api', () => ({
  post: jest.fn(() => Promise.resolve({ 
    data: { 
      access_token: 'test-access-token', 
      refresh_token: 'test-refresh-token', 
      user: { id: 1, display_name: 'Test User', role: 'teacher' } 
    } 
  })),
  defaults: {
    headers: {
      common: {}
    }
  }
}));

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};
Object.defineProperty(window, 'localStorage', {
  value: localStorageMock
});

// Mock Telegram WebApp
const mockTelegramWebApp = {
  initData: 'test-init-data',
  initDataUnsafe: {
    user: { id: 123, username: 'testuser', first_name: 'Test' }
  }
};

Object.defineProperty(window, 'Telegram', {
  value: {
    WebApp: mockTelegramWebApp
  },
  writable: true
});

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

// Test component that uses the auth context
const TestComponent = () => {
  const { isAuthenticated, isLoading, user } = useAuth();
  
  if (isLoading) {
    return <div>Loading...</div>;
  }
  
  if (!isAuthenticated) {
    return <div>Not authenticated</div>;
  }
  
  return <div>Welcome, {user?.display_name}!</div>;
};

const renderComponent = () => {
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    </QueryClientProvider>
  );
};

describe('AuthProvider', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorageMock.getItem.mockReturnValue(null);
  });

  it('shows loading state initially', () => {
    renderComponent();
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('authenticates user successfully', async () => {
    renderComponent();
    
    await waitFor(() => {
      expect(screen.getByText('Welcome, Test User!')).toBeInTheDocument();
    });
  });

  it('stores tokens in localStorage', async () => {
    renderComponent();
    
    await waitFor(() => {
      expect(localStorageMock.setItem).toHaveBeenCalledWith('accessToken', 'test-access-token');
      expect(localStorageMock.setItem).toHaveBeenCalledWith('refreshToken', 'test-refresh-token');
    });
  });

  it('sets authorization header', async () => {
    const api = require('../../services/api').default;
    renderComponent();
    
    await waitFor(() => {
      expect(api.defaults.headers.common['Authorization']).toBe('Bearer test-access-token');
    });
  });
});

describe('useAuth hook', () => {
  it('throws error when used outside AuthProvider', () => {
    const TestComponent = () => {
      useAuth();
      return <div>Test</div>;
    };

    // Suppress console.error for this test
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    
    expect(() => {
      render(<TestComponent />);
    }).toThrow('useAuth must be used within an AuthProvider');
    
    consoleSpy.mockRestore();
  });
});
