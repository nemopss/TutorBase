import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import Packages from '../Packages';

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
  });

  it('renders the main heading', async () => {
    renderComponent();
    const heading = await screen.findByText(/Lesson Packages/i);
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
    const createButton = await screen.findByText('Create Package');
    expect(createButton).toBeInTheDocument();
  });

  it('opens create package modal when button is clicked', async () => {
    renderComponent();
    
    const createButton = await screen.findByText('Create Package');
    fireEvent.click(createButton);
    
    await waitFor(() => {
      expect(screen.getByText('Create New Package')).toBeInTheDocument();
    });
  });

  it('renders search input', async () => {
    renderComponent();
    const searchInput = await screen.findByPlaceholderText('Search by title or learner');
    expect(searchInput).toBeInTheDocument();
  });

  it('renders status filter', async () => {
    renderComponent();
    const statusFilter = await screen.findByPlaceholderText('Filter by status');
    expect(statusFilter).toBeInTheDocument();
  });

  it('shows package status tags', async () => {
    renderComponent();
    
    expect(await screen.findByText('ACTIVE')).toBeInTheDocument();
    expect(await screen.findByText('DRAFT')).toBeInTheDocument();
  });

  it('shows progress information', async () => {
    renderComponent();
    
    expect(await screen.findByText('5 / 10')).toBeInTheDocument();
    expect(await screen.findByText('0 / 8')).toBeInTheDocument();
  });
});
