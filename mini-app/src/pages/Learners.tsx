import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Card, Input, message, Modal, notification, Space, Typography } from 'antd';
import { PlusOutlined, SearchOutlined } from '@ant-design/icons';
import { isAxiosError } from 'axios';
import { useTranslation } from 'react-i18next';
import api from '../services/api';
import LearnerForm from '../components/forms/LearnerForm';
import PageHeader from '../components/common/PageHeader';
import LearnerGrid from '../components/common/LearnerGrid';
import LearnerCard from '../components/cards/LearnerCard';
import FloatingActionButton from '../components/common/FloatingActionButton';
import EmptyState from '../components/common/EmptyState';
import TenantContextRequired from '../components/common/TenantContextRequired';
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
  archived_at?: string | null;
  is_archived?: boolean;
}

interface LearnerListResponse {
  items: Learner[];
}

interface InviteTokenResponse {
  token: string;
}

// --- API Fetchers --- //
type LearnerStatusView = 'active' | 'archived';

const fetchLearners = async (status: LearnerStatusView): Promise<LearnerListResponse> => {
  const { data } = await api.get('/learners', { params: { status } });
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

const archiveLearner = async (learnerId: number) => {
  const { data } = await api.post(`/learners/${learnerId}/archive`);
  return data;
};

const restoreLearner = async (learnerId: number) => {
  const { data } = await api.post(`/learners/${learnerId}/restore`);
  return data;
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

const getApiErrorDetail = (error: unknown, fallback: string) => {
  if (!isAxiosError<{ detail?: unknown }>(error)) {
    return fallback;
  }
  const detail = error.response?.data?.detail;
  return typeof detail === 'string' ? detail : fallback;
};

const getApiErrorStatus = (error: unknown) => (
  isAxiosError(error) ? error.response?.status : undefined
);

// --- Component --- //
const Learners: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { resolvedTheme } = useTheme();
  const { tenantAccess, billing, tenantId, refreshBilling } = useAuth();
  const [notificationApi, notificationContextHolder] = notification.useNotification();
  const requiresTenantContext = tenantId === null;
  const isDark = resolvedTheme.colorScheme === 'dark';
  const canUseFullActions = !tenantAccess || tenantAccess.mode === 'full' || tenantAccess.bypass_access_restrictions;
  const canCreateLearner = canUseFullActions && (billing?.can_create_learner ?? true);
  const canRestoreLearner = canUseFullActions && (billing?.can_restore_learner ?? true);
  const notificationsAllowed = billing?.notifications_allowed ?? true;
  
  // Modal states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingLearner, setEditingLearner] = useState<Learner | null>(null);
  const [unlinkModalOpen, setUnlinkModalOpen] = useState(false);
  const [learnerToUnlink, setLearnerToUnlink] = useState<Learner | null>(null);
  const [createdInvite, setCreatedInvite] = useState<{ learner: Learner; token: string } | null>(null);
  const [statusView, setStatusView] = useState<LearnerStatusView>('active');
  
  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const debouncedSearch = useDebounce(searchQuery, 300);
  
  // Track which learner is being toggled
  const [togglingLearnerId, setTogglingLearnerId] = useState<number | null>(null);

  const { data, isLoading } = useQuery<LearnerListResponse, Error>({
    queryKey: ['learners', statusView],
    queryFn: () => fetchLearners(statusView),
    enabled: !requiresTenantContext,
  });

  const createMutation = useMutation({
    mutationFn: createLearner,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learners'] });
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      refreshBilling();
      message.success(t('pages.learners.createSuccess'));
      setIsCreateModalOpen(false);
    },
    onError: (error: Error) => {
      if (getApiErrorStatus(error) === 402) {
        showLearnerLimitNotice('create');
        return;
      }
      notificationApi.error({
        message: 'Не удалось добавить ученика',
        description: getApiErrorDetail(error, t('errors.createFailed', { message: error.message })),
        placement: 'topRight',
      });
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
      message.error(getApiErrorDetail(error, t('errors.updateFailed', { message: error.message })));
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
      message.error(getApiErrorDetail(error, t('errors.updateFailed', { message: error.message })));
      setTogglingLearnerId(null);
    },
  });

  const archiveMutation = useMutation({
    mutationFn: archiveLearner,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learners'] });
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      refreshBilling();
      message.success(t('pages.learners.archiveSuccess', { defaultValue: 'Ученик перемещён в архив' }));
    },
    onError: (error: Error) => {
      message.error(getApiErrorDetail(error, t('errors.updateFailed', { message: error.message })));
    },
  });

  const restoreMutation = useMutation({
    mutationFn: restoreLearner,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learners'] });
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      refreshBilling();
      message.success(t('pages.learners.restoreSuccess', { defaultValue: 'Ученик возвращён в активные' }));
    },
    onError: (error: Error) => {
      if (getApiErrorStatus(error) === 402) {
        showLearnerLimitNotice('restore');
        return;
      }
      notificationApi.error({
        message: 'Не удалось вернуть ученика',
        description: getApiErrorDetail(error, t('errors.updateFailed', { message: error.message })),
        placement: 'topRight',
      });
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
    const scopedLearners = learners.filter((learner) =>
      statusView === 'archived' ? learner.is_archived === true : learner.is_archived !== true
    );
    
    // Sort alphabetically by display_name
    const sorted = [...scopedLearners].sort((a, b) =>
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
  }, [data?.items, debouncedSearch, statusView]);

  const handleNotificationToggle = (learnerId: number, currentValue: boolean) => {
    if (!notificationsAllowed) {
      message.warning('Уведомления отключены до продления подписки.');
      return;
    }
    setTogglingLearnerId(learnerId);
    notificationsMutation.mutate({
      learnerId,
      enabled: !currentValue,
    });
  };

  const showLearnerLimitNotice = (action: 'create' | 'restore') => {
    const actionText = action === 'create'
      ? 'добавить нового ученика'
      : 'вернуть ученика из архива';
    if (!billing) {
      notificationApi.warning({
        message: 'Пока нет места для активного ученика',
        description: `Сейчас не получается ${actionText}: лимит активных учеников уже заполнен. Можно освободить место, архивировав неактивного ученика.`,
        placement: 'topRight',
      });
      return;
    }
    notificationApi.warning({
      message: 'Пока нет места для активного ученика',
      description: `На тарифе «${billing.plan_name}» доступно ${billing.active_learners_limit} активных учеников, сейчас уже ${billing.active_learners_count}. Чтобы ${actionText}, архивируйте неактивного ученика. Данные в архиве сохранятся.`,
      placement: 'topRight',
    });
  };

  const handleOpenCreate = () => {
    if (!canUseFullActions) {
      message.warning('Создание учеников недоступно в grace-периоде.');
      return;
    }
    if (!canCreateLearner) {
      showLearnerLimitNotice('create');
      return;
    }
    setIsCreateModalOpen(true);
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

  const handleArchive = (learner: Learner) => {
    if (!canUseFullActions) {
      message.warning('Архивация учеников недоступна в grace-периоде.');
      return;
    }
    archiveMutation.mutate(learner.id);
  };

  const handleRestore = (learner: Learner) => {
    if (!canUseFullActions) {
      message.warning('Возврат учеников из архива недоступен в grace-периоде.');
      return;
    }
    if (!canRestoreLearner) {
      showLearnerLimitNotice('restore');
      return;
    }
    restoreMutation.mutate(learner.id);
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
  const isArchiveView = statusView === 'archived';

  if (requiresTenantContext) {
    return (
      <div>
        {notificationContextHolder}
        <PageHeader
          title={t('pages.learners.title')}
          subtitle={t('pages.learners.subtitle')}
        />
        <TenantContextRequired sectionLabel={t('pages.learners.title')} />
      </div>
    );
  }

  return (
    <div>
      {notificationContextHolder}
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

      <div
        role="tablist"
        aria-label={t('pages.learners.title')}
        style={{
          position: 'relative',
          display: 'inline-grid',
          gridTemplateColumns: '1fr 1fr',
          minWidth: 220,
          height: 40,
          padding: 4,
          marginBottom: spacing.md,
          borderRadius: 8,
          border: `1px solid ${resolvedTheme.colors.borderPrimary}`,
          background: resolvedTheme.colors.bgSecondary,
          overflow: 'hidden',
        }}
      >
        <span
          aria-hidden="true"
          style={{
            position: 'absolute',
            top: 4,
            bottom: 4,
            left: 4,
            width: 'calc(50% - 4px)',
            borderRadius: 6,
            background: resolvedTheme.colors.bgPrimary,
            boxShadow: isDark ? '0 1px 4px rgba(0,0,0,0.28)' : '0 1px 4px rgba(0,0,0,0.12)',
            transform: statusView === 'archived' ? 'translateX(100%)' : 'translateX(0)',
            transition: 'transform 180ms ease',
          }}
        />
        {[
          { label: t('pages.learners.activeTab', { defaultValue: 'Активные' }), value: 'active' as const },
          { label: t('pages.learners.archivedTab', { defaultValue: 'Архив' }), value: 'archived' as const },
        ].map((option) => {
          const selected = statusView === option.value;
          return (
            <button
              key={option.value}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => setStatusView(option.value)}
              style={{
                position: 'relative',
                zIndex: 1,
                minWidth: 0,
                height: 32,
                padding: `0 ${spacing.sm}`,
                border: 0,
                borderRadius: 6,
                background: 'transparent',
                color: selected ? resolvedTheme.colors.textPrimary : resolvedTheme.colors.textSecondary,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                font: 'inherit',
                fontWeight: selected ? 600 : 400,
                lineHeight: 1,
                cursor: 'pointer',
              }}
            >
              {option.label}
            </button>
          );
        })}
      </div>

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
      {!isLoading && !hasLearners && !isArchiveView && (
        <LearnerGrid>
          <Card
            hoverable={canUseFullActions}
            onClick={handleOpenCreate}
            style={{
              minHeight: 120,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '2px dashed',
              borderColor: isDark ? '#3a3a3a' : '#d9d9d9',
              background: 'transparent',
              opacity: canCreateLearner ? 1 : 0.65,
              cursor: canUseFullActions ? 'pointer' : 'not-allowed',
            }}
            styles={{
              body: {
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              },
            }}
          >
            <PlusOutlined style={{ fontSize: 32, color: '#8c8c8c' }} />
          </Card>
        </LearnerGrid>
      )}

      {!isLoading && !hasLearners && isArchiveView && (
        <EmptyState title={t('pages.learners.noArchivedLearners', { defaultValue: 'В архиве пока нет учеников' })} />
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
              onCreateInvite={handleCreateInvite}
              onUnlinkAccount={handleUnlinkAccount}
              onArchive={handleArchive}
              onRestore={handleRestore}
              onClick={handleCardClick}
              isToggling={togglingLearnerId === learner.id && notificationsMutation.isPending}
              notificationsGloballyAllowed={notificationsAllowed}
            />
          ))}
        </LearnerGrid>
      )}

      {/* FAB - only show when there are learners */}
      {hasLearners && !isArchiveView && (
        <FloatingActionButton
          icon={<PlusOutlined />}
          onClick={handleOpenCreate}
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
          if (!canCreateLearner) {
            showLearnerLimitNotice('create');
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
