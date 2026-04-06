import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Dashboard from '../Dashboard';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

jest.mock('../../services/api', () => ({
  get: jest.fn((url: string) => {
    if (url.includes('/metrics/summary')) {
      return Promise.resolve({
        data: {
          lessons: { scheduled: 2, completed: 3, cancelled: 1, rescheduled: 0 },
          reminders: {},
        },
      });
    }
    if (url.includes('/metrics/lessons/daily')) {
      return Promise.resolve({ data: { items: [{ date: '2024-01-01', value: 2 }] } });
    }
    if (url.includes('/packages')) {
      return Promise.resolve({
        data: {
          total: 1,
          items: [
            {
              id: 1,
              title: 'Active Package',
              learner_name: 'John Doe',
              status: 'active',
              progress: { total: 10, completed: 4, cancelled: 1 },
            },
          ],
        },
      });
    }
    return Promise.resolve({
      data: {
        total: 1,
        items: [
          {
            id: 1,
            package_id: 1,
            learner_name: 'John Doe',
            scheduled_at: '2024-01-15T10:00:00Z',
            status: 'scheduled',
            timezone: 'Europe/Moscow',
          },
        ],
      },
    });
  }),
}));

const createQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

describe('Dashboard', () => {
  it('renders dashboard heading', async () => {
    const queryClient = createQueryClient();
    render(
      <BrowserRouter>
        <QueryClientProvider client={queryClient}>
          <Dashboard />
        </QueryClientProvider>
      </BrowserRouter>
    );
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
  });
});
