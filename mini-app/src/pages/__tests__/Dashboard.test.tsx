import { act, render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Dashboard from '../Dashboard';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import api from '../../services/api';

const nextLessonAt = new Date(Date.now() + 60 * 60 * 1000).toISOString();
const mockUseAuth = jest.fn();

jest.mock('../../auth/AuthProvider', () => ({
  useAuth: () => mockUseAuth(),
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
  beforeEach(() => {
    mockUseAuth.mockReturnValue({
      tenantId: 1,
      canSwitchTenant: false,
    });
  });

  it('renders dashboard content without the page header', async () => {
    const queryClient = createQueryClient();
    render(
      <BrowserRouter>
        <QueryClientProvider client={queryClient}>
          <Dashboard />
        </QueryClientProvider>
      </BrowserRouter>
    );

    expect(await screen.findByText(/Upcoming lessons/i)).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Dashboard' })).not.toBeInTheDocument();
    expect(await screen.findByText('John Doe')).toBeInTheDocument();
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

  it('does not show onboarding until onboarding checks finish loading', async () => {
    let resolveLearners: ((value: { data: { total: number; items: unknown[] } }) => void) | null = null;
    const learnersPromise = new Promise<{ data: { total: number; items: unknown[] } }>((resolve) => {
      resolveLearners = resolve;
    });

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
        return learnersPromise;
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

    expect(await screen.findByText(/Upcoming lessons/i)).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Dashboard' })).not.toBeInTheDocument();
    expect(screen.queryByText('pages.dashboard.onboarding.title')).not.toBeInTheDocument();

    await act(async () => {
      resolveLearners?.({ data: { total: 0, items: [] } });
      await learnersPromise;
    });

    expect(await screen.findByText('pages.dashboard.onboarding.title')).toBeInTheDocument();
  });

  it('requires tenant context in global owner mode', async () => {
    mockUseAuth.mockReturnValue({
      tenantId: null,
      canSwitchTenant: true,
    });

    const queryClient = createQueryClient();
    render(
      <BrowserRouter>
        <QueryClientProvider client={queryClient}>
          <Dashboard />
        </QueryClientProvider>
      </BrowserRouter>
    );

    expect(await screen.findByText('common.tenantContextRequired.title')).toBeInTheDocument();
    expect(screen.getByText('common.tenantContextRequired.description')).toBeInTheDocument();
    expect(screen.queryByText(/Upcoming lessons/i)).not.toBeInTheDocument();
  });
});
