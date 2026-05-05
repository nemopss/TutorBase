import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate, Link, useLocation } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Spin,
  Alert,
  Tag,
  Button,
  message,
  Tabs,
  Typography,
  Modal,
  Form,
  InputNumber,
  DatePicker,
  Input,
} from 'antd';
import {
  ArrowLeftOutlined,
  EditOutlined,
  PlusOutlined,
  CalendarOutlined,
  BookOutlined,
  DollarOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { useTranslation } from 'react-i18next';
import api from '../services/api';
import SegmentedProgress from '../components/common/SegmentedProgress';
import CalendarContainer from '../components/common/CalendarContainer';
import PackageForm from '../components/forms/PackageForm';
import RescheduleForm from '../components/forms/RescheduleForm';
import LessonForm from '../components/forms/LessonForm';
import { DetailPageSkeleton } from '../components/common/PageSkeletons';
import TenantContextRequired from '../components/common/TenantContextRequired';
import { formatDate } from '../utils/datetime';
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

const getPaymentStatusColor = (status?: string): string => {
  switch (status) {
    case 'paid': return 'green';
    case 'partial': return 'orange';
    case 'unpaid': return 'red';
    default: return 'default';
  }
};

const getStatusColor = (status: string): string => {
  return status === 'active' ? 'green' : 'volcano';
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
  const isDark = resolvedTheme.colorScheme === 'dark';
  const canUseFullActions = !tenantAccess || tenantAccess.mode === 'full' || tenantAccess.bypass_access_restrictions;
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
      message.success(t('success.created'));
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
      message.success(t('success.deleted'));
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
      message.success(t('success.deleted'));
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
      message.success(t('pages.finance.paymentRecorded'));
      queryClient.invalidateQueries({ queryKey: ['package', id] });
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
    onSuccess: () => {
      message.success(t('success.updated'));
      queryClient.invalidateQueries({ queryKey: ['package', id] });
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      setIsEditModalOpen(false);
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
    updatePackageMutation.mutate({ status: nextStatus });
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
          message.success(t('pages.lessons.lessonRescheduled'));
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
          message.success(t('pages.lessons.lessonCompleted'));
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
          message.success(t('pages.lessons.lessonCancelled'));
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
  const remaining = progress.total - progress.completed - progress.cancelled;

  // Card style for details sections
  const cardStyle: React.CSSProperties = {
    background: isDark ? '#1f1f1f' : '#ffffff',
    borderRadius: 12,
    padding: spacing.md,
    border: `1px solid ${isDark ? '#3a3a3a' : '#f0f0f0'}`,
  };

  const cardHeaderStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  };

  const cardTitleStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: spacing.xs,
  };

  const iconStyle: React.CSSProperties = {
    fontSize: 18,
    color: '#0f7b6c',
  };

  const rowStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: spacing.xs,
    padding: '6px 0',
  };

  // Tab content
  const detailsContent = (
    <div>
      {/* Two-column grid for desktop, single column for mobile */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
        gap: spacing.md,
      }}>
        {/* Dates Card */}
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <div style={cardTitleStyle}>
              <CalendarOutlined style={iconStyle} />
              <Text strong style={{ fontSize: 14, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                {t('pages.finance.dates')}
              </Text>
            </div>
            <Button
              type="text"
              size="small"
              icon={<EditOutlined />}
              disabled={!canUseFullActions}
              onClick={() => setIsEditModalOpen(true)}
            />
          </div>
          <div style={rowStyle}>
            <Text type="secondary">{t('pages.finance.start')}:</Text>
            <Text>{packageData?.start_date ? formatDate(packageData.start_date, { timezone: packageData.timezone }) : '—'}</Text>
          </div>
          <div style={rowStyle}>
            <Text type="secondary">{t('pages.finance.end')}:</Text>
            <Text>{packageData?.end_date ? formatDate(packageData.end_date, { timezone: packageData.timezone }) : '—'}</Text>
          </div>
        </div>

        {/* Lessons Card */}
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <div style={cardTitleStyle}>
              <BookOutlined style={iconStyle} />
              <Text strong style={{ fontSize: 14, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                {t('pages.finance.lessons')}
              </Text>
            </div>
            <Text type="secondary" style={{ fontSize: 13 }}>
              {progress.total} {t('pages.finance.total')}
            </Text>
          </div>
          <div style={rowStyle}>
            <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 16 }} />
            <Text>{progress.completed} {t('pages.finance.completed')}</Text>
          </div>
          <div style={rowStyle}>
            <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 16 }} />
            <Text>{progress.cancelled} {t('pages.finance.cancelled')}</Text>
          </div>
          <div style={rowStyle}>
            <ClockCircleOutlined style={{ color: '#faad14', fontSize: 16 }} />
            <Text>{remaining} {t('pages.finance.remaining')}</Text>
          </div>
        </div>

        {/* Payment Card */}
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <div style={cardTitleStyle}>
              <DollarOutlined style={iconStyle} />
              <Text strong style={{ fontSize: 14, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                {t('pages.finance.payment')}
              </Text>
            </div>
            <Button
              type="primary"
              size="small"
              icon={<PlusOutlined />}
              onClick={openPaymentModal}
              disabled={!packageData?.price}
            >
              {t('pages.finance.add')}
            </Button>
          </div>
          <div style={rowStyle}>
            <Text type="secondary">{t('pages.finance.price')}:</Text>
            <Text strong>{packageData?.price ? formatCurrency(packageData.price) : '—'}</Text>
          </div>
          {packageData?.total_paid !== undefined && packageData.total_paid > 0 && (
            <div style={rowStyle}>
              <Text type="secondary">{t('pages.finance.paid')}:</Text>
              <Text style={{ color: '#52c41a' }}>{formatCurrency(packageData.total_paid)}</Text>
            </div>
          )}
          <div style={{ ...rowStyle, marginTop: 4 }}>
            <Tag color={getPaymentStatusColor(packageData?.payment_status)} style={{ margin: 0 }}>
              {packageData?.payment_status === 'paid' ? t('pages.finance.paid') : 
               packageData?.payment_status === 'partial' ? t('pages.finance.partial') : t('pages.finance.unpaid')}
            </Tag>
          </div>
        </div>

        {/* Notes Card */}
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <div style={cardTitleStyle}>
              <FileTextOutlined style={iconStyle} />
              <Text strong style={{ fontSize: 14, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                {t('pages.finance.notes')}
              </Text>
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
      </div>

      {/* Delete link */}
      <div style={{ textAlign: 'center', marginTop: spacing.lg }}>
        <Button
          type="link"
          danger
          style={{ fontSize: 12 }}
          disabled={!canUseFullActions}
          onClick={() => setIsDeletePackageModalOpen(true)}
        >
          {t('pages.finance.deletePackage')}
        </Button>
      </div>
    </div>
  );

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

  const lessonsContent = (
    <div>
      {isLoadingLessons ? (
        <Spin />
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
        />
      )}
    </div>
  );

  const tabItems = [
    { key: 'lessons', label: t('navigation.lessons'), children: lessonsContent },
    { key: 'details', label: t('packageDetail.details'), children: detailsContent },
  ];

  return (
    <div>
      {!canUseFullActions && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: spacing.md }}
          message="Доступ ограничен льготным периодом"
          description="Можно переносить, завершать и отменять существующие уроки, а также корректировать платежи. Новые уроки, удаление и редактирование пакета доступны после разблокировки кабинета."
        />
      )}

      {/* Header */}
      <div
        style={{
          display: 'flex',
          flexDirection: isMobile ? 'column' : 'row',
          alignItems: isMobile ? 'stretch' : 'center',
          gap: spacing.md,
          marginBottom: isMobile ? spacing.md : spacing.lg,
        }}
      >
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: spacing.sm,
          flexWrap: 'wrap',
        }}>
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/packages')}>
            {t('common.back')}
          </Button>
          <SegmentedProgress
            total={progress.total}
            completed={progress.completed}
            cancelled={progress.cancelled}
            size={80}
          />
        </div>
        <div style={{ flex: 1, minWidth: 200 }}>
          <Title level={4} style={{ margin: 0 }}>
            {packageData?.title}
          </Title>
          <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm, flexWrap: 'wrap' }}>
            <Link to={`/learners/${packageData?.learner_id}`}>
              <Text type="secondary" style={{ textDecoration: 'underline' }}>
                {packageData?.learner_name}
              </Text>
            </Link>
            <Text type="secondary">•</Text>
            <Tag color={getStatusColor(packageData?.status || '')}>
              {packageData?.status?.toUpperCase()}
            </Tag>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <Tabs items={tabItems} defaultActiveKey="lessons" />

      {/* Payment Modal */}
      <Modal
        title={t('pages.finance.recordPayment')}
        open={isPaymentModalOpen}
        onOk={() => paymentForm.validateFields().then((values) => createPaymentMutation.mutate(values))}
        onCancel={() => setIsPaymentModalOpen(false)}
        confirmLoading={createPaymentMutation.isPending}
        okText={t('common.add')}
        cancelText={t('common.cancel')}
      >
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
