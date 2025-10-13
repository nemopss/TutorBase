import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Descriptions, Spin, Alert, Tag, Table, Button, message, Space, Tabs, Progress, Card, Statistic, Row, Col, Grid } from 'antd';
import type { TableProps } from 'antd';
import { 
  ArrowLeftOutlined, 
  ReloadOutlined, 
  CheckCircleOutlined, 
  CloseCircleOutlined,
  ClockCircleOutlined
} from '@ant-design/icons';
import api from '../services/api';
import LessonForm from '../components/forms/LessonForm';
import PageHeader from '../components/common/PageHeader';
import { formatDate, formatDateTime } from '../utils/datetime';

// --- Types --- //
interface PackageProgress {
  total: number;
  completed: number;
  cancelled: number;
}

interface PackageDetails {
  id: number;
  learner_name: string;
  title: string;
  status: string;
  start_date?: string;
  end_date?: string;
  timezone: string;
  notes?: string;
  total_lessons?: number;
  progress: PackageProgress;
}

interface Lesson {
  id: number;
  scheduled_at: string;
  status: string;
  duration_minutes?: number;
  timezone: string;
}

interface LessonListResponse {
  total: number;
  items: Lesson[];
}

// --- API Fetchers --- //
const fetchPackage = async (id: string): Promise<PackageDetails> => {
  const { data } = await api.get(`/packages/${id}`);
  return data;
};

const fetchPackageLessons = async (id: string): Promise<LessonListResponse> => {
  const { data } = await api.get(`/lessons/packages/${id}`);
  return data;
};

const createLesson = async ({ packageId, values }: { packageId: string; values: any }) => {
  const { data } = await api.post(`/lessons/packages/${packageId}`, values);
  return data;
};

const updateLesson = async ({ lessonId, values }: { lessonId: number; values: any }) => {
  const { data } = await api.patch(`/lessons/${lessonId}`, values);
  return data;
};

