import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import Packages from '../Packages';
import { useAuth } from '../../auth/AuthProvider';

// Mock the api module
jest.mock('../../services/api', () => ({
  get: jest.fn(() => Promise.resolve({ 
    data: { 
      total: 2, 
      items: [
        { id: 1, title: 'Test Package 1', learner_name: 'John Doe', status: 'active', progress: { total: 10, completed: 5, cancelled: 0 } },
        { id: 2, title: 'Test Package 2', learner_name: 'Jane Smith', status: 'draft', progress: { total: 8, completed: 0, cancelled: 1 } }
      ] 
    } 
  })),
  post: jest.fn(() => Promise.resolve({ data: { id: 3, title: 'New Package' } })),
  patch: jest.fn(() => Promise.resolve({ data: { id: 1, title: 'Updated Package' } })),
}));

// Mock the useDebounce hook
jest.mock('../../hooks/useDebounce', () => ({
  useDebounce: (value: any) => value,
}));

jest.mock('../../auth/AuthProvider', () => ({
  useAuth: jest.fn(),
}));

const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

const renderComponent = () => {
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Packages />
      </BrowserRouter>
    </QueryClientProvider>
  );
};

describe('Packages', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { id: 1, display_name: 'Admin', role: 'admin', tenant_id: 1 },
      tenantId: 1,
      tenantAccess: null,
      billing: null,
      isTenantAccessLoading: false,
      isBillingLoading: false,
      isSuperAdmin: false,
      canSwitchTenant: false,
      refreshTenantAccess: jest.fn(),
      refreshBilling: jest.fn(),
      switchTenant: jest.fn(),
      registerTutor: jest.fn(),
      registerStudent: jest.fn(),
      logout: jest.fn(),
    });
  });

  it('renders the main heading', async () => {
    renderComponent();
    const heading = await screen.findByRole('heading', { name: 'Lesson Packages' });
    expect(heading).toBeInTheDocument();
  });

  it('renders package data in table', async () => {
    renderComponent();
    
    expect(await screen.findByText('Test Package 1')).toBeInTheDocument();
    expect(await screen.findByText('Test Package 2')).toBeInTheDocument();
    expect(await screen.findByText('John Doe')).toBeInTheDocument();
    expect(await screen.findByText('Jane Smith')).toBeInTheDocument();
  });

  it('shows create package button', async () => {
    renderComponent();
    const createButton = await screen.findByRole('button', { name: /plus/i });
    expect(createButton).toBeInTheDocument();
  });

  it('opens create package modal when button is clicked', async () => {
    renderComponent();
    
    const createButton = await screen.findByRole('button', { name: /plus/i });
    fireEvent.click(createButton);
    
    await waitFor(() => {
      expect(screen.getByText('Create New Package')).toBeInTheDocument();
    });
  });

  it('renders search input', async () => {
    renderComponent();
    expect(await screen.findByRole('tab', { name: 'ACTIVE' })).toBeInTheDocument();
  });

  it('renders status filter', async () => {
    renderComponent();
    expect(await screen.findByRole('tab', { name: 'DRAFT' })).toBeInTheDocument();
  });

  it('does not duplicate package statuses inside cards', async () => {
    renderComponent();

    expect((await screen.findAllByText('ACTIVE')).length).toBe(1);
    expect((await screen.findAllByText('DRAFT')).length).toBe(1);
  });

  it('shows progress information', async () => {
    renderComponent();
    
    expect(await screen.findByText('5/10 lessons')).toBeInTheDocument();
    expect(await screen.findByText('1/8 lessons')).toBeInTheDocument();
  });
});
