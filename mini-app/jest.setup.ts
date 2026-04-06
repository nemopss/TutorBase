import '@testing-library/jest-dom';
import { TextEncoder, TextDecoder } from 'util';

const translations: Record<string, string> = {
  'common.actions': 'Actions',
  'common.cancel': 'Cancel',
  'common.create': 'Create',
  'common.delete': 'Delete',
  'common.edit': 'Edit',
  'common.save': 'Save',
  'common.status': 'Status',
  'common.viewAll': 'View all',
  'common.yes': 'YES',
  'common.no': 'NO',
  'forms.package.title': 'Create New Package',
  'forms.template.title': 'Create New Template',
  'navigation.lessons': 'Lessons',
  'packageCard.noScheduled': 'No scheduled lessons',
  'pages.dashboard.title': 'Dashboard',
  'pages.dashboard.subtitle': 'Overview',
  'pages.dashboard.newPackage': 'New Package',
  'pages.dashboard.viewLessons': 'View Lessons',
  'pages.dashboard.statistics': 'Statistics',
  'pages.dashboard.total': 'Total',
  'pages.dashboard.completed': 'Completed',
  'pages.dashboard.scheduled': 'Scheduled',
  'pages.dashboard.rescheduled': 'Rescheduled',
  'pages.dashboard.cancelled': 'Cancelled',
  'pages.dashboard.lessonsOverTime': 'Lessons over time',
  'pages.dashboard.lessonsByStatus': 'Lessons by status',
  'pages.dashboard.activePackages': 'Active packages',
  'pages.dashboard.upcomingLessons': 'Upcoming lessons',
  'pages.dashboard.learner': 'Learner',
  'pages.packages.title': 'Lesson Packages',
  'pages.packages.subtitle': 'Manage lesson packages',
  'pages.packages.lessons': 'lessons',
  'pages.packages.status.active': 'ACTIVE',
  'pages.packages.status.completed': 'COMPLETED',
  'pages.packages.status.draft': 'DRAFT',
  'pages.packages.status.cancelled': 'CANCELLED',
  'pages.reminders.title': 'Reminders',
  'pages.reminders.subtitle': 'Manage reminders',
  'pages.reminders.scheduledFor': 'Scheduled for',
  'pages.reminders.package': 'Package',
  'pages.reminders.type': 'Type',
  'pages.reminders.active': 'Active',
  'pages.reminders.inactive': 'Inactive',
  'pages.reminders.lastResponse': 'Last response',
  'pages.reminders.filterByStatus': 'Filter by status',
  'pages.reminders.filterByType': 'Filter by type',
  'pages.reminders.filterByPackage': 'Filter by package',
  'pages.reminders.editReminder': 'Edit Reminder',
  'pages.reminders.status.pending': 'PENDING',
  'pages.reminders.status.scheduled': 'SCHEDULED',
  'pages.reminders.status.sent': 'SENT',
  'pages.reminders.status.responded': 'RESPONDED',
  'pages.reminders.status.failed': 'FAILED',
  'pages.reminders.status.cancelled': 'CANCELLED',
  'pages.reminders.types.lesson_reminder': 'LESSON REMINDER',
  'pages.reminders.types.homework_reminder': 'HOMEWORK REMINDER',
  'pages.reminders.types.lesson_confirm': 'Lesson confirm',
  'pages.reminders.types.lesson_day_before': 'Lesson day before',
  'pages.reminders.types.payment_week': 'Payment week',
  'pages.reminders.types.payment_day': 'Payment day',
  'pages.reminders.types.homework': 'Homework',
  'pages.reminders.types.package_renewal': 'Package renewal',
  'pages.templates.title': 'Templates',
  'pages.templates.subtitle': 'Manage templates',
  'pages.templates.createTemplate': 'Create Template',
  'pages.templates.duplicate': 'Duplicate',
  'pages.templates.name': 'Name',
  'pages.templates.description': 'Description',
  'pages.templates.lessonCount': 'Lesson count',
  'pages.templates.durationDays': 'Duration days',
  'pages.templates.deleteTitle': 'Delete template',
  'forms.template.editTitle': 'Edit Template',
};

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) => {
      if (key === 'packageCard.nextLesson') {
        return `Next lesson: ${options?.date ?? ''}`;
      }
      return translations[key] ?? key;
    },
    i18n: { changeLanguage: jest.fn() },
  }),
  Trans: ({ children }: { children: any }) => children,
}));

// Mock TextEncoder/TextDecoder
(global as any).TextEncoder = TextEncoder;
(global as any).TextDecoder = TextDecoder;

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(), // deprecated
    removeListener: jest.fn(), // deprecated
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

// Mock window.getComputedStyle
Object.defineProperty(window, 'getComputedStyle', {
  writable: true,
  value: jest.fn().mockImplementation(() => ({
    getPropertyValue: jest.fn().mockReturnValue(''),
  })),
});

class ResizeObserverMock {
  observe = jest.fn();
  unobserve = jest.fn();
  disconnect = jest.fn();
}

Object.defineProperty(window, 'ResizeObserver', {
  writable: true,
  value: ResizeObserverMock,
});
(global as any).ResizeObserver = ResizeObserverMock;

// Mock window.Telegram
Object.defineProperty(window, 'Telegram', {
  writable: true,
  value: {
    WebApp: {
      initData: 'test-init-data',
      initDataUnsafe: {
        user: { id: 123, username: 'testuser', first_name: 'Test' }
      },
      themeParams: {},
      colorScheme: 'light',
      BackButton: {
        show: jest.fn(),
        hide: jest.fn(),
        onClick: jest.fn(),
        offClick: jest.fn(),
      },
      MainButton: {
        show: jest.fn(),
        hide: jest.fn(),
        setText: jest.fn(),
        onClick: jest.fn(),
        offClick: jest.fn(),
      },
      onEvent: jest.fn(),
      offEvent: jest.fn(),
    }
  },
});
