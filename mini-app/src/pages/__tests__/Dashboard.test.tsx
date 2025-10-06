import React from 'react';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Dashboard from '../Dashboard';

// Mock the api module
jest.mock('../../services/api', () => ({
  get: jest.fn(() => Promise.resolve({ data: { lessons: {}, reminders: {} } })),
}));

const queryClient = new QueryClient();

const renderComponent = () => {
  return render(
    <QueryClientProvider client={queryClient}>
      <Dashboard />
    </QueryClientProvider>
  );
};

describe('Dashboard', () => {
  it('renders the main heading', async () => {
    renderComponent();
    // Use findByText for async elements
    const heading = await screen.findByText(/Dashboard/i);
    expect(heading).toBeInTheDocument();
  });

  it('renders lesson statistics cards', async () => {
    renderComponent();
    expect(await screen.findByText(/Total Lessons/i)).toBeInTheDocument();
    expect(await screen.findByText(/Completed/i)).toBeInTheDocument();
    expect(await screen.findByText(/Cancelled/i)).toBeInTheDocument();
  });
});
