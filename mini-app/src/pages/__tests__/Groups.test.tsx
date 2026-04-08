import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import Groups from '../Groups';

const translations: Record<string, string> = {
  'pages.groups.title': 'Groups',
  'pages.groups.subtitle': 'Learner groups',
  'pages.groups.noticeTitle': 'Future-ready groups',
  'pages.groups.noticeDescription': 'Groups are notification audiences.',
  'pages.groups.createGroup': 'Create group',
  'pages.groups.statuses.active': 'Active',
  'pages.groups.archive': 'Archive',
};

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => translations[key] ?? key,
  }),
}));

jest.mock('../../services/api', () => ({
  get: jest.fn((url: string) => {
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
  }),
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
});
