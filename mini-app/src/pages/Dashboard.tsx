import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Card, Col, List, Row, Skeleton, Spin, Typography } from 'antd';
import {
  CloseOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  TeamOutlined,
  KeyOutlined,
  PlusOutlined,
  UserAddOutlined,
  FieldTimeOutlined,
  ScheduleOutlined,
  BellOutlined,
  AppstoreOutlined,
} from '@ant-design/icons';
import { AxiosError } from 'axios';
import dayjs from 'dayjs';
import updateLocale from 'dayjs/plugin/updateLocale';
import utc from 'dayjs/plugin/utc';
import timezonePlugin from 'dayjs/plugin/timezone';
import isoWeek from 'dayjs/plugin/isoWeek';
import isSameOrAfter from 'dayjs/plugin/isSameOrAfter';
import { useTranslation } from 'react-i18next';
import api from '../services/api';
import DashboardMiniWeekCalendar from '../components/dashboard/DashboardMiniWeekCalendar';
import DashboardLessonLoadHeatmap from '../components/dashboard/DashboardLessonLoadHeatmap';
import DashboardWeeklyLoad from '../components/dashboard/DashboardWeeklyLoad';
import TenantContextRequired from '../components/common/TenantContextRequired';
import { useResponsiveStyles } from '../hooks/useResponsiveStyles';
import { useResponsive } from '../hooks/useResponsive';
import { useTheme } from '../theme/ThemeProvider';
import { spacing } from '../theme/tokens';
import { DEFAULT_TIMEZONE } from '../utils/datetime';
import { useAuth } from '../auth/AuthProvider';
import type { Lesson as CalendarLesson } from '../components/common/calendar-types';
import { statusColors } from '../components/common/calendar-types';

dayjs.extend(updateLocale);
dayjs.extend(utc);
dayjs.extend(timezonePlugin);
dayjs.extend(isoWeek);
dayjs.extend(isSameOrAfter);
dayjs.updateLocale('ru', { week: { dow: 1 } });
dayjs.locale('ru');

const { Text } = Typography;

interface Lesson extends CalendarLesson {
  package_id: number;
  package_title?: string;
  timezone: string;
}

interface LessonListResponse {
  total: number;
  items: Lesson[];
}

interface PackageListResponse {
  total: number;
  items: unknown[];
}

interface ActivePackage {
  id: number;
  learner_id: number;
  learner_name?: string;
  title: string;
  status: 'active' | 'completed' | 'cancelled' | 'draft';
  next_lesson_date?: string | null;
}

interface ActivePackageListResponse {
  total: number;
  items: ActivePackage[];
}

interface NotificationDeliveryAttempt {
  status: string;
  error_code?: string | null;
  error_message?: string | null;
  finished_at?: string | null;
  created_at?: string | null;
}

interface NotificationInstance {
  id: number;
  category: string;
  learner_display_name?: string | null;
  effective_scheduled_for: string;
  status: string;
  delivery_enabled?: boolean;
  latest_attempt?: NotificationDeliveryAttempt | null;
}

interface NotificationActivity {
  activity_type: string;
  activity_id: number;
  event_type: string;
  event_id?: number | null;
  learner_display_name?: string | null;
  status: string;
  response_value?: string | null;
  occurred_at?: string | null;
  metadata: Record<string, unknown>;
}

interface DashboardAttentionDismissal {
  id: number;
  item_type: 'package_ending_soon' | 'lesson_declined';
  item_key: string;
  dismissed_until: string;
  created_at: string;
  updated_at: string;
}

interface DashboardHistoryDayPoint {
  date: string;
  hours: number;
  lessons_count: number;
}

interface DashboardHistoryWeekPoint {
  week_start: string;
  hours: number;
  lessons_count: number;
}

interface DashboardHistoryResponse {
  heatmap: {
    from_date: string;
    to_date: string;
    days: DashboardHistoryDayPoint[];
  };
  weekly_load: {
    from_date: string;
    to_date: string;
    weeks: DashboardHistoryWeekPoint[];
  };
}

interface LearnerListResponse {
  total: number;
}

interface InviteTokenListResponse {
  total: number;
  items: unknown[];
}

interface DashboardMetrics {
  current_month_income: number;
  previous_month_income: number;
  total_outstanding: number;
  unpaid_learners_count: number;
}

const DASHBOARD_LESSON_HISTORY_DAYS = 14;
const DASHBOARD_LESSON_FUTURE_DAYS = 365;
const EMPTY_LESSONS: Lesson[] = [];
const EMPTY_ACTIVE_PACKAGES: ActivePackage[] = [];
const EMPTY_NOTIFICATION_ACTIVITY: NotificationActivity[] = [];
const EMPTY_NOTIFICATION_INSTANCES: NotificationInstance[] = [];
const EMPTY_ATTENTION_DISMISSALS: DashboardAttentionDismissal[] = [];

const getDashboardLessonRange = () => {
  const now = dayjs().tz(DEFAULT_TIMEZONE);
  return {
    fromDate: now.startOf('day').subtract(DASHBOARD_LESSON_HISTORY_DAYS, 'day').toISOString(),
    toDate: now.endOf('day').add(DASHBOARD_LESSON_FUTURE_DAYS, 'day').toISOString(),
  };
};

const fetchLessonsPage = async (
  limit: number,
  offset: number,
  fromDate: string,
  toDate: string,
): Promise<LessonListResponse> => {
  const { data } = await api.get('/lessons', {
    params: {
      from_date: fromDate,
      to_date: toDate,
      sort_by: 'scheduled_at',
      sort_order: 'asc',
      limit,
      offset,
    },
  });
  return data;
};

