import React from "react";
import { Typography, Card, Statistic, Row, Col, Spin, List, Tag } from 'antd';
import {
  BookOutlined,
  ClockCircleOutlined,
} from "@ant-design/icons";
import { useTranslation } from 'react-i18next';
import { useAuth } from "../auth/AuthProvider";
import { useQuery } from "@tanstack/react-query";
import api from "../services/api";
import dayjs from "dayjs";

const { Title, Text } = Typography;

interface Learner {
  id: number;
  display_name: string;
  notifications_enabled: boolean;
}

interface Lesson {
  id: number;
  package_title: string;
  scheduled_at: string;
  status: string;
  duration_minutes: number;
}

interface Package {
  id: number;
  title: string;
  status: string;
  total_lessons: number;
  progress: {
    completed: number;
    total: number;
  };
}

const StudentDashboard: React.FC = () => {
  const { t } = useTranslation();
  const { user } = useAuth();

  const { data: learner, isLoading: isLoadingLearner } = useQuery({
    queryKey: ['learner', 'me'],
    queryFn: async () => {
      const { data } = await api.get<Learner>('/users/me/learner');
      return data;
    },
    enabled: !!user,
  });

  const { data: lessonsData, isLoading: isLoadingLessons } = useQuery({
    queryKey: ['lessons', 'upcoming'],
    queryFn: async () => {
      const { data } = await api.get<{ items: Lesson[], total: number }>('/lessons', {
        params: { status: 'scheduled', limit: 5, sort_by: 'scheduled_at', sort_order: 'asc' }
      });
      return data;
    },
    enabled: !!learner,
  });

  const { data: packagesData, isLoading: isLoadingPackages } = useQuery({
    queryKey: ['packages', 'active'],
    queryFn: async () => {
      const { data } = await api.get<{ items: Package[], total: number }>('/packages', {
        params: { status: 'active', limit: 100 }
      });
      return data;
    },
    enabled: !!learner,
  });

  const isLoading = isLoadingLearner || isLoadingLessons || isLoadingPackages;

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '50px' }}>
        <Spin size="large" />
      </div>
    );
  }

  const upcomingLessons = lessonsData?.items || [];
  const activePackages = packagesData?.items || [];
  const nextLesson = upcomingLessons[0];

  return (
    <div style={{ padding: "16px" }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={2} style={{ margin: 0 }}>
          {t('studentDashboard.hello', { name: learner?.display_name || user?.display_name || t('studentDashboard.student') })}
        </Title>
        <Text type="secondary">{t('studentDashboard.welcome')}</Text>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12}>
          <Card>
            <Statistic
              title={t('studentDashboard.upcomingLessons')}
              value={lessonsData?.total || 0}
              prefix={<ClockCircleOutlined />}
              valueStyle={{ color: "#2383e2" }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12}>
          <Card>
            <Statistic
              title={t('studentDashboard.activeCourses')}
              value={activePackages.length}
              prefix={<BookOutlined />}
              valueStyle={{ color: "#0f7b6c" }}
            />
          </Card>
        </Col>
      </Row>

      <div style={{ marginTop: 24 }}>
        <Card title={t('studentDashboard.nextLesson')}>
          {nextLesson ? (
            <div>
              <Text strong>{dayjs(nextLesson.scheduled_at).format('MMMM D, h:mm A')}</Text>
              <br />
              <Text type="secondary">{nextLesson.duration_minutes} {t('pages.lessons.minutes')}</Text>
            </div>
          ) : (
            <div style={{ textAlign: "center", padding: "24px 0" }}>
              <Text type="secondary">{t('studentDashboard.noUpcomingLessons')}</Text>
            </div>
          )}
        </Card>
      </div>

      <div style={{ marginTop: 24 }}>
        <Card title={t('studentDashboard.yourCourses')}>
          <List
            dataSource={activePackages}
            renderItem={(pkg) => (
              <List.Item>
                <List.Item.Meta
                  title={pkg.title}
                  description={t('studentDashboard.progress', { completed: pkg.progress.completed, total: pkg.progress.total })}
                />
                <Tag color="green">{t(`pages.packages.status.${pkg.status}`)}</Tag>
              </List.Item>
            )}
          />
        </Card>
      </div>
    </div>
  );
};

export default StudentDashboard;