// --- Component --- //
const PackageDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingLesson, setEditingLesson] = useState<Lesson | null>(null);
  const screens = Grid.useBreakpoint();
  const isMobile = !screens?.md;

  const { 
    data: packageData, 
    isLoading: isLoadingPackage, 
    isError: isErrorPackage, 
    error: errorPackage 
  } = useQuery<PackageDetails, Error>({
    queryKey: ['package', id],
    queryFn: () => fetchPackage(id!),
    enabled: !!id,
  });

  const { 
    data: lessonsData, 
    isLoading: isLoadingLessons 
  } = useQuery<LessonListResponse, Error>({
    queryKey: ['packageLessons', id],
    queryFn: () => fetchPackageLessons(id!),
    enabled: !!id,
  });

  const mutationOptions = {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['packageLessons', id] });
      setIsModalOpen(false);
      setEditingLesson(null);
    },
    onError: (error: Error) => {
      message.error(`An error occurred: ${error.message}`);
    }
  };

  const createLessonMutation = useMutation({ 
    mutationFn: createLesson,
    ...mutationOptions,
    onSuccess: () => {
      message.success('Lesson created successfully!');
      mutationOptions.onSuccess();
    }
  });

  const updateLessonMutation = useMutation({ 
    mutationFn: updateLesson,
    ...mutationOptions,
    onSuccess: () => {
      message.success('Lesson updated successfully!');
      mutationOptions.onSuccess();
    }
  });

  const handleFormFinish = (values: any) => {
    if (editingLesson) {
      updateLessonMutation.mutate({ lessonId: editingLesson.id, values });
    } else {
      createLessonMutation.mutate({ packageId: id!, values });
    }
  };

  const handleCancel = () => {
    setIsModalOpen(false);
    setEditingLesson(null);
  };

  const lessonColumns: TableProps<Lesson>['columns'] = [
    {
      title: 'Scheduled At',
      dataIndex: 'scheduled_at',
      key: 'scheduled_at',
      render: (text: string) => formatDateTime(text, { timezone: packageData?.timezone }),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => <Tag>{status.toUpperCase()}</Tag>,
    },
    {
      title: 'Duration (min)',
      dataIndex: 'duration_minutes',
      key: 'duration_minutes',
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => (
        <Space size="middle">
          <Button type="link" onClick={() => { setEditingLesson(record); setIsModalOpen(true); }}>Edit</Button>
        </Space>
      ),
    },
  ];

  if (!id || isLoadingPackage) {
    return <Spin size="large" />;
  }

  if (isErrorPackage) {
    return <Alert message="Error fetching package details" description={errorPackage.message} type="error" />;
  }

  const handleRegenerateReminders = async () => {
    try {
      await api.post(`/packages/${id}/regenerate`);
      message.success('Reminders regenerated successfully!');
      queryClient.invalidateQueries({ queryKey: ['packageReminders', id] });
    } catch (error: any) {
      message.error(`Failed to regenerate reminders: ${error.message}`);
    }
  };

  const progressPercent = packageData && packageData.progress.total > 0
    ? Math.round(((packageData.progress.completed + packageData.progress.cancelled) / packageData.progress.total) * 100)
    : 0;

  const tabItems = [
    {
      key: 'lessons',
      label: `Lessons (${lessonsData?.items.length || 0})`,
      children: (
        <div>
          <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ color: '#8c8c8c', fontSize: 14 }}>
              {packageData?.progress.completed} completed, {packageData?.progress.cancelled} cancelled
            </div>
            <Button type="primary" onClick={() => { setEditingLesson(null); setIsModalOpen(true); }}>
              Add Lesson
            </Button>
          </div>
          <Table
            columns={lessonColumns}
            dataSource={lessonsData?.items}
            rowKey="id"
            loading={isLoadingLessons}
            pagination={false}
            bordered
          />
        </div>
      ),
    },
    {
      key: 'reminders',
      label: 'Reminders',
      children: (
        <div>
          <Space style={{ marginBottom: 16 }}>
            <Button type="primary" icon={<ReloadOutlined />} onClick={handleRegenerateReminders}>
              Regenerate All Reminders
            </Button>
            <Button onClick={() => queryClient.invalidateQueries({ queryKey: ['packageReminders', id] })}>
              Refresh
            </Button>
          </Space>
          <Alert 
            message="Reminders Management" 
            description="Use the Reminders page to view and manage all reminders for this package. Click 'Regenerate' to recreate all reminders based on current lessons."
            type="info" 
            showIcon
          />
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader 
        title={packageData?.title || 'Package Details'}
        subtitle={`Learner: ${packageData?.learner_name || '-'} • Status: ${packageData?.status || '-'}`}
        actions={
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/packages')}>
            Back to Packages
          </Button>
        }
      />

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Total Lessons"
              value={packageData?.progress.total || 0}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Completed"
              value={packageData?.progress.completed || 0}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Cancelled"
              value={packageData?.progress.cancelled || 0}
              prefix={<CloseCircleOutlined />}
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
      </Row>

      <Card style={{ marginBottom: 24 }}>
        <h3>Progress</h3>
        <Progress 
          percent={progressPercent} 
          status={progressPercent === 100 ? 'success' : 'active'}
          strokeColor={{
            '0%': '#108ee9',
            '100%': '#87d068',
          }}
        />
        <Descriptions 
          bordered 
          column={isMobile ? 1 : 2} 
          size={isMobile ? 'small' : 'middle'} 
          style={{ marginTop: 16 }}
        >
          <Descriptions.Item label="Start Date">
            {packageData?.start_date ? formatDate(packageData.start_date, { timezone: packageData?.timezone }) : 'N/A'}
          </Descriptions.Item>
          <Descriptions.Item label="End Date">
            {packageData?.end_date ? formatDate(packageData.end_date, { timezone: packageData?.timezone }) : 'N/A'}
          </Descriptions.Item>
          <Descriptions.Item label="Timezone">{packageData?.timezone}</Descriptions.Item>
          <Descriptions.Item label="Total Lessons">{packageData?.total_lessons || '-'}</Descriptions.Item>
          <Descriptions.Item label="Notes" span={2}>{packageData?.notes || '-'}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Tabs items={tabItems} defaultActiveKey="lessons" />

      <LessonForm
        open={isModalOpen}
        onCancel={handleCancel}
        onFinish={handleFormFinish}
        isLoading={createLessonMutation.isPending || updateLessonMutation.isPending}
        initialValues={editingLesson}
      />
    </div>
  );
};

export default PackageDetail;
