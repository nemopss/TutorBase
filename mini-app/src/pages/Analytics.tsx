import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Row, Col, Statistic, DatePicker, Space, Button, Table } from 'antd';
import { DownloadOutlined, BarChartOutlined, PieChartOutlined, LineChartOutlined } from '@ant-design/icons';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import dayjs, { Dayjs } from 'dayjs';
import { useTranslation } from 'react-i18next';
import api from '../services/api';
import PageHeader from '../components/common/PageHeader';
import { OverviewPageSkeleton } from '../components/common/PageSkeletons';
import TenantContextRequired from '../components/common/TenantContextRequired';
import { useAuth } from '../auth/AuthProvider';
import { useResponsiveStyles } from '../hooks/useResponsiveStyles';
import { useResponsive } from '../hooks/useResponsive';
import { chartHeight, spacing } from '../theme/tokens';

const { RangePicker } = DatePicker;

// --- Types --- //
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
const fetchDailyLessons = async (from?: string, to?: string): Promise<DailyMetricsResponse> => {
  const { data } = await api.get('/metrics/lessons/daily', {
    params: {
      from_date: from,
      to_date: to,
    },
  });
  return data;
};

const fetchDailyReminders = async (from?: string, to?: string): Promise<DailyMetricsResponse> => {
  const { data } = await api.get('/metrics/reminders/daily', {
    params: {
      from_date: from,
      to_date: to,
    },
  });
  return data;
};

const fetchAllPackages = async (): Promise<PackageListResponse> => {
  // Fetch all packages with pagination (max 100 per request)
  let allItems: Package[] = [];
  let offset = 0;
  const limit = 100;
  let hasMore = true;
  
  while (hasMore) {
    const { data } = await api.get('/packages', { params: { limit, offset } });
    allItems = [...allItems, ...data.items];
    hasMore = data.has_more;
    offset += limit;
    
    // Safety limit to prevent infinite loops
    if (offset > 10000) break;
  }
  
  return { items: allItems, total: allItems.length };
};


