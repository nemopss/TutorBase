import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import Learners from '../Learners';
import { useAuth } from '../../auth/AuthProvider';

const translations: Record<string, string> = {
  'pages.learners.title': 'Learners',
  'pages.learners.subtitle': 'Manage learners',
  'pages.learners.activeTab': 'Active',
  'pages.learners.archivedTab': 'Archive',
  'pages.learners.archiveAction': 'Archive learner',
  'pages.learners.restoreAction': 'Restore learner',
  'pages.learners.noArchivedLearners': 'No archived learners',
  'pages.learners.notificationsOn': 'Notifications on',
  'pages.learners.notificationsOff': 'Notifications off',
  'pages.learners.archivedNotificationsOff': 'Notifications off for archived learners',
  'pages.learners.enabled': 'Enabled',
  'pages.learners.disabled': 'Disabled',
  'common.search': 'Search',
  'common.copyChatId': 'Copy chat ID',
  'common.edit': 'Edit',
  'common.delete': 'Delete',
};

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: { defaultValue?: string }) => translations[key] ?? options?.defaultValue ?? key,
  }),
}));

jest.mock('../../auth/AuthProvider', () => ({
  useAuth: jest.fn(),
}));

jest.mock('../../services/api', () => ({
  get: jest.fn((url: string, config?: { params?: Record<string, string> }) => {
    if (url === '/learners') {
      const status = config?.params?.status;
      const mixedItems = [
        {
          id: 1,
          display_name: 'Active Student',
          notifications_enabled: true,
          chat_id: 1001,
          is_archived: false,
          archived_at: null,
          next_lesson_date: null,
        },
        {
          id: 2,
          display_name: 'Archived Student',
          notifications_enabled: false,
          chat_id: 1002,
          is_archived: true,
          archived_at: '2026-04-21T12:00:00Z',
          next_lesson_date: null,
        },
      ];

      return Promise.resolve({
        data: {
          items: status === 'archived' ? mixedItems : mixedItems,
        },
      });
    }
    return Promise.resolve({ data: {} });
  }),
  post: jest.fn(() => Promise.resolve({ data: {} })),
  patch: jest.fn(() => Promise.resolve({ data: {} })),
  delete: jest.fn(() => Promise.resolve({ data: {} })),
}));

const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;

const renderComponent = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Learners />
      </BrowserRouter>
    </QueryClientProvider>
  );
};

describe('Learners', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { id: 1, display_name: 'Admin', role: 'admin', tenant_id: 1 },
      tenantId: 1,
      isSuperAdmin: false,
      canSwitchTenant: false,
      tenantAccess: {
        tenant_id: 1,
        status: 'active',
        mode: 'full',
        bypass_access_restrictions: false,
        is_lifetime: false,
      },
      isTenantAccessLoading: false,
      refreshTenantAccess: jest.fn(),
      switchTenant: jest.fn(),
      registerTutor: jest.fn(),
      registerStudent: jest.fn(),
      logout: jest.fn(),
    });
  });

  it('keeps active and archived learner tabs separated even if the API returns a mixed list', async () => {
    renderComponent();

    expect(await screen.findByText('Active Student')).toBeInTheDocument();
    expect(screen.queryByText('Archived Student')).not.toBeInTheDocument();

    fireEvent.click(screen.getByText('Archive'));

    await waitFor(() => {
      expect(screen.getByText('Archived Student')).toBeInTheDocument();
    });
    expect(screen.queryByText('Active Student')).not.toBeInTheDocument();
  });
});
