import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Input, message, Modal, Card } from 'antd';
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

// --- Component --- //
const Learners: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme.colorScheme === 'dark';
  
  // Modal states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingLearner, setEditingLearner] = useState<Learner | null>(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [learnerToDelete, setLearnerToDelete] = useState<Learner | null>(null);
  
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
    setEditingLearner(learner);
    setIsEditModalOpen(true);
  };

  const handleEditSubmit = async (values: any) => {
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
    const learner = filteredLearners.find(l => l.id === learnerId);
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
            hoverable
            onClick={() => setIsCreateModalOpen(true)}
            style={{
              minHeight: 120,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '2px dashed',
              borderColor: isDark ? '#3a3a3a' : '#d9d9d9',
              background: 'transparent',
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
              onClick={handleCardClick}
              isToggling={togglingLearnerId === learner.id && notificationsMutation.isPending}
            />
          ))}
        </LearnerGrid>
      )}

      {/* FAB - only show when there are learners */}
      {hasLearners && (
        <FloatingActionButton
          icon={<PlusOutlined />}
          onClick={() => setIsCreateModalOpen(true)}
        />
      )}

      {/* Create Learner Modal */}
      <LearnerForm
        visible={isCreateModalOpen}
        onSubmit={createMutation.mutateAsync}
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
    </div>
  );
};

export default Learners;
