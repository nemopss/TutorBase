import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, message, Tag, Space, Switch, Typography, Tooltip, Modal } from 'antd';
import { UserAddOutlined, BellOutlined, BellFilled, IdcardOutlined, DeleteOutlined } from '@ant-design/icons';
import type { TableProps } from 'antd';
import api from '../services/api';
import LearnerForm from '../components/forms/LearnerForm';
import PageHeader from '../components/common/PageHeader';
import ResponsiveDataView from '../components/common/ResponsiveDataView';
import LearnerCard from '../components/cards/LearnerCard';

const { Text } = Typography;

// --- Types --- //
interface Learner {
  id: number;
  display_name: string;
  notifications_enabled: boolean;
  chat_id: number | null;
}

interface LearnerListResponse {
  items: Learner[];
}

// --- API Fetchers --- //
const fetchLearners = async (): Promise<LearnerListResponse> => {
  const { data } = await api.get('/learners');
  return data;
};

const createLearner = async (values: any) => {
  const { data } = await api.post('/learners', {
    chat_id: parseInt(values.chat_id),
    display_name: values.display_name,
    notes: values.notes || null,
    notifications_enabled: values.notifications_enabled ?? true,
  });
  return data;
};

const updateNotifications = async ({ learnerId, enabled }: { learnerId: number; enabled: boolean }) => {
  const { data } = await api.patch(`/learners/${learnerId}/notifications`, {
    notifications_enabled: enabled,
  });
  return data;
};

const deleteLearner = async (learnerId: number) => {
  await api.delete(`/learners/${learnerId}`);
};

// --- Component --- //
const Learners: React.FC = () => {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [learnerToDelete, setLearnerToDelete] = useState<Learner | null>(null);

  const { data, isLoading } = useQuery<LearnerListResponse, Error>({
    queryKey: ['learners'],
    queryFn: fetchLearners,
  });

  const createMutation = useMutation({
    mutationFn: createLearner,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learners'] });
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      message.success('Learner created successfully!');
      setIsModalOpen(false);
    },
    onError: (error: Error) => {
      message.error(`Failed to create learner: ${error.message}`);
    },
  });

  const notificationsMutation = useMutation({
    mutationFn: updateNotifications,
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['learners'] });
      message.success(
        variables.enabled 
          ? 'Notifications enabled successfully!' 
          : 'Notifications disabled successfully!'
      );
    },
    onError: (error: Error) => {
      message.error(`Failed to update notifications: ${error.message}`);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteLearner,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learners'] });
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      message.success('Learner deleted successfully!');
      setDeleteModalOpen(false);
      setLearnerToDelete(null);
    },
    onError: (error: Error) => {
      message.error(`Failed to delete learner: ${error.message}`);
    },
  });

  const handleNotificationToggle = (learnerId: number, currentValue: boolean) => {
    notificationsMutation.mutate({
      learnerId,
      enabled: !currentValue,
    });
  };

  const handleDelete = (learnerId: number) => {
    const learner = learners.find(l => l.id === learnerId);
    if (learner) {
      setLearnerToDelete(learner);
      setDeleteModalOpen(true);
    }
  };

  const confirmDelete = () => {
    if (learnerToDelete) {
      deleteMutation.mutate(learnerToDelete.id);
    }
  };

  const columns: TableProps<Learner>['columns'] = [
    {
      title: 'Learner',
      dataIndex: 'display_name',
      key: 'display_name',
      render: (name: string) => (
        <Space>
          <IdcardOutlined />
          <strong>{name}</strong>
        </Space>
      ),
    },
    {
      title: 'Chat ID',
      dataIndex: 'chat_id',
      key: 'chat_id',
      render: (chat_id: number | null) => (
        <Text type="secondary" copyable={chat_id ? { text: String(chat_id) } : false}>
          {chat_id || '—'}
        </Text>
      ),
    },
    {
      title: 'Notifications',
      dataIndex: 'notifications_enabled',
      key: 'notifications',
      render: (enabled: boolean, record: Learner) => (
        <Space>
          <Tooltip title={enabled ? 'Click to disable notifications' : 'Click to enable notifications'}>
            <Switch
              checked={enabled}
              onChange={() => handleNotificationToggle(record.id, enabled)}
              loading={notificationsMutation.isPending}
              checkedChildren={<BellFilled />}
              unCheckedChildren={<BellOutlined />}
            />
          </Tooltip>
          <Tag color={enabled ? 'green' : 'red'}>
            {enabled ? 'Enabled' : 'Disabled'}
          </Tag>
        </Space>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record: Learner) => (
        <Button
          type="link"
          danger
          icon={<DeleteOutlined />}
          onClick={() => handleDelete(record.id)}
        >
          Delete
        </Button>
      ),
    },
  ];

  const learners = data?.items || [];

  return (
    <div>
      <PageHeader
        title="Learners"
        subtitle="Manage learners and their notification settings"
        actions={
          <Button
            type="primary"
            icon={<UserAddOutlined />}
            onClick={() => setIsModalOpen(true)}
          >
            Add Learner
          </Button>
        }
      />

      <ResponsiveDataView<Learner>
        data={learners}
        loading={isLoading}
        columns={columns}
        rowKey="id"
        emptyText="No learners yet"
        emptyDescription="Create your first learner by clicking the 'Add Learner' button above"
        emptyActionText="Add Learner"
        onEmptyAction={() => setIsModalOpen(true)}
        renderCard={(learner) => (
          <LearnerCard
            key={learner.id}
            learner={learner}
            onNotificationToggle={handleNotificationToggle}
            onDelete={handleDelete}
            isToggling={notificationsMutation.isPending}
          />
        )}
        pagination={{
          pageSize: 20,
          showSizeChanger: true,
          showTotal: (total) => `Total ${total} learner${total !== 1 ? 's' : ''}`,
        }}
      />

      <LearnerForm
        visible={isModalOpen}
        onSubmit={createMutation.mutateAsync}
        onCancel={() => setIsModalOpen(false)}
        loading={createMutation.isPending}
        mode="create"
      />

      <Modal
        open={deleteModalOpen}
        title="Delete Learner"
        onCancel={() => { setDeleteModalOpen(false); setLearnerToDelete(null); }}
        onOk={confirmDelete}
        okText="Delete"
        okButtonProps={{ danger: true, loading: deleteMutation.isPending }}
        cancelButtonProps={{ disabled: deleteMutation.isPending }}
      >
        <p>Are you sure you want to delete <strong>{learnerToDelete?.display_name}</strong>?</p>
        <p style={{ color: '#ff4d4f' }}>This will also delete all their packages, lessons, and reminders.</p>
        <p style={{ color: '#8c8c8c' }}>This action cannot be undone.</p>
      </Modal>
    </div>
  );
};

export default Learners;
