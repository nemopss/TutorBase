import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from '../AuthProvider';
import apiClient, {
  setAuthFailureHandler as authFailureHandlerSetter,
  setBrowserRefreshHandler as browserRefreshHandlerSetter,
} from '../../services/api';

// Mock the api module
jest.mock('../../services/api', () => ({
  __esModule: true,
  setBrowserRefreshHandler: jest.fn(),
  setAuthFailureHandler: jest.fn(),
  default: {
    get: jest.fn(() => Promise.resolve({ data: null })),
    post: jest.fn(),
    defaults: {
      headers: {
        common: {} as Record<string, string>,
      },
    },
  },
}));

const api = apiClient as unknown as {
  get: jest.Mock;
  post: jest.Mock;
  defaults: { headers: { common: Record<string, string> } };
};
const setBrowserRefreshHandler = browserRefreshHandlerSetter as jest.Mock;
const setAuthFailureHandler = authFailureHandlerSetter as jest.Mock;

const postMock = api.post;
const validAccessToken = 'eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJleHAiOjQxMDI0NDQ4MDAsInRlbmFudF9pZCI6MSwicm9sZSI6InRlYWNoZXIifQ.sig';

const defaultAuthResponse = {
  data: {
    access_token: validAccessToken,
    refresh_token: 'test-refresh-token',
    user: { id: 1, display_name: 'Test User', role: 'teacher' },
  },
};

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

const sessionStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};
Object.defineProperty(window, 'sessionStorage', {
  value: sessionStorageMock
});

// Mock Telegram WebApp
const mockTelegramWebApp = {
  initData: 'test-init-data',
  initDataUnsafe: {
    user: { id: 123, username: 'testuser', first_name: 'Test' }
  },
  ready: jest.fn(),
  expand: jest.fn(),
  enableClosingConfirmation: jest.fn(),
  setHeaderColor: jest.fn(),
  setBackgroundColor: jest.fn(),
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
  const { isAuthenticated, isLoading, user, switchTenant } = useAuth();
  
  if (isLoading) {
    return <div>Loading...</div>;
  }
  
  if (!isAuthenticated) {
    return <div>Not authenticated</div>;
  }
  
  return (
    <div>
      Welcome, {user?.display_name}!
      <button type="button" onClick={() => void switchTenant(2)}>Switch tenant</button>
    </div>
  );
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
    postMock.mockImplementation((url: string) => {
      if (url === '/auth/session/refresh') {
        return Promise.reject({ response: { status: 401 } });
      }
      return Promise.resolve(defaultAuthResponse);
    });
    setBrowserRefreshHandler.mockImplementation(() => undefined);
    setAuthFailureHandler.mockImplementation(() => undefined);
    queryClient.clear();
    localStorageMock.getItem.mockReturnValue(null);
    sessionStorageMock.getItem.mockReturnValue(null);
    window.Telegram = { WebApp: mockTelegramWebApp } as any;
    Object.keys(api.defaults.headers.common).forEach((key) => delete api.defaults.headers.common[key]);
  });

  it('shows loading state initially', () => {
    postMock.mockImplementation(() => new Promise(() => undefined));
    renderComponent();
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('authenticates user successfully', async () => {
    renderComponent();
    
    await waitFor(() => {
      expect(screen.getByText('Welcome, Test User!')).toBeInTheDocument();
    });
  });

  it('does not store new telegram session tokens in localStorage', async () => {
    renderComponent();
    
    await waitFor(() => {
      expect(screen.getByText('Welcome, Test User!')).toBeInTheDocument();
    });

    expect(localStorageMock.setItem).not.toHaveBeenCalledWith('accessToken', expect.anything());
    expect(localStorageMock.setItem).not.toHaveBeenCalledWith('refreshToken', expect.anything());
    expect(sessionStorageMock.setItem).not.toHaveBeenCalledWith('authUser', expect.any(String));
  });

  it('sets authorization header', async () => {
    const api = require('../../services/api').default;
    renderComponent();
    
    await waitFor(() => {
      expect(api.defaults.headers.common['Authorization']).toBe(`Bearer ${validAccessToken}`);
    });
  });

  it('clears tenant-scoped query cache when switching tenant', async () => {
    renderComponent();
    await screen.findByText('Welcome, Test User!');
    queryClient.setQueryData(['learners'], { items: [{ id: 1 }] });

    fireEvent.click(screen.getByRole('button', { name: 'Switch tenant' }));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith(
        '/auth/switch-tenant',
        { tenant_id: 2 },
        { withCredentials: true },
      );
      expect(queryClient.getQueryData(['learners'])).toBeUndefined();
    });
  });

  it('clears the live authenticated UI after refresh failure', async () => {
    let authFailureHandler: (() => void) | null = null;
    setAuthFailureHandler.mockImplementation((handler: (() => void) | null) => {
      authFailureHandler = handler;
    });
    renderComponent();
    await screen.findByText('Welcome, Test User!');

    act(() => authFailureHandler?.());

    expect(await screen.findByText('Not authenticated')).toBeInTheDocument();
  });

  it('restores browser sessions without writing tokens to localStorage', async () => {
    (window as any).Telegram = undefined;

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Welcome, Test User!')).toBeInTheDocument();
    });

    expect(postMock).toHaveBeenCalledWith('/auth/browser/refresh', undefined, {
      withCredentials: true,
    });
    expect(localStorageMock.setItem).not.toHaveBeenCalledWith('accessToken', expect.anything());
    expect(localStorageMock.setItem).not.toHaveBeenCalledWith('refreshToken', expect.anything());
    expect(localStorageMock.setItem).not.toHaveBeenCalledWith('authUser', expect.any(String));
    expect(sessionStorageMock.setItem).toHaveBeenCalledWith('authUser', expect.any(String));
    expect(api.defaults.headers.common['Authorization']).toBe(`Bearer ${validAccessToken}`);
  });

  it('restores telegram sessions from cookie before legacy localStorage', async () => {
    postMock.mockImplementation((url: string) => {
      if (url === '/auth/session/refresh') {
        return Promise.resolve(defaultAuthResponse);
      }
      return Promise.resolve(defaultAuthResponse);
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Welcome, Test User!')).toBeInTheDocument();
    });

    expect(postMock).toHaveBeenCalledWith('/auth/session/refresh', undefined, {
      withCredentials: true,
    });
    expect(postMock).not.toHaveBeenCalledWith(
      '/auth/login',
      expect.anything(),
      expect.anything()
    );
    expect(localStorageMock.setItem).not.toHaveBeenCalledWith('accessToken', expect.anything());
    expect(localStorageMock.setItem).not.toHaveBeenCalledWith('refreshToken', expect.anything());
  });

  it('migrates legacy telegram localStorage refresh into cookie session', async () => {
    localStorageMock.getItem.mockImplementation((key: string) => {
      if (key === 'accessToken') return validAccessToken;
      if (key === 'refreshToken') return 'legacy-refresh-token';
      return null;
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Welcome, Test User!')).toBeInTheDocument();
    });

    expect(postMock).toHaveBeenCalledWith('/auth/refresh', {
      refresh_token: 'legacy-refresh-token',
    }, {
      withCredentials: true,
    });
    expect(localStorageMock.removeItem).toHaveBeenCalledWith('accessToken');
    expect(localStorageMock.removeItem).toHaveBeenCalledWith('refreshToken');
    expect(localStorageMock.setItem).not.toHaveBeenCalledWith('accessToken', expect.anything());
    expect(localStorageMock.setItem).not.toHaveBeenCalledWith('refreshToken', expect.anything());
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
