import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Card, Input, message, Modal, Space, Typography } from 'antd';
import { PlusOutlined, SearchOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import api from '../services/api';
import LearnerForm from '../components/forms/LearnerForm';
import PageHeader from '../components/common/PageHeader';
import LearnerGrid from '../components/common/LearnerGrid';
import LearnerCard from '../components/cards/LearnerCard';
import FloatingActionButton from '../components/common/FloatingActionButton';
import EmptyState from '../components/common/EmptyState';
import { useTheme } from '../theme/ThemeProvider';
import { useDebounce } from '../hooks/useDebounce';
import { spacing } from '../theme/tokens';
import { useAuth } from '../auth/AuthProvider';

const { Text } = Typography;

// --- Types --- //
interface Learner {
  id: number;
  display_name: string;
  notifications_enabled: boolean;
  chat_id: number | null;
  notes?: string;
  lesson_rate?: number;
  next_lesson_date?: string | null;
}

interface LearnerListResponse {
  items: Learner[];
}

interface InviteTokenResponse {
  token: string;
}

// --- API Fetchers --- //
const fetchLearners = async (): Promise<LearnerListResponse> => {
  const { data } = await api.get('/learners');
  return data;
};

const createLearner = async (values: any) => {
  const { data } = await api.post('/learners', {
    chat_id: values.chat_id ? parseInt(values.chat_id) : null,
    display_name: values.display_name,
    notes: values.notes || null,
    notifications_enabled: values.notifications_enabled ?? true,
    lesson_rate: values.lesson_rate || null,
  });
  return data;
};

const updateLearner = async ({ learnerId, values }: { learnerId: number; values: any }) => {
  const { data } = await api.patch(`/learners/${learnerId}`, values);
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

const unlinkLearnerAccount = async (learnerId: number) => {
  const { data } = await api.post(`/learners/${learnerId}/unlink-account`, {
    reason: 'manual reset from learners list',
  });
  return data;
};

const createLearnerInvite = async (learnerId: number): Promise<InviteTokenResponse> => {
  const { data } = await api.post(`/learners/${learnerId}/invite`);
  return data;
};

// --- Component --- //
const Learners: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { resolvedTheme } = useTheme();
  const { tenantAccess } = useAuth();
  const isDark = resolvedTheme.colorScheme === 'dark';
  const canUseFullActions = !tenantAccess || tenantAccess.mode === 'full' || tenantAccess.bypass_access_restrictions;
  
  // Modal states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingLearner, setEditingLearner] = useState<Learner | null>(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [learnerToDelete, setLearnerToDelete] = useState<Learner | null>(null);
  const [unlinkModalOpen, setUnlinkModalOpen] = useState(false);
  const [learnerToUnlink, setLearnerToUnlink] = useState<Learner | null>(null);
  const [createdInvite, setCreatedInvite] = useState<{ learner: Learner; token: string } | null>(null);
  
  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const debouncedSearch = useDebounce(searchQuery, 300);
  
  // Track which learner is being toggled
  const [togglingLearnerId, setTogglingLearnerId] = useState<number | null>(null);

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
      setIsCreateModalOpen(false);
    },
    onError: (error: Error) => {
      message.error(t('errors.createFailed', { message: error.message }));
    },
  });

  const updateMutation = useMutation({
    mutationFn: updateLearner,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learners'] });
      message.success(t('success.updated'));
      setIsEditModalOpen(false);
      setEditingLearner(null);
    },
    onError: (error: Error) => {
      message.error(t('errors.updateFailed', { message: error.message }));
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
      setTogglingLearnerId(null);
    },
    onError: (error: Error) => {
      message.error(t('errors.updateFailed', { message: error.message }));
      setTogglingLearnerId(null);
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

  const unlinkAccountMutation = useMutation({
    mutationFn: unlinkLearnerAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learners'] });
      if (learnerToUnlink) {
        queryClient.invalidateQueries({ queryKey: ['learnerDetail', learnerToUnlink.id] });
      }
      message.success(t('learnerProfile.unlinkAccountSuccess'));
      setUnlinkModalOpen(false);
      setLearnerToUnlink(null);
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || t('errors.updateFailed', { message: error.message }));
    },
  });

  const createInviteMutation = useMutation({
    mutationFn: createLearnerInvite,
    onSuccess: (data, learnerId) => {
      queryClient.invalidateQueries({ queryKey: ['learners'] });
      queryClient.invalidateQueries({ queryKey: ['learnerDetail', learnerId] });
      const learner = filteredLearners.find((item) => item.id === learnerId);
      if (learner) {
        setCreatedInvite({ learner, token: data.token });
      }
    },
    onError: (error: any) => {
      message.error(error.response?.data?.detail || t('errors.createFailed', { message: error.message }));
    },
  });

  // Filter and sort learners
  const filteredLearners = useMemo(() => {
    const learners = data?.items || [];
    
    // Sort alphabetically by display_name
    const sorted = [...learners].sort((a, b) => 
      a.display_name.localeCompare(b.display_name, undefined, { sensitivity: 'base' })
    );
    
    // Filter by search query
    if (!debouncedSearch.trim()) {
      return sorted;
    }
    
    const query = debouncedSearch.toLowerCase().trim();
    return sorted.filter(learner => 
      learner.display_name.toLowerCase().includes(query)
    );
  }, [data?.items, debouncedSearch]);

  const handleNotificationToggle = (learnerId: number, currentValue: boolean) => {
    setTogglingLearnerId(learnerId);
    notificationsMutation.mutate({
      learnerId,
      enabled: !currentValue,
    });
  };

  const handleEdit = (learner: Learner) => {
    if (!canUseFullActions) {
      message.warning('В grace-периоде можно только обслуживать существующие уроки, уведомления и платежи.');
      return;
    }
    setEditingLearner(learner);
    setIsEditModalOpen(true);
  };

  const handleEditSubmit = async (values: any) => {
    if (!canUseFullActions) {
      message.warning('Редактирование учеников недоступно в grace-периоде.');
      return;
    }
    if (!editingLearner) return;
    await updateMutation.mutateAsync({
      learnerId: editingLearner.id,
      values: {
        display_name: values.display_name,
        notes: values.notes,
        lesson_rate: values.lesson_rate,
      },
    });
  };

  const handleDelete = (learnerId: number) => {
    if (!canUseFullActions) {
      message.warning('Удаление учеников недоступно в grace-периоде.');
      return;
    }
    const learner = filteredLearners.find(l => l.id === learnerId);
    if (learner) {
      setLearnerToDelete(learner);
      setDeleteModalOpen(true);
    }
  };

  const confirmDelete = () => {
    if (!canUseFullActions) {
      message.warning('Удаление учеников недоступно в grace-периоде.');
      return;
    }
    if (learnerToDelete) {
      deleteMutation.mutate(learnerToDelete.id);
    }
  };

  const handleCreateInvite = (learner: Learner) => {
    if (!canUseFullActions) {
      message.warning('Создание инвайта недоступно в grace-периоде.');
      return;
    }
    createInviteMutation.mutate(learner.id);
  };

  const handleUnlinkAccount = (learner: Learner) => {
    if (!canUseFullActions) {
      message.warning('Отвязка аккаунта недоступна в grace-периоде.');
      return;
    }
    setLearnerToUnlink(learner);
    setUnlinkModalOpen(true);
  };

  const confirmUnlinkAccount = () => {
    if (!learnerToUnlink) return;
    unlinkAccountMutation.mutate(learnerToUnlink.id);
  };

  const handleCopyCreatedInvite = () => {
    if (!createdInvite) return;
    navigator.clipboard?.writeText(createdInvite.token);
    message.success(t('common.copied'));
  };

  const handleCardClick = (learner: Learner) => {
    navigate(`/learners/${learner.id}`);
  };

  const hasLearners = (data?.items?.length || 0) > 0;
  const hasFilteredResults = filteredLearners.length > 0;
  const isSearching = debouncedSearch.trim().length > 0;

  return (
    <div>
      <PageHeader
        title={t('pages.learners.title')}
        subtitle={t('pages.learners.subtitle')}
      />

      {!canUseFullActions && (
        <Alert
          type="warning"
          showIcon
          message="Grace-период"
          description="Создание, редактирование и удаление учеников временно недоступны. Можно отключать уведомления и обслуживать уже запланированные занятия."
          style={{ marginBottom: spacing.md }}
        />
      )}

      {/* Search input - only show when there are learners */}
      {hasLearners && (
        <Input
          placeholder={t('common.search')}
          prefix={<SearchOutlined style={{ color: resolvedTheme.colors.textTertiary }} />}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          allowClear
          style={{ marginBottom: spacing.md }}
        />
      )}

      {/* Loading state */}
      {isLoading && <LearnerGrid loading />}

      {/* Empty state - no learners at all */}
      {!isLoading && !hasLearners && (
        <LearnerGrid>
          <Card
            hoverable={canUseFullActions}
            onClick={() => canUseFullActions && setIsCreateModalOpen(true)}
            style={{
              minHeight: 120,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '2px dashed',
              borderColor: isDark ? '#3a3a3a' : '#d9d9d9',
              background: 'transparent',
              opacity: canUseFullActions ? 1 : 0.5,
            }}
            bodyStyle={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <PlusOutlined style={{ fontSize: 32, color: '#8c8c8c' }} />
          </Card>
        </LearnerGrid>
      )}

      {/* Empty search results */}
      {!isLoading && hasLearners && isSearching && !hasFilteredResults && (
        <EmptyState
          title={t('common.noLearnersFound')}
          actionText={t('common.clearSearch')}
          onAction={() => setSearchQuery('')}
        />
      )}

      {/* Learner cards grid */}
      {!isLoading && hasFilteredResults && (
        <LearnerGrid>
          {filteredLearners.map((learner) => (
            <LearnerCard
              key={learner.id}
              learner={learner}
              onNotificationToggle={handleNotificationToggle}
              onEdit={handleEdit}
              onDelete={handleDelete}
              onCreateInvite={handleCreateInvite}
              onUnlinkAccount={handleUnlinkAccount}
              onClick={handleCardClick}
              isToggling={togglingLearnerId === learner.id && notificationsMutation.isPending}
            />
          ))}
        </LearnerGrid>
      )}

      {/* FAB - only show when there are learners */}
      {hasLearners && canUseFullActions && (
        <FloatingActionButton
          icon={<PlusOutlined />}
          onClick={() => setIsCreateModalOpen(true)}
        />
      )}

      {/* Create Learner Modal */}
      <LearnerForm
        visible={isCreateModalOpen}
        onSubmit={(values) => {
          if (!canUseFullActions) {
            message.warning('Создание учеников недоступно в grace-периоде.');
            return Promise.resolve();
          }
          return createMutation.mutateAsync(values);
        }}
        onCancel={() => setIsCreateModalOpen(false)}
        loading={createMutation.isPending}
        mode="create"
      />

      {/* Edit Learner Modal */}
      <LearnerForm
        visible={isEditModalOpen}
        onSubmit={handleEditSubmit}
        onCancel={() => {
          setIsEditModalOpen(false);
          setEditingLearner(null);
        }}
        loading={updateMutation.isPending}
        mode="edit"
        initialValues={editingLearner ? {
          display_name: editingLearner.display_name,
          notes: editingLearner.notes,
          lesson_rate: editingLearner.lesson_rate,
        } : undefined}
      />

      {/* Delete Confirmation Modal */}
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

      <Modal
        open={unlinkModalOpen}
        title={t('learnerProfile.unlinkAccountTitle')}
        onCancel={() => { setUnlinkModalOpen(false); setLearnerToUnlink(null); }}
        onOk={confirmUnlinkAccount}
        okText={t('learnerProfile.unlinkAccountAction')}
        cancelText={t('common.cancel')}
        okButtonProps={{ danger: true, loading: unlinkAccountMutation.isPending }}
        cancelButtonProps={{ disabled: unlinkAccountMutation.isPending }}
      >
        <p>{t('learnerProfile.unlinkAccountConfirm')}</p>
      </Modal>

      <Modal
        open={!!createdInvite}
        title={t('learnerProfile.inviteCreatedTitle')}
        onCancel={() => setCreatedInvite(null)}
        footer={[
          <Button key="close" onClick={() => setCreatedInvite(null)}>
            {t('common.close')}
          </Button>,
          <Button key="copy" type="primary" onClick={handleCopyCreatedInvite}>
            {t('common.copy')}
          </Button>,
        ]}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text>{t('learnerProfile.inviteCreatedDescription')}</Text>
          <Input.TextArea value={createdInvite?.token} readOnly autoSize />
        </Space>
      </Modal>
    </div>
  );
};

export default Learners;
