import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import Groups from '../Groups';
import { useAuth } from '../../auth/AuthProvider';

const translations: Record<string, string> = {
  'pages.groups.title': 'Groups',
  'pages.groups.subtitle': 'Learner groups',
  'pages.groups.noticeTitle': 'Future-ready groups',
  'pages.groups.noticeDescription': 'Groups are notification audiences.',
  'pages.groups.createGroup': 'Create group',
  'pages.groups.statuses.active': 'Active',
  'pages.groups.archive': 'Archive',
  'common.tenantContextRequired.title': 'Choose a school first',
  'common.tenantContextRequired.description': 'The Groups section works only inside a selected school context.',
  'common.tenantContextRequired.globalContextNotice': 'You are currently in the global view without a selected school.',
  'common.tenantContextRequired.switchHint': 'Select a school with the tenant switcher in the menu, then open this section again.',
};

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => translations[key] ?? key,
  }),
}));

const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;
const mockGet = jest.fn((url: string, _config?: unknown) => {
    if (url === '/groups') {
      return Promise.resolve({
        data: [
          {
            id: 1,
            name: 'TOPIK group',
            description: 'Exam prep',
            color: '#1677ff',
            status: 'active',
            member_count: 1,
            members: [{ learner_id: 10, display_name: 'Vika', status: 'active' }],
          },
        ],
      });
    }

    if (url === '/learners') {
      return Promise.resolve({
        data: { items: [{ id: 10, display_name: 'Vika' }] },
      });
    }

    return Promise.resolve({ data: [] });
  });

jest.mock('../../auth/AuthProvider', () => ({
  useAuth: jest.fn(),
}));

jest.mock('../../services/api', () => ({
  get: (url: string, config?: unknown) => mockGet(url, config),
  post: jest.fn(() => Promise.resolve({ data: {} })),
  patch: jest.fn(() => Promise.resolve({ data: {} })),
  delete: jest.fn(() => Promise.resolve({ data: {} })),
}));

const renderComponent = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Groups />
      </BrowserRouter>
    </QueryClientProvider>
  );
};

describe('Groups', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { id: 1, display_name: 'Admin', role: 'admin', tenant_id: 1 },
      tenantId: 1,
      tenantAccess: null,
      isTenantAccessLoading: false,
      isSuperAdmin: true,
      canSwitchTenant: true,
      refreshTenantAccess: jest.fn(),
      switchTenant: jest.fn(),
      registerTutor: jest.fn(),
      registerStudent: jest.fn(),
      logout: jest.fn(),
    });
  });

  it('renders group data', async () => {
    renderComponent();

    expect(await screen.findByText('Groups')).toBeInTheDocument();
    expect(await screen.findByText('TOPIK group')).toBeInTheDocument();
    expect(await screen.findByText('Vika')).toBeInTheDocument();
  });

  it('opens create group modal', async () => {
    renderComponent();

    fireEvent.click(await screen.findByText('Create group'));

    await waitFor(() => {
      expect(screen.getAllByText('Create group').length).toBeGreaterThan(1);
    });
  });

  it('shows tenant selection prompt in global super-admin context without loading groups', async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { id: 1, display_name: 'Admin', role: 'admin', tenant_id: null },
      tenantId: null,
      tenantAccess: null,
      isTenantAccessLoading: false,
      isSuperAdmin: true,
      canSwitchTenant: true,
      refreshTenantAccess: jest.fn(),
      switchTenant: jest.fn(),
      registerTutor: jest.fn(),
      registerStudent: jest.fn(),
      logout: jest.fn(),
    });

    renderComponent();

    expect(await screen.findByText('Choose a school first')).toBeInTheDocument();
    expect(screen.getByText('The Groups section works only inside a selected school context.')).toBeInTheDocument();
    expect(mockGet).not.toHaveBeenCalled();
  });
});
