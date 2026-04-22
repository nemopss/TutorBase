import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Dashboard from '../Dashboard';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import api from '../../services/api';

const nextLessonAt = new Date(Date.now() + 60 * 60 * 1000).toISOString();

jest.mock('../../auth/AuthProvider', () => ({
  useAuth: () => ({
    tenantId: 1,
  }),
}));

jest.mock('../../services/api', () => ({
  get: jest.fn((url: string) => {
    if (url === '/metrics/dashboard-history') {
      const today = new Date();
      const fromDate = new Date(today);
      fromDate.setMonth(today.getMonth() - 6);
      const weekStart = new Date(today);
      weekStart.setDate(today.getDate() - ((today.getDay() + 6) % 7));
      return Promise.resolve({
        data: {
          heatmap: {
            from_date: fromDate.toISOString().slice(0, 10),
            to_date: today.toISOString().slice(0, 10),
            days: [
              {
                date: today.toISOString().slice(0, 10),
                hours: 2.5,
                lessons_count: 3,
              },
            ],
          },
          weekly_load: {
            from_date: weekStart.toISOString().slice(0, 10),
            to_date: today.toISOString().slice(0, 10),
            weeks: [
              {
                week_start: weekStart.toISOString().slice(0, 10),
                hours: 2.5,
                lessons_count: 3,
              },
            ],
          },
        },
      });
    }
    if (url === '/metrics/dashboard-attention-dismissals') {
      return Promise.resolve({ data: [] });
    }
    if (url === '/notifications/activity') {
      return Promise.resolve({ data: [] });
    }
    if (url === '/notifications/instances') {
      return Promise.resolve({ data: [] });
    }
    if (url.includes('/tenants/')) {
      return Promise.resolve({ data: { total: 1, items: [{}] } });
    }
    if (url.includes('/learners')) {
      return Promise.resolve({ data: { total: 1, items: [] } });
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
            scheduled_at: nextLessonAt,
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
    expect(screen.getByText(/Upcoming lessons/i)).toBeInTheDocument();
    expect(screen.getByText('John Doe')).toBeInTheDocument();
  });

  it('treats missing dashboard attention dismissals endpoint as non-blocking', async () => {
    const mockedApi = api as jest.Mocked<typeof api>;
    mockedApi.get.mockImplementation((url: string) => {
      if (url === '/metrics/dashboard-history') {
        const today = new Date();
        const fromDate = new Date(today);
        fromDate.setMonth(today.getMonth() - 6);
        const weekStart = new Date(today);
        weekStart.setDate(today.getDate() - ((today.getDay() + 6) % 7));
        return Promise.resolve({
          data: {
            heatmap: {
              from_date: fromDate.toISOString().slice(0, 10),
              to_date: today.toISOString().slice(0, 10),
              days: [
                {
                  date: today.toISOString().slice(0, 10),
                  hours: 2.5,
                  lessons_count: 3,
                },
              ],
            },
            weekly_load: {
              from_date: weekStart.toISOString().slice(0, 10),
              to_date: today.toISOString().slice(0, 10),
              weeks: [
                {
                  week_start: weekStart.toISOString().slice(0, 10),
                  hours: 2.5,
                  lessons_count: 3,
                },
              ],
            },
          },
        });
      }
      if (url === '/metrics/dashboard-attention-dismissals') {
        return Promise.reject(new AxiosError('Not Found', 'ERR_BAD_REQUEST', undefined, undefined, {
          status: 404,
          statusText: 'Not Found',
          headers: {},
          config: { headers: {} } as never,
          data: {},
        }));
      }
      if (url === '/notifications/activity') {
        return Promise.resolve({ data: [] });
      }
      if (url === '/notifications/instances') {
        return Promise.resolve({ data: [] });
      }
      if (url.includes('/tenants/')) {
        return Promise.resolve({ data: { total: 1, items: [{}] } });
      }
      if (url.includes('/learners')) {
        return Promise.resolve({ data: { total: 1, items: [] } });
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
              scheduled_at: nextLessonAt,
              status: 'scheduled',
              timezone: 'Europe/Moscow',
            },
          ],
        },
      });
    });

    const queryClient = createQueryClient();
    render(
      <BrowserRouter>
        <QueryClientProvider client={queryClient}>
          <Dashboard />
        </QueryClientProvider>
      </BrowserRouter>
    );

    expect(await screen.findByText(/Active Package/i)).toBeInTheDocument();
  });

  it('renders level 3 historical load tiles', async () => {
    const queryClient = createQueryClient();
    render(
      <BrowserRouter>
        <QueryClientProvider client={queryClient}>
          <Dashboard />
        </QueryClientProvider>
      </BrowserRouter>
    );

    expect(
      await screen.findByText((content) =>
        /Lesson load heatmap/i.test(content) || content.includes('pages.dashboard.level3.heatmap.title'),
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText((content) =>
        /Weekly load/i.test(content) || content.includes('pages.dashboard.level3.weeklyLoad.title'),
      ),
    ).toBeInTheDocument();
  });
});
