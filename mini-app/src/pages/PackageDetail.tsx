import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Descriptions, Spin, Alert, Tag, Table, Button, message, Space } from 'antd';
import type { TableProps } from 'antd';
import api from '../services/api';
import LessonForm from '../components/forms/LessonForm';

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
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingLesson, setEditingLesson] = useState<Lesson | null>(null);

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
      render: (text: string) => new Date(text).toLocaleString(),
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

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>{packageData?.title}</h1>
        <Button type="primary" onClick={() => { setEditingLesson(null); setIsModalOpen(true); }}>
          Add Lesson
        </Button>
      </div>
      <Descriptions bordered column={1} style={{ marginBottom: 24 }}>
        <Descriptions.Item label="Learner">{packageData?.learner_name}</Descriptions.Item>
        <Descriptions.Item label="Status">
          <Tag color={packageData?.status === 'active' ? 'green' : 'volcano'}>{packageData?.status.toUpperCase()}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="Progress">
          {`${packageData?.progress.completed} / ${packageData?.progress.total} lessons`}
        </Descriptions.Item>
        <Descriptions.Item label="Start Date">
          {packageData?.start_date ? new Date(packageData.start_date).toLocaleDateString() : 'N/A'}
        </Descriptions.Item>
        <Descriptions.Item label="End Date">
          {packageData?.end_date ? new Date(packageData.end_date).toLocaleDateString() : 'N/A'}
        </Descriptions.Item>
        <Descriptions.Item label="Timezone">{packageData?.timezone}</Descriptions.Item>
        <Descriptions.Item label="Notes">{packageData?.notes || '-'}</Descriptions.Item>
      </Descriptions>

      <h2>Lessons</h2>
      <Table
        columns={lessonColumns}
        dataSource={lessonsData?.items}
        rowKey="id"
        loading={isLoadingLessons}
        pagination={false}
        bordered
      />

      <LessonForm
        open={isModalOpen}
        onCancel={handleCancel}
        onFinish={handleFormFinish}
        isLoading={createLessonMutation.isLoading || updateLessonMutation.isLoading}
        initialValues={editingLesson}
      />
    </div>
  );
};

export default PackageDetail;
