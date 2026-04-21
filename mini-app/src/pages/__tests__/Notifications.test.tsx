import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import Notifications from '../Notifications';
import { useAuth } from '../../auth/AuthProvider';

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
  'pages.notifications.ruleWizard.presets.lesson_confirmation.title': 'Lesson confirmation preset',
  'pages.notifications.ruleWizard.presets.lesson_confirmation.description': 'Lesson confirmation description',
  'pages.notifications.ruleWizard.presets.lesson_confirmation.name': 'Lesson confirmation rule',
  'pages.notifications.ruleWizard.presets.homework.title': 'Homework preset',
  'pages.notifications.ruleWizard.presets.homework.description': 'Homework description',
  'pages.notifications.ruleWizard.presets.homework.name': 'Homework rule',
  'pages.notifications.ruleWizard.presets.package_renewal.title': 'Package renewal preset',
  'pages.notifications.ruleWizard.presets.package_renewal.description': 'Package renewal description',
  'pages.notifications.ruleWizard.presets.package_renewal.name': 'Package renewal rule',
  'pages.notifications.ruleWizard.presets.custom_message.title': 'Custom preset',
  'pages.notifications.ruleWizard.presets.custom_message.description': 'Custom description',
  'pages.notifications.ruleWizard.presets.custom_message.name': 'Custom rule',
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
  'pages.notifications.rolloutStatus.title': 'Current pilot status',
  'pages.notifications.rolloutStatus.nextActionTitle': 'Recommended next action',
  'pages.notifications.rolloutStatus.globalMode': 'Global mode',
  'pages.notifications.rolloutStatus.totalLearners': 'Learners in scope',
  'pages.notifications.rolloutStatus.learnersInTestMode': 'Learners in test mode',
  'pages.notifications.rolloutStatus.learnersInNew': 'Learners on the new system',
  'pages.notifications.rolloutStatus.plannedNotifications': 'Notifications in plan',
  'pages.notifications.rolloutStatus.readyForDelivery': 'Ready for real delivery now',
  'pages.notifications.rolloutStatus.attentionAlerts': 'Events requiring attention',
  'pages.notifications.rolloutStatus.nextActions.choosePilotLearner': 'Choose one learner for the new-system pilot before running real deliveries.',
  'pages.notifications.rolloutStatus.nextActions.readyForControlledSend': 'You can now run a controlled manual delivery for the pilot and inspect the real message flow.',
  'pages.notifications.rolloutStatus.nextActions.refreshPlan': 'Refresh the notification plan so you can inspect the future queue before any real sends.',
  'pages.notifications.rolloutStatus.nextActions.enableTestMode': 'Enable the global test mode or move one learner to test mode first so you can build the notification plan safely.',
  'pages.notifications.rolloutStatus.nextActions.waitForDueNotifications': 'The plan is ready, but there are no due notifications for real delivery right now. Wait for the due time or check the schedule.',
  'pages.notifications.rolloutStatus.nextActions.reviewAlerts': 'Review attention-required events first so the pilot does not hide real problems.',
  'pages.notifications.pilotControls.title': 'Manual pilot controls',
  'pages.notifications.pilotControls.noticeTitle': 'Use this instead of automatic Beat during the pilot',
  'pages.notifications.pilotControls.noticeDescription': 'Process jobs first',
  'pages.notifications.pilotControls.processJobs': 'Process pending jobs',
  'pages.notifications.pilotControls.processJobsQueued': 'Notification job processing queued',
  'pages.notifications.pilotControls.deliverNow': 'Run delivery tick',
  'pages.notifications.pilotControls.deliveryQueued': 'Delivery tick queued',
  'pages.notifications.pilotControls.statusSummary': 'Currently in plan: {{planned}}. Ready for real delivery: {{ready}}.',
  'pages.notifications.pilotControls.deliveryBlockedHint': 'There are no due notifications with delivery enabled right now.',
  'pages.notifications.pilotControls.deliverNowConfirmTitle': 'Run real delivery for due notifications?',
  'pages.notifications.pilotControls.deliverNowConfirmDescription': 'This action can send real messages',
  'pages.notifications.technicalList': 'Technical list',
  'pages.notifications.queueSections.past_due': 'Needs attention now',
  'pages.notifications.queueSections.today': 'Today',
  'pages.notifications.queueSections.tomorrow': 'Tomorrow',
  'pages.notifications.queueSections.later': 'Later',
  'pages.notifications.queueTimeline.deliveryLine': '{{event}} · event at {{eventTime}}',
  'pages.notifications.activitySections.attention': 'Needs attention',
  'pages.notifications.activitySections.recent': 'Recent activity',
  'pages.notifications.activityDetails.lessonConfirmed': 'The learner confirmed the lesson',
  'pages.notifications.activityDetails.packageRenewalNeedsDiscussion': 'The learner wants to discuss package renewal',
  'pages.notifications.activityDetails.responseConfirmed': 'The learner confirmed the notification',
  'pages.notifications.activityDetails.responseRecorded': 'The learner response was recorded',
  'pages.notifications.activityDetails.deliverySent': 'The message was sent via Telegram',
  'pages.notifications.activityDetails.deliveryProcessing': 'The notification is being sent now',
  'pages.notifications.activityDetails.deliveryScheduled': 'The notification is queued for the next delivery tick',
  'pages.notifications.activityDetails.deliveryFailed': 'The message could not be delivered',
  'pages.notifications.activityDetails.deliveryRecorded': 'A delivery event was recorded',
  'pages.notifications.modes.inherit': 'Inherit',
  'pages.notifications.modes.shadow': 'Shadow',
  'pages.notifications.modes.legacy': 'Legacy',
  'pages.notifications.modes.new': 'New',
  'pages.notifications.modeDescriptions.shadow': 'Shadow mode description',
  'pages.notifications.modeDescriptions.legacy': 'Legacy mode description',
  'pages.notifications.modeDescriptions.new': 'New mode description',
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
  'pages.notifications.instanceStatus.sent': 'Sent',
  'pages.notifications.instanceStatus.scheduled': 'Scheduled',
  'pages.notifications.instanceStatus.processing': 'Processing',
  'pages.notifications.instanceStatus.failed': 'Failed',
  'pages.notifications.instanceStatus.cancelled': 'Cancelled',
  'pages.notifications.instanceStatus.shadow': 'Test',
  'pages.notifications.instanceStatus.skipped': 'Skipped',
  'pages.notifications.instanceStatus.suppressed': 'Suppressed',
  'pages.notifications.instanceStatus.expired': 'Expired',
  'pages.notifications.warningLabels.calendarConflict': 'Another active lesson exists in the same slot',
  'navigation.newBadge': 'NEW',
  'common.tenantContextRequired.title': 'Choose a school first',
  'common.tenantContextRequired.description': 'The Notifications section works only inside a selected school context.',
  'common.tenantContextRequired.globalContextNotice': 'You are currently in the global view without a selected school.',
  'common.tenantContextRequired.switchHint': 'Select a school with the tenant switcher in the menu, then open this section again.',
};

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => translations[key] ?? key,
  }),
}));

