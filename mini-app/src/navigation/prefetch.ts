import dayjs from 'dayjs';
import type { QueryClient } from '@tanstack/react-query';
import api from '../services/api';

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

const fetchLessons = async (status: string | null, search: string, limit: number, offset: number): Promise<LessonListResponse> => {
  const { data } = await api.get('/lessons', {
    params: {
      status: status || undefined,
      search: search || undefined,
      limit,
      offset,
      sort_by: 'scheduled_at',
      sort_order: 'asc',
    },
  });
  return data;
};

const fetchAllLessons = async (): Promise<LessonListResponse> => {
  const firstPage = await fetchLessons(null, '', LESSONS_PAGE_LIMIT, 0);
  let allItems = [...firstPage.items];
  let offset = LESSONS_PAGE_LIMIT;

  while (offset < firstPage.total && offset < 1000) {
    const page = await fetchLessons(null, '', LESSONS_PAGE_LIMIT, offset);
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
  await Promise.allSettled([
    queryClient.prefetchQuery({
      queryKey: ['dashboardLessons'],
      queryFn: fetchAllLessons,
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
      queryFn: async () => {
        const { data } = await api.get('/packages', {
          params: {
            status_filter: 'active',
            limit: PACKAGES_PAGE_LIMIT,
          },
        });
        return data;
      },
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
  await queryClient.prefetchQuery({
    queryKey: ['lessons', 'calendar', 'all'],
    queryFn: fetchAllLessons,
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
