import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate, Link, useLocation } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Spin,
  Alert,
  Button,
  message,
  notification,
  Typography,
  Modal,
  Form,
  InputNumber,
  DatePicker,
  Input,
  Dropdown,
  Progress,
  Space,
} from 'antd';
import type { MenuProps } from 'antd';
import {
  ArrowLeftOutlined,
  CalendarOutlined,
  EditOutlined,
  PlusOutlined,
  BookOutlined,
  DollarOutlined,
  FileTextOutlined,
  DeleteOutlined,
  MoreOutlined,
  PlayCircleOutlined,
  StopOutlined,
  UserOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { useTranslation } from 'react-i18next';
import api from '../services/api';
import CalendarContainer from '../components/common/CalendarContainer';
import PackageForm from '../components/forms/PackageForm';
import RescheduleForm from '../components/forms/RescheduleForm';
import LessonForm from '../components/forms/LessonForm';
import { DetailPageSkeleton } from '../components/common/PageSkeletons';
import TenantContextRequired from '../components/common/TenantContextRequired';
import { formatDate, formatNextLessonDate } from '../utils/datetime';
import { spacing } from '../theme/tokens';
import { useTheme } from '../theme/ThemeProvider';
import { useAuth } from '../auth/AuthProvider';
import { useResponsive } from '../hooks/useResponsive';

const { Text, Title } = Typography;

// --- Types --- //
interface PackageProgress {
  total: number;
  completed: number;
  cancelled: number;
}

interface PackageDetails {
  id: number;
  learner_id: number;
  learner_name: string;
  title: string;
  status: string;
  start_date?: string;
  end_date?: string;
  timezone: string;
  notes?: string;
  total_lessons?: number;
  progress: PackageProgress;
  price?: number | null;
  payment_status?: string;
  total_paid?: number;
  package_type?: 'package' | 'one_off';
  schedule_mode?: 'fixed' | 'flexible' | 'one_off';
  renewal_enabled?: boolean;
  balance?: {
    purchased: number;
    completed: number;
    scheduled: number;
    cancelled: number;
    remaining: number;
    available_to_schedule: number;
    amount_total: number;
    amount_paid: number;
    amount_due: number;
  };
}

interface Lesson {
  id: number;
  scheduled_at: string;
  status: 'scheduled' | 'rescheduled' | 'completed' | 'cancelled';
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

const updateLesson = async ({ lessonId, values }: { lessonId: number; values: any }) => {
  const { data } = await api.patch(`/lessons/${lessonId}`, values);
  return data;
};

const deleteLesson = async (lessonId: number) => {
  await api.delete(`/lessons/${lessonId}`);
};

const deletePackage = async (id: number) => {
  await api.delete(`/packages/${id}`);
};

type PackageRouteAction = 'edit' | 'payment' | 'delete' | 'activate' | 'complete';

const isPackageRouteAction = (value: string | null): value is PackageRouteAction => (
  value === 'edit' ||
  value === 'payment' ||
  value === 'delete' ||
  value === 'activate' ||
  value === 'complete'
);

// --- Helper functions --- //
const formatCurrency = (value: number): string => {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
};

const getPaymentStatusLabelKey = (status?: string): string => {
  switch (status) {
    case 'paid': return 'pages.finance.paid';
    case 'partial': return 'pages.finance.partial';
    case 'unpaid': return 'pages.finance.unpaid';
    default: return 'pages.finance.unpaid';
  }
};

const getStatusAccentKey = (status: string): 'accentSuccess' | 'accentPrimary' | 'accentWarning' | 'accentError' | 'borderPrimary' => {
  switch (status) {
    case 'active': return 'accentSuccess';
    case 'completed': return 'accentPrimary';
    case 'draft': return 'accentWarning';
    case 'cancelled': return 'accentError';
    default: return 'borderPrimary';
  }
};

// --- Component --- //
const PackageDetail: React.FC = () => {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const { resolvedTheme } = useTheme();
  const { tenantAccess, tenantId } = useAuth();
  const requiresTenantContext = tenantId === null;
  const { isMobile } = useResponsive();
  const colors = resolvedTheme.colors;
  const canUseFullActions = !tenantAccess || tenantAccess.mode === 'full' || tenantAccess.bypass_access_restrictions;
  const [notificationApi, notificationContextHolder] = notification.useNotification();
  const [paymentForm] = Form.useForm();
  const handledRouteActionRef = useRef<string | null>(null);

  // Modal states
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isRescheduleModalOpen, setIsRescheduleModalOpen] = useState(false);
  const [isDeletePackageModalOpen, setIsDeletePackageModalOpen] = useState(false);
  const [isDeleteLessonModalOpen, setIsDeleteLessonModalOpen] = useState(false);
  const [isCompleteLessonModalOpen, setIsCompleteLessonModalOpen] = useState(false);
  const [isCancelLessonModalOpen, setIsCancelLessonModalOpen] = useState(false);
  const [isAddLessonModalOpen, setIsAddLessonModalOpen] = useState(false);
  const [statusAction, setStatusAction] = useState<'active' | 'completed' | null>(null);
  const [selectedLessonId, setSelectedLessonId] = useState<number | null>(null);
  const [selectedLesson, setSelectedLesson] = useState<Lesson | null>(null);
  const [newLessonDate, setNewLessonDate] = useState<string | null>(null);

  // Queries
  const {
    data: packageData,
    isLoading: isLoadingPackage,
    isError: isErrorPackage,
    error: errorPackage,
  } = useQuery<PackageDetails, Error>({
    queryKey: ['package', id],
    queryFn: () => fetchPackage(id!),
    enabled: !!id && !requiresTenantContext,
  });

  const { data: lessonsData, isLoading: isLoadingLessons } = useQuery<LessonListResponse, Error>({
    queryKey: ['packageLessons', id],
    queryFn: () => fetchPackageLessons(id!),
    enabled: !!id && !requiresTenantContext,
  });

  // Mutations
  const createLessonMutation = useMutation({
    mutationFn: async (values: any) => {
      const { data } = await api.post(`/lessons/packages/${id}`, values);
      return data;
    },
    onSuccess: () => {
      notificationApi.success({ message: t('success.created'), placement: 'topRight' });
      queryClient.invalidateQueries({ queryKey: ['packageLessons', id] });
      queryClient.invalidateQueries({ queryKey: ['package', id] });
      setIsAddLessonModalOpen(false);
      setNewLessonDate(null);
    },
    onError: (error: Error) => {
      message.error(t('errors.createFailed', { message: error.message }));
    },
  });

  const updateLessonMutation = useMutation({
    mutationFn: updateLesson,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['packageLessons', id] });
      queryClient.invalidateQueries({ queryKey: ['package', id] });
    },
    onError: (error: Error) => {
      message.error(t('errors.updateFailed', { message: error.message }));
    },
  });

  const deleteLessonMutation = useMutation({
    mutationFn: deleteLesson,
    onSuccess: () => {
      notificationApi.success({ message: t('success.deleted'), placement: 'topRight' });
      queryClient.invalidateQueries({ queryKey: ['packageLessons', id] });
      queryClient.invalidateQueries({ queryKey: ['package', id] });
      setIsDeleteLessonModalOpen(false);
      setSelectedLessonId(null);
    },
    onError: (error: Error) => {
      message.error(t('errors.deleteFailed', { message: error.message }));
    },
  });

  const deletePackageMutation = useMutation({
    mutationFn: deletePackage,
    onSuccess: () => {
      notificationApi.success({ message: t('success.deleted'), placement: 'topRight' });
      queryClient.removeQueries({ queryKey: ['package', id] });
      queryClient.removeQueries({ queryKey: ['packageLessons', id] });
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      queryClient.invalidateQueries({ queryKey: ['learnerPackages'] });
      queryClient.invalidateQueries({ queryKey: ['lessons'] });
      navigate('/packages');
    },
    onError: (error: Error) => {
      message.error(t('errors.deleteFailed', { message: error.message }));
    },
  });

  const createPaymentMutation = useMutation({
    mutationFn: async (values: any) => {
      const { data } = await api.post('/payments', {
        learner_id: packageData?.learner_id,
        package_id: parseInt(id!),
        amount: values.amount,
        paid_at: values.paid_at.toISOString(),
        notes: values.notes || null,
      });
      return data;
    },
    onSuccess: () => {
      notificationApi.success({ message: t('pages.finance.paymentRecorded'), placement: 'topRight' });
      queryClient.invalidateQueries({ queryKey: ['package', id] });
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      setIsPaymentModalOpen(false);
      paymentForm.resetFields();
    },
    onError: (error: Error) => {
      message.error(t('errors.saveFailed', { message: error.message }));
    },
  });

  const clearRouteAction = () => {
    if (location.search.includes('action=')) {
      navigate(`/packages/${id}`, { replace: true });
    }
  };

  const updatePackageMutation = useMutation({
    mutationFn: async (values: any) => {
      const { data } = await api.patch(`/packages/${id}`, values);
      return data;
    },
    onSuccess: (_, variables) => {
      notificationApi.success({
        message: variables?.status === 'active'
          ? t('packageCard.actions.activatedToast')
          : variables?.status === 'completed'
            ? t('packageCard.actions.completedToast')
            : t('success.updated'),
        placement: 'topRight',
      });
      queryClient.invalidateQueries({ queryKey: ['package', id] });
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      setIsEditModalOpen(false);
      setStatusAction(null);
      clearRouteAction();
    },
    onError: (error: Error) => {
      message.error(t('errors.updateFailed', { message: error.message }));
    },
  });

  const updatePackageStatus = (nextStatus: 'active' | 'completed') => {
    if (!canUseFullActions) {
      message.warning('Во время льготного периода нельзя менять статус пакета.');
      clearRouteAction();
      return;
    }
    setStatusAction(nextStatus);
    clearRouteAction();
  };

  // Handlers
  const openPaymentModal = () => {
    const price = packageData?.price || 0;
    const totalPaid = packageData?.total_paid || 0;
    const remaining = Math.max(0, price - totalPaid);
    paymentForm.setFieldsValue({
      amount: remaining > 0 ? remaining : undefined,
      paid_at: dayjs(),
    });
    setIsPaymentModalOpen(true);
  };

  const handleReschedule = (lessonId: number, newDate?: string) => {
    const lesson = lessonsData?.items.find((l) => l.id === lessonId);
    if (newDate && lesson) {
      // Drag & drop reschedule - update directly
      updateLessonMutation.mutate({
        lessonId,
        values: { scheduled_at: newDate, status: 'rescheduled' },
      });
    } else {
      // Context menu reschedule - open modal
      setSelectedLesson(lesson || null);
      setSelectedLessonId(lessonId);
      setIsRescheduleModalOpen(true);
    }
  };

  const handleRescheduleSubmit = (values: { date: dayjs.Dayjs; time: dayjs.Dayjs; duration_minutes?: number }) => {
    if (!selectedLessonId) return;
    const newDateTime = values.date
      .hour(values.time.hour())
      .minute(values.time.minute())
      .second(0);
    const updateValues: any = { 
      scheduled_at: newDateTime.toISOString(), 
      status: 'rescheduled' 
    };
    if (values.duration_minutes) {
      updateValues.duration_minutes = values.duration_minutes;
    }
    updateLessonMutation.mutate(
      { lessonId: selectedLessonId, values: updateValues },
      {
        onSuccess: () => {
          notificationApi.success({ message: t('pages.lessons.lessonRescheduled'), placement: 'topRight' });
          setIsRescheduleModalOpen(false);
          setSelectedLessonId(null);
          setSelectedLesson(null);
        },
      }
    );
  };

  const handleComplete = (lessonId: number) => {
    setSelectedLessonId(lessonId);
    setIsCompleteLessonModalOpen(true);
  };

  const confirmComplete = () => {
    if (!selectedLessonId) return;
    updateLessonMutation.mutate(
      { lessonId: selectedLessonId, values: { status: 'completed' } },
      {
        onSuccess: () => {
          notificationApi.success({ message: t('pages.lessons.lessonCompleted'), placement: 'topRight' });
          setIsCompleteLessonModalOpen(false);
          setSelectedLessonId(null);
        },
      }
    );
  };

  const handleCancel = (lessonId: number) => {
    setSelectedLessonId(lessonId);
    setIsCancelLessonModalOpen(true);
  };

  const confirmCancel = () => {
    if (!selectedLessonId) return;
    updateLessonMutation.mutate(
      { lessonId: selectedLessonId, values: { status: 'cancelled' } },
      {
        onSuccess: () => {
          notificationApi.success({ message: t('pages.lessons.lessonCancelled'), placement: 'topRight' });
          setIsCancelLessonModalOpen(false);
          setSelectedLessonId(null);
        },
      }
    );
  };

  const handleDelete = (lessonId: number) => {
    if (!canUseFullActions) {
      message.warning('Во время льготного периода можно вести существующие уроки и платежи, но нельзя удалять уроки.');
      return;
    }
    setSelectedLessonId(lessonId);
    setIsDeleteLessonModalOpen(true);
  };

  const confirmDeleteLesson = () => {
    if (!canUseFullActions) {
      message.warning('Во время льготного периода можно вести существующие уроки и платежи, но нельзя удалять уроки.');
      return;
    }
    if (selectedLessonId) {
      deleteLessonMutation.mutate(selectedLessonId);
    }
  };

  const confirmDeletePackage = () => {
    if (!canUseFullActions) {
      message.warning('Во время льготного периода можно вести существующие уроки и платежи, но нельзя удалять пакеты.');
      return;
    }
    if (id) {
      deletePackageMutation.mutate(parseInt(id));
    }
  };

  useEffect(() => {
    if (!id || !packageData) {
      return;
    }

    const action = new URLSearchParams(location.search).get('action');
    if (!isPackageRouteAction(action)) {
      return;
    }

    const actionKey = `${id}:${action}:${location.search}`;
    if (handledRouteActionRef.current === actionKey) {
      return;
    }
    handledRouteActionRef.current = actionKey;

    if (action === 'payment') {
      openPaymentModal();
      clearRouteAction();
      return;
    }

    if (!canUseFullActions) {
      message.warning('Во время льготного периода это действие с пакетом недоступно.');
      clearRouteAction();
      return;
    }

    if (action === 'edit') {
      setIsEditModalOpen(true);
      clearRouteAction();
      return;
    }

    if (action === 'delete') {
      setIsDeletePackageModalOpen(true);
      clearRouteAction();
      return;
    }

    if (action === 'activate') {
      updatePackageStatus('active');
      return;
    }

    if (action === 'complete') {
      updatePackageStatus('completed');
    }
  }, [canUseFullActions, id, location.search, packageData]);

  if (requiresTenantContext) {
    return <TenantContextRequired sectionLabel={t('pages.packages.title')} />;
  }

  // Loading/Error states
  if (!id || isLoadingPackage) {
    return <DetailPageSkeleton showTabs={false} />;
  }

  if (isErrorPackage) {
    return <Alert message={t('common.error')} description={errorPackage.message} type="error" />;
  }

  const progress = packageData?.progress || { total: 0, completed: 0, cancelled: 0 };
  const purchasedLessons = packageData?.balance?.purchased ?? packageData?.total_lessons ?? progress.total;
  const remaining = packageData?.balance?.remaining ?? Math.max(purchasedLessons - progress.completed, 0);
  const completedOrClosed = packageData?.balance?.completed ?? progress.completed;
  const progressPercent = purchasedLessons > 0
    ? Math.round((completedOrClosed / purchasedLessons) * 100)
    : 0;
  const price = Number(packageData?.price || 0);
  const totalPaid = Number(packageData?.total_paid || 0);
  const outstanding = Math.max(0, price - totalPaid);
  const statusAccent = colors[getStatusAccentKey(packageData?.status || '')];
  const upcomingLesson = lessonsData?.items
    .filter((lesson) => (
      (lesson.status === 'scheduled' || lesson.status === 'rescheduled') &&
      dayjs(lesson.scheduled_at).isAfter(dayjs().subtract(1, 'minute'))
    ))
    .sort((a, b) => dayjs(a.scheduled_at).valueOf() - dayjs(b.scheduled_at).valueOf())[0];

  const panelStyle: React.CSSProperties = {
    background: colors.bgTertiary,
    border: 0,
    borderRadius: 10,
    boxShadow: 'none',
  };

  const panelBodyStyle: React.CSSProperties = {
    padding: spacing.md,
  };

  const sectionHeaderStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
    marginBottom: isMobile ? spacing.md : spacing.sm,
  };

  const subtleIconStyle: React.CSSProperties = {
    color: colors.textSecondary,
    fontSize: 16,
  };

  const innerSurfaceStyle: React.CSSProperties = {
    background: colors.bgSecondary,
    borderRadius: 10,
    padding: spacing.sm,
  };

  const valueRowStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    gap: spacing.sm,
    padding: isMobile ? '7px 0' : '5px 0',
  };

  // Handle lesson click from calendar
  const handleLessonClick = (lessonId: number) => {
    setSelectedLessonId(lessonId);
    const lesson = lessonsData?.items.find((l) => l.id === lessonId);
    setSelectedLesson(lesson || null);
    // Open action modal or reschedule directly
    setIsRescheduleModalOpen(true);
  };

  // Handle add lesson from calendar
  const handleAddLesson = (date: string) => {
    if (!canUseFullActions) {
      message.warning('Во время льготного периода можно вести существующие уроки и платежи, но нельзя добавлять новые уроки.');
      return;
    }
    setNewLessonDate(date);
    setIsAddLessonModalOpen(true);
  };

  const actionMenuItems: MenuProps['items'] = [
    {
      key: 'edit',
      icon: <EditOutlined />,
      label: t('common.edit'),
      disabled: !canUseFullActions,
    },
    {
      key: 'payment',
      icon: <DollarOutlined />,
      label: t('pages.finance.recordPayment'),
      disabled: !packageData?.price,
    },
    ...(packageData?.status === 'active'
      ? [{
          key: 'complete',
          icon: <StopOutlined />,
          label: t('packageCard.actions.complete'),
          disabled: !canUseFullActions,
        } as const]
      : [{
          key: 'activate',
          icon: <PlayCircleOutlined />,
          label: t('packageCard.actions.activate'),
          disabled: !canUseFullActions,
        } as const]),
    {
      type: 'divider',
    },
    {
      key: 'delete',
      icon: <DeleteOutlined />,
      label: t('common.delete'),
      danger: true,
      disabled: !canUseFullActions,
    },
  ];

  const handleActionMenuClick: MenuProps['onClick'] = ({ key }) => {
    if (key === 'edit') {
      setIsEditModalOpen(true);
      return;
    }
    if (key === 'payment') {
      openPaymentModal();
      return;
    }
    if (key === 'activate') {
      updatePackageStatus('active');
      return;
    }
    if (key === 'complete') {
      updatePackageStatus('completed');
      return;
    }
    if (key === 'delete') {
      setIsDeletePackageModalOpen(true);
    }
  };

  return (
    <div>
      {notificationContextHolder}

      {!canUseFullActions && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: spacing.md }}
          message="Доступ ограничен льготным периодом"
          description="Можно переносить, завершать и отменять существующие уроки, а также корректировать платежи. Новые уроки, удаление и редактирование пакета доступны после разблокировки кабинета."
        />
      )}

      <div
        style={{
          display: 'flex',
          flexDirection: isMobile ? 'column' : 'row',
          alignItems: isMobile ? 'stretch' : 'flex-start',
          justifyContent: 'space-between',
          gap: spacing.sm,
          marginBottom: isMobile ? spacing.md : spacing.sm,
        }}
      >
        <div style={{ minWidth: 0 }}>
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/packages')}
            style={{ marginLeft: -spacing.sm, marginBottom: spacing.xs }}
          >
            {t('common.back')}
          </Button>
          <Title level={3} style={{ margin: 0, lineHeight: 1.2 }}>
            {packageData?.title}
          </Title>
          <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm, flexWrap: 'wrap', marginTop: spacing.xs }}>
            <Link to={`/learners/${packageData?.learner_id}`}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: colors.textSecondary }}>
                <UserOutlined style={{ fontSize: 12 }} />
                {packageData?.learner_name}
              </span>
            </Link>
            <Text type="secondary">•</Text>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: statusAccent,
                }}
              />
              <Text type="secondary" style={{ fontSize: 13 }}>
                {t(`pages.packages.status.${packageData?.status}`)}
              </Text>
            </span>
          </div>
        </div>
        <Space size={spacing.sm} wrap style={{ justifyContent: isMobile ? 'flex-start' : 'flex-end' }}>
          {canUseFullActions && (
            <Button icon={<EditOutlined />} onClick={() => setIsEditModalOpen(true)}>
              {t('common.edit')}
            </Button>
          )}
          <Dropdown
            menu={{ items: actionMenuItems, onClick: handleActionMenuClick }}
            placement="bottomRight"
            trigger={['click']}
          >
            <Button icon={<MoreOutlined />} aria-label={t('packageCard.actions.menu')} />
          </Dropdown>
        </Space>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: isMobile ? '1fr' : 'minmax(0, 1fr) minmax(300px, 360px)',
          gap: spacing.md,
          alignItems: 'start',
        }}
      >
        <div style={panelStyle}>
          <div style={{ ...panelBodyStyle, paddingBottom: 0 }}>
            <div style={sectionHeaderStyle}>
              <div>
                <Text strong style={{ fontSize: 16 }}>{t('navigation.lessons')}</Text>
                <div>
                  <Text type="secondary" style={{ fontSize: 13 }}>
                    {progress.total} {t('pages.finance.total')}
                  </Text>
                </div>
              </div>
              {canUseFullActions && (
                <Button
                  icon={<PlusOutlined />}
                  onClick={() => {
                    setNewLessonDate(null);
                    setIsAddLessonModalOpen(true);
                  }}
                >
                  {t('pages.lessons.addLesson')}
                </Button>
              )}
            </div>
          </div>
          <div style={{ ...panelBodyStyle, paddingTop: 0 }}>
            {isLoadingLessons ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: spacing.xl }}>
                <Spin />
              </div>
            ) : (
              <CalendarContainer
                lessons={lessonsData?.items || []}
                timezone={packageData?.timezone || 'UTC'}
                onLessonClick={handleLessonClick}
                onAddLesson={handleAddLesson}
                onReschedule={handleReschedule}
                onComplete={handleComplete}
                onCancel={handleCancel}
                onDelete={handleDelete}
                calendarHeight={isMobile ? undefined : 'calc(100vh - 430px)'}
                calendarMinHeight={isMobile ? undefined : 300}
                compact={!isMobile}
              />
            )}
          </div>
        </div>

        <Space direction="vertical" size={spacing.md} style={{ width: '100%' }}>
          <div style={{ ...panelStyle, ...panelBodyStyle }}>
            <div style={sectionHeaderStyle}>
              <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
                <BookOutlined style={subtleIconStyle} />
                <Text strong>{t('packageDetail.summary')}</Text>
              </div>
              <Button
                type="text"
                size="small"
                icon={<EditOutlined />}
                disabled={!canUseFullActions}
                onClick={() => setIsEditModalOpen(true)}
              />
            </div>
            <div style={{ marginBottom: spacing.sm }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: spacing.sm, marginBottom: 6 }}>
                <Text type="secondary">{t('pages.packages.progress')}</Text>
                <Text strong>{completedOrClosed}/{purchasedLessons}</Text>
              </div>
              <Progress
                percent={progressPercent}
                showInfo={false}
                size="small"
                strokeColor={colors.accentPrimary}
                trailColor={colors.borderPrimary}
              />
              <Text type="secondary" style={{ display: 'block', fontSize: 12, marginTop: spacing.xs }}>
                {progress.completed} {t('pages.finance.completed')} · {progress.cancelled} {t('pages.finance.cancelled')} · {remaining} {t('pages.finance.remaining')}
              </Text>
            </div>
            {packageData?.balance && (
              <div style={{ ...innerSurfaceStyle, marginBottom: spacing.sm }}>
                <div style={valueRowStyle}>
                  <Text type="secondary">{t('packageDetail.availableToSchedule')}</Text>
                  <Text strong>{packageData.balance.available_to_schedule}</Text>
                </div>
                <div style={valueRowStyle}>
                  <Text type="secondary">{t('packageDetail.scheduledLessons')}</Text>
                  <Text>{packageData.balance.scheduled}</Text>
                </div>
              </div>
            )}
            <div style={valueRowStyle}>
              <Text type="secondary">{t('forms.packageWizard.modeLabel')}</Text>
              <Text>
                {t(`forms.packageWizard.${packageData?.schedule_mode === 'one_off' ? 'oneOffTitle' : `${packageData?.schedule_mode || 'flexible'}Title`}`)}
              </Text>
            </div>
            <div style={valueRowStyle}>
              <Text type="secondary">{t('forms.packageWizard.renewalTitle')}</Text>
              <Text type={packageData?.renewal_enabled ? undefined : 'secondary'}>
                {packageData?.renewal_enabled
                  ? t('forms.packageWizard.renewalOnReview')
                  : t('forms.packageWizard.renewalOffReview')}
              </Text>
            </div>
            <div style={valueRowStyle}>
              <Text type="secondary">{t('packageDetail.nextLesson')}</Text>
              <Text style={{ textAlign: 'right' }}>
                {upcomingLesson
                  ? formatNextLessonDate(upcomingLesson.scheduled_at, t, packageData?.timezone)
                  : t('packageCard.noScheduled')}
              </Text>
            </div>
            <div style={valueRowStyle}>
              <Text type="secondary">{t('pages.finance.start')}</Text>
              <Text>{packageData?.start_date ? formatDate(packageData.start_date, { timezone: packageData.timezone }) : '—'}</Text>
            </div>
            <div style={valueRowStyle}>
              <Text type="secondary">{t('pages.finance.end')}</Text>
              <Text>{packageData?.end_date ? formatDate(packageData.end_date, { timezone: packageData.timezone }) : '—'}</Text>
            </div>
            <div style={{ ...innerSurfaceStyle, marginTop: spacing.sm }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: spacing.sm }}>
                <CalendarOutlined style={{ ...subtleIconStyle, marginTop: 2 }} />
                <div style={{ minWidth: 0, flex: 1 }}>
                  <Text strong style={{ display: 'block', fontSize: 13 }}>
                    {t('packageDetail.scheduleSource')}
                  </Text>
                  <Text type="secondary" style={{ display: 'block', fontSize: 12, lineHeight: 1.35 }}>
                    {t('packageDetail.scheduleSourceDescription')}
                  </Text>
                  <Button
                    type="link"
                    size="small"
                    style={{ padding: 0, height: 'auto', marginTop: spacing.xs }}
                    onClick={() => navigate(`/learners/${packageData?.learner_id}?section=schedule`)}
                  >
                    {t('packageDetail.openLearnerSchedule')}
                  </Button>
                </div>
              </div>
            </div>
          </div>

          <div style={{ ...panelStyle, ...panelBodyStyle }}>
            <div style={sectionHeaderStyle}>
              <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
                <DollarOutlined style={subtleIconStyle} />
                <Text strong>{t('pages.finance.payment')}</Text>
              </div>
              <Button
                type="text"
                size="small"
                icon={<PlusOutlined />}
                onClick={openPaymentModal}
                disabled={!packageData?.price}
              />
            </div>
            <div style={valueRowStyle}>
              <Text type="secondary">{t('pages.finance.price')}</Text>
              <Text>{price > 0 ? formatCurrency(price) : '—'}</Text>
            </div>
            <div style={valueRowStyle}>
              <Text type="secondary">{t('pages.finance.paid')}</Text>
              <Text>{formatCurrency(totalPaid)}</Text>
            </div>
            <div style={valueRowStyle}>
              <Text type="secondary">{t('pages.finance.outstanding')}</Text>
              <Text strong>{price > 0 ? formatCurrency(outstanding) : '—'}</Text>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: spacing.xs }}>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: outstanding > 0 ? colors.accentWarning : colors.accentPrimary,
                }}
              />
              <Text type="secondary" style={{ fontSize: 13 }}>
                {t(getPaymentStatusLabelKey(packageData?.payment_status))}
              </Text>
            </div>
          </div>

          <div style={{ ...panelStyle, ...panelBodyStyle }}>
            <div style={sectionHeaderStyle}>
              <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
                <FileTextOutlined style={subtleIconStyle} />
                <Text strong>{t('pages.finance.notes')}</Text>
              </div>
              <Button
                type="text"
                size="small"
                icon={<EditOutlined />}
                disabled={!canUseFullActions}
                onClick={() => setIsEditModalOpen(true)}
              />
            </div>
            <Text type={packageData?.notes ? undefined : 'secondary'} style={{ whiteSpace: 'pre-wrap' }}>
              {packageData?.notes || t('pages.finance.noNotes')}
            </Text>
          </div>

          <Button
            danger
            type="text"
            icon={<DeleteOutlined />}
            disabled={!canUseFullActions}
            onClick={() => setIsDeletePackageModalOpen(true)}
            style={{ alignSelf: 'flex-start', paddingLeft: 0 }}
          >
            {t('pages.finance.deletePackage')}
          </Button>
        </Space>
      </div>

      {/* Payment Modal */}
      <Modal
        title={t('pages.finance.recordPayment')}
        open={isPaymentModalOpen}
        onOk={() => paymentForm.validateFields().then((values) => createPaymentMutation.mutate(values))}
        onCancel={() => {
          setIsPaymentModalOpen(false);
          paymentForm.resetFields();
        }}
        confirmLoading={createPaymentMutation.isPending}
        okText={t('pages.finance.recordPayment')}
        cancelText={t('common.cancel')}
      >
        <Space direction="vertical" size={spacing.md} style={{ width: '100%' }}>
          <div>
            <Text strong>{packageData?.title}</Text>
            <div>
              <Text type="secondary">
                {t('pages.finance.price')}: {price > 0 ? formatCurrency(price) : '—'}
              </Text>
            </div>
            <div>
              <Text type="secondary">
                {t('pages.finance.outstanding')}: {price > 0 ? formatCurrency(outstanding) : '—'}
              </Text>
            </div>
          </div>
          <Form form={paymentForm} layout="vertical">
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
      </Modal>

      {/* Edit Package Modal */}
      <PackageForm
        open={isEditModalOpen}
        onCancel={() => setIsEditModalOpen(false)}
        onFinish={(values) => {
          if (!canUseFullActions) {
            message.warning('Во время льготного периода можно вести существующие уроки и платежи, но нельзя редактировать пакет.');
            return;
          }
          updatePackageMutation.mutate(values);
        }}
        isLoading={updatePackageMutation.isPending}
        initialValues={{
          id: packageData?.id,
          title: packageData?.title,
          notes: packageData?.notes,
          price: packageData?.price,
          start_date: packageData?.start_date,
          end_date: packageData?.end_date,
          timezone: packageData?.timezone,
          learner_id: packageData?.learner_id,
        }}
      />

      {/* Package Status Modal */}
      <Modal
        open={!!statusAction}
        title={
          statusAction === 'active'
            ? t('packageCard.actions.activateConfirmTitle')
            : t('packageCard.actions.completeConfirmTitle')
        }
        onCancel={() => setStatusAction(null)}
        onOk={() => {
          if (statusAction) {
            updatePackageMutation.mutate({ status: statusAction });
          }
        }}
        okText={
          statusAction === 'active'
            ? t('packageCard.actions.activate')
            : t('packageCard.actions.complete')
        }
        cancelText={t('common.cancel')}
        confirmLoading={updatePackageMutation.isPending}
      >
        <p>
          {statusAction === 'active'
            ? t('packageCard.actions.activateConfirmDescription', { title: packageData?.title })
            : t('packageCard.actions.completeConfirmDescription', { title: packageData?.title })}
        </p>
      </Modal>

      {/* Reschedule Modal */}
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

      {/* Delete Package Modal */}
      <Modal
        title={t('pages.finance.deletePackage')}
        open={isDeletePackageModalOpen}
        onOk={confirmDeletePackage}
        onCancel={() => setIsDeletePackageModalOpen(false)}
        okText={t('common.delete')}
        okButtonProps={{ danger: true, loading: deletePackageMutation.isPending }}
      >
        <p>{t('packageDetail.deletePackageConfirm')}</p>
        <p style={{ color: '#8c8c8c' }}>{t('pages.lessons.deleteIrreversible')}</p>
      </Modal>

      {/* Delete Lesson Modal */}
      <Modal
        title={t('pages.lessons.deleteTitle')}
        open={isDeleteLessonModalOpen}
        onOk={confirmDeleteLesson}
        onCancel={() => {
          setIsDeleteLessonModalOpen(false);
          setSelectedLessonId(null);
        }}
        okText={t('common.delete')}
        okButtonProps={{ danger: true, loading: deleteLessonMutation.isPending }}
      >
        <p>{t('pages.lessons.deleteConfirm')}</p>
        <p style={{ color: '#8c8c8c' }}>{t('pages.lessons.deleteIrreversible')}</p>
      </Modal>

      {/* Complete Lesson Modal */}
      <Modal
        title={t('pages.lessons.markCompleted')}
        open={isCompleteLessonModalOpen}
        onOk={confirmComplete}
        onCancel={() => {
          setIsCompleteLessonModalOpen(false);
          setSelectedLessonId(null);
        }}
        okText={t('common.confirm')}
        confirmLoading={updateLessonMutation.isPending}
      >
        <p>{t('pages.lessons.markCompletedConfirm')}</p>
      </Modal>

      {/* Cancel Lesson Modal */}
      <Modal
        title={t('pages.lessons.cancelLesson')}
        open={isCancelLessonModalOpen}
        onOk={confirmCancel}
        onCancel={() => {
          setIsCancelLessonModalOpen(false);
          setSelectedLessonId(null);
        }}
        okText={t('common.yes')}
        okButtonProps={{ danger: true }}
        confirmLoading={updateLessonMutation.isPending}
      >
        <p>{t('pages.lessons.cancelConfirm')}</p>
      </Modal>

      {/* Add Lesson Modal */}
      <LessonForm
        open={isAddLessonModalOpen}
        onCancel={() => {
          setIsAddLessonModalOpen(false);
          setNewLessonDate(null);
        }}
        onFinish={(values) => {
          if (!canUseFullActions) {
            message.warning('Во время льготного периода можно вести существующие уроки и платежи, но нельзя добавлять новые уроки.');
            return;
          }
          createLessonMutation.mutate(values);
        }}
        isLoading={createLessonMutation.isPending}
        mode="create"
        initialValues={newLessonDate ? {
          scheduled_at: dayjs(newLessonDate).hour(10).minute(0),
          duration_minutes: 60,
          timezone: packageData?.timezone || 'Europe/Moscow',
        } : undefined}
      />
    </div>
  );
};

export default PackageDetail;
