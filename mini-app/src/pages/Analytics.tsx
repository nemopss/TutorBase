import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  Col,
  Collapse,
  DatePicker,
  Progress,
  Row,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from 'antd';
import {
  AlertOutlined,
  BarChartOutlined,
  BellOutlined,
  CalendarOutlined,
  ClockCircleOutlined,
  DollarOutlined,
  FireOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import dayjs, { Dayjs } from 'dayjs';
import { useTranslation } from 'react-i18next';
import api from '../services/api';
import PageHeader from '../components/common/PageHeader';
import TenantContextRequired from '../components/common/TenantContextRequired';
import { useAuth } from '../auth/AuthProvider';
import { useResponsiveStyles } from '../hooks/useResponsiveStyles';
import { useResponsive } from '../hooks/useResponsive';
import { useTheme } from '../theme/ThemeProvider';
import { spacing } from '../theme/tokens';

const { RangePicker } = DatePicker;
const { Text } = Typography;

interface AnalyticsMetricComparison {
  current: number;
  previous: number;
  delta: number;
  change_percent: number | null;
}

interface AnalyticsSummary {
  active_learners: number;
  completed_lessons: number;
  planned_lessons: number;
  cancelled_lessons: number;
  completed_hours: number;
  planned_hours: number;
  cash_revenue: number | string;
  earned_revenue: number | string;
  planned_revenue: number | string;
  outstanding_revenue: number | string;
  cancellation_rate: number;
  notification_delivery_rate: number;
}

interface AnalyticsTimePoint {
  date: string;
  completed_lessons: number;
  planned_lessons: number;
  cancelled_lessons: number;
  completed_hours: number;
  planned_hours: number;
  cash_revenue: number | string;
  earned_revenue: number | string;
  reminders_scheduled: number;
  reminders_delivered: number;
  reminders_failed: number;
}

interface AnalyticsWeekdayPoint {
  weekday: number;
  completed_lessons: number;
  planned_lessons: number;
  cancelled_lessons: number;
  completed_hours: number;
  planned_hours: number;
}

interface AnalyticsLearnerBreakdown {
  learner_id: number;
  learner_name: string;
  completed_lessons: number;
  planned_lessons: number;
  cancelled_lessons: number;
  completed_hours: number;
  planned_hours: number;
  cash_revenue: number | string;
  earned_revenue: number | string;
  planned_revenue: number | string;
  outstanding_revenue: number | string;
  cancellation_rate: number;
  has_future_lessons: boolean;
  risk_flags: string[];
}

interface AnalyticsPackageBreakdown {
  package_id: number;
  package_title: string;
  learner_id: number;
  learner_name: string;
  status: string;
  total_lessons: number;
  completed_lessons: number;
  cancelled_lessons: number;
  remaining_lessons: number;
  progress_percent: number;
  next_lesson_at?: string | null;
  last_lesson_at?: string | null;
  ends_soon: boolean;
  risk_flags: string[];
}

interface AnalyticsNotifications {
  total_scheduled: number;
  total_delivered: number;
  total_failed: number;
  delivery_rate: number;
  failed_learners_count: number;
  no_telegram_learners_count: number;
}

interface AnalyticsInsight {
  code:
    | 'no_future_learners'
    | 'high_cancellation_rate'
    | 'ending_packages'
    | 'outstanding_balance'
    | 'notification_failures'
    | 'no_telegram_learners'
    | 'no_critical_issues';
  category: 'learner' | 'package' | 'finance' | 'notifications' | 'workload';
  severity: 'info' | 'warning' | 'critical';
  title: string;
  detail: string;
  action_label?: string | null;
  target_path?: string | null;
  metric_value?: number | null;
}

interface AnalyticsOverviewResponse {
  period_start: string;
  period_end: string;
  previous_period_start: string;
  previous_period_end: string;
  summary: AnalyticsSummary;
  comparisons: Record<string, AnalyticsMetricComparison>;
  timeseries: AnalyticsTimePoint[];
  weekday_load: AnalyticsWeekdayPoint[];
  learners: AnalyticsLearnerBreakdown[];
  packages: AnalyticsPackageBreakdown[];
  notifications: AnalyticsNotifications;
  insights: AnalyticsInsight[];
}

type PresetKey = '7d' | '30d' | 'month' | 'next7';
type ActivePresetKey = PresetKey | 'custom';

const presetRanges: Array<{ key: PresetKey; labelKey: string; getRange: () => [Dayjs, Dayjs] }> = [
  { key: '7d', labelKey: 'pages.analytics.presets.sevenDays', getRange: () => [dayjs().subtract(6, 'day').startOf('day'), dayjs().endOf('day')] },
  { key: '30d', labelKey: 'pages.analytics.presets.thirtyDays', getRange: () => [dayjs().subtract(29, 'day').startOf('day'), dayjs().endOf('day')] },
  { key: 'month', labelKey: 'pages.analytics.presets.month', getRange: () => [dayjs().startOf('month'), dayjs().endOf('day')] },
  { key: 'next7', labelKey: 'pages.analytics.presets.nextSevenDays', getRange: () => [dayjs().startOf('day'), dayjs().add(7, 'day').endOf('day')] },
];

const currencyFormatter = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'RUB',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const numberFormatter = new Intl.NumberFormat('ru-RU', {
  maximumFractionDigits: 1,
});

const compactNumberFormatter = new Intl.NumberFormat('ru-RU', {
  notation: 'compact',
  maximumFractionDigits: 1,
});

const toNumber = (value: number | string | null | undefined): number => Number(value || 0);

const formatCurrency = (value: number | string): string => currencyFormatter.format(toNumber(value));

const formatPercent = (value: number): string => `${Math.round(value * 100)}%`;

const formatHours = (value: number, unit: string): string => `${numberFormatter.format(value)} ${unit}`;

const getSeverityColor = (severity: AnalyticsInsight['severity'], colors: ReturnType<typeof useTheme>['resolvedTheme']['colors']) => {
  if (severity === 'critical') return colors.accentError;
  if (severity === 'warning') return colors.accentWarning;
  return colors.accentInfo;
};

const fetchAnalyticsOverview = async (fromDate: string, toDate: string): Promise<AnalyticsOverviewResponse> => {
  const { data } = await api.get('/analytics/overview', {
    params: {
      from_date: fromDate,
      to_date: toDate,
    },
  });
  return data;
};

const Analytics: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { tenantId } = useAuth();
  const requiresTenantContext = tenantId === null;
  const { cardStyle, textColor, subtitleColor, chartGridColor, tooltipStyle } = useResponsiveStyles();
  const { resolvedTheme } = useTheme();
  const { isMobile } = useResponsive();
  const colors = resolvedTheme.colors;
  const tileRadius = 10;
  const hourUnit = t('pages.analytics.units.hoursShort');
  const weekdayLabels = [
    t('pages.analytics.weekdays.mon'),
    t('pages.analytics.weekdays.tue'),
    t('pages.analytics.weekdays.wed'),
    t('pages.analytics.weekdays.thu'),
    t('pages.analytics.weekdays.fri'),
    t('pages.analytics.weekdays.sat'),
    t('pages.analytics.weekdays.sun'),
  ];
  const [activePreset, setActivePreset] = useState<ActivePresetKey>('30d');
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs]>(presetRanges[1].getRange());

  const getRiskLabel = (flag: string) => t(`pages.analytics.riskFlags.${flag}`, { defaultValue: flag });

  const getInsightCopy = (insight: AnalyticsInsight) => {
    const count = Math.round(insight.metric_value ?? 0);
    return {
      title: t(`pages.analytics.insights.${insight.code}.title`, { defaultValue: insight.title, count }),
      detail: t(`pages.analytics.insights.${insight.code}.detail`, { defaultValue: insight.detail, count }),
      action: insight.action_label
        ? t(`pages.analytics.insights.${insight.code}.action`, { defaultValue: insight.action_label, count })
        : null,
    };
  };

  const fromDate = dateRange[0].toISOString();
  const toDate = dateRange[1].toISOString();

  const {
    data,
    isLoading,
    isError,
    error,
  } = useQuery<AnalyticsOverviewResponse, Error>({
    queryKey: ['analyticsOverview', fromDate, toDate],
    queryFn: () => fetchAnalyticsOverview(fromDate, toDate),
    enabled: !requiresTenantContext,
  });

  const chartData = useMemo(
    () => (data?.timeseries || []).map((item) => ({
      date: dayjs(item.date).format('D MMM'),
      completedHours: item.completed_hours,
      plannedHours: item.planned_hours,
      completedLessons: item.completed_lessons,
      plannedLessons: item.planned_lessons,
      cancelledLessons: item.cancelled_lessons,
      cashRevenue: toNumber(item.cash_revenue),
      earnedRevenue: toNumber(item.earned_revenue),
      delivered: item.reminders_delivered,
      failed: item.reminders_failed,
      scheduled: item.reminders_scheduled,
    })),
    [data?.timeseries],
  );

  const weekdayData = useMemo(
    () => (data?.weekday_load || []).map((item) => ({
      name: weekdayLabels[item.weekday],
      completed: item.completed_hours,
      planned: item.planned_hours,
      cancelled: item.cancelled_lessons,
    })),
    [data?.weekday_load],
  );

  const highRiskLearners = useMemo(
    () => (data?.learners || []).filter((learner) => learner.risk_flags.length > 0).slice(0, 6),
    [data?.learners],
  );

  const importantPackages = useMemo(
    () => (data?.packages || []).filter((pkg) => pkg.risk_flags.length > 0).slice(0, 6),
    [data?.packages],
  );

  const learnersWithoutFuture = useMemo(
    () => (data?.learners || []).filter((learner) => learner.risk_flags.includes('no_future_lessons')),
    [data?.learners],
  );

  const learnersWithHighCancellation = useMemo(
    () => (data?.learners || []).filter((learner) => learner.risk_flags.includes('high_cancellation_rate')),
    [data?.learners],
  );

  const learnersWithDebt = useMemo(
    () => (data?.learners || []).filter((learner) => learner.risk_flags.includes('outstanding_balance')),
    [data?.learners],
  );

  const learnersWithoutTelegram = useMemo(
    () => (data?.learners || []).filter((learner) => learner.risk_flags.includes('no_telegram')),
    [data?.learners],
  );

  const packagesEndingSoon = useMemo(
    () => (data?.packages || []).filter((pkg) => pkg.risk_flags.includes('ending_soon')),
    [data?.packages],
  );

  const applyPreset = (key: PresetKey) => {
    const preset = presetRanges.find((item) => item.key === key);
    if (!preset) return;
    setActivePreset(key);
    setDateRange(preset.getRange());
  };

  const handleDateChange = (dates: null | [Dayjs | null, Dayjs | null]) => {
    if (dates?.[0] && dates?.[1]) {
      setActivePreset('custom');
      setDateRange([dates[0], dates[1]]);
    }
  };

  const shellStyle = {
    ...cardStyle,
    border: 0,
    borderRadius: tileRadius,
    boxShadow: 'none',
  };

  const sectionCardProps = {
    variant: 'borderless' as const,
    style: shellStyle,
    styles: {
      header: { borderBottom: 0 },
      body: { padding: isMobile ? 12 : 16 },
    },
  };

  const comparisonText = (comparison?: AnalyticsMetricComparison) => {
    if (!comparison) return t('pages.analytics.comparison.noData');
    const sign = comparison.delta > 0 ? '+' : '';
    const percent = comparison.change_percent === null
      ? t('pages.analytics.comparison.newPeriod')
      : `${sign}${comparison.change_percent}%`;
    return t('pages.analytics.comparison.summary', {
      delta: `${sign}${numberFormatter.format(comparison.delta)}`,
      percent,
    });
  };

  const renderKpiTile = ({
    label,
    value,
    helper,
    icon,
    color,
    comparison,
  }: {
    label: string;
    value: string;
    helper: string;
    icon: React.ReactNode;
    color: string;
    comparison?: AnalyticsMetricComparison;
  }) => (
    <div
      style={{
        minHeight: 128,
        padding: 14,
        borderRadius: tileRadius,
        background: colors.bgTertiary,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        gap: 12,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'flex-start' }}>
        <Text type="secondary" style={{ fontSize: 12, lineHeight: 1.25 }}>
          {label}
        </Text>
        <span
          style={{
            width: 34,
            height: 34,
            borderRadius: tileRadius,
            background: `${color}16`,
            color,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            flex: '0 0 auto',
          }}
        >
          {icon}
        </span>
      </div>
      <div>
        <Text strong style={{ display: 'block', color: textColor, fontSize: isMobile ? 22 : 26, lineHeight: 1.05 }}>
          {value}
        </Text>
        <Text type="secondary" style={{ display: 'block', fontSize: 12, lineHeight: 1.3, marginTop: 6 }}>
          {helper}
        </Text>
      </div>
      {comparison && (
        <Text type="secondary" style={{ fontSize: 11, lineHeight: 1.2 }}>
          {comparisonText(comparison)}
        </Text>
      )}
    </div>
  );

  const pageHeader = (
    <PageHeader
      title={t('pages.analytics.title')}
      subtitle={t('pages.analytics.subtitle')}
      actions={
        <Space direction={isMobile ? 'vertical' : 'horizontal'} size="small" style={{ width: isMobile ? '100%' : 'auto' }}>
          <div
            role="tablist"
            aria-label={t('pages.analytics.presets.ariaLabel')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              width: isMobile ? '100%' : undefined,
              padding: 4,
              borderRadius: tileRadius,
              background: colors.bgTertiary,
            }}
          >
            {presetRanges.map((preset) => {
              const selected = activePreset === preset.key;
              return (
                <button
                  key={preset.key}
                  type="button"
                  role="tab"
                  aria-selected={selected}
                  onClick={() => applyPreset(preset.key)}
                  style={{
                    flex: isMobile ? 1 : undefined,
                    minWidth: isMobile ? 0 : 88,
                    height: 32,
                    border: 0,
                    borderRadius: 8,
                    background: selected ? colors.bgSecondary : 'transparent',
                    color: selected ? colors.textPrimary : colors.textSecondary,
                    cursor: 'pointer',
                    font: 'inherit',
                    fontSize: 13,
                    fontWeight: selected ? 600 : 400,
                  }}
                >
            {t(preset.labelKey)}
                </button>
              );
            })}
          </div>
          <div style={{ width: isMobile ? '100%' : 278 }}>
            <Text
              type="secondary"
              style={{
                display: 'block',
                marginBottom: 4,
                fontSize: 11,
                lineHeight: 1,
                color: activePreset === 'custom' ? colors.textPrimary : colors.textSecondary,
              }}
            >
              {t('pages.analytics.presets.customRange')}
            </Text>
            <RangePicker
              value={dateRange}
              onChange={handleDateChange}
              format="YYYY-MM-DD"
              style={{ width: '100%' }}
              placement="bottomLeft"
              getPopupContainer={(trigger) => trigger.parentElement || document.body}
            />
          </div>
        </Space>
      }
    />
  );

  if (requiresTenantContext) {
    return (
      <div>
        {pageHeader}
        <TenantContextRequired sectionLabel={t('pages.analytics.title')} />
      </div>
    );
  }

  if (isLoading) {
    return (
      <div>
        {pageHeader}
        <div style={{ display: 'flex', justifyContent: 'center', paddingBlock: spacing.xl }}>
          <Spin />
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div>
        {pageHeader}
        <Alert
          type="error"
          showIcon
          message={t('errors.fetchMetrics')}
          description={error?.message}
        />
      </div>
    );
  }

  const summary = data.summary;
  const earnedRevenue = toNumber(summary.earned_revenue);
  const cashRevenue = toNumber(summary.cash_revenue);
  const plannedRevenue = toNumber(summary.planned_revenue);
  const earnedPerCompletedHour = summary.completed_hours > 0 ? earnedRevenue / summary.completed_hours : 0;
  const earnedPerCompletedLesson = summary.completed_lessons > 0 ? earnedRevenue / summary.completed_lessons : 0;
  const cashPerActiveLearner = summary.active_learners > 0 ? cashRevenue / summary.active_learners : 0;
  const plannedToEarnedRatio = earnedRevenue > 0 ? plannedRevenue / earnedRevenue : 0;

  const getInsightItems = (insight: AnalyticsInsight) => {
    if (insight.code === 'high_cancellation_rate') {
      return learnersWithHighCancellation.map((learner) => ({
        key: `learner-cancel-${learner.learner_id}`,
        title: learner.learner_name,
        detail: t('pages.analytics.insightItems.highCancellation', {
          rate: formatPercent(learner.cancellation_rate),
          cancelled: learner.cancelled_lessons,
          completed: learner.completed_lessons,
        }),
        path: `/learners/${learner.learner_id}`,
        action: t('pages.analytics.actions.openLearner'),
      }));
    }
    if (insight.code === 'no_future_learners') {
      return learnersWithoutFuture.map((learner) => ({
        key: `learner-future-${learner.learner_id}`,
        title: learner.learner_name,
        detail: t('pages.analytics.insightItems.noFuture', {
          completed: learner.completed_lessons,
          planned: learner.planned_lessons,
        }),
        path: `/learners/${learner.learner_id}?section=schedule`,
        action: t('pages.analytics.actions.openSchedule'),
      }));
    }
    if (insight.code === 'ending_packages') {
      return packagesEndingSoon.map((pkg) => ({
        key: `package-ending-${pkg.package_id}`,
        title: pkg.package_title,
        detail: t('pages.analytics.insightItems.endingPackage', {
          learner: pkg.learner_name,
          remaining: pkg.remaining_lessons,
        }),
        path: `/packages/${pkg.package_id}`,
        action: t('pages.analytics.actions.openPackage'),
      }));
    }
    if (insight.code === 'outstanding_balance') {
      return learnersWithDebt.map((learner) => ({
        key: `learner-debt-${learner.learner_id}`,
        title: learner.learner_name,
        detail: t('pages.analytics.insightItems.debt', {
          debt: formatCurrency(learner.outstanding_revenue),
        }),
        path: `/learners/${learner.learner_id}/finance`,
        action: t('pages.analytics.actions.openFinance'),
      }));
    }
    if (insight.code === 'no_telegram_learners') {
      return learnersWithoutTelegram.map((learner) => ({
        key: `learner-telegram-${learner.learner_id}`,
        title: learner.learner_name,
        detail: t('pages.analytics.insightItems.noTelegram'),
        path: `/learners/${learner.learner_id}`,
        action: t('pages.analytics.actions.openLearner'),
      }));
    }
    return [];
  };

  return (
    <div>
      {pageHeader}

      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12} xl={6}>
            {renderKpiTile({
              label: t('pages.analytics.kpi.completedHours'),
              value: formatHours(summary.completed_hours, hourUnit),
              helper: t('pages.analytics.kpi.completedLessons', { count: summary.completed_lessons }),
              icon: <ClockCircleOutlined />,
              color: colors.accentPrimary,
              comparison: data.comparisons.completed_hours,
            })}
          </Col>
          <Col xs={24} sm={12} xl={6}>
            {renderKpiTile({
              label: t('pages.analytics.kpi.plannedLoad'),
              value: formatHours(summary.planned_hours, hourUnit),
              helper: t('pages.analytics.kpi.plannedLessons', { count: summary.planned_lessons }),
              icon: <CalendarOutlined />,
              color: colors.accentSuccess,
            })}
          </Col>
          <Col xs={24} sm={12} xl={6}>
            {renderKpiTile({
              label: t('pages.analytics.kpi.money'),
              value: formatCurrency(summary.cash_revenue),
              helper: t('pages.analytics.kpi.moneyHelper', {
                earned: formatCurrency(summary.earned_revenue),
                planned: formatCurrency(summary.planned_revenue),
              }),
              icon: <DollarOutlined />,
              color: colors.accentWarning,
              comparison: data.comparisons.cash_revenue,
            })}
          </Col>
          <Col xs={24} sm={12} xl={6}>
            {renderKpiTile({
              label: t('pages.analytics.kpi.risks'),
              value: String(data.insights.filter((item) => item.severity !== 'info').length),
              helper: t('pages.analytics.kpi.risksHelper', {
                cancellations: formatPercent(summary.cancellation_rate),
                delivery: formatPercent(summary.notification_delivery_rate),
              }),
              icon: <AlertOutlined />,
              color: summary.cancellation_rate >= 0.2 || data.notifications.total_failed > 0 ? colors.accentError : colors.accentInfo,
            })}
          </Col>
        </Row>

        <Card {...sectionCardProps} title={t('pages.analytics.sections.attention')}>
          <Row gutter={[12, 12]}>
            {data.insights.map((insight) => {
              const accent = getSeverityColor(insight.severity, colors);
              const copy = getInsightCopy(insight);
              const insightItems = getInsightItems(insight);
              const visibleItems = insightItems.slice(0, 3);
              return (
                <Col key={`${insight.category}-${insight.title}`} xs={24} md={12} xl={8}>
                  <div
                    style={{
                      minHeight: 112,
                      height: '100%',
                      padding: 14,
                      borderRadius: tileRadius,
                      background: colors.bgTertiary,
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      gap: 12,
                      borderLeft: `3px solid ${accent}`,
                    }}
                  >
                    <div>
                      <Text strong style={{ display: 'block', lineHeight: 1.25 }}>
                        {copy.title}
                      </Text>
                      <Text type="secondary" style={{ display: 'block', fontSize: 12, lineHeight: 1.35, marginTop: 6 }}>
                        {copy.detail}
                      </Text>
                    </div>
                    {visibleItems.length > 0 && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {visibleItems.map((item) => (
                          <button
                            key={item.key}
                            type="button"
                            onClick={() => navigate(item.path)}
                            style={{
                              width: '100%',
                              border: `1px solid ${colors.borderPrimary}`,
                              borderRadius: 8,
                              background: colors.bgSecondary,
                              color: textColor,
                              cursor: 'pointer',
                              padding: '8px 10px',
                              textAlign: 'left',
                              display: 'grid',
                              gridTemplateColumns: 'minmax(0, 1fr) auto',
                              alignItems: 'center',
                              gap: 8,
                              font: 'inherit',
                            }}
                          >
                            <span style={{ minWidth: 0 }}>
                              <Text strong style={{ display: 'block', fontSize: 12 }} ellipsis>
                                {item.title}
                              </Text>
                              <Text type="secondary" style={{ display: 'block', fontSize: 11, lineHeight: 1.25 }}>
                                {item.detail}
                              </Text>
                            </span>
                            <Text style={{ color: accent, fontSize: 11, whiteSpace: 'nowrap' }}>
                              {item.action}
                            </Text>
                          </button>
                        ))}
                        {insightItems.length > visibleItems.length && (
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            {t('pages.analytics.insightItems.more', { count: insightItems.length - visibleItems.length })}
                          </Text>
                        )}
                      </div>
                    )}
                    {visibleItems.length === 0 && copy.action && insight.target_path && (
                      <Button
                        type="text"
                        size="small"
                        onClick={() => navigate(insight.target_path!)}
                        style={{ alignSelf: 'flex-start', paddingInline: 0, color: accent }}
                      >
                        {copy.action}
                      </Button>
                    )}
                  </div>
                </Col>
              );
            })}
          </Row>
        </Card>

        <Row gutter={[16, 16]}>
          <Col xs={24} xl={15}>
            <Card {...sectionCardProps} title={t('pages.analytics.sections.workloadMoney')}>
              <ResponsiveContainer width="100%" height={isMobile ? 260 : 320}>
                <ComposedChart data={chartData}>
                  <defs>
                    <linearGradient id="completedHours" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={colors.accentPrimary} stopOpacity={0.28} />
                      <stop offset="95%" stopColor={colors.accentPrimary} stopOpacity={0.02} />
                    </linearGradient>
                    <linearGradient id="plannedHours" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={colors.accentSuccess} stopOpacity={0.22} />
                      <stop offset="95%" stopColor={colors.accentSuccess} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke={chartGridColor} strokeDasharray="2 6" vertical={false} />
                  <XAxis dataKey="date" stroke={subtitleColor} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <YAxis
                    yAxisId="hours"
                    stroke={subtitleColor}
                    tick={{ fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) => `${numberFormatter.format(Number(value))} ${hourUnit}`}
                  />
                  <YAxis
                    yAxisId="money"
                    orientation="right"
                    stroke={subtitleColor}
                    tick={{ fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) => compactNumberFormatter.format(Number(value))}
                  />
                  <Tooltip
                    contentStyle={tooltipStyle}
                    formatter={(value: number, name: string, item) => {
                      const dataKey = String(item.dataKey || '');
                      const formattedValue = dataKey.includes('Revenue')
                        ? formatCurrency(value)
                        : formatHours(Number(value), hourUnit);
                      return [formattedValue, name];
                    }}
                  />
                  <Bar
                    yAxisId="money"
                    dataKey="cashRevenue"
                    name={t('pages.analytics.chart.cashRevenue')}
                    fill={colors.accentWarning}
                    opacity={0.28}
                    radius={[6, 6, 0, 0]}
                  />
                  <Area
                    yAxisId="hours"
                    type="monotone"
                    dataKey="completedHours"
                    name={t('pages.analytics.chart.completedHours')}
                    stroke={colors.accentPrimary}
                    strokeWidth={2}
                    fill="url(#completedHours)"
                  />
                  <Area
                    yAxisId="hours"
                    type="monotone"
                    dataKey="plannedHours"
                    name={t('pages.analytics.chart.plannedHours')}
                    stroke={colors.accentSuccess}
                    strokeWidth={2}
                    fill="url(#plannedHours)"
                  />
                  <Line
                    yAxisId="money"
                    type="monotone"
                    dataKey="earnedRevenue"
                    name={t('pages.analytics.chart.earnedRevenue')}
                    stroke={colors.accentWarning}
                    strokeWidth={2}
                    dot={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </Card>
          </Col>
          <Col xs={24} xl={9}>
            <Card {...sectionCardProps} title={t('pages.analytics.sections.weeklyRhythm')}>
              <ResponsiveContainer width="100%" height={isMobile ? 220 : 320}>
                <BarChart data={weekdayData}>
                  <CartesianGrid stroke={chartGridColor} strokeDasharray="2 6" vertical={false} />
                  <XAxis dataKey="name" stroke={subtitleColor} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <YAxis
                    stroke={subtitleColor}
                    tick={{ fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) => `${numberFormatter.format(Number(value))} ${hourUnit}`}
                  />
                  <Tooltip
                    contentStyle={tooltipStyle}
                    labelFormatter={(label) => t('pages.analytics.chart.weekdayTooltip', { day: label })}
                    formatter={(value: number, name: string) => [formatHours(Number(value), hourUnit), name]}
                  />
                  <Bar dataKey="completed" name={t('pages.analytics.chart.completed')} fill={colors.accentPrimary} radius={[6, 6, 0, 0]} />
                  <Bar dataKey="planned" name={t('pages.analytics.chart.planned')} fill={colors.accentSuccess} radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </Col>
        </Row>

        <Row gutter={[16, 16]}>
          <Col xs={24} lg={12}>
            <Card {...sectionCardProps} title={t('pages.analytics.sections.focusLearners')}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {highRiskLearners.length === 0 ? (
                  <div style={{ padding: 12, borderRadius: tileRadius, background: colors.bgTertiary }}>
                    <Text type="secondary">{t('pages.analytics.empty.noLearnerRisks')}</Text>
                  </div>
                ) : highRiskLearners.map((learner) => (
                  <div
                    key={learner.learner_id}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: isMobile ? '1fr' : 'minmax(0, 1fr) auto',
                      gap: 10,
                      padding: '10px 12px',
                      borderRadius: tileRadius,
                      background: colors.bgTertiary,
                      alignItems: 'center',
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <Text strong style={{ display: 'block' }} ellipsis>
                        {learner.learner_name}
                      </Text>
                      <Text type="secondary" style={{ display: 'block', fontSize: 12 }}>
                        {t('pages.analytics.focus.learnerLine', {
                          completed: learner.completed_lessons,
                          cancelled: learner.cancelled_lessons,
                          debt: formatCurrency(learner.outstanding_revenue),
                        })}
                      </Text>
                    </div>
                    <Space size={4} wrap>
                      {learner.risk_flags.slice(0, 3).map((flag) => (
                        <Tag key={flag} bordered={false}>{getRiskLabel(flag)}</Tag>
                      ))}
                    </Space>
                  </div>
                ))}
              </div>
            </Card>
          </Col>
          <Col xs={24} lg={12}>
            <Card {...sectionCardProps} title={t('pages.analytics.sections.focusPackages')}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {importantPackages.length === 0 ? (
                  <div style={{ padding: 12, borderRadius: tileRadius, background: colors.bgTertiary }}>
                    <Text type="secondary">{t('pages.analytics.empty.noPackageRisks')}</Text>
                  </div>
                ) : importantPackages.map((pkg) => (
                  <div
                    key={pkg.package_id}
                    style={{
                      padding: '10px 12px',
                      borderRadius: tileRadius,
                      background: colors.bgTertiary,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 8,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                      <div style={{ minWidth: 0 }}>
                        <Text strong style={{ display: 'block' }} ellipsis>{pkg.package_title}</Text>
                        <Text type="secondary" style={{ display: 'block', fontSize: 12 }}>
                          {t('pages.analytics.focus.packageLine', {
                            learner: pkg.learner_name,
                            remaining: pkg.remaining_lessons,
                          })}
                        </Text>
                      </div>
                      <Text type="secondary" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
                        {Math.round(pkg.progress_percent)}%
                      </Text>
                    </div>
                    <Progress percent={pkg.progress_percent} showInfo={false} size="small" strokeColor={colors.accentPrimary} trailColor={colors.borderPrimary} />
                    <Space size={4} wrap>
                      {pkg.risk_flags.slice(0, 3).map((flag) => (
                        <Tag key={flag} bordered={false}>{getRiskLabel(flag)}</Tag>
                      ))}
                    </Space>
                  </div>
                ))}
              </div>
            </Card>
          </Col>
        </Row>

        <Collapse
          bordered={false}
          style={{ ...shellStyle, background: colors.bgSecondary }}
          items={[
            {
              key: 'details',
              label: (
                <Space size={8}>
                  <BarChartOutlined />
                  <span>{t('pages.analytics.details.title')}</span>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {t('pages.analytics.details.subtitle')}
                  </Text>
                </Space>
              ),
              children: (
                <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
                  <Row gutter={[12, 12]}>
                    {[
                      { label: t('pages.analytics.details.activeLearners'), value: summary.active_learners, icon: <TeamOutlined />, color: colors.accentPrimary },
                      { label: t('pages.analytics.details.outstanding'), value: formatCurrency(summary.outstanding_revenue), icon: <DollarOutlined />, color: colors.accentError },
                      { label: t('pages.analytics.details.notificationDelivery'), value: formatPercent(summary.notification_delivery_rate), icon: <BellOutlined />, color: colors.accentInfo },
                      { label: t('pages.analytics.details.cancellations'), value: formatPercent(summary.cancellation_rate), icon: <FireOutlined />, color: colors.accentWarning },
                      { label: t('pages.analytics.details.earnedPerHour'), value: formatCurrency(earnedPerCompletedHour), icon: <ClockCircleOutlined />, color: colors.accentPrimary },
                      { label: t('pages.analytics.details.earnedPerLesson'), value: formatCurrency(earnedPerCompletedLesson), icon: <BarChartOutlined />, color: colors.accentSuccess },
                      { label: t('pages.analytics.details.cashPerActiveLearner'), value: formatCurrency(cashPerActiveLearner), icon: <TeamOutlined />, color: colors.accentWarning },
                      { label: t('pages.analytics.details.plannedToEarned'), value: formatPercent(plannedToEarnedRatio), icon: <CalendarOutlined />, color: colors.accentInfo },
                    ].map((item) => (
                      <Col key={item.label} xs={24} sm={12} lg={6}>
                        <div style={{ padding: 12, borderRadius: tileRadius, background: colors.bgTertiary }}>
                          <Text type="secondary" style={{ display: 'block', fontSize: 12 }}>{item.label}</Text>
                          <Space align="center" size={8} style={{ marginTop: 8 }}>
                            <span style={{ color: item.color }}>{item.icon}</span>
                            <Text strong style={{ fontSize: 18 }}>{item.value}</Text>
                          </Space>
                        </div>
                      </Col>
                    ))}
                  </Row>

                  <Card {...sectionCardProps} title={t('pages.analytics.sections.moneyNotificationsByDay')}>
                    <ResponsiveContainer width="100%" height={isMobile ? 240 : 280}>
                      <BarChart data={chartData}>
                        <CartesianGrid stroke={chartGridColor} strokeDasharray="2 6" vertical={false} />
                        <XAxis dataKey="date" stroke={subtitleColor} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                        <YAxis stroke={subtitleColor} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={(value) => compactNumberFormatter.format(Number(value))} />
                        <Tooltip contentStyle={tooltipStyle} formatter={(value: number, name: string) => (
                          name === t('pages.analytics.chart.cashRevenue') || name === t('pages.analytics.chart.earnedRevenue')
                            ? formatCurrency(value)
                            : numberFormatter.format(value)
                        )} />
                        <Bar dataKey="cashRevenue" name={t('pages.analytics.chart.cashRevenue')} fill={colors.accentWarning} radius={[6, 6, 0, 0]} />
                        <Bar dataKey="earnedRevenue" name={t('pages.analytics.chart.earnedRevenue')} fill={colors.accentPrimary} radius={[6, 6, 0, 0]} />
                        <Bar dataKey="failed" name={t('pages.analytics.chart.failedReminders')} fill={colors.accentError} radius={[6, 6, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </Card>

                  <Card {...sectionCardProps} title={t('pages.analytics.tables.learners')}>
                    <Table
                      rowKey="learner_id"
                      dataSource={data.learners}
                      size="small"
                      scroll={{ x: 980 }}
                      pagination={{ pageSize: 8 }}
                      columns={[
                        {
                          title: t('pages.analytics.tables.learner'),
                          dataIndex: 'learner_name',
                          fixed: isMobile ? undefined : 'left',
                          width: 180,
                        },
                        {
                          title: t('pages.analytics.tables.completed'),
                          dataIndex: 'completed_lessons',
                          width: 110,
                        },
                        {
                          title: t('pages.analytics.tables.planned'),
                          dataIndex: 'planned_lessons',
                          width: 90,
                        },
                        {
                          title: t('pages.analytics.tables.cancelled'),
                          dataIndex: 'cancelled_lessons',
                          width: 90,
                        },
                        {
                          title: t('pages.analytics.tables.cancellationRate'),
                          dataIndex: 'cancellation_rate',
                          width: 110,
                          render: (value: number) => formatPercent(value),
                        },
                        {
                          title: t('pages.analytics.tables.hours'),
                          dataIndex: 'completed_hours',
                          width: 90,
                          render: (value: number) => formatHours(value, hourUnit),
                        },
                        {
                          title: t('pages.analytics.tables.cash'),
                          dataIndex: 'cash_revenue',
                          width: 120,
                          render: formatCurrency,
                        },
                        {
                          title: t('pages.analytics.tables.earned'),
                          dataIndex: 'earned_revenue',
                          width: 120,
                          render: formatCurrency,
                        },
                        {
                          title: t('pages.analytics.tables.plannedRevenue'),
                          dataIndex: 'planned_revenue',
                          width: 120,
                          render: formatCurrency,
                        },
                        {
                          title: t('pages.analytics.tables.debt'),
                          dataIndex: 'outstanding_revenue',
                          width: 120,
                          render: (value: number | string) => (
                            <Text style={{ color: toNumber(value) > 0 ? colors.accentError : textColor }}>
                              {formatCurrency(value)}
                            </Text>
                          ),
                        },
                        {
                          title: t('pages.analytics.tables.risks'),
                          dataIndex: 'risk_flags',
                          width: 220,
                          render: (flags: string[]) => (
                            <Space size={4} wrap>
                              {flags.length === 0 ? <Text type="secondary">—</Text> : flags.map((flag) => (
                                <Tag key={flag} bordered={false}>{getRiskLabel(flag)}</Tag>
                              ))}
                            </Space>
                          ),
                        },
                      ]}
                    />
                  </Card>

                  <Card {...sectionCardProps} title={t('pages.analytics.tables.packages')}>
                    <Table
                      rowKey="package_id"
                      dataSource={data.packages}
                      size="small"
                      scroll={{ x: 900 }}
                      pagination={{ pageSize: 8 }}
                      columns={[
                        {
                          title: t('pages.analytics.tables.package'),
                          dataIndex: 'package_title',
                          width: 220,
                        },
                        {
                          title: t('pages.analytics.tables.learner'),
                          dataIndex: 'learner_name',
                          width: 180,
                        },
                        {
                          title: t('pages.analytics.tables.status'),
                          dataIndex: 'status',
                          width: 100,
                          render: (status: string) => t(`pages.packages.status.${status}`, { defaultValue: status }),
                        },
                        {
                          title: t('pages.analytics.tables.progress'),
                          dataIndex: 'progress_percent',
                          width: 220,
                          render: (value: number, record: AnalyticsPackageBreakdown) => (
                            <Space direction="vertical" size={2} style={{ width: '100%' }}>
                              <Progress percent={value} size="small" />
                              <Text type="secondary" style={{ fontSize: 11 }}>
                                {t('pages.analytics.tables.lessonProgress', {
                                  completed: record.completed_lessons,
                                  cancelled: record.cancelled_lessons,
                                  total: record.total_lessons,
                                })}
                              </Text>
                            </Space>
                          ),
                        },
                        {
                          title: t('pages.analytics.tables.remaining'),
                          dataIndex: 'remaining_lessons',
                          width: 100,
                        },
                        {
                          title: t('pages.analytics.tables.nextLesson'),
                          dataIndex: 'next_lesson_at',
                          width: 160,
                          render: (value?: string | null) => value ? dayjs(value).format('D MMM, HH:mm') : '—',
                        },
                        {
                          title: t('pages.analytics.tables.lastLesson'),
                          dataIndex: 'last_lesson_at',
                          width: 160,
                          render: (value?: string | null) => value ? dayjs(value).format('D MMM, HH:mm') : '—',
                        },
                        {
                          title: t('pages.analytics.tables.risks'),
                          dataIndex: 'risk_flags',
                          width: 220,
                          render: (flags: string[]) => (
                            <Space size={4} wrap>
                              {flags.length === 0 ? <Text type="secondary">—</Text> : flags.map((flag) => (
                                <Tag key={flag} bordered={false}>{getRiskLabel(flag)}</Tag>
                              ))}
                            </Space>
                          ),
                        },
                      ]}
                    />
                  </Card>
                </div>
              ),
            },
          ]}
        />
      </div>
    </div>
  );
};

export default Analytics;
