import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Col, Row, Statistic, Spin, Alert, List, Typography } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';
import api from '../services/api';

// --- Types --- //
interface MetricsSummary {
  lessons: Record<string, number>;
  reminders: Record<string, number>;
}

interface Lesson {
  id: number;
  package_id: number;
  scheduled_at: string;
  status: string;
}

interface LessonListResponse {
  total: number;
  items: Lesson[];
}

// --- API Fetchers --- //
const fetchMetrics = async (): Promise<MetricsSummary> => {
  const { data } = await api.get('/metrics/summary');
  return data;
};

const fetchUpcomingLessons = async (): Promise<LessonListResponse> => {
  const { data } = await api.get('/lessons', {
    params: {
      status: 'scheduled',
      sort_by: 'scheduled_at',
      sort_order: 'asc',
      limit: 5,
    },
  });
  return data;
};

// --- Component --- //
const Dashboard: React.FC = () => {
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

  if (isLoadingMetrics) {
    return <Spin size="large" />;
  }

  if (isErrorMetrics) {
    return <Alert message="Error fetching metrics" description={errorMetrics.message} type="error" />;
  }

  return (
    <div>
      <h1>Dashboard</h1>
      <Row gutter={16}>
        <Col span={8}>
          <Card>
            <Statistic
              title="Total Lessons"
              value={metricsData?.lessons.total || 0}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="Completed"
              value={metricsData?.lessons.completed || 0}
              valueStyle={{ color: '#3f8600' }}
              prefix={<ArrowUpOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="Cancelled"
              value={metricsData?.lessons.cancelled || 0}
              valueStyle={{ color: '#cf1322' }}
              prefix={<ArrowDownOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <h2 style={{ marginTop: 24 }}>Upcoming Lessons</h2>
      {isLoadingLessons ? (
        <Spin />
      ) : isErrorLessons ? (
        <Alert message="Error fetching lessons" description={errorLessons.message} type="error" />
      ) : (
        <List
          bordered
          dataSource={lessonsData?.items}
          renderItem={(item) => (
            <List.Item key={item.id}>
              <Typography.Text>{new Date(item.scheduled_at).toLocaleString()}</Typography.Text>
            </List.Item>
          )}
        />
      )}
    </div>
  );
};

export default Dashboard;