const fetchDashboardLessons = async (fromDate: string, toDate: string): Promise<LessonListResponse> => {
  const limit = 100;
  const firstPage = await fetchLessonsPage(limit, 0, fromDate, toDate);
  let allItems = [...firstPage.items];
  let offset = limit;

  while (offset < firstPage.total && offset < 1000) {
    const page = await fetchLessonsPage(limit, offset, fromDate, toDate);
    allItems = [...allItems, ...page.items];
    offset += limit;
  }

  return {
    total: firstPage.total,
    items: allItems,
  };
};

const fetchPackagesSummary = async (): Promise<PackageListResponse> => {
  const { data } = await api.get('/packages', {
    params: { limit: 1 },
  });
  return data;
};

const fetchActivePackagesPage = async (limit: number, offset: number): Promise<ActivePackageListResponse> => {
  const { data } = await api.get('/packages', {
    params: {
      status_filter: 'active',
      limit,
      offset,
    },
  });
  return data;
};

const fetchActivePackages = async (): Promise<ActivePackageListResponse> => {
  const limit = 100;
  const firstPage = await fetchActivePackagesPage(limit, 0);
  let allItems = [...firstPage.items];
  let offset = limit;

  while (offset < firstPage.total && offset < 1000) {
    const page = await fetchActivePackagesPage(limit, offset);
    allItems = [...allItems, ...page.items];
    offset += limit;
  }

  return {
    total: firstPage.total,
    items: allItems,
  };
};

const fetchNotificationActivity = async (): Promise<NotificationActivity[]> => {
  const { data } = await api.get('/notifications/activity', {
    params: { limit: 200 },
  });
  return data;
};

const fetchNotificationInstancesByStatus = async (status: string): Promise<NotificationInstance[]> => {
  const { data } = await api.get('/notifications/instances', {
    params: { status, limit: 200 },
  });
  return data;
};

const fetchNotificationQueueInstances = async (): Promise<NotificationInstance[]> => {
  const { data } = await api.get('/notifications/instances', {
    params: { queue_only: true, limit: 200 },
  });
  return data;
};

const fetchDashboardAttentionDismissals = async (): Promise<DashboardAttentionDismissal[]> => {
  try {
    const { data } = await api.get('/metrics/dashboard-attention-dismissals');
    return data;
  } catch (error) {
    if (error instanceof AxiosError && error.response?.status === 404) {
      return [];
    }
    throw error;
  }
};

const dismissDashboardAttentionItem = async (payload: {
  item_type: 'package_ending_soon' | 'lesson_declined';
  item_key: string;
  dismissed_until: string;
}): Promise<DashboardAttentionDismissal> => {
  const { data } = await api.post('/metrics/dashboard-attention-dismissals', payload);
  return data;
};

const fetchDashboardHistory = async (): Promise<DashboardHistoryResponse> => {
  const { data } = await api.get('/metrics/dashboard-history');
  return data;
};

const fetchLessonsSummary = async (): Promise<LessonListResponse> => {
  const { data } = await api.get('/lessons', {
    params: { limit: 1 },
  });
  return data;
};

const fetchLearnersSummary = async (): Promise<LearnerListResponse> => {
  const { data } = await api.get('/learners', {
    params: { limit: 1 },
  });
  return data;
};

const fetchInviteTokensSummary = async (tenantId: number): Promise<InviteTokenListResponse> => {
  const { data } = await api.get(`/tenants/${tenantId}/invitations`, {
    params: { limit: 1 },
  });
  return data;
};

const fetchDashboardMetrics = async (): Promise<DashboardMetrics> => {
  const { data } = await api.get('/finance/dashboard');
  return data;
};

const formatCurrency = (value: number): string => new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'RUB',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
}).format(value);