const Analytics: React.FC = () => {
  const { t } = useTranslation();
  const { tenantId } = useAuth();
  const requiresTenantContext = tenantId === null;
  const { cardStyle, textColor, chartGridColor, tooltipStyle } = useResponsiveStyles();
  const { isMobile } = useResponsive();
  const currentChartHeight = isMobile ? chartHeight.mobile : chartHeight.desktop;
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs]>([
    dayjs().subtract(30, 'days'),
    dayjs(),
  ]);

  const { data: lessonsData, isLoading: isLoadingLessons } = useQuery<DailyMetricsResponse, Error>({
    queryKey: ['analyticsLessons', dateRange[0].toISOString(), dateRange[1].toISOString()],
    queryFn: () => fetchDailyLessons(dateRange[0].toISOString(), dateRange[1].toISOString()),
    enabled: !requiresTenantContext,
  });

  const { data: remindersData, isLoading: isLoadingReminders } = useQuery<DailyMetricsResponse, Error>({
    queryKey: ['analyticsReminders', dateRange[0].toISOString(), dateRange[1].toISOString()],
    queryFn: () => fetchDailyReminders(dateRange[0].toISOString(), dateRange[1].toISOString()),
    enabled: !requiresTenantContext,
  });

  const { data: packagesData } = useQuery<PackageListResponse, Error>({
    queryKey: ['analyticsPackages'],
    queryFn: fetchAllPackages,
    enabled: !requiresTenantContext,
  });

  const handleDateChange = (dates: any) => {
    if (dates && dates[0] && dates[1]) {
      setDateRange([dates[0], dates[1]]);
    }
  };

  const handleExport = () => {
    // TODO: Implement CSV export
    const csvContent = 'Date,Lessons,Reminders\n' + 
      (lessonsData?.items || []).map((item, idx) => 
        `${item.date},${item.value},${remindersData?.items[idx]?.value || 0}`
      ).join('\n');
    
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `analytics_${dayjs().format('YYYY-MM-DD')}.csv`;
    a.click();
  };

  // Prepare chart data
  const chartData = (lessonsData?.items || []).map((item, idx) => ({
    date: dayjs(item.date).format('MMM DD'),
    lessons: item.value,
    reminders: remindersData?.items[idx]?.value || 0,
  }));

  // Learner breakdown data
  const learnerData = (packagesData?.items || []).reduce((acc: any[], pkg) => {
    if (!pkg.learner_name || !pkg.progress) return acc;
    
    const existing = acc.find(item => item.name === pkg.learner_name);
    if (existing) {
      existing.total += pkg.progress?.total || 0;
      existing.completed += pkg.progress?.completed || 0;
      existing.cancelled += pkg.progress?.cancelled || 0;
      existing.packages += 1;
    } else {
      acc.push({
        name: pkg.learner_name,
        total: pkg.progress?.total || 0,
        completed: pkg.progress?.completed || 0,
        cancelled: pkg.progress?.cancelled || 0,
        packages: 1,
      });
    }
    return acc;
  }, []);

  const topLearners = learnerData
    .sort((a, b) => b.completed - a.completed)
    .slice(0, 5);

  const pageHeader = (
    <PageHeader 
      title={t('pages.analytics.title')}
      subtitle={t('pages.analytics.subtitle')}
      actions={
        <Space wrap size="small" direction={isMobile ? 'vertical' : 'horizontal'} style={{ width: isMobile ? '100%' : 'auto' }}>
          <RangePicker
            value={dateRange}
            onChange={handleDateChange}
            format="YYYY-MM-DD"
            style={{ width: isMobile ? '100%' : 'auto' }}
            placement="bottomLeft"
            getPopupContainer={(trigger) => trigger.parentElement || document.body}
            panelRender={isMobile ? (panelNode) => (
              <div style={{ maxWidth: '100vw', overflow: 'auto' }}>{panelNode}</div>
            ) : undefined}
          />
          <Button icon={<DownloadOutlined />} onClick={handleExport} block={isMobile}>
            {t('pages.analytics.exportCsv')}
          </Button>
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

  if (isLoadingLessons || isLoadingReminders) {
    return (
      <div>
        {pageHeader}
        <OverviewPageSkeleton />
      </div>
    );
  }

  return (
    <div>
      {pageHeader}

      {/* Summary Cards */}
      <Row gutter={[16, 16]} style={{ marginBottom: spacing.lg }}>
        <Col xs={24} sm={12} lg={6}>
          <Card style={cardStyle}>
            <Statistic
              title={t('pages.analytics.totalLessonsPeriod')}
              value={(lessonsData?.items || []).reduce((sum, item) => sum + item.value, 0)}
              prefix={<LineChartOutlined />}
              valueStyle={{ color: textColor }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={cardStyle}>
            <Statistic
              title={t('pages.analytics.totalRemindersPeriod')}
              value={(remindersData?.items || []).reduce((sum, item) => sum + item.value, 0)}
              prefix={<BarChartOutlined />}
              valueStyle={{ color: textColor }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={cardStyle}>
            <Statistic
              title={t('pages.analytics.activeLearners')}
              value={learnerData.length}
              prefix={<PieChartOutlined />}
              valueStyle={{ color: textColor }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={cardStyle}>
            <Statistic
              title={t('pages.analytics.totalPackages')}
              value={packagesData?.items.length || 0}
              prefix={<BarChartOutlined />}
              valueStyle={{ color: textColor }}
            />
          </Card>
        </Col>
      </Row>

      {/* Charts */}
      <Row gutter={[16, 16]} style={{ marginBottom: spacing.lg }}>
        <Col xs={24} lg={16}>
          <Card title={t('pages.analytics.lessonsRemindersOverTime')} style={cardStyle}>
            <ResponsiveContainer width="100%" height={currentChartHeight}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke={chartGridColor} />
                <XAxis dataKey="date" stroke={textColor} tick={{ fontSize: isMobile ? 10 : 12 }} />
                <YAxis stroke={textColor} tick={{ fontSize: isMobile ? 10 : 12 }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: isMobile ? 10 : 12 }} />
                <Line type="monotone" dataKey="lessons" stroke="#1890ff" strokeWidth={2} name={t('pages.analytics.lessons')} />
                <Line type="monotone" dataKey="reminders" stroke="#52c41a" strokeWidth={2} name={t('pages.analytics.reminders')} />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title={t('pages.analytics.topLearners')} style={cardStyle}>
            <ResponsiveContainer width="100%" height={currentChartHeight}>
              <BarChart data={topLearners} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke={chartGridColor} />
                <XAxis type="number" stroke={textColor} tick={{ fontSize: isMobile ? 10 : 12 }} />
                <YAxis dataKey="name" type="category" width={isMobile ? 60 : 100} stroke={textColor} tick={{ fontSize: isMobile ? 10 : 12 }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar dataKey="completed" fill="#52c41a" name={t('pages.dashboard.completed')} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>

      {/* Learner Breakdown Table */}
      <Card title={t('pages.analytics.learnerBreakdown')} style={cardStyle}>
        <Table
          dataSource={learnerData}
          rowKey="name"
          scroll={{ x: 600 }}
          pagination={{ pageSize: 10 }}
          columns={[
            {
              title: t('pages.learners.learner'),
              dataIndex: 'name',
              key: 'name',
            },
            {
              title: t('navigation.packages'),
              dataIndex: 'packages',
              key: 'packages',
            },
            {
              title: t('pages.analytics.totalLessons'),
              dataIndex: 'total',
              key: 'total',
            },
            {
              title: t('pages.dashboard.completed'),
              dataIndex: 'completed',
              key: 'completed',
            },
            {
              title: t('pages.dashboard.cancelled'),
              dataIndex: 'cancelled',
              key: 'cancelled',
            },
            {
              title: t('pages.analytics.completionRate'),
              key: 'rate',
              render: (_: any, record: any) => 
                record.total > 0 ? `${Math.round(((record.completed + record.cancelled) / record.total) * 100)}%` : '0%',
            },
          ]}
        />
      </Card>
    </div>
  );
};

export default Analytics;
