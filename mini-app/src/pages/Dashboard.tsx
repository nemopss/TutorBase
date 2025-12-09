import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card, Col, Row, Statistic, Spin, Alert, List, Button, Progress, Space } from 'antd';
import { 
  PlusOutlined, 
  CalendarOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined
} from '@ant-design/icons';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import dayjs from 'dayjs';
import api from '../services/api';
import PageHeader from '../components/common/PageHeader';
import { useResponsiveStyles } from '../hooks/useResponsiveStyles';
import { useResponsive } from '../hooks/useResponsive';
import { chartHeight } from '../theme/tokens';
import { formatDateTime } from '../utils/datetime';

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

// --- API Fetchers --- //
const fetchMetrics = async (): Promise<MetricsSummary> => {
  // Filter by current calendar month
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

// --- Component --- //
const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { cardStyle, textColor, subtitleColor, chartGridColor, tooltipStyle } = useResponsiveStyles();
  const { isMobile } = useResponsive();
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

  if (isLoadingMetrics) {
    return <Spin size="large" />;
  }

  if (isErrorMetrics) {
    return <Alert message="Error fetching metrics" description={errorMetrics.message} type="error" />;
  }

  // Prepare chart data
  const chartData = dailyData?.items.map(item => ({
    date: dayjs(item.date).format('MMM DD'),
    lessons: item.value,
  })) || [];

  // Prepare pie chart data
  const totalLessons = Object.values(metricsData?.lessons || {}).reduce((a, b) => a + b, 0);
  const pieData = [
    { name: 'Scheduled', value: metricsData?.lessons.scheduled || 0, color: '#1890ff' },
    { name: 'Rescheduled', value: metricsData?.lessons.rescheduled || 0, color: '#faad14' },
    { name: 'Completed', value: metricsData?.lessons.completed || 0, color: '#52c41a' },
    { name: 'Cancelled', value: metricsData?.lessons.cancelled || 0, color: '#ff4d4f' },
  ].filter(item => item.value > 0);

  return (
    <div>
      <PageHeader 
        title="Dashboard"
        subtitle="Overview of your lessons and packages"
        actions={
          <Space wrap size="small" style={{ display: 'flex', flexWrap: 'wrap' }}>
            <Button 
              type="primary" 
              icon={<PlusOutlined />} 
              onClick={() => navigate('/packages')}
              size="middle"
            >
              New Package
            </Button>
            <Button 
              icon={<CalendarOutlined />} 
              onClick={() => navigate('/lessons')}
              size="middle"
            >
              View Lessons
            </Button>
          </Space>
        }
      />

      {/* Key Metrics - Current Month */}
      <div style={{ marginBottom: 8 }}>
        <span style={{ color: subtitleColor, fontSize: 12 }}>
          Statistics for {dayjs().format('MMMM YYYY')}
        </span>
      </div>
      <Row gutter={[12, 12]}>
        <Col xs={12} sm={12} lg={6}>
          <Card style={cardStyle} bodyStyle={{ padding: isMobile ? 12 : 24 }}>
            <Statistic
              title={<span style={{ fontSize: isMobile ? 12 : 14 }}>Total</span>}
              value={totalLessons}
              prefix={<ClockCircleOutlined />}
              valueStyle={{ color: textColor, fontSize: isMobile ? 20 : 24 }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={12} lg={6}>
          <Card style={cardStyle} bodyStyle={{ padding: isMobile ? 12 : 24 }}>
            <Statistic
              title={<span style={{ fontSize: isMobile ? 12 : 14 }}>Completed</span>}
              value={metricsData?.lessons.completed || 0}
              valueStyle={{ color: '#52c41a', fontSize: isMobile ? 20 : 24 }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={12} lg={6}>
          <Card style={cardStyle} bodyStyle={{ padding: isMobile ? 12 : 24 }}>
            <Statistic
              title={<span style={{ fontSize: isMobile ? 12 : 14 }}>Scheduled</span>}
              value={metricsData?.lessons.scheduled || 0}
              valueStyle={{ color: '#1890ff', fontSize: isMobile ? 20 : 24 }}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={12} lg={6}>
          <Card style={cardStyle} bodyStyle={{ padding: isMobile ? 12 : 24 }}>
            <Statistic
              title={<span style={{ fontSize: isMobile ? 12 : 14 }}>Cancelled</span>}
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
          <Card title="Lessons Over Time (Last 30 Days)" bordered={false} style={cardStyle}>
            <ResponsiveContainer width="100%" height={currentChartHeight}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke={chartGridColor} />
                <XAxis dataKey="date" stroke={textColor} tick={{ fontSize: isMobile ? 10 : 12 }} />
                <YAxis stroke={textColor} tick={{ fontSize: isMobile ? 10 : 12 }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: isMobile ? 10 : 12 }} />
                <Line type="monotone" dataKey="lessons" stroke="#1890ff" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="Lessons by Status" bordered={false} style={cardStyle}>
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

      {/* Active Packages & Calendar */}
      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} lg={12}>
          <Card 
            title="Active Packages" 
            bordered={false}
            style={cardStyle}
            extra={<Button type="link" onClick={() => navigate('/packages')}>View All</Button>}
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
                    description={`Learner: ${pkg.learner_name}`}
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
          <Card title="Upcoming Lessons" bordered={false} style={cardStyle}>
            {isLoadingLessons ? (
              <Spin />
            ) : isErrorLessons ? (
              <Alert message="Error fetching lessons" description={errorLessons.message} type="error" />
            ) : (
              <List
                dataSource={lessonsData?.items}
                renderItem={(item) => (
                  <List.Item key={item.id}>
                    <List.Item.Meta
                      avatar={<CalendarOutlined style={{ fontSize: 20, color: '#1890ff' }} />}
                      title={formatDateTime(item.scheduled_at, { timezone: item.timezone, format: 'MMM DD, YYYY HH:mm' })}
                      description={item.learner_name || item.package_title || `Status: ${item.status}`}
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
