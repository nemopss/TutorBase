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
  Dropdown,
  Input,
} from 'antd';
import {
  ArrowLeftOutlined,
  EditOutlined,
  DeleteOutlined,
  MoreOutlined,
  BellOutlined,
  CalendarOutlined,
  PlusOutlined,
  DollarOutlined,
  DisconnectOutlined,
  LinkOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { useTranslation } from 'react-i18next';
import api from '../services/api';
import PageHeader from '../components/common/PageHeader';
import LearnerForm from '../components/forms/LearnerForm';
import PackageCard from '../components/cards/PackageCard';
import PackageForm from '../components/forms/PackageForm';
import EmptyState from '../components/common/EmptyState';
import ScheduleTab from '../components/learner/ScheduleTab';
import { useTheme } from '../theme/ThemeProvider';
import { spacing } from '../theme/tokens';

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
}

interface Package {
  id: number;
  title: string;
  learner_name: string;
  status: 'active' | 'completed' | 'cancelled' | 'draft';
  progress: { total: number; completed: number; cancelled: number };
  next_lesson_date?: string | null;
}

interface Payment {
  id: number;
  amount: number;
  paid_at: string;
  notes: string | null;
  package_title: string | null;
}

interface LearnerFinance {
  total_paid: number;
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

// --- Component --- //
const LearnerProfile: React.FC = () => {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { resolvedTheme } = useTheme();
  const colors = resolvedTheme.colors;
  
  const learnerId = parseInt(id || '0');
  
  // State
  const [activeTab, setActiveTab] = useState('overview');
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isPackageModalOpen, setIsPackageModalOpen] = useState(false);

  // Fetch learner detail
  const { data: learner, isLoading, isError, error } = useQuery<LearnerDetail, Error>({
    queryKey: ['learnerDetail', learnerId],
    queryFn: async () => {
      const { data } = await api.get(`/learners/${learnerId}`);
      return data;
    },
    enabled: !!learnerId,
  });

  // Fetch packages
  const { data: packagesData } = useQuery<{ items: Package[] }>({
    queryKey: ['learnerPackages', learnerId],
    queryFn: async () => {
      const { data } = await api.get('/packages', { params: { learner_id: learnerId } });
      return data;
    },
    enabled: !!learnerId,
  });

