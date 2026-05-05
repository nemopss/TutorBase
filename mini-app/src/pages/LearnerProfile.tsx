import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card,
  Tabs,
  Spin,
  Alert,
  Button,
  Switch,
  Space,
  Modal,
  Typography,
  Tag,
  message,
  notification,
  Dropdown,
  Input,
  Form,
  DatePicker,
  InputNumber,
} from 'antd';
import {
  ArrowLeftOutlined,
  EditOutlined,
  MoreOutlined,
  BellOutlined,
  CalendarOutlined,
  PlusOutlined,
  DollarOutlined,
  DisconnectOutlined,
  LinkOutlined,
  InboxOutlined,
  RollbackOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { isAxiosError } from 'axios';
import { useTranslation } from 'react-i18next';
import api from '../services/api';
import PageHeader from '../components/common/PageHeader';
import LearnerForm from '../components/forms/LearnerForm';
import PackageCard from '../components/cards/PackageCard';
import type { PackageCardAction } from '../components/cards/PackageCard';
import PackageForm from '../components/forms/PackageForm';
import LessonForm from '../components/forms/LessonForm';
import RescheduleForm from '../components/forms/RescheduleForm';
import EmptyState from '../components/common/EmptyState';
import CalendarContainer from '../components/common/CalendarContainer';
import ScheduleTab from '../components/learner/ScheduleTab';
import { DetailPageSkeleton } from '../components/common/PageSkeletons';
import TenantContextRequired from '../components/common/TenantContextRequired';
import { useTheme } from '../theme/ThemeProvider';
import { spacing } from '../theme/tokens';
import { useAuth } from '../auth/AuthProvider';

const { Text, Title } = Typography;

// --- Types --- //
interface LearnerDetail {
  id: number;
  display_name: string;
  notifications_enabled: boolean;
  chat_id: number | null;
  notes: string | null;
  lesson_rate: number | null;
  next_lesson_date: string | null;
  first_package_date: string | null;
  archived_at?: string | null;
  is_archived?: boolean;
}

interface Package {
  id: number;
  title: string;
  learner_name: string;
  package_type?: 'package' | 'one_off';
  status: 'active' | 'completed' | 'cancelled' | 'draft';
  progress: { total: number; completed: number; cancelled: number };
  start_date?: string | null;
  next_lesson_date?: string | null;
  price?: number | null;
  total_paid?: number;
}

interface Payment {
  id: number;
  amount: number;
  paid_at: string;
  notes: string | null;
  package_title: string | null;
}

type LessonStatus = 'scheduled' | 'rescheduled' | 'completed' | 'cancelled';

interface Lesson {
  id: number;
  package_id: number;
  package_title?: string;
  learner_name?: string;
  scheduled_at: string;
  status: LessonStatus;
  duration_minutes?: number;
  teacher_notes?: string;
  sequence_index?: number;
  timezone: string;
}

interface LessonListResponse {
  total: number;
  items: Lesson[];
}

interface LearnerFinance {
  total_paid: number;
  outstanding_balance: number;
  lesson_rate: number | null;
  payment_history: Payment[];
}

// --- Helpers --- //
const formatCurrency = (value: number): string => {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
};

const formatNextLessonDate = (dateStr: string | null, t: (key: string) => string): string => {
  if (!dateStr) return t('common.noLessons');
  
  const date = dayjs(dateStr);
  const now = dayjs();
  const tomorrow = now.add(1, 'day');
  
  if (date.isSame(now, 'day')) {
    return `${t('common.today')}, ${date.format('HH:mm')}`;
  }
  if (date.isSame(tomorrow, 'day')) {
    return `${t('common.tomorrow')}, ${date.format('HH:mm')}`;
  }
  return `${date.format('D MMM')}, ${date.format('HH:mm')}`;
};

const formatLessonDate = (dateStr?: string | null): string => {
  if (!dateStr) return '';
  return dayjs(dateStr).format('D MMMM, HH:mm');
};

// --- Component --- //
const LearnerProfile: React.FC = () => {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { resolvedTheme } = useTheme();
  const { tenantAccess, billing, tenantId, refreshBilling } = useAuth();
  const [notificationApi, notificationContextHolder] = notification.useNotification();
  const requiresTenantContext = tenantId === null;
  const colors = resolvedTheme.colors;
  const canUseFullActions = !tenantAccess || tenantAccess.mode === 'full' || tenantAccess.bypass_access_restrictions;
  const canRestoreLearner = canUseFullActions && (billing?.can_restore_learner ?? true);
  
  const learnerId = parseInt(id || '0');
  
  // State
  const [activeTab, setActiveTab] = useState('overview');
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isArchiveModalOpen, setIsArchiveModalOpen] = useState(false);
  const [isPackageModalOpen, setIsPackageModalOpen] = useState(false);
  const [isOneOffLessonModalOpen, setIsOneOffLessonModalOpen] = useState(false);
  const [isLessonModalOpen, setIsLessonModalOpen] = useState(false);
  const [isRescheduleModalOpen, setIsRescheduleModalOpen] = useState(false);
  const [isUnlinkModalOpen, setIsUnlinkModalOpen] = useState(false);
  const [createdInviteToken, setCreatedInviteToken] = useState<string | null>(null);
  const [editingLesson, setEditingLesson] = useState<Lesson | null>(null);
  const [selectedLessonId, setSelectedLessonId] = useState<number | null>(null);
  const [selectedLesson, setSelectedLesson] = useState<Lesson | null>(null);
  const [oneOffLessonForm] = Form.useForm();
  const [packagePaymentForm] = Form.useForm();
  const [paymentPackage, setPaymentPackage] = useState<Package | null>(null);
  const [statusActionPackage, setStatusActionPackage] = useState<{ package: Package; status: 'active' | 'completed' } | null>(null);

  // Fetch learner detail
  const { data: learner, isLoading, isError, error } = useQuery<LearnerDetail, Error>({
    queryKey: ['learnerDetail', learnerId],
    queryFn: async () => {
      const { data } = await api.get(`/learners/${learnerId}`);
      return data;
    },
    enabled: !!learnerId && !requiresTenantContext,
  });

  // Fetch packages
  const { data: packagesData } = useQuery<{ items: Package[] }>({
    queryKey: ['learnerPackages', learnerId],
    queryFn: async () => {
      const { data } = await api.get('/packages', { params: { learner_id: learnerId } });
      return data;
    },
    enabled: !!learnerId && !requiresTenantContext,
  });

  const { data: oneOffPackagesData } = useQuery<{ items: Package[] }>({
    queryKey: ['learnerOneOffPackages', learnerId],
    queryFn: async () => {
      const { data } = await api.get('/packages', {
        params: { learner_id: learnerId, package_type: 'one_off', limit: 100 },
      });
      return data;
    },
    enabled: !!learnerId && !requiresTenantContext,
  });

  const { data: learnerLessonsData, isLoading: isLoadingLearnerLessons } = useQuery<LessonListResponse>({
    queryKey: ['learnerLessons', learnerId],
    queryFn: async () => {
      const limit = 100;
      const { data: firstPage } = await api.get('/lessons', {
        params: {
          learner_id: learnerId,
          limit,
          offset: 0,
          sort_by: 'scheduled_at',
          sort_order: 'asc',
        },
      });
      let items = [...firstPage.items];
      let offset = limit;
      while (offset < firstPage.total && offset < 1000) {
        const { data } = await api.get('/lessons', {
          params: {
            learner_id: learnerId,
            limit,
            offset,
            sort_by: 'scheduled_at',
            sort_order: 'asc',
          },
        });
        items = [...items, ...data.items];
        offset += limit;
      }
      return { items, total: firstPage.total };
    },
    enabled: !!learnerId && !requiresTenantContext,
  });

  // Fetch finance
  const { data: finance } = useQuery<LearnerFinance>({
    queryKey: ['learnerFinance', learnerId],
    queryFn: async () => {
      const { data } = await api.get(`/learners/${learnerId}/finance`);
      return data;
    },
    enabled: !!learnerId && !requiresTenantContext,
  });

  // Update learner mutation
  const updateMutation = useMutation({
    mutationFn: async (values: any) => {
      const { data } = await api.patch(`/learners/${learnerId}`, values);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learnerDetail', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['learners'] });
      message.success(t('success.updated'));
      setIsEditModalOpen(false);
    },
    onError: (err: Error) => {
      message.error(t('errors.updateFailed', { message: err.message }));
    },
  });

  // Toggle notifications mutation
  const notificationsMutation = useMutation({
    mutationFn: async (enabled: boolean) => {
      const { data } = await api.patch(`/learners/${learnerId}/notifications`, {
        notifications_enabled: enabled,
      });
      return data;
    },
    onSuccess: (_, enabled) => {
      queryClient.invalidateQueries({ queryKey: ['learnerDetail', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['learners'] });
      message.success(
        enabled ? t('pages.learners.notificationsEnabled') : t('pages.learners.notificationsDisabled')
      );
    },
    onError: (err: Error) => {
      message.error(t('errors.updateFailed', { message: err.message }));
    },
  });

  // Unlink Telegram account mutation
  const unlinkAccountMutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.post(`/learners/${learnerId}/unlink-account`, {
        reason: 'manual reset from learner profile',
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learnerDetail', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['learners'] });
      message.success(t('learnerProfile.unlinkAccountSuccess'));
      setIsUnlinkModalOpen(false);
    },
    onError: (err: any) => {
      message.error(err.response?.data?.detail || t('errors.updateFailed', { message: err.message }));
    },
  });

  const createInviteMutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.post(`/learners/${learnerId}/invite`);
      return data as { token: string };
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['learnerDetail', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['learners'] });
      setCreatedInviteToken(data.token);
    },
    onError: (err: any) => {
      message.error(err.response?.data?.detail || t('errors.createFailed', { message: err.message }));
    },
  });

  const archiveMutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.post(`/learners/${learnerId}/archive`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learnerDetail', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['learners'] });
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      refreshBilling();
      message.success(t('pages.learners.archiveSuccess', { defaultValue: 'Ученик перемещён в архив' }));
      setIsArchiveModalOpen(false);
    },
    onError: (err: Error) => {
      message.error(t('errors.updateFailed', { message: err.message }));
    },
  });

  const restoreMutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.post(`/learners/${learnerId}/restore`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learnerDetail', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['learners'] });
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      refreshBilling();
      message.success(t('pages.learners.restoreSuccess', { defaultValue: 'Ученик возвращён в активные' }));
    },
    onError: (err: Error) => {
      const detail = isAxiosError<{ detail?: unknown }>(err) ? err.response?.data?.detail : null;
      notificationApi.error({
        message: 'Не удалось вернуть ученика',
        description: typeof detail === 'string' ? detail : t('errors.updateFailed', { message: err.message }),
        placement: 'topRight',
      });
    },
  });

  // Create package mutation
  const createPackageMutation = useMutation({
    mutationFn: async (values: any) => {
      const { data } = await api.post('/packages', values);
      return data;
    },
    onSuccess: (createdPackage, variables) => {
      queryClient.invalidateQueries({ queryKey: ['learnerPackages', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      const title = createdPackage?.title || variables?.title;
      const baseMessage = variables?.status === 'draft'
        ? t('forms.packageWizard.createdDraft', { title })
        : t('forms.packageWizard.createdActive', { title });
      const lessonCount = variables?.lesson_dates?.length ?? 0;
      notificationApi.success({
        message: baseMessage,
        description: lessonCount > 0
          ? t('forms.packageWizard.createdLessonsSuffix', { count: lessonCount })
          : undefined,
        placement: 'topRight',
      });
      setIsPackageModalOpen(false);
    },
    onError: (err: Error) => {
      message.error(t('errors.createFailed', { message: err.message }));
    },
  });

  const createPackagePaymentMutation = useMutation({
    mutationFn: async (values: any) => {
      if (!paymentPackage) {
        throw new Error(t('errors.notFound'));
      }
      const { data } = await api.post('/payments', {
        learner_id: learnerId,
        package_id: paymentPackage.id,
        amount: values.amount,
        paid_at: values.paid_at.toISOString(),
        notes: values.notes || null,
      });
      return data;
    },
    onSuccess: () => {
      notificationApi.success({
        message: t('pages.finance.paymentRecorded'),
        placement: 'topRight',
      });
      queryClient.invalidateQueries({ queryKey: ['learnerFinance', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['learnerPackages', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      queryClient.invalidateQueries({ queryKey: ['package', paymentPackage?.id?.toString()] });
      setPaymentPackage(null);
      packagePaymentForm.resetFields();
    },
    onError: (err: Error) => {
      message.error(t('errors.saveFailed', { message: err.message }));
    },
  });

  const updatePackageStatusMutation = useMutation({
    mutationFn: async ({ packageId, status }: { packageId: number; status: 'active' | 'completed' }) => {
      const { data } = await api.patch(`/packages/${packageId}`, { status });
      return data;
    },
    onSuccess: (_, variables) => {
      notificationApi.success({
        message: variables.status === 'active'
          ? t('packageCard.actions.activatedToast')
          : t('packageCard.actions.completedToast'),
        placement: 'topRight',
      });
      queryClient.invalidateQueries({ queryKey: ['learnerPackages', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      queryClient.invalidateQueries({ queryKey: ['package', variables.packageId.toString()] });
      setStatusActionPackage(null);
    },
    onError: (err: Error) => {
      message.error(t('errors.updateFailed', { message: err.message }));
    },
  });

  const updateLessonMutation = useMutation({
    mutationFn: async ({ lessonId, values }: { lessonId: number; values: any }) => {
      const { data } = await api.patch(`/lessons/${lessonId}`, values);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learnerLessons', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['learnerDetail', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['learnerPackages', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['learnerOneOffPackages', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['lessons'] });
      message.success(t('success.updated'));
      setIsLessonModalOpen(false);
      setEditingLesson(null);
    },
    onError: (err: Error) => {
      message.error(t('errors.updateFailed', { message: err.message }));
    },
  });

  const createOneOffLessonMutation = useMutation({
    mutationFn: async (values: any) => {
      const { data } = await api.post('/packages/one-off', {
        learner_id: learnerId,
        scheduled_at: values.scheduled_at.toISOString(),
        duration_minutes: values.duration_minutes,
        price: values.price || null,
        title: values.title || null,
        notes: values.notes || null,
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learnerDetail', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['learnerPackages', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['learnerOneOffPackages', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['learnerLessons', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['learnerFinance', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['learners'] });
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      queryClient.invalidateQueries({ queryKey: ['lessons'] });
      setActiveTab('packages');
      message.success(t('learnerProfile.oneOffLessonCreatedInList'));
      oneOffLessonForm.resetFields();
      setIsOneOffLessonModalOpen(false);
    },
    onError: (err: Error) => {
      message.error(t('errors.createFailed', { message: err.message }));
    },
  });

  const handleEditSubmit = async (values: any) => {
    if (!canUseFullActions) {
      message.warning('Редактирование ученика недоступно в grace-периоде.');
      return;
    }
    await updateMutation.mutateAsync({
      display_name: values.display_name,
      notes: values.notes,
      lesson_rate: values.lesson_rate,
    });
  };

  const handleUnlinkAccount = () => {
    if (!canUseFullActions) {
      message.warning('Отвязка аккаунта недоступна в grace-периоде.');
      return;
    }
    setIsUnlinkModalOpen(true);
  };

  const handleCreateInvite = () => {
    if (!canUseFullActions) {
      message.warning('Создание инвайта недоступно в grace-периоде.');
      return;
    }
    createInviteMutation.mutate();
  };

  const handleOpenOneOffLessonModal = () => {
    if (!canUseFullActions) {
      message.warning('Создание разового урока недоступно в grace-периоде.');
      return;
    }
    oneOffLessonForm.setFieldsValue({
      duration_minutes: 60,
      price: learner?.lesson_rate ?? undefined,
    });
    setIsOneOffLessonModalOpen(true);
  };

  const handlePackageCardAction = (action: PackageCardAction, pkg: Package) => {
    if (action === 'payment') {
      const price = Number(pkg.price || 0);
      const totalPaid = Number(pkg.total_paid || 0);
      const remaining = Math.max(0, price - totalPaid);
      packagePaymentForm.setFieldsValue({
        amount: remaining > 0 ? remaining : undefined,
        paid_at: dayjs(),
      });
      setPaymentPackage(pkg);
      return;
    }
    if (action === 'activate' || action === 'complete') {
      setStatusActionPackage({
        package: pkg,
        status: action === 'activate' ? 'active' : 'completed',
      });
      return;
    }
    const actionPath = action === 'open' ? `/packages/${pkg.id}` : `/packages/${pkg.id}?action=${action}`;
    navigate(actionPath);
  };

  const handleCreateOneOffLesson = async () => {
    if (!canUseFullActions) {
      message.warning('Создание разового урока недоступно в grace-периоде.');
      return;
    }
    const values = await oneOffLessonForm.validateFields();
    await createOneOffLessonMutation.mutateAsync(values);
  };

  const handleLessonClick = (lessonId: number) => {
    const lesson = learnerLessonsData?.items.find((item) => item.id === lessonId);
    if (!lesson) return;
    setEditingLesson(lesson);
    setIsLessonModalOpen(true);
  };

  const handleRescheduleLesson = (lessonId: number, newDate?: string) => {
    const lesson = learnerLessonsData?.items.find((item) => item.id === lessonId);
    if (newDate && lesson) {
      updateLessonMutation.mutate({
        lessonId,
        values: { scheduled_at: newDate, status: 'rescheduled' },
      });
      return;
    }
    setSelectedLesson(lesson || null);
    setSelectedLessonId(lessonId);
    setIsRescheduleModalOpen(true);
  };

  const handleRescheduleSubmit = (values: { date: dayjs.Dayjs; time: dayjs.Dayjs; duration_minutes?: number }) => {
    if (!selectedLessonId) return;
    const newDateTime = values.date
      .hour(values.time.hour())
      .minute(values.time.minute())
      .second(0);
    updateLessonMutation.mutate(
      {
        lessonId: selectedLessonId,
        values: {
          scheduled_at: newDateTime.toISOString(),
          status: 'rescheduled',
          duration_minutes: values.duration_minutes,
        },
      },
      {
        onSuccess: () => {
          setIsRescheduleModalOpen(false);
          setSelectedLessonId(null);
          setSelectedLesson(null);
        },
      },
    );
  };

  const handleCopyCreatedInvite = () => {
    if (!createdInviteToken) return;
    navigator.clipboard?.writeText(createdInviteToken);
    message.success(t('common.copied'));
  };

  const showLearnerLimitWarning = () => {
    notificationApi.warning({
      message: 'Пока нет места для активного ученика',
      description: billing
        ? `На тарифе «${billing.plan_name}» доступно ${billing.active_learners_limit} активных учеников, сейчас уже ${billing.active_learners_count}. Чтобы вернуть ученика, архивируйте неактивного ученика. Данные в архиве сохранятся.`
        : 'Сейчас не получается вернуть ученика: лимит активных учеников уже заполнен. Можно освободить место, архивировав неактивного ученика.',
      placement: 'topRight',
    });
  };

  const menuItems = canUseFullActions ? [
    learner?.is_archived
      ? {
          key: 'restore',
          label: t('pages.learners.restoreAction', { defaultValue: 'Вернуть из архива' }),
          icon: <RollbackOutlined />,
          onClick: () => {
            if (!canRestoreLearner) {
              showLearnerLimitWarning();
              return;
            }
            restoreMutation.mutate();
          },
        }
      : {
          key: 'archive',
          label: t('pages.learners.archiveAction', { defaultValue: 'Архивировать' }),
          icon: <InboxOutlined />,
          danger: true,
          onClick: () => setIsArchiveModalOpen(true),
        },
  ] : [];

  if (requiresTenantContext) {
    return (
      <>
        {notificationContextHolder}
        <TenantContextRequired sectionLabel={t('pages.learners.title')} />
      </>
    );
  }

  if (isLoading) {
    return <DetailPageSkeleton />;
  }

  if (isError || !learner) {
    return <Alert message={t('errors.loadFailed', { message: error?.message || '' })} type="error" />;
  }

  const packages = packagesData?.items || [];
  const oneOffPackages = oneOffPackagesData?.items || [];
  const learnerLessons = learnerLessonsData?.items || [];
  const payments = finance?.payment_history || [];

  const cardStyle = {
    background: colors.bgSecondary,
    borderColor: colors.borderPrimary,
    marginBottom: spacing.md,
  };

  return (
    <div>
      {notificationContextHolder}
      <PageHeader
        title={learner.display_name}
        variant="compact"
        leading={(
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/learners')}>
            {t('common.back')}
          </Button>
        )}
        actions={
          <Space>
            <Button icon={<EditOutlined />} disabled={!canUseFullActions} onClick={() => setIsEditModalOpen(true)}>
              {t('common.edit')}
            </Button>
            <Dropdown menu={{ items: menuItems }} trigger={['click']} disabled={!canUseFullActions}>
              <Button icon={<MoreOutlined />} />
            </Dropdown>
          </Space>
        }
      />

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'overview',
            label: t('learnerProfile.tabs.overview'),
            children: (
              <div>
                {/* Basic Info */}
                <Card style={cardStyle}>
                  <Title level={5} style={{ marginTop: 0, marginBottom: spacing.md }}>
                    {t('learnerProfile.basicInfo')}
                  </Title>
                  
                  <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
                    <div>
                      <Text type="secondary">{t('forms.learner.displayNameLabel')}</Text>
                      <div><Text strong>{learner.display_name}</Text></div>
                    </div>
                    
                    {learner.notes && (
                      <div>
                        <Text type="secondary">{t('forms.learner.notesLabel')}</Text>
                        <div><Text>{learner.notes}</Text></div>
                      </div>
                    )}
                    
                    {learner.lesson_rate && (
                      <div>
                        <Text type="secondary">{t('pages.finance.lessonRate')}</Text>
                        <div><Text strong>{formatCurrency(learner.lesson_rate)}</Text></div>
                      </div>
                    )}

                    <div>
                      <Text type="secondary">{t('learnerProfile.telegramAccount')}</Text>
                      <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm, flexWrap: 'wrap' }}>
                        <Text>{learner.chat_id ? String(learner.chat_id) : t('learnerProfile.notLinked')}</Text>
                        {learner.chat_id && (
                          <Button
                            size="small"
                            danger
                            icon={<DisconnectOutlined />}
                            loading={unlinkAccountMutation.isPending}
                            onClick={handleUnlinkAccount}
                          >
                            {t('learnerProfile.unlinkAccountAction')}
                          </Button>
                        )}
                        {!learner.chat_id && (
                          <Button
                            size="small"
                            icon={<LinkOutlined />}
                            loading={createInviteMutation.isPending}
                            onClick={handleCreateInvite}
                          >
                            {t('learnerProfile.createInviteAction')}
                          </Button>
                        )}
                      </div>
                    </div>
                    
                    {learner.first_package_date && (
                      <div>
                        <Text type="secondary">{t('learnerProfile.studiesSince')}</Text>
                        <div><Text>{dayjs(learner.first_package_date).format('D MMMM YYYY')}</Text></div>
                      </div>
                    )}
                  </div>
                </Card>

                {/* Notifications */}
                <Card style={cardStyle}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
                      <BellOutlined />
                      <Text>{t('pages.learners.notifications')}</Text>
                    </div>
                    <Switch
                      checked={learner.notifications_enabled}
                      onChange={(checked) => notificationsMutation.mutate(checked)}
                      loading={notificationsMutation.isPending}
                      disabled={learner.is_archived}
                    />
                  </div>
                </Card>

                {/* Next Lesson */}
                <Card style={cardStyle}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
                    <CalendarOutlined />
                    <div>
                      <Text type="secondary">{t('learnerProfile.nextLesson')}</Text>
                      <div><Text strong>{formatNextLessonDate(learner.next_lesson_date, t)}</Text></div>
                    </div>
                  </div>
                </Card>
              </div>
            ),
          },
          {
            key: 'packages',
            label: t('learnerProfile.tabs.packages'),
            children: (
              <div>
                <Space wrap style={{ marginBottom: spacing.md }}>
                  <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    disabled={!canUseFullActions}
                    onClick={() => setIsPackageModalOpen(true)}
                  >
                    {t('learnerProfile.createPackage')}
                  </Button>
                  <Button
                    icon={<CalendarOutlined />}
                    disabled={!canUseFullActions}
                    onClick={handleOpenOneOffLessonModal}
                  >
                    {t('learnerProfile.createOneOffLesson')}
                  </Button>
                </Space>

                <Card
                  title={t('learnerProfile.learnerCalendar')}
                  style={cardStyle}
                >
                  {isLoadingLearnerLessons ? (
                    <Spin />
                  ) : learnerLessons.length === 0 ? (
                    <EmptyState
                      title={t('learnerProfile.noCalendarLessons')}
                      description={t('learnerProfile.noCalendarLessonsDescription')}
                    />
                  ) : (
                    <CalendarContainer
                      lessons={learnerLessons}
                      timezone="Europe/Moscow"
                      onLessonClick={handleLessonClick}
                      onReschedule={handleRescheduleLesson}
                    />
                  )}
                </Card>

                {packages.length === 0 && oneOffPackages.length === 0 ? (
                  <EmptyState
                    title={t('learnerProfile.noLessons')}
                    description={t('learnerProfile.noLessonsDescription')}
                    actionText={canUseFullActions ? t('learnerProfile.createPackage') : undefined}
                    onAction={canUseFullActions ? () => setIsPackageModalOpen(true) : undefined}
                  />
                ) : (
                  <Space direction="vertical" size={spacing.lg} style={{ width: '100%' }}>
                    <section>
                      <Title level={5} style={{ marginTop: 0, marginBottom: spacing.md }}>
                        {t('learnerProfile.lessonPackages')}
                      </Title>
                      {packages.length === 0 ? (
                        <EmptyState
                          title={t('pages.packages.noPackages')}
                          description={t('pages.packages.noPackagesDescription')}
                          actionText={canUseFullActions ? t('learnerProfile.createPackage') : undefined}
                          onAction={canUseFullActions ? () => setIsPackageModalOpen(true) : undefined}
                        />
                      ) : (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: spacing.md }}>
                          {packages.map((pkg) => (
                            <PackageCard
                              key={pkg.id}
                              package={pkg}
                              showStatus
                              onClick={() => navigate(`/packages/${pkg.id}`)}
                              onAction={handlePackageCardAction}
                            />
                          ))}
                        </div>
                      )}
                    </section>

                    <section>
                      <Title level={5} style={{ marginTop: 0, marginBottom: spacing.md }}>
                        {t('learnerProfile.oneOffLessons')}
                      </Title>
                      {oneOffPackages.length === 0 ? (
                        <EmptyState
                          title={t('learnerProfile.noOneOffLessons')}
                          description={t('learnerProfile.noOneOffLessonsDescription')}
                          actionText={canUseFullActions ? t('learnerProfile.createOneOffLesson') : undefined}
                          onAction={canUseFullActions ? handleOpenOneOffLessonModal : undefined}
                        />
                      ) : (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: spacing.md }}>
                          {oneOffPackages.map((lesson) => {
                            const lessonDate = lesson.next_lesson_date || lesson.start_date;
                            const price = Number(lesson.price || 0);
                            return (
                              <Card
                                key={lesson.id}
                                hoverable
                                style={{ background: colors.bgSecondary, borderColor: colors.borderPrimary }}
                                styles={{ body: { padding: spacing.md } }}
                                onClick={() => navigate(`/packages/${lesson.id}`)}
                              >
                                <Space direction="vertical" size={spacing.xs} style={{ width: '100%' }}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: spacing.sm }}>
                                    <Text strong ellipsis style={{ fontSize: 16 }}>
                                      {lesson.title}
                                    </Text>
                                  </div>
                                  {lessonDate && (
                                    <Text type="secondary">
                                      <CalendarOutlined style={{ marginRight: spacing.xs }} />
                                      {formatLessonDate(lessonDate)}
                                    </Text>
                                  )}
                                  {price > 0 && (
                                    <Text type="secondary">
                                      {t('pages.finance.price')}: {formatCurrency(price)}
                                    </Text>
                                  )}
                                </Space>
                              </Card>
                            );
                          })}
                        </div>
                      )}
                    </section>
                  </Space>
                )}
              </div>
            ),
          },
          {
            key: 'schedule',
            label: t('learnerProfile.tabs.schedule'),
            children: <ScheduleTab learnerId={learnerId} />,
          },
          {
            key: 'finance',
            label: t('learnerProfile.tabs.finance'),
            children: (
              <div>
                {/* Total Payments */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: spacing.md }}>
                  <Card style={cardStyle}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
                      <DollarOutlined
                        style={{
                          fontSize: 24,
                          color: (finance?.outstanding_balance || 0) > 0 ? '#faad14' : colors.accentSuccess,
                        }}
                      />
                      <div>
                        <Text type="secondary">{t('pages.finance.outstanding')}</Text>
                        <div>
                          <Text strong style={{ fontSize: 20 }}>
                            {formatCurrency(finance?.outstanding_balance || 0)}
                          </Text>
                        </div>
                      </div>
                    </div>
                  </Card>
                  <Card style={cardStyle}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
                      <DollarOutlined style={{ fontSize: 24, color: colors.accentSuccess }} />
                      <div>
                        <Text type="secondary">{t('pages.finance.totalPaid')}</Text>
                        <div>
                          <Text strong style={{ fontSize: 20 }}>
                            {formatCurrency(finance?.total_paid || 0)}
                          </Text>
                        </div>
                      </div>
                    </div>
                  </Card>
                  <Card style={cardStyle}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
                      <DollarOutlined style={{ fontSize: 24, color: colors.accentPrimary }} />
                      <div>
                        <Text type="secondary">{t('pages.finance.lessonRate')}</Text>
                        <div>
                          <Text strong style={{ fontSize: 20 }}>
                            {finance?.lesson_rate ? formatCurrency(finance.lesson_rate) : t('pages.finance.notSet')}
                          </Text>
                        </div>
                      </div>
                    </div>
                  </Card>
                </div>

                <Space wrap style={{ marginBottom: spacing.md }}>
                  <Button
                    onClick={() => navigate(`/learners/${learnerId}/finance`)}
                  >
                    {t('learnerProfile.openFullFinance')}
                  </Button>
                  <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={() => navigate(`/learners/${learnerId}/finance?recordPayment=1`)}
                  >
                    {t('pages.finance.recordPayment')}
                  </Button>
                </Space>

                {/* Payment History */}
                <Card title={t('pages.finance.paymentHistory')} style={cardStyle}>
                  {payments.length === 0 ? (
                    <EmptyState
                      title={t('pages.finance.noPayments')}
                      description={t('pages.finance.noPaymentsDescription')}
                    />
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
                      {payments.slice(0, 10).map((payment) => (
                        <div
                          key={payment.id}
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            padding: spacing.sm,
                            background: colors.bgPrimary,
                            borderRadius: 8,
                          }}
                        >
                          <div>
                            <Text>{dayjs(payment.paid_at).format('DD.MM.YYYY')}</Text>
                            {payment.package_title && (
                              <Text type="secondary" style={{ display: 'block', fontSize: 12 }}>
                                {payment.package_title}
                              </Text>
                            )}
                            {payment.notes && (
                              <Text type="secondary" style={{ display: 'block', fontSize: 12, fontStyle: 'italic' }}>
                                {payment.notes}
                              </Text>
                            )}
                          </div>
                          <Tag color="green">{formatCurrency(payment.amount)}</Tag>
                        </div>
                      ))}
                      {payments.length > 10 && (
                        <Button type="link" onClick={() => navigate(`/learners/${learnerId}/finance`)}>
                          {t('common.viewAll')}
                        </Button>
                      )}
                    </div>
                  )}
                </Card>
              </div>
            ),
          },
        ]}
      />

      {/* Edit Modal */}
      <LearnerForm
        visible={isEditModalOpen}
        onSubmit={handleEditSubmit}
        onCancel={() => setIsEditModalOpen(false)}
        loading={updateMutation.isPending}
        mode="edit"
        initialValues={{
          display_name: learner.display_name,
          notes: learner.notes ?? undefined,
          lesson_rate: learner.lesson_rate ?? undefined,
        }}
      />

      {/* Archive Confirmation Modal */}
      <Modal
        open={isArchiveModalOpen}
        title={t('pages.learners.archiveTitle', { defaultValue: 'Архивировать ученика' })}
        onCancel={() => setIsArchiveModalOpen(false)}
        onOk={() => {
          if (!canUseFullActions) {
            message.warning('Архивация ученика недоступна в grace-периоде.');
            return;
          }
          archiveMutation.mutate();
        }}
        okText={t('pages.learners.archiveAction', { defaultValue: 'Архивировать' })}
        cancelText={t('common.cancel')}
        okButtonProps={{ danger: true, loading: archiveMutation.isPending }}
      >
        <p>
          {t('pages.learners.archiveConfirm', {
            name: learner.display_name,
            defaultValue: `Архивировать ученика ${learner.display_name}?`,
          })}
        </p>
        <p style={{ color: '#ff4d4f' }}>
          {t('pages.learners.archiveWarning', {
            defaultValue: 'Ученик будет скрыт из активных списков, а уведомления отключатся.',
          })}
        </p>
        <p style={{ color: '#8c8c8c' }}>
          {t('pages.learners.archiveKeepsHistory', {
            defaultValue: 'История уроков, пакетов и финансов сохранится.',
          })}
        </p>
      </Modal>

      {/* Unlink Telegram Account Modal */}
      <Modal
        open={isUnlinkModalOpen}
        title={t('learnerProfile.unlinkAccountTitle')}
        onCancel={() => setIsUnlinkModalOpen(false)}
        onOk={() => unlinkAccountMutation.mutateAsync()}
        okText={t('learnerProfile.unlinkAccountAction')}
        cancelText={t('common.cancel')}
        okButtonProps={{ danger: true, loading: unlinkAccountMutation.isPending }}
        cancelButtonProps={{ disabled: unlinkAccountMutation.isPending }}
      >
        <p>{t('learnerProfile.unlinkAccountConfirm')}</p>
      </Modal>

      {/* Created Invite Modal */}
      <Modal
        open={!!createdInviteToken}
        title={t('learnerProfile.inviteCreatedTitle')}
        onCancel={() => setCreatedInviteToken(null)}
        footer={[
          <Button key="close" onClick={() => setCreatedInviteToken(null)}>
            {t('common.close')}
          </Button>,
          <Button key="copy" type="primary" onClick={handleCopyCreatedInvite}>
            {t('common.copy')}
          </Button>,
        ]}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text>{t('learnerProfile.inviteCreatedDescription')}</Text>
          <Input.TextArea value={createdInviteToken || ''} readOnly autoSize />
        </Space>
      </Modal>

      {/* Create Package Modal */}
      <PackageForm
        visible={isPackageModalOpen}
        onSubmit={(values) => {
          if (!canUseFullActions) {
            message.warning('Создание пакета недоступно в grace-периоде.');
            return Promise.resolve();
          }
          return createPackageMutation.mutateAsync(values);
        }}
        onCancel={() => setIsPackageModalOpen(false)}
        loading={createPackageMutation.isPending}
        mode="create"
        preselectedLearnerId={learnerId}
      />

      <Modal
        open={!!paymentPackage}
        title={t('pages.finance.recordPayment')}
        onCancel={() => {
          setPaymentPackage(null);
          packagePaymentForm.resetFields();
        }}
        onOk={() => packagePaymentForm.validateFields().then((values) => createPackagePaymentMutation.mutate(values))}
        okText={t('pages.finance.recordPayment')}
        cancelText={t('common.cancel')}
        confirmLoading={createPackagePaymentMutation.isPending}
      >
        {paymentPackage && (
          <Space direction="vertical" size={spacing.md} style={{ width: '100%' }}>
            <div>
              <Text strong>{paymentPackage.title}</Text>
              <div>
                <Text type="secondary">
                  {t('pages.finance.price')}: {paymentPackage.price ? formatCurrency(Number(paymentPackage.price)) : '—'}
                </Text>
              </div>
              <div>
                <Text type="secondary">
                  {t('pages.finance.outstanding')}: {formatCurrency(Math.max(0, Number(paymentPackage.price || 0) - Number(paymentPackage.total_paid || 0)))}
                </Text>
              </div>
            </div>
            <Form form={packagePaymentForm} layout="vertical">
              <Form.Item
                name="amount"
                label={t('pages.finance.amount')}
                rules={[{ required: true, message: t('common.required') }]}
              >
                <InputNumber style={{ width: '100%' }} min={1} />
              </Form.Item>
              <Form.Item
                name="paid_at"
                label={t('pages.finance.date')}
                rules={[{ required: true, message: t('common.required') }]}
              >
                <DatePicker style={{ width: '100%' }} format="DD.MM.YYYY" />
              </Form.Item>
              <Form.Item name="notes" label={t('pages.finance.notes')}>
                <Input.TextArea rows={2} />
              </Form.Item>
            </Form>
          </Space>
        )}
      </Modal>

      <Modal
        open={!!statusActionPackage}
        title={
          statusActionPackage?.status === 'active'
            ? t('packageCard.actions.activateConfirmTitle')
            : t('packageCard.actions.completeConfirmTitle')
        }
        onCancel={() => setStatusActionPackage(null)}
        onOk={() => {
          if (statusActionPackage) {
            updatePackageStatusMutation.mutate({
              packageId: statusActionPackage.package.id,
              status: statusActionPackage.status,
            });
          }
        }}
        okText={
          statusActionPackage?.status === 'active'
            ? t('packageCard.actions.activate')
            : t('packageCard.actions.complete')
        }
        cancelText={t('common.cancel')}
        confirmLoading={updatePackageStatusMutation.isPending}
      >
        <p>
          {statusActionPackage?.status === 'active'
            ? t('packageCard.actions.activateConfirmDescription', { title: statusActionPackage.package.title })
            : t('packageCard.actions.completeConfirmDescription', { title: statusActionPackage?.package.title })}
        </p>
      </Modal>

      <Modal
        open={isOneOffLessonModalOpen}
        title={t('learnerProfile.createOneOffLesson')}
        onCancel={() => setIsOneOffLessonModalOpen(false)}
        onOk={handleCreateOneOffLesson}
        okText={t('common.create')}
        cancelText={t('common.cancel')}
        okButtonProps={{ loading: createOneOffLessonMutation.isPending }}
      >
        <Form
          form={oneOffLessonForm}
          layout="vertical"
          initialValues={{ duration_minutes: 60 }}
        >
          <Form.Item
            name="scheduled_at"
            label={t('learnerProfile.oneOffLessonDate')}
            rules={[{ required: true, message: t('learnerProfile.oneOffLessonDateRequired') }]}
          >
            <DatePicker
              showTime={{ format: 'HH:mm', minuteStep: 5 }}
              format="DD.MM.YYYY HH:mm"
              style={{ width: '100%' }}
            />
          </Form.Item>
          <Form.Item
            name="duration_minutes"
            label={t('schedule.duration')}
            rules={[
              { required: true, message: t('schedule.durationRequired') },
              { type: 'number', min: 15, max: 480, message: t('schedule.durationInvalid') },
            ]}
          >
            <InputNumber min={15} max={480} step={5} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="price" label={t('pages.finance.lessonRate')}>
            <InputNumber min={0} step={100} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="title" label={t('learnerProfile.oneOffLessonTitle')}>
            <Input maxLength={255} placeholder={t('learnerProfile.oneOffLessonTitlePlaceholder')} />
          </Form.Item>
          <Form.Item name="notes" label={t('forms.package.notesLabel')}>
            <Input.TextArea rows={3} maxLength={5000} />
          </Form.Item>
        </Form>
      </Modal>

      <LessonForm
        open={isLessonModalOpen}
        onCancel={() => {
          setIsLessonModalOpen(false);
          setEditingLesson(null);
        }}
        onFinish={(values) => {
          if (!editingLesson) return;
          updateLessonMutation.mutate({ lessonId: editingLesson.id, values });
        }}
        isLoading={updateLessonMutation.isPending}
        initialValues={editingLesson}
        mode="edit"
      />

      <RescheduleForm
        open={isRescheduleModalOpen}
        onCancel={() => {
          setIsRescheduleModalOpen(false);
          setSelectedLessonId(null);
          setSelectedLesson(null);
        }}
        onFinish={handleRescheduleSubmit}
        isLoading={updateLessonMutation.isPending}
        currentDateTime={selectedLesson?.scheduled_at}
        currentDuration={selectedLesson?.duration_minutes}
      />
    </div>
  );
};

export default LearnerProfile;
