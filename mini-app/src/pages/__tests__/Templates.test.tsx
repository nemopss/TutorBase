import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import Templates from '../Templates';

// Mock the api module
jest.mock('../../services/api', () => ({
  get: jest.fn(() => Promise.resolve({ 
    data: { 
      total: 2, 
      items: [
        { id: 1, name: 'Basic Template', description: 'A basic lesson template', lesson_count: 10, duration_days: 30 },
        { id: 2, name: 'Advanced Template', description: 'An advanced lesson template', lesson_count: 20, duration_days: 60 }
      ] 
    } 
  })),
  post: jest.fn(() => Promise.resolve({ data: { id: 3, name: 'New Template' } })),
  patch: jest.fn(() => Promise.resolve({ data: { id: 1, name: 'Updated Template' } })),
  delete: jest.fn(() => Promise.resolve()),
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
        <Templates />
      </BrowserRouter>
    </QueryClientProvider>
  );
};

describe('Templates', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the main heading', async () => {
    renderComponent();
    const heading = await screen.findByRole('heading', { name: 'Templates' });
    expect(heading).toBeInTheDocument();
  });

  it('renders template data in table', async () => {
    renderComponent();
    
    expect(await screen.findByText('Basic Template')).toBeInTheDocument();
    expect(await screen.findByText('Advanced Template')).toBeInTheDocument();
    expect(await screen.findByText('A basic lesson template')).toBeInTheDocument();
    expect(await screen.findByText('An advanced lesson template')).toBeInTheDocument();
  });

  it('shows create template button', async () => {
    renderComponent();
    const createButton = await screen.findByText('Create Template');
    expect(createButton).toBeInTheDocument();
  });

  it('opens create template modal when button is clicked', async () => {
    renderComponent();
    
    const createButton = await screen.findByText('Create Template');
    fireEvent.click(createButton);
    
    await waitFor(() => {
      expect(screen.getByText('Create New Template')).toBeInTheDocument();
    });
  });

  it('shows lesson count and duration', async () => {
    renderComponent();
    
    expect(await screen.findByText('10 lessons')).toBeInTheDocument();
    expect(await screen.findByText('20 lessons')).toBeInTheDocument();
    expect(await screen.findByText('30 days')).toBeInTheDocument();
    expect(await screen.findByText('60 days')).toBeInTheDocument();
  });

  it('shows action buttons for each template', async () => {
    renderComponent();
    
    const editButtons = await screen.findAllByText('Edit');
    const duplicateButtons = await screen.findAllByText('Copy');
    const deleteButtons = await screen.findAllByText('Delete');
    
    expect(editButtons).toHaveLength(2);
    expect(duplicateButtons).toHaveLength(2);
    expect(deleteButtons).toHaveLength(2);
  });
});
