import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, message, Tag, Space, Switch, Typography, Tooltip, Modal } from 'antd';
import { UserAddOutlined, BellOutlined, BellFilled, IdcardOutlined, DeleteOutlined, DollarOutlined } from '@ant-design/icons';
import type { TableProps } from 'antd';
import { useTranslation } from 'react-i18next';
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
    lesson_rate: values.lesson_rate || null,
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
  const { t } = useTranslation();
  const navigate = useNavigate();
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
      message.success(t('pages.learners.createSuccess'));
      setIsModalOpen(false);
    },
    onError: (error: Error) => {
      message.error(t('errors.createFailed', { message: error.message }));
    },
  });

  const notificationsMutation = useMutation({
    mutationFn: updateNotifications,
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['learners'] });
      message.success(
        variables.enabled 
          ? t('pages.learners.notificationsEnabled')
          : t('pages.learners.notificationsDisabled')
      );
    },
    onError: (error: Error) => {
      message.error(t('errors.updateFailed', { message: error.message }));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteLearner,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learners'] });
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      message.success(t('pages.learners.deleteSuccess'));
      setDeleteModalOpen(false);
      setLearnerToDelete(null);
    },
    onError: (error: Error) => {
      message.error(t('errors.deleteFailed', { message: error.message }));
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
      title: t('pages.learners.learner'),
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
      title: t('pages.learners.chatId'),
      dataIndex: 'chat_id',
      key: 'chat_id',
      render: (chat_id: number | null) => (
        <Text type="secondary" copyable={chat_id ? { text: String(chat_id) } : false}>
          {chat_id || '—'}
        </Text>
      ),
    },
    {
      title: t('pages.learners.notifications'),
      dataIndex: 'notifications_enabled',
      key: 'notifications',
      render: (enabled: boolean, record: Learner) => (
        <Space>
          <Tooltip title={enabled ? t('pages.learners.notificationsOff') : t('pages.learners.notificationsOn')}>
            <Switch
              checked={enabled}
              onChange={() => handleNotificationToggle(record.id, enabled)}
              loading={notificationsMutation.isPending}
              checkedChildren={<BellFilled />}
              unCheckedChildren={<BellOutlined />}
            />
          </Tooltip>
          <Tag color={enabled ? 'green' : 'red'}>
            {enabled ? t('pages.learners.enabled') : t('pages.learners.disabled')}
          </Tag>
        </Space>
      ),
    },
    {
      title: t('common.actions'),
      key: 'actions',
      render: (_, record: Learner) => (
        <Space>
          <Button
            type="link"
            icon={<DollarOutlined />}
            onClick={() => navigate(`/learners/${record.id}/finance`)}
          >
            {t('pages.learners.finance')}
          </Button>
          <Button
            type="link"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record.id)}
          >
            {t('common.delete')}
          </Button>
        </Space>
      ),
    },
  ];

  const learners = data?.items || [];

  return (
    <div>
      <PageHeader
        title={t('pages.learners.title')}
        subtitle={t('pages.learners.subtitle')}
        actions={
          <Button
            type="primary"
            icon={<UserAddOutlined />}
            onClick={() => setIsModalOpen(true)}
          >
            {t('pages.learners.addLearner')}
          </Button>
        }
      />

      <ResponsiveDataView<Learner>
        data={learners}
        loading={isLoading}
        columns={columns}
        rowKey="id"
        emptyText={t('pages.learners.noLearners')}
        emptyDescription={t('pages.learners.noLearnersDescription')}
        emptyActionText={t('pages.learners.addLearner')}
        onEmptyAction={() => setIsModalOpen(true)}
        renderCard={(learner) => (
          <LearnerCard
            key={learner.id}
            learner={learner}
            onNotificationToggle={handleNotificationToggle}
            onDelete={handleDelete}
            onFinance={(id) => navigate(`/learners/${id}/finance`)}
            isToggling={notificationsMutation.isPending}
          />
        )}
        pagination={{
          pageSize: 20,
          showSizeChanger: true,
          showTotal: (total) => t('pages.learners.totalLearners', { count: total }),
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
        title={t('pages.learners.deleteTitle')}
        onCancel={() => { setDeleteModalOpen(false); setLearnerToDelete(null); }}
        onOk={confirmDelete}
        okText={t('common.delete')}
        cancelText={t('common.cancel')}
        okButtonProps={{ danger: true, loading: deleteMutation.isPending }}
        cancelButtonProps={{ disabled: deleteMutation.isPending }}
      >
        <p>{t('pages.learners.deleteConfirm', { name: learnerToDelete?.display_name })}</p>
        <p style={{ color: '#ff4d4f' }}>{t('pages.learners.deleteWarning')}</p>
        <p style={{ color: '#8c8c8c' }}>{t('pages.learners.deleteIrreversible')}</p>
      </Modal>
    </div>
  );
};

export default Learners;