const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;
const mockGet = jest.fn((url: string, _config?: unknown) => {
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
          {
            id: 2,
            rule_id: 1,
            category: 'lesson_confirmation',
            event_type: 'lesson',
            event_id: 618,
            event_key: 'lesson:618',
            recipient_type: 'learner',
            recipient_id: 11,
            learner_id: 11,
            learner_display_name: 'Masha',
            scheduled_for: '2026-04-07T08:00:00+00:00',
            effective_scheduled_for: '2026-04-07T08:00:00+00:00',
            status: 'cancelled',
            status_reason: 'rematerialized:active_rules',
            delivery_enabled: false,
            priority: 'normal',
            channel: 'telegram',
            dedupe_key: 'single|lesson_confirmation|rule:1|cancelled',
            combination_key: null,
            explanation: {
              rule_name: 'Lesson confirmation',
              event_starts_at: '2026-04-08T21:00:00+03:00',
              warnings: [],
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

    if (url === '/notifications/activity') {
      return Promise.resolve({
        data: [
          {
            activity_type: 'response',
            activity_id: 301,
            notification_instance_id: 1,
            category: 'lesson_confirmation',
            event_type: 'lesson',
            event_id: 617,
            learner_id: 10,
            learner_display_name: 'Vika',
            status: 'confirmed',
            action_key: 'confirm_lesson',
            response_value: 'confirmed',
            occurred_at: '2026-04-07T07:05:00+00:00',
            metadata: {},
          },
          {
            activity_type: 'teacher_alert',
            activity_id: 302,
            notification_instance_id: 2,
            category: 'teacher_alert',
            event_type: 'package',
            event_id: 64,
            learner_id: 10,
            learner_display_name: 'Vika',
            status: 'requires_attention',
            action_key: 'discuss_package_renewal',
            response_value: 'needs_discussion',
            occurred_at: '2026-04-07T07:04:00+00:00',
            metadata: {
              alert_code: 'package_renewal_needs_discussion',
            },
          },
          {
            activity_type: 'delivery_attempt',
            activity_id: 201,
            notification_instance_id: 1,
            category: 'lesson_confirmation',
            event_type: 'lesson',
            event_id: 617,
            learner_id: 10,
            learner_display_name: 'Vika',
            status: 'sent',
            provider_message_id: '3106',
            occurred_at: '2026-04-07T07:00:03+00:00',
            metadata: {
              attempt_no: 1,
              channel: 'telegram',
              provider: 'telegram',
            },
          },
        ],
      });
    }

    if (url === '/groups') {
      return Promise.resolve({ data: [] });
    }

    if (url === '/packages') {
      return Promise.resolve({ data: { items: [] } });
    }

    return Promise.resolve({ data: [] });
  });

jest.mock('../../auth/AuthProvider', () => ({
  useAuth: jest.fn(),
}));

jest.mock('../../services/api', () => ({
  get: (url: string, config?: unknown) => mockGet(url, config),
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
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { id: 1, display_name: 'Admin', role: 'admin', tenant_id: 1 },
      tenantId: 1,
      tenantAccess: null,
      isSuperAdmin: true,
      canSwitchTenant: true,
      isTenantAccessLoading: false,
      switchTenant: jest.fn(),
      refreshTenantAccess: jest.fn(),
      registerTutor: jest.fn(),
      registerStudent: jest.fn(),
      logout: jest.fn(),
    });
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

  it('switches active rule preset card', async () => {
    renderComponent();

    fireEvent.click(await screen.findByText('Create rule'));

    const lessonPreset = await screen.findByTestId('rule-wizard-preset-lesson_confirmation');
    const homeworkPreset = await screen.findByTestId('rule-wizard-preset-homework');

    expect(lessonPreset).toHaveAttribute('data-active', 'true');
    expect(homeworkPreset).toHaveAttribute('data-active', 'false');

    fireEvent.click(homeworkPreset);

    expect(homeworkPreset).toHaveAttribute('data-active', 'true');
    expect(lessonPreset).toHaveAttribute('data-active', 'false');
  });

  it('loads learner rollout settings', async () => {
    renderComponent();

    fireEvent.click(await screen.findByText('Settings'));

    expect(await screen.findByText('Learner pilot')).toBeInTheDocument();
    expect(await screen.findByText('Vika')).toBeInTheDocument();
    expect(await screen.findByText('Current pilot status')).toBeInTheDocument();
    expect(await screen.findByText('Safe rollout checklist')).toBeInTheDocument();
    expect(await screen.findByText('Manual pilot controls')).toBeInTheDocument();
  });

  it('opens queue details drawer', async () => {
    renderComponent();

    fireEvent.click(await screen.findByText('Queue'));
    fireEvent.click(await screen.findByText('View details'));

    expect(await screen.findByText('Summary')).toBeInTheDocument();
    expect((await screen.findAllByText('Another active lesson exists in the same slot')).length).toBeGreaterThan(0);
  });

  it('opens send now confirmation', async () => {
    renderComponent();

    fireEvent.click(await screen.findByText('Queue'));
    fireEvent.click(await screen.findByText('Send now'));

    expect(await screen.findByText('Send this notification outside the normal queue?')).toBeInTheDocument();
  });

  it('requests queue-only instances and hides cancelled rows from the queue', async () => {
    renderComponent();

    fireEvent.click(await screen.findByText('Queue'));

    expect(await screen.findByText('Vika')).toBeInTheDocument();
    expect(screen.queryByText('Masha')).not.toBeInTheDocument();
    expect(mockGet).toHaveBeenCalledWith(
      '/notifications/instances',
      expect.objectContaining({
        params: expect.objectContaining({
          limit: 100,
          queue_only: true,
        }),
      }),
    );
  });

  it('shows human-readable activity details instead of raw response and message ids', async () => {
    renderComponent();

    fireEvent.click(await screen.findByText('Activity'));

    expect(await screen.findByText('The learner confirmed the lesson')).toBeInTheDocument();
    expect(await screen.findByText('The learner wants to discuss package renewal')).toBeInTheDocument();
    expect(await screen.findByText('The message was sent via Telegram')).toBeInTheDocument();
    expect(screen.queryByText('confirmed')).not.toBeInTheDocument();
    expect(screen.queryByText('3106')).not.toBeInTheDocument();
  });

  it('shows tenant selection prompt in global super-admin context without firing notification queries', async () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { id: 1, display_name: 'Admin', role: 'admin', tenant_id: null },
      tenantId: null,
      tenantAccess: null,
      isSuperAdmin: true,
      canSwitchTenant: true,
      isTenantAccessLoading: false,
      switchTenant: jest.fn(),
      refreshTenantAccess: jest.fn(),
      registerTutor: jest.fn(),
      registerStudent: jest.fn(),
      logout: jest.fn(),
    });

    renderComponent();

    expect(await screen.findByText('Choose a school first')).toBeInTheDocument();
    expect(screen.getByText('The Notifications section works only inside a selected school context.')).toBeInTheDocument();
    expect(mockGet).not.toHaveBeenCalled();
  });
});
