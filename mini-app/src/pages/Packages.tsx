import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Tabs, message, Alert, notification, Button, Modal, Form, InputNumber, DatePicker, Input, Typography, Space } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import api from '../services/api';
import PackageForm from '../components/forms/PackageForm';
import type { PackageSubmitValues } from '../components/forms/PackageForm';
import PageHeader from '../components/common/PageHeader';
import PackageCard from '../components/cards/PackageCard';
import type { PackageCardAction } from '../components/cards/PackageCard';
import PackageGrid from '../components/common/PackageGrid';
import FloatingActionButton from '../components/common/FloatingActionButton';
import TenantContextRequired from '../components/common/TenantContextRequired';
import EmptyState from '../components/common/EmptyState';
import { spacing } from '../theme/tokens';
import { useAuth } from '../auth/AuthProvider';
import { useResponsive } from '../hooks/useResponsive';
import dayjs from 'dayjs';

const { Text } = Typography;

// --- Types --- //
interface PackageProgress {
  total: number;
  completed: number;
  cancelled: number;
}

interface Package {
  id: number;
  learner_id?: number;
  learner?: { id: number; display_name: string };
  notes?: string;
  learner_name: string;
  title: string;
  status: 'active' | 'completed' | 'cancelled' | 'draft';
  start_date?: string;
  end_date?: string;
  timezone?: string;
  total_lessons?: number;
  progress: PackageProgress;
  template_id?: number | null;
  price?: number | null;
  payment_status?: string;
  total_paid?: number;
  created_at?: string;
  next_lesson_date?: string | null;
}

interface PackageListResponse {
  total: number;
  items: Package[];
}

type PackageStatus = 'active' | 'completed' | 'draft' | 'cancelled';

// --- API Fetchers --- //
const fetchPackages = async (status: string): Promise<PackageListResponse> => {
  const { data } = await api.get('/packages', {
    params: {
      status_filter: status,
      limit: 100,
    },
  });
  return data;
};

interface PaymentFormValues {
  amount: number;
  paid_at: dayjs.Dayjs;
  notes?: string;
}

const createPackage = async (values: PackageSubmitValues) => {
  const { _creation_kind: creationKind, ...payload } = values;
  const { data } = await api.post(
    creationKind === 'one_off' ? '/packages/one-off' : '/packages',
    payload,
  );
  return data;
};

