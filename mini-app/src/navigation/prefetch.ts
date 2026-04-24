import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import isoWeek from 'dayjs/plugin/isoWeek';
import type { QueryClient } from '@tanstack/react-query';
import api from '../services/api';
import { DEFAULT_TIMEZONE } from '../utils/datetime';

dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.extend(isoWeek);

type RouteLoader = () => Promise<unknown>;

type LessonListResponse = {
  total: number;
  items: unknown[];
};

type LearnerListResponse<T = unknown> = {
  items: T[];
};

type PackageListResponse<T = unknown> = {
  total: number;
  items: T[];
  has_more?: boolean;
};

const LESSONS_PAGE_LIMIT = 100;
const PACKAGES_PAGE_LIMIT = 100;
const DASHBOARD_LESSON_HISTORY_DAYS = 14;
const DASHBOARD_LESSON_FUTURE_DAYS = 365;

const getDashboardLessonRange = () => {
  const now = dayjs().tz(DEFAULT_TIMEZONE);
  return {
    fromDate: now.startOf('day').subtract(DASHBOARD_LESSON_HISTORY_DAYS, 'day').toISOString(),
    toDate: now.endOf('day').add(DASHBOARD_LESSON_FUTURE_DAYS, 'day').toISOString(),
  };
};

const getInitialCalendarRange = () => ({
  from: dayjs().tz(DEFAULT_TIMEZONE).startOf('month').startOf('isoWeek').subtract(14, 'day').toISOString(),
  to: dayjs().tz(DEFAULT_TIMEZONE).endOf('month').endOf('isoWeek').add(21, 'day').toISOString(),
});

export const loadDashboardPage = () => import('../pages/Dashboard');
export const loadPackagesPage = () => import('../pages/Packages');
export const loadPackageDetailPage = () => import('../pages/PackageDetail');
export const loadRemindersPage = () => import('../pages/Reminders');
export const loadNotificationsPage = () => import('../pages/Notifications');
export const loadGroupsPage = () => import('../pages/Groups');
export const loadSettingsPage = () => import('../pages/Settings');
export const loadAnalyticsPage = () => import('../pages/Analytics');
export const loadLessonsPage = () => import('../pages/Lessons');
export const loadLearnersPage = () => import('../pages/Learners');
export const loadPlatformConsolePage = () => import('../pages/PlatformConsole');
export const loadAccessDeniedPage = () => import('../pages/AccessDenied');
export const loadTenantAccessBlockedPage = () => import('../pages/TenantAccessBlocked');
export const loadTenantAccessPreviewPage = () => import('../pages/TenantAccessPreview');
export const loadRoleSelectionScreenPage = () => import('../pages/RoleSelectionScreen');
export const loadTutorRegistrationFormPage = () => import('../pages/TutorRegistrationForm');
export const loadStudentRegistrationFormPage = () => import('../pages/StudentRegistrationForm');
export const loadStudentDashboardPage = () => import('../pages/StudentDashboard');
export const loadSchedulePage = () => import('../pages/Schedule');
export const loadInviteCodesPage = () => import('../pages/InviteCodes');
export const loadFinanceDashboardPage = () => import('../pages/FinanceDashboard');
export const loadIncomeReportsPage = () => import('../pages/IncomeReports');
export const loadLearnerFinancePage = () => import('../pages/LearnerFinance');
export const loadLearnerProfilePage = () => import('../pages/LearnerProfile');

const routeLoaders: Record<string, RouteLoader> = {
  '/': loadDashboardPage,
  '/packages': loadPackagesPage,
  '/lessons': loadLessonsPage,
  '/learners': loadLearnersPage,
  '/finance/dashboard': loadFinanceDashboardPage,
  '/finance/reports': loadIncomeReportsPage,
  '/notifications': loadNotificationsPage,
  '/reminders': loadRemindersPage,
  '/groups': loadGroupsPage,
  '/analytics': loadAnalyticsPage,
  '/settings': loadSettingsPage,
  '/platform': loadPlatformConsolePage,
  '/schedule': loadSchedulePage,
  '/invite-codes': loadInviteCodesPage,
};

