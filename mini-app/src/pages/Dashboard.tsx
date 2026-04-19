import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card, Col, Row, Statistic, Spin, Alert, List, Button, Progress, Space } from 'antd';
import { 
  PlusOutlined, 
  CalendarOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  KeyOutlined,
  UserAddOutlined,
} from '@ant-design/icons';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import dayjs from 'dayjs';
import { useTranslation } from 'react-i18next';
import api from '../services/api';
import PageHeader from '../components/common/PageHeader';
import { useResponsiveStyles } from '../hooks/useResponsiveStyles';
import { useResponsive } from '../hooks/useResponsive';
import { chartHeight } from '../theme/tokens';
import { formatDateTime } from '../utils/datetime';
import { useAuth } from '../auth/AuthProvider';

// --- Types --- //
interface MetricsSummary {
  lessons: Record<string, number>;
  reminders: Record<string, number>;
}

interface Lesson {
  id: number;
  package_id: number;
  package_title?: string;
  learner_name?: string;
  scheduled_at: string;
  status: string;
  timezone: string;
}

interface LessonListResponse {
  total: number;
  items: Lesson[];
}

interface DailyPoint {
  date: string;
  value: number;
}

interface DailyMetricsResponse {
  items: DailyPoint[];
}

interface Package {
  id: number;
  title: string;
  learner_name: string;
  status: string;
  progress: {
    total: number;
    completed: number;
    cancelled: number;
  };
}

interface PackageListResponse {
  total: number;
  items: Package[];
}

interface LearnerListResponse {
  total: number;
}

interface InviteTokenListResponse {
  total: number;
  items: unknown[];
}

// --- API Fetchers --- //
const fetchMetrics = async (): Promise<MetricsSummary> => {
  const startOfMonth = dayjs().startOf('month').toISOString();
  const endOfMonth = dayjs().endOf('month').toISOString();
  const { data } = await api.get('/metrics/summary', {
    params: {
      from_date: startOfMonth,
      to_date: endOfMonth,
    },
  });
  return data;
};

const fetchUpcomingLessons = async (): Promise<LessonListResponse> => {
  const { data } = await api.get('/lessons', {
    params: {
      status: 'scheduled',
      sort_by: 'scheduled_at',
      sort_order: 'asc',
      limit: 10,
    },
  });
  return data;
};

const fetchDailyLessons = async (): Promise<DailyMetricsResponse> => {
  const { data } = await api.get('/metrics/lessons/daily', {
    params: {
      from_date: dayjs().subtract(30, 'days').toISOString(),
      to_date: dayjs().toISOString(),
    },
  });
  return data;
};

const fetchActivePackages = async (): Promise<PackageListResponse> => {
  const { data } = await api.get('/packages', {
    params: {
      status_filter: 'active',
      limit: 5,
    },
  });
  return data;
};