// --- Component --- //
const Packages: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isMobile } = useResponsive();
  const { tenantAccess, tenantId } = useAuth();
  const [notificationApi, notificationContextHolder] = notification.useNotification();
  const requiresTenantContext = tenantId === null;
  const canUseFullActions = !tenantAccess || tenantAccess.mode === 'full' || tenantAccess.bypass_access_restrictions;
  const [activeTab, setActiveTab] = useState<PackageStatus>('active');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [paymentForm] = Form.useForm();
  const [paymentPackage, setPaymentPackage] = useState<Package | null>(null);
  const [statusActionPackage, setStatusActionPackage] = useState<{ package: Package; status: 'active' | 'completed' } | null>(null);

  const { data, isLoading, error, isError } = useQuery<PackageListResponse, Error>({
    queryKey: ['packages', activeTab],
    queryFn: () => fetchPackages(activeTab),
    enabled: !requiresTenantContext,
  });

  const packagesData = useMemo(() => data?.items ?? [], [data?.items]);

  // Sort by creation date (newest first)
  const sortedPackages = useMemo(() => {
    return [...packagesData].sort((a, b) => {
      const dateA = a.created_at ? new Date(a.created_at).getTime() : 0;
      const dateB = b.created_at ? new Date(b.created_at).getTime() : 0;
      return dateB - dateA;
    });
  }, [packagesData]);

  const createMutation = useMutation({
    mutationFn: createPackage,
    onSuccess: (createdPackage, variables) => {
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
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      setIsModalOpen(false);
    },
    onError: (error: Error) => {
      message.error(t('errors.createFailed', { message: error.message }));
    },
  });

  const createPaymentMutation = useMutation({
    mutationFn: async (values: PaymentFormValues) => {
      if (!paymentPackage?.learner_id) {
        throw new Error(t('errors.notFound'));
      }
      const { data } = await api.post('/payments', {
        learner_id: paymentPackage.learner_id,
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
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      queryClient.invalidateQueries({ queryKey: ['package', paymentPackage?.id?.toString()] });
      setPaymentPackage(null);
      paymentForm.resetFields();
    },
    onError: (error: Error) => {
      message.error(t('errors.saveFailed', { message: error.message }));
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
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      queryClient.invalidateQueries({ queryKey: ['package', variables.packageId.toString()] });
      setStatusActionPackage(null);
    },
    onError: (error: Error) => {
      message.error(t('errors.updateFailed', { message: error.message }));
    },
  });

  const handleFormFinish = (values: PackageSubmitValues) => {
    if (!canUseFullActions) {
      message.warning('Создание пакетов недоступно в grace-периоде.');
      return;
    }
    createMutation.mutate(values);
  };

  const hasPackages = sortedPackages.length > 0;

  const tabItems = [
    { key: 'active', label: t('pages.packages.status.active') },
    { key: 'completed', label: t('pages.packages.status.completed') },
    { key: 'draft', label: t('pages.packages.status.draft') },
    { key: 'cancelled', label: t('pages.packages.status.cancelled') },
  ];

  const openCreatePackage = () => {
    if (canUseFullActions) {
      setIsModalOpen(true);
    }
  };

  const handlePackageAction = (action: PackageCardAction, pkg: Package) => {
    if (action === 'payment') {
      const price = Number(pkg.price || 0);
      const totalPaid = Number(pkg.total_paid || 0);
      const remaining = Math.max(0, price - totalPaid);
      paymentForm.setFieldsValue({
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

  if (requiresTenantContext) {
    return (
      <div>
        {notificationContextHolder}
        <PageHeader
          title={t('pages.packages.title')}
          subtitle={t('pages.packages.subtitle')}
        />
        <TenantContextRequired sectionLabel={t('pages.packages.title')} />
      </div>
    );
  }

  return (
    <div>
      {notificationContextHolder}
      <PageHeader
        title={t('pages.packages.title')}
        subtitle={t('pages.packages.subtitle')}
        actions={!isMobile && canUseFullActions ? (
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreatePackage}>
            {t('pages.packages.addPackage')}
          </Button>
        ) : undefined}
      />

      {!canUseFullActions && (
        <Alert
          message="Grace-период"
          description="Создание новых пакетов временно недоступно. Можно переносить существующие уроки и корректировать платежи."
          type="warning"
          showIcon
          style={{ marginBottom: spacing.md }}
        />
      )}

      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as PackageStatus)}
        items={tabItems}
        style={{ marginBottom: spacing.md }}
      />

      {isError && (
        <Alert
          message={t('errors.loadFailed', { message: '' })}
          description={error?.message || t('common.error')}
          type="error"
          showIcon
          style={{ marginBottom: spacing.md }}
        />
      )}

      {!hasPackages && !isLoading ? (
        <EmptyState
          title={t('pages.packages.noPackages')}
          description={t('pages.packages.noPackagesDescription')}
          actionText={canUseFullActions ? t('pages.packages.addPackage') : undefined}
          onAction={canUseFullActions ? openCreatePackage : undefined}
        />
      ) : (
        <PackageGrid loading={isLoading}>
          {sortedPackages.map((pkg) => (
            <PackageCard
              key={pkg.id}
              package={pkg}
              onClick={() => navigate(`/packages/${pkg.id}`)}
              onAction={handlePackageAction}
            />
          ))}
        </PackageGrid>
      )}

      {hasPackages && canUseFullActions && isMobile && (
        <FloatingActionButton
          icon={<PlusOutlined />}
          onClick={() => setIsModalOpen(true)}
        />
      )}

      <PackageForm
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        onFinish={handleFormFinish}
        isLoading={createMutation.isPending}
      />

      <Modal
        open={!!paymentPackage}
        title={t('pages.finance.recordPayment')}
        onCancel={() => {
          setPaymentPackage(null);
          paymentForm.resetFields();
        }}
        onOk={() => paymentForm.validateFields().then((values) => createPaymentMutation.mutate(values))}
        okText={t('pages.finance.recordPayment')}
        cancelText={t('common.cancel')}
        confirmLoading={createPaymentMutation.isPending}
      >
        {paymentPackage && (
          <Space direction="vertical" size={spacing.md} style={{ width: '100%' }}>
            <div>
              <Text strong>{paymentPackage.title}</Text>
              <div>
                <Text type="secondary">
                  {t('pages.finance.price')}: {paymentPackage.price ? new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 }).format(Number(paymentPackage.price)) : '—'}
                </Text>
              </div>
              <div>
                <Text type="secondary">
                  {t('pages.finance.outstanding')}: {new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 }).format(Math.max(0, Number(paymentPackage.price || 0) - Number(paymentPackage.total_paid || 0)))}
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
    </div>
  );
};

export default Packages;