const matchPrefetchRoute = (pathname: string): string | null => {
  if (pathname === '/') {
    return pathname;
  }

  if (pathname.startsWith('/packages/')) {
    return '/packages';
  }

  if (pathname.startsWith('/learners/')) {
    return '/learners';
  }

  if (pathname.startsWith('/finance/')) {
    return pathname.startsWith('/finance/reports') ? '/finance/reports' : '/finance/dashboard';
  }

  if (pathname.startsWith('/platform/')) {
    return '/platform';
  }

  return routeLoaders[pathname] ? pathname : null;
};

export const preloadRouteModule = async (pathname: string) => {
  const routeKey = matchPrefetchRoute(pathname);
  if (!routeKey) {
    return;
  }

  await routeLoaders[routeKey]().catch(() => undefined);
};

const fetchLessons = async (
  status: string | null,
  search: string,
  limit: number,
  offset: number,
  range: { from: string; to: string },
): Promise<LessonListResponse> => {
  const { data } = await api.get('/lessons', {
    params: {
      status: status || undefined,
      search: search || undefined,
      from_date: range.from,
      to_date: range.to,
      limit,
      offset,
      sort_by: 'scheduled_at',
      sort_order: 'asc',
    },
  });
  return data;
};

const fetchAllLessons = async (range: { from: string; to: string }): Promise<LessonListResponse> => {
  const firstPage = await fetchLessons(null, '', LESSONS_PAGE_LIMIT, 0, range);
  let allItems = [...firstPage.items];
  let offset = LESSONS_PAGE_LIMIT;

  while (offset < firstPage.total && offset < 1000) {
    const page = await fetchLessons(null, '', LESSONS_PAGE_LIMIT, offset, range);
    allItems = [...allItems, ...page.items];
    offset += LESSONS_PAGE_LIMIT;
  }

  return {
    total: firstPage.total,
    items: allItems,
  };
};

const fetchLearners = async (status: 'active' | 'archived' = 'active') => {
  const { data } = await api.get<LearnerListResponse>('/learners', {
    params: { status },
  });
  return data;
};

const fetchDashboardMetrics = async () => {
  const { data } = await api.get('/finance/dashboard');
  return data;
};

const fetchLearnersWithBalance = async () => {
  const { data } = await api.get('/finance/debtors', {
    params: { limit: 10, offset: 0 },
  });
  return data.items || [];
};

const fetchPackages = async (status: 'active' | 'completed' | 'draft' | 'cancelled' = 'active') => {
  const { data } = await api.get('/packages', {
    params: {
      status_filter: status,
      limit: PACKAGES_PAGE_LIMIT,
    },
  });
  return data;
};

const fetchActivePackages = async () => {
  const firstPage = await fetchPackages('active');
  let allItems = [...firstPage.items];
  let offset = PACKAGES_PAGE_LIMIT;

  while (offset < firstPage.total && offset < 1000) {
    const { data } = await api.get<PackageListResponse>('/packages', {
      params: {
        status_filter: 'active',
        limit: PACKAGES_PAGE_LIMIT,
        offset,
      },
    });
    allItems = [...allItems, ...data.items];
    offset += PACKAGES_PAGE_LIMIT;
  }

  return {
    total: firstPage.total,
    items: allItems,
  };
};

const fetchGroups = async () => {
  const { data } = await api.get('/groups');
  return data;
};

const fetchLearnersForGroups = async () => {
  const { data } = await api.get<LearnerListResponse>('/learners');
  return data.items;
};

const fetchNotificationRules = async () => {
  const { data } = await api.get('/notifications/rules', {
    params: { include_archived: true },
  });
  return data;
};

