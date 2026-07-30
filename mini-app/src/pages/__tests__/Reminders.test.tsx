import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import Reminders from '../Reminders';

jest.mock('../../auth/AuthProvider', () => ({
  useAuth: () => ({ tenantId: 1 }),
}));

// Mock the api module
jest.mock('../../services/api', () => ({
  get: jest.fn((url) => {
    if (url.includes('/packages')) {
      return Promise.resolve({ 
        data: { 
          total: 2, 
          items: [
            { id: 1, title: 'Test Package 1', learner_name: 'John Doe' },
            { id: 2, title: 'Test Package 2', learner_name: 'Jane Smith' }
          ] 
        } 
      });
    }
    return Promise.resolve({ 
      data: { 
        total: 2, 
        items: [
          { 
            id: 1, 
            package_id: 1, 
            lesson_id: 1, 
            reminder_type: 'lesson_reminder', 
            scheduled_for: '2024-01-15T10:00:00Z', 
            status: 'pending', 
            active: true, 
            payload: {}, 
            comment: 'Test reminder' 
          },
          { 
            id: 2, 
            package_id: 2, 
            lesson_id: 2, 
            reminder_type: 'homework_reminder', 
            scheduled_for: '2024-01-16T14:00:00Z', 
            status: 'sent', 
            active: false, 
            payload: {}, 
            comment: null 
          }
        ] 
      } 
    });
  }),
  patch: jest.fn(() => Promise.resolve({ data: { id: 1, status: 'updated' } })),
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
        <Reminders />
      </BrowserRouter>
    </QueryClientProvider>
  );
};

describe('Reminders', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the main heading', async () => {
    renderComponent();
    const heading = await screen.findByRole('heading', { name: 'Reminders' });
    expect(heading).toBeInTheDocument();
  });

  it('renders reminder data in table', async () => {
    renderComponent();

    expect(await screen.findByText((text) => text.includes('2024-01-15'))).toBeInTheDocument();
    expect(await screen.findByText((text) => text.includes('2024-01-16'))).toBeInTheDocument();
  });

  it('shows package information', async () => {
    renderComponent();
    
    expect(await screen.findByText('Test Package 1 (John Doe)')).toBeInTheDocument();
    expect(await screen.findByText('Test Package 2 (Jane Smith)')).toBeInTheDocument();
  });

  it('shows reminder types', async () => {
    renderComponent();
    
    expect(await screen.findByText('LESSON REMINDER')).toBeInTheDocument();
    expect(await screen.findByText('HOMEWORK REMINDER')).toBeInTheDocument();
  });

  it('shows status tags', async () => {
    renderComponent();
    
    expect(await screen.findByText('PENDING')).toBeInTheDocument();
    expect(await screen.findByText('SENT')).toBeInTheDocument();
  });

  it('shows active status', async () => {
    renderComponent();
    
    expect(await screen.findByText('Active')).toBeInTheDocument();
    expect(await screen.findByText('Inactive')).toBeInTheDocument();
  });

  it('renders search input', async () => {
    renderComponent();
    const searchInput = await screen.findByRole('searchbox');
    expect(searchInput).toBeInTheDocument();
  });

  it('renders status filter', async () => {
    renderComponent();
    expect(await screen.findByText('Filter by status')).toBeInTheDocument();
  });

  it('renders package filter', async () => {
    renderComponent();
    expect(await screen.findByText('Filter by package')).toBeInTheDocument();
  });

  it('shows edit buttons', async () => {
    renderComponent();
    
    const editButtons = await screen.findAllByText('Edit');
    expect(editButtons).toHaveLength(2);
  });

  it('opens edit modal when edit button is clicked', async () => {
    renderComponent();
    
    const editButtons = await screen.findAllByText('Edit');
    fireEvent.click(editButtons[0]);
    
    await waitFor(() => {
      expect(screen.getByText('Edit Reminder')).toBeInTheDocument();
    });
  });
});
