import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import AppLayout from '../AppLayout';
import { useAuth } from '../../../auth/AuthProvider';
import { useResponsive } from '../../../hooks/useResponsive';

jest.mock('../../../auth/AuthProvider', () => ({
  useAuth: jest.fn(),
}));

jest.mock('../../../hooks/useResponsive', () => ({
  useResponsive: jest.fn(),
}));

jest.mock('../../../theme/ThemeProvider', () => ({
  useTheme: () => ({
    themeId: 'light',
    resolvedTheme: {
      id: 'light',
      name: 'Light',
      colorScheme: 'light',
      colors: {
        bgPrimary: '#ffffff',
        bgSecondary: '#f7f7f5',
        bgTertiary: '#f0f0ee',
        textPrimary: '#37352f',
        textSecondary: '#6b6b6b',
        textTertiary: '#9b9b9b',
        accentPrimary: '#2383e2',
        accentSuccess: '#0f7b6c',
        accentWarning: '#e16259',
        accentError: '#eb5757',
        accentInfo: '#2383e2',
        borderPrimary: '#e8e8e8',
        borderSecondary: '#f0f0f0',
      },
      previewColors: ['#2383e2', '#0f7b6c', '#37352f', '#f7f7f5', '#ffffff'],
    },
    setThemeId: jest.fn(),
    availableThemes: [],
  }),
}));

jest.mock('../../../navigation/prefetch', () => ({
  prefetchNavigationTarget: jest.fn(() => Promise.resolve()),
  preloadRouteModule: jest.fn(() => Promise.resolve()),
}));

jest.mock('../../common/TenantIndicator', () => () => <div>TenantIndicator</div>);
jest.mock('../../common/TenantSwitcher', () => () => <div>TenantSwitcher</div>);

const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;
const mockUseResponsive = useResponsive as jest.MockedFunction<typeof useResponsive>;

const createQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

describe('AppLayout', () => {
  beforeEach(() => {
    jest.clearAllMocks();

    mockUseResponsive.mockReturnValue({
      isMobile: true,
      isTablet: false,
      isDesktop: false,
      breakpoint: 'xs',
      screens: {} as never,
    });

    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { id: 1, display_name: 'Teacher', role: 'teacher', tenant_id: 1 },
      tenantAccess: null,
      tenantId: 1,
      isSuperAdmin: false,
      canSwitchTenant: false,
      isTenantAccessLoading: false,
      refreshTenantAccess: jest.fn(),
      switchTenant: jest.fn(),
      registerTutor: jest.fn(),
      registerStudent: jest.fn(),
      logout: jest.fn(),
    });
  });

  it('toggles the mobile more drawer when tapping the more button twice', async () => {
    const queryClient = createQueryClient();

    render(
      <MemoryRouter initialEntries={['/']}>
        <QueryClientProvider client={queryClient}>
          <AppLayout>
            <div>Page content</div>
          </AppLayout>
        </QueryClientProvider>
      </MemoryRouter>
    );

    const moreButton = screen.getByRole('button', { name: /navigation\.more/i });
    fireEvent.click(moreButton);

    expect(await screen.findByText('Остальные разделы и настройки кабинета.')).toBeInTheDocument();

    fireEvent.click(moreButton);

    await waitFor(() => {
      expect(screen.queryByText('Остальные разделы и настройки кабинета.')).not.toBeInTheDocument();
    });
  });
});