const fetchRemindersList = async () => {
  const { data } = await api.get('/reminders', {
    params: {
      offset: 0,
      limit: 10,
    },
  });
  return data;
};

const fetchPackagesForReminders = async () => {
  let allItems: unknown[] = [];
  let offset = 0;
  const limit = PACKAGES_PAGE_LIMIT;
  let hasMore = true;

  while (hasMore) {
    const { data } = await api.get('/packages', {
      params: { limit, offset },
    });
    allItems = [...allItems, ...data.items];
    hasMore = Boolean(data.has_more);
    offset += limit;

    if (offset > 10000) {
      break;
    }
  }

  return { items: allItems, total: allItems.length };
};

const fetchAnalyticsLessons = async (fromDate: string, toDate: string) => {
  const { data } = await api.get('/metrics/lessons/daily', {
    params: {
      from_date: fromDate,
      to_date: toDate,
    },
  });
  return data;
};

const fetchAnalyticsReminders = async (fromDate: string, toDate: string) => {
  const { data } = await api.get('/metrics/reminders/daily', {
    params: {
      from_date: fromDate,
      to_date: toDate,
    },
  });
  return data;
};

const fetchAnalyticsPackages = async () => {
  let allItems: unknown[] = [];
  let offset = 0;
  let hasMore = true;

  while (hasMore) {
    const { data } = await api.get<PackageListResponse>('/packages', {
      params: { limit: PACKAGES_PAGE_LIMIT, offset },
    });
    allItems = [...allItems, ...data.items];
    hasMore = !!data.has_more;
    offset += PACKAGES_PAGE_LIMIT;

    if (offset > 10000) {
      break;
    }
  }

  return {
    total: allItems.length,
    items: allItems,
  };
};

const prefetchDashboardData = async (queryClient: QueryClient) => {
  const range = getDashboardLessonRange();
  await Promise.allSettled([
    queryClient.prefetchQuery({
      queryKey: ['dashboardLessons', range.fromDate, range.toDate],
      queryFn: () => fetchAllLessons({ from: range.fromDate, to: range.toDate }),
    }),
    queryClient.prefetchQuery({
      queryKey: ['dashboardPackagesSummary'],
      queryFn: async () => {
        const { data } = await api.get('/packages', { params: { limit: 1 } });
        return data;
      },
    }),
    queryClient.prefetchQuery({
      queryKey: ['dashboardActivePackages'],
      queryFn: fetchActivePackages,
    }),
    queryClient.prefetchQuery({
      queryKey: ['dashboardHistory'],
      queryFn: async () => {
        const { data } = await api.get('/metrics/dashboard-history');
        return data;
      },
    }),
  ]);
};

const prefetchLessonsData = async (queryClient: QueryClient) => {
  const range = getInitialCalendarRange();
  await queryClient.prefetchQuery({
    queryKey: ['lessons', 'calendar', range.from, range.to],
    queryFn: () => fetchAllLessons(range),
  });
};

const prefetchLearnersData = async (queryClient: QueryClient) => {
  await queryClient.prefetchQuery({
    queryKey: ['learners', 'active'],
    queryFn: () => fetchLearners('active'),
  });
};

const prefetchFinanceData = async (queryClient: QueryClient) => {
  await Promise.allSettled([
    queryClient.prefetchQuery({
      queryKey: ['financeDashboard'],
      queryFn: fetchDashboardMetrics,
    }),
    queryClient.prefetchQuery({
      queryKey: ['learnersWithBalance'],
      queryFn: fetchLearnersWithBalance,
    }),
  ]);
};

const prefetchPackagesData = async (queryClient: QueryClient) => {
  await queryClient.prefetchQuery({
    queryKey: ['packages', 'active'],
    queryFn: () => fetchPackages('active'),
  });
};

