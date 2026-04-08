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
  'pages.notifications.rollout.title': 'Learner pilot',
  'pages.notifications.rollout.noticeTitle': 'Safe rollout',
  'pages.notifications.rollout.noticeDescription': 'Roll out safely',
  'pages.notifications.rollout.effectiveMode': 'Effective mode',
  'pages.notifications.rolloutChecklist.title': 'Safe rollout checklist',
  'pages.notifications.rolloutChecklist.noticeTitle': 'Recommended order before production',
  'pages.notifications.rolloutChecklist.noticeDescription': 'Verify in test mode first',
  'pages.notifications.rolloutChecklist.steps.1': 'Keep the global mode as legacy or test mode.',
  'pages.notifications.rolloutChecklist.steps.2': 'Refresh the notification plan and review the queue and warnings.',
  'pages.notifications.rolloutChecklist.steps.3': 'Enable the new system for one learner and verify real notifications.',
  'pages.notifications.rolloutChecklist.steps.4': 'Only after a successful pilot, enable the new system globally.',
  'pages.notifications.pilotControls.title': 'Manual pilot controls',
  'pages.notifications.pilotControls.noticeTitle': 'Use this instead of automatic Beat during the pilot',
  'pages.notifications.pilotControls.noticeDescription': 'Process jobs first',
  'pages.notifications.pilotControls.processJobs': 'Process pending jobs',
  'pages.notifications.pilotControls.processJobsQueued': 'Notification job processing queued',
  'pages.notifications.pilotControls.deliverNow': 'Run delivery tick',
  'pages.notifications.pilotControls.deliveryQueued': 'Delivery tick queued',
  'pages.notifications.pilotControls.deliverNowConfirmTitle': 'Run real delivery for due notifications?',
  'pages.notifications.pilotControls.deliverNowConfirmDescription': 'This action can send real messages',
  'pages.notifications.modes.inherit': 'Inherit',
  'pages.notifications.modes.shadow': 'Shadow',
  'pages.notifications.modes.legacy': 'Legacy',
  'pages.notifications.modes.new': 'New',
  'pages.notifications.viewDetails': 'View details',
  'pages.notifications.sendNow': 'Send now',
  'pages.notifications.sendNowConfirmTitle': 'Send this notification outside the normal queue?',
  'pages.notifications.sendNowConfirmDescription': 'Send now confirmation',
  'pages.notifications.globalNewConfirmTitle': 'Enable the new system globally?',
  'pages.notifications.globalNewConfirmDescription': 'Global new confirmation',
  'pages.notifications.enableGlobalNew': 'Enable for all learners',
  'pages.notifications.queueDetails.titleWithId': 'Notification #{{id}}',
  'pages.notifications.queueDetails.summary': 'Summary',
  'pages.notifications.queueDetails.source': 'Source',
  'pages.notifications.queueDetails.warnings': 'Warnings',
  'pages.notifications.queueDetails.latestAttempt': 'Latest delivery attempt',
  'pages.notifications.queueDetails.debug': 'Technical details',
  'pages.notifications.queueDetails.statusReason': 'Status reason',
  'pages.notifications.queueDetails.eventTime': 'Event time',
  'pages.notifications.queueDetails.effectiveScheduledFor': 'Effective delivery time',
  'pages.notifications.queueDetails.deliveryEnabled': 'Delivery enabled',
  'pages.notifications.queueDetails.deliveryDisabled': 'Delivery disabled',
  'pages.notifications.queueDetails.priority': 'Priority',
  'pages.notifications.queueDetails.channel': 'Channel',
  'pages.notifications.queueDetails.rule': 'Rule',
  'pages.notifications.queueDetails.event': 'Event',
  'pages.notifications.queueDetails.combination': 'Combination',
  'pages.notifications.queueDetails.dedupeKey': 'Dedupe key',
  'pages.notifications.queueDetails.noWarnings': 'No additional warnings',
  'pages.notifications.queueDetails.providerMessageId': 'Telegram message_id',
  'pages.notifications.queueDetails.providerChatId': 'Telegram chat_id',
  'pages.notifications.queueDetails.error': 'Error',
  'pages.notifications.queueDetails.sentAt': 'Sent at',
  'pages.notifications.queueDetails.noAttempt': 'No attempts yet',
  'pages.notifications.warningLabels.calendarConflict': 'Another active lesson exists in the same slot',
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

    if (url === '/notifications/settings') {
      return Promise.resolve({
        data: {
          tenant_id: 1,
          mode: 'shadow',
          notifications_enabled: true,
          daily_cap: 3,
          cap_mode: 'warn_only',
          category_preferences: {},
        },
      });
    }

    if (url === '/notifications/learner-modes') {
      return Promise.resolve({
        data: [
          {
            learner_id: 10,
            display_name: 'Vika',
            mode_override: 'inherit',
            effective_mode: 'shadow',
            updated_at: null,
          },
        ],
      });
    }

    if (url === '/learners') {
      return Promise.resolve({ data: { items: [{ id: 10, display_name: 'Vika' }] } });
    }

    if (url === '/notifications/instances') {
      return Promise.resolve({
        data: [
          {
            id: 1,
            rule_id: 1,
            category: 'lesson_confirmation',
            event_type: 'lesson',
            event_id: 617,
            event_key: 'lesson:617',
            recipient_type: 'learner',
            recipient_id: 10,
            learner_id: 10,
            learner_display_name: 'Vika',
            scheduled_for: '2026-04-07T07:00:00+00:00',
            effective_scheduled_for: '2026-04-07T07:00:00+00:00',
            status: 'scheduled',
            status_reason: null,
            delivery_enabled: true,
            priority: 'normal',
            channel: 'telegram',
            dedupe_key: 'single|lesson_confirmation|rule:1',
            combination_key: null,
            explanation: {
              rule_name: 'Lesson confirmation',
              event_starts_at: '2026-04-08T20:00:00+03:00',
              warnings: ['calendar_conflict:active_lessons_same_slot'],
              calendar_conflict: {
                count: 2,
                lesson_ids: [581, 617],
                package_ids: [64, 74],
              },
            },
            components: [],
            latest_attempt: null,
          },
        ],
      });
    }

    if (url === '/notifications/instances/1') {
      return Promise.resolve({
        data: {
          id: 1,
          rule_id: 1,
          category: 'lesson_confirmation',
          event_type: 'lesson',
          event_id: 617,
          event_key: 'lesson:617',
          recipient_type: 'learner',
          recipient_id: 10,
          learner_id: 10,
          learner_display_name: 'Vika',
          scheduled_for: '2026-04-07T07:00:00+00:00',
          effective_scheduled_for: '2026-04-07T07:00:00+00:00',
          status: 'scheduled',
          status_reason: null,
          delivery_enabled: true,
          priority: 'normal',
          channel: 'telegram',
          dedupe_key: 'single|lesson_confirmation|rule:1',
          combination_key: null,
          explanation: {
            rule_name: 'Lesson confirmation',
            event_starts_at: '2026-04-08T20:00:00+03:00',
            warnings: ['calendar_conflict:active_lessons_same_slot'],
            calendar_conflict: {
              count: 2,
              lesson_ids: [581, 617],
              package_ids: [64, 74],
            },
          },
          components: [],
          latest_attempt: null,
        },
      });
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

  it('loads learner rollout settings', async () => {
    renderComponent();

    fireEvent.click(await screen.findByText('Settings'));

    expect(await screen.findByText('Learner pilot')).toBeInTheDocument();
    expect(await screen.findByText('Vika')).toBeInTheDocument();
    expect(await screen.findByText('Safe rollout checklist')).toBeInTheDocument();
    expect(await screen.findByText('Manual pilot controls')).toBeInTheDocument();
  });

  it('opens queue details drawer', async () => {
    renderComponent();

    fireEvent.click(await screen.findByText('Queue'));
    fireEvent.click(await screen.findByText('View details'));

    expect(await screen.findByText('Summary')).toBeInTheDocument();
    expect(await screen.findByText('Another active lesson exists in the same slot')).toBeInTheDocument();
  });

  it('opens send now confirmation', async () => {
    renderComponent();

    fireEvent.click(await screen.findByText('Queue'));
    fireEvent.click(await screen.findByText('Send now'));

    expect(await screen.findByText('Send this notification outside the normal queue?')).toBeInTheDocument();
  });
});