  // Fetch finance
  const { data: finance } = useQuery<LearnerFinance>({
    queryKey: ['learnerFinance', learnerId],
    queryFn: async () => {
      const { data } = await api.get(`/learners/${learnerId}/finance`);
      return data;
    },
    enabled: !!learnerId,
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
    },
    onError: (err: Error) => {
      message.error(t('errors.updateFailed', { message: err.message }));
    },
  });

  const createInviteMutation = useMutation({
    mutationFn: async () => {
      const { data } = await api.post(`/learners/${learnerId}/invite`);
      return data as { token: string };
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['learnerDetail', learnerId] });
      Modal.success({
        title: t('learnerProfile.inviteCreatedTitle'),
        content: (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Text>{t('learnerProfile.inviteCreatedDescription')}</Text>
            <Input.TextArea value={data.token} readOnly autoSize />
            <Button
              onClick={() => {
                navigator.clipboard?.writeText(data.token);
                message.success(t('common.copied'));
              }}
            >
              {t('common.copy')}
            </Button>
          </Space>
        ),
      });
    },
    onError: (err: Error) => {
      message.error(t('errors.createFailed', { message: err.message }));
    },
  });

  // Delete learner mutation
  const deleteMutation = useMutation({
    mutationFn: async () => {
      await api.delete(`/learners/${learnerId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learners'] });
      message.success(t('pages.learners.deleteSuccess'));
      navigate('/learners');
    },
    onError: (err: Error) => {
      message.error(t('errors.deleteFailed', { message: err.message }));
    },
  });

  // Create package mutation
  const createPackageMutation = useMutation({
    mutationFn: async (values: any) => {
      const { data } = await api.post('/packages', values);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learnerPackages', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      message.success(t('success.created'));
      setIsPackageModalOpen(false);
    },
    onError: (err: Error) => {
      message.error(t('errors.createFailed', { message: err.message }));
    },
  });

  const handleEditSubmit = async (values: any) => {
    await updateMutation.mutateAsync({
      display_name: values.display_name,
      notes: values.notes,
      lesson_rate: values.lesson_rate,
    });
  };

  const handleUnlinkAccount = () => {
    Modal.confirm({
      title: t('learnerProfile.unlinkAccountTitle'),
      content: t('learnerProfile.unlinkAccountConfirm'),
      okText: t('learnerProfile.unlinkAccountAction'),
      cancelText: t('common.cancel'),
      okButtonProps: { danger: true, loading: unlinkAccountMutation.isPending },
      onOk: () => unlinkAccountMutation.mutateAsync(),
    });
  };

  const menuItems = [
    {
      key: 'delete',
      label: t('common.delete'),
      icon: <DeleteOutlined />,
      danger: true,
      onClick: () => setIsDeleteModalOpen(true),
    },
  ];

  if (isLoading) {
    return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  }

  if (isError || !learner) {
    return <Alert message={t('errors.loadFailed', { message: error?.message || '' })} type="error" />;
  }

  const packages = packagesData?.items || [];
  const payments = finance?.payment_history || [];

  const cardStyle = {
    background: colors.bgSecondary,
    borderColor: colors.borderPrimary,
    marginBottom: spacing.md,
  };

  return (
    <div>
      <PageHeader
        title={learner.display_name}
        actions={
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/learners')}>
              {t('common.back')}
            </Button>
            <Button icon={<EditOutlined />} onClick={() => setIsEditModalOpen(true)}>
              {t('common.edit')}
            </Button>
            <Dropdown menu={{ items: menuItems }} trigger={['click']}>
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
                            onClick={() => createInviteMutation.mutate()}
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
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => setIsPackageModalOpen(true)}
                  style={{ marginBottom: spacing.md }}
                >
                  {t('learnerProfile.createPackage')}
                </Button>

                {packages.length === 0 ? (
                  <EmptyState
                    title={t('pages.packages.noPackages')}
                    description={t('pages.packages.noPackagesDescription')}
                    actionText={t('learnerProfile.createPackage')}
                    onAction={() => setIsPackageModalOpen(true)}
                  />
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: spacing.md }}>
                    {packages.map((pkg) => (
                      <PackageCard
                        key={pkg.id}
                        package={pkg}
                        onClick={() => navigate(`/packages/${pkg.id}`)}
                      />
                    ))}
                  </div>
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

                {/* Record Payment Button */}
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => navigate(`/learners/${learnerId}/finance`)}
                  style={{ marginBottom: spacing.md }}
                >
                  {t('pages.finance.recordPayment')}
                </Button>

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

      {/* Delete Confirmation Modal */}
      <Modal
        open={isDeleteModalOpen}
        title={t('pages.learners.deleteTitle')}
        onCancel={() => setIsDeleteModalOpen(false)}
        onOk={() => deleteMutation.mutate()}
        okText={t('common.delete')}
        cancelText={t('common.cancel')}
        okButtonProps={{ danger: true, loading: deleteMutation.isPending }}
      >
        <p>{t('pages.learners.deleteConfirm', { name: learner.display_name })}</p>
        <p style={{ color: '#ff4d4f' }}>{t('pages.learners.deleteWarning')}</p>
        <p style={{ color: '#8c8c8c' }}>{t('pages.learners.deleteIrreversible')}</p>
      </Modal>

      {/* Create Package Modal */}
      <PackageForm
        visible={isPackageModalOpen}
        onSubmit={createPackageMutation.mutateAsync}
        onCancel={() => setIsPackageModalOpen(false)}
        loading={createPackageMutation.isPending}
        mode="create"
        preselectedLearnerId={learnerId}
      />
    </div>
  );
};

export default LearnerProfile;