const prefetchGroupsData = async (queryClient: QueryClient) => {
  await Promise.allSettled([
    queryClient.prefetchQuery({
      queryKey: ['learnerGroups'],
      queryFn: fetchGroups,
    }),
    queryClient.prefetchQuery({
      queryKey: ['learnersForGroups'],
      queryFn: fetchLearnersForGroups,
    }),
  ]);
};

const prefetchNotificationsData = async (queryClient: QueryClient) => {
  await queryClient.prefetchQuery({
    queryKey: ['notificationRules'],
    queryFn: fetchNotificationRules,
  });
};

const prefetchRemindersData = async (queryClient: QueryClient) => {
  await Promise.allSettled([
    queryClient.prefetchQuery({
      queryKey: ['reminders', 1, 10, null, null, null, ''],
      queryFn: fetchRemindersList,
    }),
    queryClient.prefetchQuery({
      queryKey: ['packagesForReminders'],
      queryFn: fetchPackagesForReminders,
    }),
  ]);
};

const prefetchAnalyticsData = async (queryClient: QueryClient) => {
  const endDate = dayjs();
  const startDate = endDate.subtract(30, 'days');
  const fromDate = startDate.toISOString();
  const toDate = endDate.toISOString();

  await Promise.allSettled([
    queryClient.prefetchQuery({
      queryKey: ['analyticsLessons', fromDate, toDate],
      queryFn: () => fetchAnalyticsLessons(fromDate, toDate),
    }),
    queryClient.prefetchQuery({
      queryKey: ['analyticsReminders', fromDate, toDate],
      queryFn: () => fetchAnalyticsReminders(fromDate, toDate),
    }),
    queryClient.prefetchQuery({
      queryKey: ['analyticsPackages'],
      queryFn: fetchAnalyticsPackages,
    }),
  ]);
};

const routeDataPrefetchers: Partial<Record<string, (queryClient: QueryClient) => Promise<void>>> = {
  '/': prefetchDashboardData,
  '/packages': prefetchPackagesData,
  '/lessons': prefetchLessonsData,
  '/learners': prefetchLearnersData,
  '/finance/dashboard': prefetchFinanceData,
  '/notifications': prefetchNotificationsData,
  '/reminders': prefetchRemindersData,
  '/groups': prefetchGroupsData,
  '/analytics': prefetchAnalyticsData,
};

export const prefetchRouteData = async (queryClient: QueryClient, pathname: string) => {
  const routeKey = matchPrefetchRoute(pathname);
  if (!routeKey) {
    return;
  }

  const prefetcher = routeDataPrefetchers[routeKey];
  if (!prefetcher) {
    return;
  }

  await prefetcher(queryClient).catch(() => undefined);
};

export const prefetchNavigationTarget = async (queryClient: QueryClient, pathname: string) => {
  await Promise.allSettled([
    preloadRouteModule(pathname),
    prefetchRouteData(queryClient, pathname),
  ]);
};

export const prefetchStaffPrimaryNavigation = async (queryClient: QueryClient) => {
  await Promise.allSettled([
    prefetchNavigationTarget(queryClient, '/lessons'),
    prefetchNavigationTarget(queryClient, '/learners'),
    prefetchNavigationTarget(queryClient, '/finance/dashboard'),
  ]);
};

export const prefetchStaffMoreNavigation = async (queryClient: QueryClient, isSuperAdmin: boolean) => {
  const targets = [
    '/packages',
    '/notifications',
    '/groups',
    '/analytics',
    '/settings',
  ];

  if (isSuperAdmin) {
    targets.push('/platform');
  }

  await Promise.allSettled(targets.map((pathname) => prefetchNavigationTarget(queryClient, pathname)));
};

export const prefetchStudentNavigation = async (queryClient: QueryClient) => {
  await Promise.allSettled([
    preloadRouteModule('/schedule'),
    preloadRouteModule('/settings'),
    prefetchRouteData(queryClient, '/schedule'),
  ]);
};
