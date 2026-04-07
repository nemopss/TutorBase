import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import Notifications from '../Notifications';

const translations: Record<string, string> = {
  'pages.notifications.title': 'Notifications',
  'pages.notifications.subtitle': 'New notification system',
  'pages.notifications.pilotNoticeTitle': 'Pilot mode',
  'pages.notifications.pilotNoticeDescription': 'Testing notification system',
  'pages.notifications.tabs.rules': 'Rules',
  'pages.notifications.tabs.templates': 'Templates',
  'pages.notifications.tabs.queue': 'Queue',
  'pages.notifications.tabs.activity': 'Activity',
  'pages.notifications.tabs.settings': 'Settings',
  'pages.notifications.categories.lesson_confirmation': 'Lesson confirmation',
  'pages.notifications.categories.custom': 'Custom',
  'pages.notifications.createRuleWizard': 'Create rule',
  'pages.notifications.ruleWizard.title': 'Create notification rule',
  'navigation.newBadge': 'NEW',
};

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => translations[key] ?? key,
  }),
}));

jest.mock('../../services/api', () => ({
  get: jest.fn((url: string) => {
    if (url === '/notifications/rules') {
      return Promise.resolve({
        data: [
          {
            id: 1,
            name: 'Lesson confirmation',
            category: 'lesson_confirmation',
            event_type: 'lesson',
            trigger_type: 'day_offset_at_time',
            trigger_config: {},
            priority: 'normal',
            status: 'draft',
            assignments: [{ scope_type: 'all_learners', scope_id: null, is_exclusion: false }],
          },
        ],
      });
    }

    if (url === '/notifications/templates') {
      return Promise.resolve({
        data: [
          {
            id: 1,
            category: 'lesson_confirmation',
            key: 'lesson_confirmation_test',
            name: 'Lesson confirmation template',
            body: 'Hello {student_name}',
            locale: 'ru',
            version: 1,
            system: false,
            archived_at: null,
          },
        ],
      });
    }

    if (url === '/learners') {
      return Promise.resolve({ data: { items: [{ id: 10, display_name: 'Vika' }] } });
    }

    if (url === '/groups') {
      return Promise.resolve({ data: [] });
    }

    if (url === '/packages') {
      return Promise.resolve({ data: { items: [] } });
    }

    return Promise.resolve({ data: [] });
  }),
  post: jest.fn(() => Promise.resolve({ data: {} })),
  patch: jest.fn(() => Promise.resolve({ data: {} })),
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
        <Notifications />
      </BrowserRouter>
    </QueryClientProvider>
  );
};

describe('Notifications', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders rules tab data', async () => {
    renderComponent();

    expect(await screen.findByText('Notifications')).toBeInTheDocument();
    expect((await screen.findAllByText('Lesson confirmation')).length).toBeGreaterThan(0);
  });

  it('loads templates tab data', async () => {
    renderComponent();

    fireEvent.click(await screen.findByText('Templates'));

    expect(await screen.findByText('Lesson confirmation template')).toBeInTheDocument();
  });

  it('opens create rule wizard', async () => {
    renderComponent();

    fireEvent.click(await screen.findByText('Create rule'));

    expect(await screen.findByText('Create notification rule')).toBeInTheDocument();
  });
});