const fetchPackagesSummary = async (): Promise<PackageListResponse> => {
  const { data } = await api.get('/packages', {
    params: { limit: 1 },
  });
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

// --- Component --- //
const Dashboard: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { cardStyle, textColor, subtitleColor, chartGridColor, tooltipStyle } = useResponsiveStyles();
  const { isMobile } = useResponsive();
  const { tenantId } = useAuth();
  const currentChartHeight = isMobile ? chartHeight.mobile : chartHeight.desktop;

  const { 
    data: metricsData, 
    isLoading: isLoadingMetrics, 
    isError: isErrorMetrics, 
    error: errorMetrics 
  } = useQuery<MetricsSummary, Error>({ 
    queryKey: ['metricsSummary'], 
    queryFn: fetchMetrics 
  });

  const { 
    data: lessonsData, 
    isLoading: isLoadingLessons, 
    isError: isErrorLessons, 
    error: errorLessons 
  } = useQuery<LessonListResponse, Error>({ 
    queryKey: ['upcomingLessons'], 
    queryFn: fetchUpcomingLessons 
  });

  const { data: dailyData } = useQuery<DailyMetricsResponse, Error>({
    queryKey: ['dailyLessons'],
    queryFn: fetchDailyLessons,
  });

  const { data: packagesData } = useQuery<PackageListResponse, Error>({
    queryKey: ['activePackages'],
    queryFn: fetchActivePackages,
  });

  const { data: packagesSummaryData } = useQuery<PackageListResponse, Error>({
    queryKey: ['dashboardPackagesSummary'],
    queryFn: fetchPackagesSummary,
  });

  const { data: lessonsSummaryData } = useQuery<LessonListResponse, Error>({
    queryKey: ['dashboardLessonsSummary'],
    queryFn: fetchLessonsSummary,
  });

  const { data: learnersData } = useQuery<LearnerListResponse, Error>({
    queryKey: ['dashboardLearnersSummary'],
    queryFn: fetchLearnersSummary,
  });

  const { data: inviteTokensData } = useQuery<InviteTokenListResponse, Error>({
    queryKey: ['dashboardInviteTokensSummary', tenantId],
    queryFn: () => fetchInviteTokensSummary(tenantId!),
    enabled: !!tenantId,
  });

  if (isLoadingMetrics) {
    return <Spin size="large" />;
  }

  if (isErrorMetrics) {
    return <Alert message={t('errors.fetchMetrics')} description={errorMetrics.message} type="error" />;
  }

  // Prepare chart data
  const chartData = dailyData?.items.map(item => ({
    date: dayjs(item.date).format('MMM DD'),
    lessons: item.value,
  })) || [];

  // Prepare pie chart data with translated names
  const totalLessons = Object.values(metricsData?.lessons || {}).reduce((a, b) => a + b, 0);
  const pieData = [
    { name: t('pages.dashboard.scheduled'), value: metricsData?.lessons.scheduled || 0, color: '#1890ff' },
    { name: t('pages.dashboard.rescheduled'), value: metricsData?.lessons.rescheduled || 0, color: '#faad14' },
    { name: t('pages.dashboard.completed'), value: metricsData?.lessons.completed || 0, color: '#52c41a' },
    { name: t('pages.dashboard.cancelled'), value: metricsData?.lessons.cancelled || 0, color: '#ff4d4f' },
  ].filter(item => item.value > 0);

  const learnerCount = learnersData?.total ?? 0;
  const inviteCount = inviteTokensData?.total ?? inviteTokensData?.items?.length ?? 0;
  const packageCount = packagesSummaryData?.total ?? 0;
  const lessonCount = lessonsSummaryData?.total ?? totalLessons;
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
      path: '/invite-codes',
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
  const showOnboarding = completedOnboardingSteps < onboardingSteps.length;

  return (
    <div>
      <PageHeader 
        title={t('pages.dashboard.title')}
        subtitle={t('pages.dashboard.subtitle')}
        actions={
          <Space wrap size="small" style={{ display: 'flex', flexWrap: 'wrap' }}>
            <Button 
              type="primary" 
              icon={<PlusOutlined />} 
              onClick={() => navigate('/packages')}
              size="middle"
            >
              {t('pages.dashboard.newPackage')}
            </Button>
            <Button 
              icon={<CalendarOutlined />} 
              onClick={() => navigate('/lessons')}
              size="middle"
            >
              {t('pages.dashboard.viewLessons')}
            </Button>
          </Space>
        }
      />

      {showOnboarding && (
        <Card
          title={t('pages.dashboard.onboarding.title')}
          bordered={false}
          style={{ ...cardStyle, marginBottom: 24 }}
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
                  avatar={step.done ? (
                    <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 20 }} />
                  ) : (
                    <span style={{ color: '#1890ff', fontSize: 20 }}>{step.icon}</span>
                  )}
                  title={step.title}
                  description={step.description}
                />
              </List.Item>
            )}
          />
        </Card>
      )}

      {/* Key Metrics - Current Month */}
      <div style={{ marginBottom: 8 }}>
        <span style={{ color: subtitleColor, fontSize: 12 }}>
          {t('pages.dashboard.statistics', { month: dayjs().format('MMMM YYYY') })}
        </span>
      </div>
      <Row gutter={[12, 12]}>
        <Col xs={12} sm={12} lg={6}>
          <Card style={cardStyle} bodyStyle={{ padding: isMobile ? 12 : 24 }}>
            <Statistic
              title={<span style={{ fontSize: isMobile ? 12 : 14 }}>{t('pages.dashboard.total')}</span>}
              value={totalLessons}
              prefix={<ClockCircleOutlined />}
              valueStyle={{ color: textColor, fontSize: isMobile ? 20 : 24 }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={12} lg={6}>
          <Card style={cardStyle} bodyStyle={{ padding: isMobile ? 12 : 24 }}>
            <Statistic
              title={<span style={{ fontSize: isMobile ? 12 : 14 }}>{t('pages.dashboard.completed')}</span>}
              value={metricsData?.lessons.completed || 0}
              valueStyle={{ color: '#52c41a', fontSize: isMobile ? 20 : 24 }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={12} lg={6}>
          <Card style={cardStyle} bodyStyle={{ padding: isMobile ? 12 : 24 }}>
            <Statistic
              title={<span style={{ fontSize: isMobile ? 12 : 14 }}>{t('pages.dashboard.scheduled')}</span>}
              value={metricsData?.lessons.scheduled || 0}
              valueStyle={{ color: '#1890ff', fontSize: isMobile ? 20 : 24 }}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={12} lg={6}>
          <Card style={cardStyle} bodyStyle={{ padding: isMobile ? 12 : 24 }}>
            <Statistic
              title={<span style={{ fontSize: isMobile ? 12 : 14 }}>{t('pages.dashboard.cancelled')}</span>}
              value={metricsData?.lessons.cancelled || 0}
              valueStyle={{ color: '#ff4d4f', fontSize: isMobile ? 20 : 24 }}
              prefix={<CloseCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* Charts Row */}
      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} lg={16}>
          <Card title={t('pages.dashboard.lessonsOverTime')} bordered={false} style={cardStyle}>
            <ResponsiveContainer width="100%" height={currentChartHeight}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke={chartGridColor} />
                <XAxis dataKey="date" stroke={textColor} tick={{ fontSize: isMobile ? 10 : 12 }} />
                <YAxis stroke={textColor} tick={{ fontSize: isMobile ? 10 : 12 }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: isMobile ? 10 : 12 }} />
                <Line type="monotone" dataKey="lessons" stroke="#1890ff" strokeWidth={2} name={t('navigation.lessons')} />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title={t('pages.dashboard.lessonsByStatus')} bordered={false} style={cardStyle}>
            <ResponsiveContainer width="100%" height={currentChartHeight}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={isMobile ? false : (props: any) => `${(props.percent * 100).toFixed(0)}%`}
                  outerRadius={isMobile ? 50 : 80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend 
                  wrapperStyle={{ fontSize: isMobile ? 10 : 12 }} 
                  layout={isMobile ? 'horizontal' : 'vertical'}
                  align={isMobile ? 'center' : 'right'}
                  verticalAlign={isMobile ? 'bottom' : 'middle'}
                />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>

      {/* Active Packages & Upcoming Lessons */}
      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} lg={12}>
          <Card 
            title={t('pages.dashboard.activePackages')} 
            bordered={false}
            style={cardStyle}
            extra={<Button type="link" onClick={() => navigate('/packages')}>{t('common.viewAll')}</Button>}
          >
            <List
              dataSource={packagesData?.items || []}
              loading={!packagesData}
              renderItem={(pkg) => (
                <List.Item 
                  key={pkg.id}
                  style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/packages/${pkg.id}`)}
                >
                  <List.Item.Meta
                    title={pkg.title}
                    description={`${t('pages.dashboard.learner')}: ${pkg.learner_name}`}
                  />
                  <div style={{ textAlign: 'right' }}>
                    <Progress 
                      type="circle" 
                      percent={pkg.progress.total > 0 ? Math.round(((pkg.progress.completed + pkg.progress.cancelled) / pkg.progress.total) * 100) : 0} 
                      width={50}
                      strokeColor="#52c41a"
                    />
                    <div style={{ marginTop: 8, fontSize: 12, color: subtitleColor }}>
                      {pkg.progress.completed}+{pkg.progress.cancelled}/{pkg.progress.total}
                    </div>
                  </div>
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title={t('pages.dashboard.upcomingLessons')} bordered={false} style={cardStyle}>
            {isLoadingLessons ? (
              <Spin />
            ) : isErrorLessons ? (
              <Alert message={t('errors.fetchLessons')} description={errorLessons.message} type="error" />
            ) : (
              <List
                dataSource={lessonsData?.items}
                renderItem={(item) => (
                  <List.Item key={item.id}>
                    <List.Item.Meta
                      avatar={<CalendarOutlined style={{ fontSize: 20, color: '#1890ff' }} />}
                      title={formatDateTime(item.scheduled_at, { timezone: item.timezone, format: 'MMM DD, YYYY HH:mm' })}
                      description={item.learner_name || item.package_title || `${t('common.status')}: ${item.status}`}
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;
