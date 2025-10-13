import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Row, Col, Statistic, DatePicker, Space, Button, Table, Spin } from 'antd';
import { DownloadOutlined, BarChartOutlined, PieChartOutlined, LineChartOutlined } from '@ant-design/icons';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import dayjs, { Dayjs } from 'dayjs';
import api from '../services/api';
import PageHeader from '../components/common/PageHeader';
import { useResponsiveStyles } from '../hooks/useResponsiveStyles';

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
  const { data } = await api.get('/packages', { params: { limit: 1000 } });
  return data;
};


const Analytics: React.FC = () => {
  const { cardStyle, textColor, chartGridColor, tooltipStyle } = useResponsiveStyles();
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs]>([
    dayjs().subtract(30, 'days'),
    dayjs(),
  ]);

  const { data: lessonsData, isLoading: isLoadingLessons } = useQuery<DailyMetricsResponse, Error>({
    queryKey: ['analyticsLessons', dateRange[0].toISOString(), dateRange[1].toISOString()],
    queryFn: () => fetchDailyLessons(dateRange[0].toISOString(), dateRange[1].toISOString()),
  });

  const { data: remindersData, isLoading: isLoadingReminders } = useQuery<DailyMetricsResponse, Error>({
    queryKey: ['analyticsReminders', dateRange[0].toISOString(), dateRange[1].toISOString()],
    queryFn: () => fetchDailyReminders(dateRange[0].toISOString(), dateRange[1].toISOString()),
  });

  const { data: packagesData } = useQuery<PackageListResponse, Error>({
    queryKey: ['analyticsPackages'],
    queryFn: fetchAllPackages,
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

  if (isLoadingLessons || isLoadingReminders) {
    return <Spin size="large" />;
  }

  return (
    <div>
      <PageHeader 
        title="Analytics"
        subtitle="Insights and statistics about your lessons"
        actions={
          <Space wrap size="small" direction="vertical" style={{ width: '100%' }}>
            <RangePicker
              value={dateRange}
              onChange={handleDateChange}
              format="YYYY-MM-DD"
              style={{ width: '100%' }}
              placement="bottomLeft"
              getPopupContainer={(trigger) => trigger.parentElement || document.body}
            />
            <Button icon={<DownloadOutlined />} onClick={handleExport} block>
              Export CSV
            </Button>
          </Space>
        }
      />

      {/* Summary Cards */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card style={cardStyle}>
            <Statistic
              title="Total Lessons (Period)"
              value={(lessonsData?.items || []).reduce((sum, item) => sum + item.value, 0)}
              prefix={<LineChartOutlined />}
              valueStyle={{ color: textColor }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={cardStyle}>
            <Statistic
              title="Total Reminders (Period)"
              value={(remindersData?.items || []).reduce((sum, item) => sum + item.value, 0)}
              prefix={<BarChartOutlined />}
              valueStyle={{ color: textColor }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={cardStyle}>
            <Statistic
              title="Active Learners"
              value={learnerData.length}
              prefix={<PieChartOutlined />}
              valueStyle={{ color: textColor }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={cardStyle}>
            <Statistic
              title="Total Packages"
              value={packagesData?.items.length || 0}
              prefix={<BarChartOutlined />}
              valueStyle={{ color: textColor }}
            />
          </Card>
        </Col>
      </Row>

      {/* Charts */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={16}>
          <Card title="Lessons & Reminders Over Time" style={cardStyle}>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke={chartGridColor} />
                <XAxis dataKey="date" stroke={textColor} />
                <YAxis stroke={textColor} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend />
                <Line type="monotone" dataKey="lessons" stroke="#1890ff" strokeWidth={2} name="Lessons" />
                <Line type="monotone" dataKey="reminders" stroke="#52c41a" strokeWidth={2} name="Reminders" />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="Top 5 Learners by Completed Lessons" style={cardStyle}>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={topLearners} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke={chartGridColor} />
                <XAxis type="number" stroke={textColor} />
                <YAxis dataKey="name" type="category" width={100} stroke={textColor} />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar dataKey="completed" fill="#52c41a" />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>

      {/* Learner Breakdown Table */}
      <Card title="Learner Breakdown" style={cardStyle}>
        <Table
          dataSource={learnerData}
          rowKey="name"
          scroll={{ x: 600 }}
          pagination={{ pageSize: 10 }}
          columns={[
            {
              title: 'Learner',
              dataIndex: 'name',
              key: 'name',
            },
            {
              title: 'Packages',
              dataIndex: 'packages',
              key: 'packages',
            },
            {
              title: 'Total Lessons',
              dataIndex: 'total',
              key: 'total',
            },
            {
              title: 'Completed',
              dataIndex: 'completed',
              key: 'completed',
            },
            {
              title: 'Cancelled',
              dataIndex: 'cancelled',
              key: 'cancelled',
            },
            {
              title: 'Completion Rate',
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