const Dashboard: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { cardStyle, subtitleColor, borderColor, textColor } = useResponsiveStyles();
  const { isMobile } = useResponsive();
  const { resolvedTheme } = useTheme();
  const { tenantId } = useAuth();
  const requiresTenantContext = tenantId === null;
  const colors = resolvedTheme.colors;
  const topRowHeight = isMobile ? undefined : 432;
  const tileRadius = 10;
  const [loadDeferredPanels, setLoadDeferredPanels] = useState(false);
  const dashboardLessonRange = useMemo(() => getDashboardLessonRange(), []);
  const kpiPalette = {
    blue: '#1677ff',
    green: '#52c41a',
    amber: '#faad14',
    violet: '#722ed1',
  };
  const dashboardTileStyle = {
    ...cardStyle,
    width: '100%',
    height: topRowHeight ?? '100%',
    border: `0px solid ${colors.borderPrimary}`,
    borderRadius: tileRadius,
    boxShadow: 'none',
    display: 'flex',
    flexDirection: 'column' as const,
  };
  const dashboardCardHeaderStyle = { borderBottom: 0 };

  const {
    data: lessonsData,
    isLoading: isLoadingLessons,
    isError: isErrorLessons,
    error: errorLessons,
  } = useQuery<LessonListResponse, Error>({
    queryKey: ['dashboardLessons', dashboardLessonRange.fromDate, dashboardLessonRange.toDate],
    queryFn: () => fetchDashboardLessons(dashboardLessonRange.fromDate, dashboardLessonRange.toDate),
    enabled: !requiresTenantContext,
  });

  const { data: packagesSummaryData, isSuccess: hasPackagesSummaryData } = useQuery<PackageListResponse, Error>({
    queryKey: ['dashboardPackagesSummary'],
    queryFn: fetchPackagesSummary,
    enabled: !requiresTenantContext,
  });

  const { data: activePackagesData, isLoading: isLoadingActivePackages } = useQuery<ActivePackageListResponse, Error>({
    queryKey: ['dashboardActivePackages'],
    queryFn: fetchActivePackages,
    enabled: !requiresTenantContext && loadDeferredPanels,
  });

  const { data: notificationActivityData, isLoading: isLoadingNotificationActivity } = useQuery<NotificationActivity[], Error>({
    queryKey: ['dashboardNotificationActivity'],
    queryFn: fetchNotificationActivity,
    enabled: !requiresTenantContext && loadDeferredPanels,
  });

  const { data: failedNotificationInstancesData, isLoading: isLoadingFailedNotificationInstances } = useQuery<NotificationInstance[], Error>({
    queryKey: ['dashboardFailedNotificationInstances'],
    queryFn: () => fetchNotificationInstancesByStatus('failed'),
    enabled: !requiresTenantContext && loadDeferredPanels,
  });

  const { data: queuedNotificationInstancesData, isLoading: isLoadingQueuedNotificationInstances } = useQuery<NotificationInstance[], Error>({
    queryKey: ['dashboardQueuedNotificationInstances'],
    queryFn: fetchNotificationQueueInstances,
    enabled: !requiresTenantContext && loadDeferredPanels,
  });

  const { data: attentionDismissalsData, isLoading: isLoadingAttentionDismissals } = useQuery<DashboardAttentionDismissal[], Error>({
    queryKey: ['dashboardAttentionDismissals'],
    queryFn: fetchDashboardAttentionDismissals,
    enabled: !requiresTenantContext && loadDeferredPanels,
  });

  const {
    data: dashboardHistoryData,
    isLoading: isLoadingDashboardHistory,
    isError: isErrorDashboardHistory,
    error: dashboardHistoryError,
  } = useQuery<DashboardHistoryResponse, Error>({
    queryKey: ['dashboardHistory'],
    queryFn: fetchDashboardHistory,
    enabled: !requiresTenantContext && loadDeferredPanels,
  });

  const { data: lessonsSummaryData, isSuccess: hasLessonsSummaryData } = useQuery<LessonListResponse, Error>({
    queryKey: ['dashboardLessonsSummary'],
    queryFn: fetchLessonsSummary,
    enabled: !requiresTenantContext,
  });

  const { data: learnersData, isSuccess: hasLearnersData } = useQuery<LearnerListResponse, Error>({
    queryKey: ['dashboardLearnersSummary'],
    queryFn: fetchLearnersSummary,
    enabled: !requiresTenantContext,
  });

  const { data: inviteTokensData, isSuccess: hasInviteTokensData } = useQuery<InviteTokenListResponse, Error>({
    queryKey: ['dashboardInviteTokensSummary', tenantId],
    queryFn: () => fetchInviteTokensSummary(tenantId!),
    enabled: !requiresTenantContext && !!tenantId,
  });

  const {
    data: financeMetrics,
    isLoading: isLoadingFinanceMetrics,
    isError: isErrorFinanceMetrics,
    error: financeMetricsError,
  } = useQuery<DashboardMetrics, Error>({
    queryKey: ['financeDashboard'],
    queryFn: fetchDashboardMetrics,
    enabled: !requiresTenantContext && loadDeferredPanels,
  });

  const dismissAttentionMutation = useMutation({
    mutationFn: dismissDashboardAttentionItem,
    onSuccess: (dismissal) => {
      queryClient.setQueryData<DashboardAttentionDismissal[]>(
        ['dashboardAttentionDismissals'],
        (current) => {
          const existing = current || [];
          if (existing.some((item) => item.item_key === dismissal.item_key)) {
            return existing;
          }
          return [...existing, dismissal];
        },
      );
    },
    onError: (error: Error) => {
      // Keep the dismiss action quiet but not silent.
      // The dashboard should stay usable even if the acknowledge call fails.
      console.error('Dismiss dashboard attention item failed:', error);
    },
  });

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setLoadDeferredPanels(true);
    }, 220);

    return () => {
      window.clearTimeout(timer);
    };
  }, []);

  const allLessons = lessonsData?.items ?? EMPTY_LESSONS;
  const activePackages = activePackagesData?.items ?? EMPTY_ACTIVE_PACKAGES;
  const notificationActivity = notificationActivityData ?? EMPTY_NOTIFICATION_ACTIVITY;
  const failedNotificationInstances = failedNotificationInstancesData ?? EMPTY_NOTIFICATION_INSTANCES;
  const queuedNotificationInstances = queuedNotificationInstancesData ?? EMPTY_NOTIFICATION_INSTANCES;
  const attentionDismissals = attentionDismissalsData ?? EMPTY_ATTENTION_DISMISSALS;
  const nonCancelledLessons = useMemo(
    () => allLessons.filter((lesson) => lesson.status !== 'cancelled'),
    [allLessons],
  );

  const todayKey = dayjs().tz(DEFAULT_TIMEZONE).format('YYYY-MM-DD');
  const tomorrowKey = dayjs().tz(DEFAULT_TIMEZONE).add(1, 'day').format('YYYY-MM-DD');
  const weekStart = dayjs().tz(DEFAULT_TIMEZONE).startOf('isoWeek');
  const weekEnd = weekStart.add(7, 'day');

  const todayLessons = useMemo(
    () =>
      allLessons.filter(
        (lesson) => dayjs(lesson.scheduled_at).tz(lesson.timezone || DEFAULT_TIMEZONE).format('YYYY-MM-DD') === todayKey,
      ).sort((a, b) => dayjs(a.scheduled_at).valueOf() - dayjs(b.scheduled_at).valueOf()),
    [allLessons, todayKey],
  );

  const tomorrowLessons = useMemo(
    () =>
      allLessons.filter(
        (lesson) => dayjs(lesson.scheduled_at).tz(lesson.timezone || DEFAULT_TIMEZONE).format('YYYY-MM-DD') === tomorrowKey,
      ).sort((a, b) => dayjs(a.scheduled_at).valueOf() - dayjs(b.scheduled_at).valueOf()),
    [allLessons, tomorrowKey],
  );

  const weekLessons = useMemo(
    () =>
      nonCancelledLessons.filter((lesson) => {
        const lessonTime = dayjs(lesson.scheduled_at).tz(lesson.timezone || DEFAULT_TIMEZONE);
        return lessonTime.isSameOrAfter(weekStart) && lessonTime.isBefore(weekEnd);
      }),
    [nonCancelledLessons, weekEnd, weekStart],
  );

  const learnerCount = learnersData?.total ?? 0;
  const inviteCount = inviteTokensData?.total ?? inviteTokensData?.items?.length ?? 0;
  const packageCount = packagesSummaryData?.total ?? 0;
  const lessonCount = lessonsSummaryData?.total ?? 0;
  const lessonById = useMemo(
    () => new Map(allLessons.map((lesson) => [lesson.id, lesson])),
    [allLessons],
  );
  const activeDismissalKeys = useMemo(
    () => new Set(attentionDismissals.map((item) => item.item_key)),
    [attentionDismissals],
  );
  const attentionNow = dayjs().tz(DEFAULT_TIMEZONE);
  const attentionCutoff = attentionNow.add(3, 'day');

  const packageAttentionItems = useMemo(() => (
    activePackages
      .flatMap((pkg) => {
        const futureLessons = allLessons
          .filter((lesson) => {
            if (lesson.package_id !== pkg.id || lesson.status === 'cancelled') {
              return false;
            }
            const lessonTime = dayjs(lesson.scheduled_at).tz(lesson.timezone || DEFAULT_TIMEZONE);
            return lessonTime.isSameOrAfter(attentionNow);
          })
          .sort((a, b) => dayjs(a.scheduled_at).valueOf() - dayjs(b.scheduled_at).valueOf());

        if (futureLessons.length === 0) {
          return [];
        }

        const lastLesson = futureLessons[futureLessons.length - 1];
        const lastLessonTime = dayjs(lastLesson.scheduled_at).tz(lastLesson.timezone || DEFAULT_TIMEZONE);
        if (lastLessonTime.isAfter(attentionCutoff)) {
          return [];
        }

        const itemKey = `package_ending_soon:${pkg.id}:${lastLessonTime.toISOString()}`;
        if (activeDismissalKeys.has(itemKey)) {
          return [];
        }

        return [{
          key: itemKey,
          learnerName: pkg.learner_name || t('pages.dashboard.learner'),
          packageTitle: pkg.title,
          lastLessonTime,
          dismissedUntil: lastLessonTime.toISOString(),
        }];
      })
      .sort((a, b) => a.lastLessonTime.valueOf() - b.lastLessonTime.valueOf())
  ), [activeDismissalKeys, activePackages, allLessons, attentionCutoff, attentionNow, t]);

  const lessonAttentionItems = useMemo(() => (
    notificationActivity
      .flatMap((activity) => {
        if (
          activity.activity_type !== 'teacher_alert'
          || activity.event_type !== 'lesson'
          || activity.metadata?.alert_code !== 'lesson_declined'
          || !activity.event_id
        ) {
          return [];
        }

        const lesson = lessonById.get(activity.event_id);
        if (!lesson) {
          return [];
        }

        const lessonTime = dayjs(lesson.scheduled_at).tz(lesson.timezone || DEFAULT_TIMEZONE);
        if (!lessonTime.isAfter(attentionNow)) {
          return [];
        }

        const itemKey = `lesson_declined:${activity.activity_id}:${lesson.id}`;
        if (activeDismissalKeys.has(itemKey)) {
          return [];
        }

        return [{
          key: itemKey,
          learnerName: activity.learner_display_name || lesson.learner_name || t('pages.dashboard.learner'),
          lessonTime,
          dismissedUntil: lessonTime.toISOString(),
        }];
      })
      .sort((a, b) => a.lessonTime.valueOf() - b.lessonTime.valueOf())
  ), [activeDismissalKeys, attentionNow, lessonById, notificationActivity, t]);

  const notificationIssueItems = useMemo(() => {
    const issueMap = new Map<number, NotificationInstance>();

    failedNotificationInstances.forEach((instance) => {
      issueMap.set(instance.id, instance);
    });

    queuedNotificationInstances.forEach((instance) => {
      const latestAttemptStatus = instance.latest_attempt?.status;
      if (latestAttemptStatus === 'failed' || latestAttemptStatus === 'failed_retryable') {
        issueMap.set(instance.id, instance);
      }
    });

    return Array.from(issueMap.values()).sort(
      (a, b) => dayjs(a.effective_scheduled_for).valueOf() - dayjs(b.effective_scheduled_for).valueOf(),
    );
  }, [failedNotificationInstances, queuedNotificationInstances]);

  const upcomingNotificationItems = useMemo(() => (
    queuedNotificationInstances
      .filter((instance) => {
        if (instance.status !== 'scheduled' || instance.delivery_enabled === false) {
          return false;
        }
        return dayjs(instance.effective_scheduled_for).tz(DEFAULT_TIMEZONE).isSameOrAfter(attentionNow);
      })
      .sort((a, b) => dayjs(a.effective_scheduled_for).valueOf() - dayjs(b.effective_scheduled_for).valueOf())
      .slice(0, 5)
  ), [attentionNow, queuedNotificationInstances]);

  const isLoadingAttention =
    !loadDeferredPanels
    || isLoadingActivePackages
    || isLoadingNotificationActivity
    || isLoadingFailedNotificationInstances
    || isLoadingQueuedNotificationInstances
    || isLoadingAttentionDismissals;
  const hasAttentionItems =
    packageAttentionItems.length > 0
    || lessonAttentionItems.length > 0
    || notificationIssueItems.length > 0;

  const onboardingSteps = [
    {
      key: 'learners',
      done: learnerCount > 0,
      icon: <UserAddOutlined />,
      title: t('pages.dashboard.onboarding.steps.learners.title'),
      description: t('pages.dashboard.onboarding.steps.learners.description'),
      action: t('pages.dashboard.onboarding.steps.learners.action'),
      path: '/learners',
    },
    {
      key: 'invite',
      done: inviteCount > 0,
      icon: <KeyOutlined />,
      title: t('pages.dashboard.onboarding.steps.invite.title'),
      description: t('pages.dashboard.onboarding.steps.invite.description'),
      action: t('pages.dashboard.onboarding.steps.invite.action'),
      path: '/learners',
    },
    {
      key: 'packages',
      done: packageCount > 0,
      icon: <PlusOutlined />,
      title: t('pages.dashboard.onboarding.steps.packages.title'),
      description: t('pages.dashboard.onboarding.steps.packages.description'),
      action: t('pages.dashboard.onboarding.steps.packages.action'),
      path: '/packages',
    },
    {
      key: 'lessons',
      done: lessonCount > 0,
      icon: <CalendarOutlined />,
      title: t('pages.dashboard.onboarding.steps.lessons.title'),
      description: t('pages.dashboard.onboarding.steps.lessons.description'),
      action: t('pages.dashboard.onboarding.steps.lessons.action'),
      path: '/lessons',
    },
  ];

  const completedOnboardingSteps = onboardingSteps.filter((step) => step.done).length;
  const isOnboardingReady =
    hasLearnersData
    && hasPackagesSummaryData
    && hasLessonsSummaryData
    && (tenantId === null || hasInviteTokensData);
  const showOnboarding = isOnboardingReady && completedOnboardingSteps < onboardingSteps.length;

  const upcomingSections = [
    {
      key: 'today',
      title: t('pages.dashboard.todayLabel'),
      lessons: todayLessons,
      emptyText: t('pages.dashboard.noLessonsToday'),
    },
    {
      key: 'tomorrow',
      title: t('pages.dashboard.tomorrowLabel'),
      lessons: tomorrowLessons,
      emptyText: t('pages.dashboard.noLessonsTomorrow'),
    },
  ];

  const renderLessonRow = (lesson: Lesson) => {
    const palette = statusColors[lesson.status];
    return (
      <div
        key={lesson.id}
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: spacing.sm,
          width: '100%',
          padding: '8px 10px',
          borderRadius: tileRadius,
          background: colors.bgTertiary,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 84 }}>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: palette.border,
              flex: '0 0 auto',
            }}
          />
          <div>
          <Text strong style={{ display: 'block', lineHeight: 1.1 }}>
            {dayjs(lesson.scheduled_at).tz(lesson.timezone || DEFAULT_TIMEZONE).format('HH:mm')}
          </Text>
          <Text type="secondary" style={{ fontSize: 11, lineHeight: 1.2 }}>
            {t(`calendar.status.${lesson.status}`)}
          </Text>
          </div>
        </div>
        <Text
          style={{
            flex: 1,
            minWidth: 0,
            textAlign: 'right',
            color: textColor,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {lesson.learner_name || t('pages.dashboard.learner')}
        </Text>
      </div>
    );
  };

  const kpiItems = [
    {
      label: t('pages.dashboard.todayKpi'),
      value: todayLessons.length,
      icon: <FieldTimeOutlined />,
      tint: `${colors.accentPrimary}14`,
      iconColor: colors.accentPrimary,
    },
    {
      label: t('pages.dashboard.tomorrowKpi'),
      value: tomorrowLessons.length,
      icon: <CalendarOutlined />,
      tint: `${kpiPalette.green}14`,
      iconColor: kpiPalette.green,
    },
    {
      label: t('pages.dashboard.weekKpi'),
      value: weekLessons.length,
      icon: <ScheduleOutlined />,
      tint: `${kpiPalette.amber}14`,
      iconColor: kpiPalette.amber,
    },
    {
      label: t('pages.dashboard.learnersKpi'),
      value: learnerCount,
      icon: <TeamOutlined />,
      tint: `${kpiPalette.violet}14`,
      iconColor: kpiPalette.violet,
    },
  ];

  const attentionTileStyle = {
    ...cardStyle,
    width: '100%',
    border: `0px solid ${colors.borderPrimary}`,
    borderRadius: tileRadius,
    boxShadow: 'none',
  };
  const historyTileStyle = attentionTileStyle;
  const secondaryTileStyle = attentionTileStyle;

  const formatAttentionDateTime = (value: string | dayjs.Dayjs) =>
    (dayjs.isDayjs(value) ? value : dayjs(value).tz(DEFAULT_TIMEZONE)).format('D MMM, HH:mm');

  const renderAttentionRow = ({
    key,
    primary,
    secondary,
    dismissible = false,
    onDismiss,
  }: {
    key: string;
    primary: string;
    secondary: string;
    dismissible?: boolean;
    onDismiss?: () => void;
  }) => (
    <div
      key={key}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: spacing.sm,
        padding: '10px 12px',
        borderRadius: tileRadius,
        background: colors.bgTertiary,
      }}
    >
      <div style={{ minWidth: 0, flex: 1 }}>
        <Text strong style={{ display: 'block', lineHeight: 1.2 }}>
          {primary}
        </Text>
        <Text type="secondary" style={{ fontSize: 12, lineHeight: 1.3 }}>
          {secondary}
        </Text>
      </div>
      {dismissible && onDismiss ? (
        <Button
          type="text"
          size="small"
          icon={<CloseOutlined />}
          aria-label={t('pages.dashboard.attention.dismiss')}
          onClick={onDismiss}
          disabled={dismissAttentionMutation.isPending && dismissAttentionMutation.variables?.item_key === key}
          style={{ flex: '0 0 auto', color: colors.textSecondary }}
        />
      ) : null}
    </div>
  );

  const upcomingTile = (
    <Card
      title={t('pages.dashboard.upcomingLessons')}
      variant="borderless"
      style={dashboardTileStyle}
      styles={{
        header: dashboardCardHeaderStyle,
        body: { height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 },
      }}
    >
      {isLoadingLessons ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
          <Skeleton active paragraph={{ rows: 4 }} title={{ width: '42%' }} />
          <Skeleton active paragraph={{ rows: 4 }} title={{ width: '42%' }} />
        </div>
      ) : (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: spacing.md,
            height: '100%',
            minHeight: 0,
            overflowY: 'auto',
            paddingRight: 2,
          }}
        >
          {upcomingSections.map((section) => (
            <div
              key={section.key}
              style={{ display: 'flex', flexDirection: 'column', gap: 4 }}
            >
              <Text type="secondary" style={{ fontSize: 12 }}>
                {section.title}
              </Text>
              {section.lessons.length > 0 ? (
                section.lessons.map((lesson) => renderLessonRow(lesson))
              ) : (
                <div
                  style={{
                    minHeight: 44,
                    display: 'flex',
                    alignItems: 'center',
                    paddingInline: spacing.sm,
                    borderRadius: tileRadius,
                    background: colors.bgTertiary,
                  }}
                >
                  <Text type="secondary">{section.emptyText}</Text>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );

  const miniCalendarTile = (
    <Card
      variant="borderless"
      style={dashboardTileStyle}
      styles={{ body: { padding: isMobile ? 12 : 16, height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 } }}
    >
      {isLoadingLessons ? (
        <Skeleton active paragraph={{ rows: 8 }} title={{ width: '48%' }} />
      ) : (
        <DashboardMiniWeekCalendar
          lessons={allLessons}
          timezone={DEFAULT_TIMEZONE}
          onOpenCalendar={() => navigate('/lessons')}
        />
      )}
    </Card>
  );

  const kpiTile = (
    <Card
      title={t('pages.dashboard.kpiTitle')}
      variant="borderless"
      style={dashboardTileStyle}
      styles={{
        header: dashboardCardHeaderStyle,
        body: { height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 },
      }}
    >
      <div style={{ display: 'grid', gridTemplateRows: 'repeat(4, minmax(0, 1fr))', gap: 6, height: '100%', minHeight: 0 }}>
        {kpiItems.map((item) => (
          <div
            key={item.label}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 10,
              padding: isMobile ? 10 : 10,
              borderRadius: tileRadius,
              background: colors.bgTertiary,
              border: `0px solid ${borderColor}`,
              minHeight: 0,
            }}
          >
            <div
              style={{
                width: isMobile ? 32 : 34,
                height: isMobile ? 32 : 34,
                borderRadius: tileRadius,
                background: item.tint,
                color: item.iconColor,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flex: '0 0 auto',
                fontSize: isMobile ? 15 : 16,
              }}
            >
              {item.icon}
            </div>
            <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
              <Text type="secondary" style={{ fontSize: 12, lineHeight: 1.2, minWidth: 0 }}>
                {item.label}
              </Text>
              <Text strong style={{ fontSize: isMobile ? 18 : 22, lineHeight: 1, flex: '0 0 auto' }}>
                {item.value}
              </Text>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );

  const attentionSections = [
    {
      key: 'packages',
      icon: <AppstoreOutlined />,
      title: t('pages.dashboard.attention.sections.packages'),
      items: packageAttentionItems.map((item) => renderAttentionRow({
        key: item.key,
        primary: `${item.learnerName} · ${item.packageTitle}`,
        secondary: t('pages.dashboard.attention.packageEndingSoonLine', {
          date: formatAttentionDateTime(item.lastLessonTime),
        }),
        dismissible: true,
        onDismiss: () => dismissAttentionMutation.mutate({
          item_type: 'package_ending_soon',
          item_key: item.key,
          dismissed_until: item.dismissedUntil,
        }),
      })),
    },
    {
      key: 'notifications',
      icon: <BellOutlined />,
      title: t('pages.dashboard.attention.sections.notifications'),
      items: notificationIssueItems.map((item) => renderAttentionRow({
        key: `notification_issue:${item.id}`,
        primary: item.learner_display_name || t('pages.dashboard.learner'),
        secondary: [
          t(`pages.notifications.categories.${item.category}`, { defaultValue: item.category }),
          formatAttentionDateTime(item.effective_scheduled_for),
          item.latest_attempt?.error_message || t('pages.dashboard.attention.notificationIssueFallback'),
        ].join(' · '),
      })),
    },
    {
      key: 'lessons',
      icon: <CalendarOutlined />,
      title: t('pages.dashboard.attention.sections.lessons'),
      items: lessonAttentionItems.map((item) => renderAttentionRow({
        key: item.key,
        primary: item.learnerName,
        secondary: t('pages.dashboard.attention.lessonDeclinedLine', {
          date: formatAttentionDateTime(item.lessonTime),
        }),
        dismissible: true,
        onDismiss: () => dismissAttentionMutation.mutate({
          item_type: 'lesson_declined',
          item_key: item.key,
          dismissed_until: item.dismissedUntil,
        }),
      })),
    },
  ].filter((section) => section.items.length > 0);

  const attentionTile = (
    <Card
      title={t('pages.dashboard.attention.title')}
      variant="borderless"
      style={attentionTileStyle}
      styles={{
        header: dashboardCardHeaderStyle,
        body: {
          padding: isLoadingAttention || hasAttentionItems ? (isMobile ? 12 : 16) : 12,
        },
      }}
    >
      {isLoadingAttention ? (
        <div style={{ display: 'flex', justifyContent: 'center', paddingBlock: spacing.md }}>
          <Spin size="small" />
        </div>
      ) : !hasAttentionItems ? (
        <div
          style={{
            padding: '8px 12px',
            borderRadius: tileRadius,
            background: colors.bgTertiary,
          }}
        >
          <Text type="secondary">{t('pages.dashboard.attention.empty')}</Text>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
          {attentionSections.map((section) => (
            <div key={section.key} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <Text type="secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                {section.icon}
                {section.title}
              </Text>
              {section.items}
            </div>
          ))}
        </div>
      )}
    </Card>
  );

  const financeTile = (
    <Card
      title={t('pages.dashboard.finance.title')}
      variant="borderless"
      style={secondaryTileStyle}
      extra={(
        <Button type="text" size="small" onClick={() => navigate('/finance/dashboard')}>
          {t('pages.dashboard.finance.open')}
        </Button>
      )}
      styles={{
        header: dashboardCardHeaderStyle,
        body: { padding: isMobile ? 12 : 16 },
      }}
    >
      {!loadDeferredPanels || isLoadingFinanceMetrics ? (
        <div style={{ display: 'flex', justifyContent: 'center', paddingBlock: spacing.md }}>
          <Spin size="small" />
        </div>
      ) : isErrorFinanceMetrics ? (
        <Alert
          type="warning"
          showIcon
          message={t('pages.dashboard.finance.unavailable')}
          description={
            financeMetricsError instanceof AxiosError && financeMetricsError.response?.status === 403
              ? t('pages.dashboard.finance.noAccess')
              : financeMetricsError.message
          }
        />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'repeat(3, minmax(0, 1fr))', gap: 10 }}>
          {[
            {
              label: t('pages.dashboard.finance.monthIncome'),
              value: formatCurrency(financeMetrics?.current_month_income || 0),
              color: colors.accentSuccess,
            },
            {
              label: t('pages.dashboard.finance.outstanding'),
              value: formatCurrency(financeMetrics?.total_outstanding || 0),
              color: (financeMetrics?.total_outstanding || 0) > 0 ? '#faad14' : textColor,
            },
            {
              label: t('pages.dashboard.finance.debtors'),
              value: String(financeMetrics?.unpaid_learners_count || 0),
              color: (financeMetrics?.unpaid_learners_count || 0) > 0 ? '#ff4d4f' : textColor,
            },
          ].map((item) => (
            <div
              key={item.label}
              style={{
                minHeight: 92,
                padding: 14,
                borderRadius: tileRadius,
                background: colors.bgTertiary,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                gap: 10,
              }}
            >
              <Text type="secondary" style={{ fontSize: 12, lineHeight: 1.25 }}>
                {item.label}
              </Text>
              <Text strong style={{ color: item.color, fontSize: 20, lineHeight: 1.1 }}>
                {item.value}
              </Text>
            </div>
          ))}
        </div>
      )}
    </Card>
  );

  const notificationsTile = (
    <Card
      title={t('pages.dashboard.notifications.title')}
      variant="borderless"
      style={secondaryTileStyle}
      extra={(
        <Button type="text" size="small" onClick={() => navigate('/notifications')}>
          {t('pages.dashboard.notifications.open')}
        </Button>
      )}
      styles={{
        header: dashboardCardHeaderStyle,
        body: { padding: isMobile ? 12 : 16 },
      }}
    >
      {!loadDeferredPanels || isLoadingQueuedNotificationInstances ? (
        <div style={{ display: 'flex', justifyContent: 'center', paddingBlock: spacing.md }}>
          <Spin size="small" />
        </div>
      ) : upcomingNotificationItems.length === 0 ? (
        <div
          style={{
            padding: '10px 12px',
            borderRadius: tileRadius,
            background: colors.bgTertiary,
          }}
        >
          <Text type="secondary">{t('pages.dashboard.notifications.empty')}</Text>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {upcomingNotificationItems.map((item) => (
            <div
              key={item.id}
              style={{
                display: 'grid',
                gridTemplateColumns: 'minmax(0, 1fr) auto',
                gap: 10,
                alignItems: 'center',
                padding: '10px 12px',
                borderRadius: tileRadius,
                background: colors.bgTertiary,
              }}
            >
              <div style={{ minWidth: 0 }}>
                <Text strong style={{ display: 'block', lineHeight: 1.2 }}>
                  {item.learner_display_name || t('pages.dashboard.learner')}
                </Text>
                <Text type="secondary" style={{ display: 'block', fontSize: 12, lineHeight: 1.3 }}>
                  {t(`pages.notifications.categories.${item.category}`, { defaultValue: item.category })}
                </Text>
              </div>
              <Text style={{ color: textColor, fontSize: 12, whiteSpace: 'nowrap' }}>
                {formatAttentionDateTime(item.effective_scheduled_for)}
              </Text>
            </div>
          ))}
        </div>
      )}
    </Card>
  );

  const heatmapTile = (
    <Card
      title={t('pages.dashboard.level3.heatmap.title')}
      variant="borderless"
      style={historyTileStyle}
      styles={{
        header: dashboardCardHeaderStyle,
        body: { padding: isMobile ? 12 : 16 },
      }}
    >
      {!loadDeferredPanels || isLoadingDashboardHistory ? (
        <div style={{ display: 'flex', justifyContent: 'center', paddingBlock: spacing.lg }}>
          <Spin size="small" />
        </div>
      ) : isErrorDashboardHistory || !dashboardHistoryData ? (
        <Alert
          type="warning"
          showIcon
          message={t('pages.dashboard.level3.historyUnavailable')}
          description={dashboardHistoryError?.message}
        />
      ) : (
        <DashboardLessonLoadHeatmap
          days={dashboardHistoryData.heatmap.days}
          fromDate={dashboardHistoryData.heatmap.from_date}
          toDate={dashboardHistoryData.heatmap.to_date}
        />
      )}
    </Card>
  );

  const weeklyLoadTile = (
    <Card
      title={t('pages.dashboard.level3.weeklyLoad.title')}
      variant="borderless"
      style={historyTileStyle}
      styles={{
        header: dashboardCardHeaderStyle,
        body: { padding: isMobile ? 12 : 16 },
      }}
    >
      {!loadDeferredPanels || isLoadingDashboardHistory ? (
        <div style={{ display: 'flex', justifyContent: 'center', paddingBlock: spacing.lg }}>
          <Spin size="small" />
        </div>
      ) : isErrorDashboardHistory || !dashboardHistoryData ? (
        <Alert
          type="warning"
          showIcon
          message={t('pages.dashboard.level3.historyUnavailable')}
          description={dashboardHistoryError?.message}
        />
      ) : (
        <DashboardWeeklyLoad weeks={dashboardHistoryData.weekly_load.weeks} />
      )}
    </Card>
  );

  if (requiresTenantContext) {
    return <TenantContextRequired sectionLabel={t('pages.dashboard.title')} />;
  }

  if (isErrorLessons) {
    return <Alert message={t('errors.fetchLessons')} description={errorLessons?.message} type="error" />;
  }

  return (
    <div style={{ padding: isMobile ? 0 : spacing.lg }}>
      {showOnboarding && (
        <Card
          title={t('pages.dashboard.onboarding.title')}
          variant="borderless"
          style={{ ...cardStyle, marginBottom: 24 }}
          styles={{ header: dashboardCardHeaderStyle }}
          extra={
            <span style={{ color: subtitleColor, fontSize: 13 }}>
              {t('pages.dashboard.onboarding.progress', {
                completed: completedOnboardingSteps,
                total: onboardingSteps.length,
              })}
            </span>
          }
        >
          <div style={{ marginBottom: 16 }}>
            <span style={{ color: subtitleColor }}>
              {t('pages.dashboard.onboarding.description')}
            </span>
          </div>
          <List
            dataSource={onboardingSteps}
            renderItem={(step) => (
              <List.Item
                actions={[
                  step.done ? (
                    <Button key="done" disabled>
                      {t('pages.dashboard.onboarding.done')}
                    </Button>
                  ) : (
                    <Button key="action" type="primary" onClick={() => navigate(step.path)}>
                      {step.action}
                    </Button>
                  ),
                ]}
              >
                <List.Item.Meta
                  avatar={
                    step.done ? (
                      <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 20 }} />
                    ) : (
                      <span style={{ color: '#1890ff', fontSize: 20 }}>{step.icon}</span>
                    )
                  }
                  title={step.title}
                  description={step.description}
                />
              </List.Item>
            )}
          />
        </Card>
      )}

      {isMobile ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
          {upcomingTile}
          {attentionTile}
          {miniCalendarTile}
          {financeTile}
          {notificationsTile}
          {kpiTile}
          {heatmapTile}
          {weeklyLoadTile}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={9} xl={7} style={{ display: 'flex' }}>
              {upcomingTile}
            </Col>
            <Col xs={24} lg={15} xl={13} style={{ display: 'flex' }}>
              {miniCalendarTile}
            </Col>
            <Col xs={24} lg={24} xl={4} style={{ display: 'flex' }}>
              {kpiTile}
            </Col>
          </Row>
          {attentionTile}
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={12} style={{ display: 'flex' }}>
              {financeTile}
            </Col>
            <Col xs={24} lg={12} style={{ display: 'flex' }}>
              {notificationsTile}
            </Col>
          </Row>
          <Row gutter={[16, 16]}>
            <Col xs={24} style={{ display: 'flex' }}>
              {heatmapTile}
            </Col>
          </Row>
          <Row gutter={[16, 16]}>
            <Col xs={24} style={{ display: 'flex' }}>
              {weeklyLoadTile}
            </Col>
          </Row>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
