import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Tag, Select, Space, Input, Button, message, Modal, Form, Switch, Alert } from 'antd';
import type { TableProps } from 'antd';
import type { FormInstance } from 'antd/es/form';
import { EditOutlined, ClockCircleOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { useTranslation } from 'react-i18next';
import api from '../services/api';
import { appEnv } from '../env';
import { useDebounce } from '../hooks/useDebounce';
import PageHeader from '../components/common/PageHeader';
import ResponsiveDataView from '../components/common/ResponsiveDataView';
import ReminderCard from '../components/cards/ReminderCard';
import TenantContextRequired from '../components/common/TenantContextRequired';
import { useAuth } from '../auth/AuthProvider';

// --- Types --- //
interface Reminder {
  id: number;
  package_id: number;
  lesson_id?: number;
  reminder_type?: string;
  scheduled_for: string;
  status: string;
  active: boolean;
  payload: Record<string, any>;
  comment?: string;
  last_notified_at?: string;
  last_response?: string;
  last_response_at?: string;
  last_decline_reason?: string;
}

interface ReminderListResponse {
  total: number;
  items: Reminder[];
}

interface Package {
  id: number;
  title: string;
  learner_name: string;
}

interface PackageListResponse {
  total: number;
  items: Package[];
}

// Status and type options will be generated with translations in component

// --- API Fetchers --- //
const fetchReminders = async (page: number, pageSize: number, status: string | null, type: string | null, packageId: number | null, search: string): Promise<ReminderListResponse> => {
  const params: any = {
    offset: (page - 1) * pageSize,
    limit: pageSize,
    status: status || undefined,
    reminder_type: type || undefined,
    search: search || undefined,
  };

  // If package filter is selected, fetch reminders for that package
  if (packageId) {
    const { data } = await api.get(`/reminders/packages/${packageId}`, { params });
    return data;
  }

  // Otherwise, use the general reminders endpoint
  const { data } = await api.get('/reminders', { params });
  return data;
};

const fetchPackages = async (): Promise<PackageListResponse> => {
  // Fetch all packages with pagination (max 100 per request)
  let allItems: Package[] = [];
  let offset = 0;
  const limit = 100;
  let hasMore = true;
  
  while (hasMore) {
    const { data } = await api.get('/packages', { params: { limit, offset } });
    allItems = [...allItems, ...data.items];
    hasMore = data.has_more;
    offset += limit;
    
    // Safety limit to prevent infinite loops
    if (offset > 10000) break;
  }
  
  return { items: allItems, total: allItems.length };
};

const updateReminder = async ({ id, values }: { id: number; values: any }) => {
  const { data } = await api.patch(`/reminders/${id}`, values);
  return data;
};

// --- Component --- //
const Reminders: React.FC = () => {
  const { t } = useTranslation();
  const { tenantId } = useAuth();
  const requiresTenantContext = tenantId === null;
  const queryClient = useQueryClient();

  // Status options with translations
  const STATUS_OPTIONS = [
    { value: 'scheduled', label: t('pages.reminders.status.scheduled') },
    { value: 'sent', label: t('pages.reminders.status.sent') },
    { value: 'responded', label: t('pages.reminders.status.responded') },
    { value: 'failed', label: t('pages.reminders.status.failed') },
    { value: 'cancelled', label: t('pages.reminders.status.cancelled') },
  ];

  // Reminder type options with translations
  const REMINDER_TYPE_OPTIONS = [
    { value: 'lesson_confirm', label: t('pages.reminders.types.lesson_confirm') },
    { value: 'lesson_day_before', label: t('pages.reminders.types.lesson_day_before') },
    { value: 'payment_week', label: t('pages.reminders.types.payment_week') },
    { value: 'payment_day', label: t('pages.reminders.types.payment_day') },
    { value: 'homework', label: t('pages.reminders.types.homework') },
    { value: 'package_renewal', label: t('pages.reminders.types.package_renewal') },
  ];
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<string | null>(null);
  const [packageFilter, setPackageFilter] = useState<number | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingReminder, setEditingReminder] = useState<Reminder | null>(null);
  const [form] = Form.useForm();

  const debouncedSearchTerm = useDebounce(searchTerm, 500);

  const { data, isLoading, isError, error } = useQuery<ReminderListResponse, Error>({
    queryKey: ['reminders', currentPage, pageSize, statusFilter, typeFilter, packageFilter, debouncedSearchTerm],
    queryFn: () => fetchReminders(currentPage, pageSize, statusFilter, typeFilter, packageFilter, debouncedSearchTerm),
    placeholderData: (previousData) => previousData,
    enabled: !requiresTenantContext,
  });

  const { data: packagesData } = useQuery<PackageListResponse, Error>({
    queryKey: ['packagesForReminders'],
    queryFn: fetchPackages,
    enabled: !requiresTenantContext,
  });

  const updateMutation = useMutation({
    mutationFn: updateReminder,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reminders'] });
      setIsModalOpen(false);
      setEditingReminder(null);
      message.success(t('pages.reminders.reminderUpdated'));
    },
    onError: (error: Error) => {
      message.error(t('errors.updateFailed', { message: error.message }));
    }
  });

  const handleFormFinish = (values: any) => {
    if (editingReminder) {
      updateMutation.mutate({ id: editingReminder.id, values });
    }
  };

  const handleCancel = () => {
    setIsModalOpen(false);
    setEditingReminder(null);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'scheduled': return 'default';
      case 'sent': return 'processing';
      case 'responded': return 'success';
      case 'failed': return 'error';
      case 'cancelled': return 'warning';
      default: return 'default';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'scheduled': return <ClockCircleOutlined />;
      case 'sent': return <ClockCircleOutlined />;
      case 'responded': return <CheckCircleOutlined />;
      case 'failed': return <CloseCircleOutlined />;
      case 'cancelled': return <CloseCircleOutlined />;
      default: return null;
    }
  };

  const columns: TableProps<Reminder>['columns'] = [
    {
      title: t('pages.reminders.scheduledFor'),
      dataIndex: 'scheduled_for',
      key: 'scheduled_for',
      render: (text: string) => dayjs(text).format('YYYY-MM-DD HH:mm'),
      sorter: (a, b) => dayjs(a.scheduled_for).unix() - dayjs(b.scheduled_for).unix(),
    },
    {
      title: t('pages.reminders.package'),
      key: 'package',
      render: (_, record) => {
        const packageInfo = packagesData?.items.find(p => p.id === record.package_id);
        return packageInfo ? `${packageInfo.title} (${packageInfo.learner_name})` : `${t('pages.reminders.package')} ${record.package_id}`;
      },
    },
    {
      title: t('pages.reminders.type'),
      dataIndex: 'reminder_type',
      key: 'reminder_type',
      render: (type: string) => type ? <Tag>{t(`pages.reminders.types.${type}`)}</Tag> : '-',
    },
    {
      title: t('common.status'),
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={getStatusColor(status)} icon={getStatusIcon(status)}>
          {t(`pages.reminders.status.${status}`)}
        </Tag>
      ),
      filters: STATUS_OPTIONS.map(option => ({ text: option.label, value: option.value })),
      onFilter: (value, record) => record.status === value,
    },
    {
      title: t('pages.reminders.active'),
      dataIndex: 'active',
      key: 'active',
      render: (active: boolean) => <Tag color={active ? 'green' : 'red'}>{active ? t('common.yes') : t('common.no')}</Tag>,
      filters: [
        { text: t('pages.reminders.active'), value: true },
        { text: t('pages.reminders.inactive'), value: false },
      ],
      onFilter: (value, record) => record.active === value,
    },
    {
      title: t('pages.reminders.lastResponse'),
      dataIndex: 'last_response',
      key: 'last_response',
      render: (response: string) => response || '-',
    },
    {
      title: t('common.actions'),
      key: 'actions',
      render: (_, record) => (
        <Button 
          type="link" 
          icon={<EditOutlined />}
          onClick={(e) => { 
            e.stopPropagation(); 
            setEditingReminder(record); 
            setIsModalOpen(true); 
          }}
        >
          {t('common.edit')}
        </Button>
      ),
    },
  ];

  if (requiresTenantContext) {
    return (
      <div>
        <PageHeader
          title={t('pages.reminders.title')}
          subtitle={t('pages.reminders.subtitle')}
        />
        <TenantContextRequired sectionLabel={t('pages.reminders.title')} />
      </div>
    );
  }

  const handleTableChange = (pagination: any, _filters: any) => {
    setCurrentPage(pagination.current);
    setPageSize(pagination.pageSize);
  };

  if (isError) {
    return <Alert message={t('errors.loadFailed', { message: '' })} description={error.message} type="error" />;
  }

  return (
    <div>
      <PageHeader 
        title={t('pages.reminders.title')}
        subtitle={t('pages.reminders.subtitle')}
        actions={<Tag color="warning">{t('navigation.legacyBadge')}</Tag>}
      />
      <Alert
        type="warning"
        showIcon
        message={t('pages.reminders.legacyNoticeTitle')}
        description={t('pages.reminders.legacyNoticeDescription')}
        style={{ marginBottom: 16 }}
      />
      
      <Space style={{ marginBottom: 16 }} wrap>
        <Input.Search
          allowClear
          onSearch={(value) => {
            setSearchTerm(value);
            setCurrentPage(1);
          }}
          onChange={(e) => {
            setSearchTerm(e.target.value);
            setCurrentPage(1);
          }}
          style={{ width: 300 }}
        />
        <Select
          placeholder={t('pages.reminders.filterByStatus')}
          allowClear
          style={{ width: 200 }}
          options={STATUS_OPTIONS}
          onChange={(value) => {
            setStatusFilter(value);
            setCurrentPage(1);
          }}
        />
        <Select
          placeholder={t('pages.reminders.filterByType')}
          allowClear
          style={{ width: 200 }}
          options={REMINDER_TYPE_OPTIONS}
          onChange={(value) => {
            setTypeFilter(value);
            setCurrentPage(1);
          }}
        />
        <Select
          placeholder={t('pages.reminders.filterByPackage')}
          allowClear
          style={{ width: 250 }}
          showSearch
          optionFilterProp="children"
          filterOption={(input, option) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())}
          options={packagesData?.items.map(pkg => ({ 
            value: pkg.id, 
            label: `${pkg.title} (${pkg.learner_name})` 
          }))}
          onChange={(value) => {
            setPackageFilter(value);
            setCurrentPage(1);
          }}
        />
      </Space>

      <ResponsiveDataView<Reminder>
        data={data?.items || []}
        loading={isLoading}
        columns={columns}
        rowKey="id"
        emptyText={t('pages.reminders.noReminders')}
        emptyDescription={t('pages.reminders.noRemindersDescription')}
        renderCard={(reminder) => (
          <ReminderCard
            key={reminder.id}
            reminder={reminder}
            packageInfo={packagesData?.items.find(p => p.id === reminder.package_id)}
            onEdit={(r) => {
              setEditingReminder(r as Reminder);
              setIsModalOpen(true);
            }}
          />
        )}
        tableProps={{
          onChange: handleTableChange,
          bordered: true,
          scroll: { x: 1200 },
        }}
        pagination={{
          current: currentPage,
          pageSize: pageSize,
          total: data?.total,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total, range) => t('pages.reminders.showTotal', { start: range[0], end: range[1], total }),
        }}
      />

      <Modal
        open={isModalOpen}
        title={t('pages.reminders.editReminder')}
        cancelText={t('common.cancel')}
        onCancel={handleCancel}
        onOk={() => form.submit()}
        confirmLoading={updateMutation.isPending}
        destroyOnHidden
      >
        <ReminderEditForm
          reminder={editingReminder}
          onFinish={handleFormFinish}
          isLoading={updateMutation.isPending}
          form={form}
        />
      </Modal>
    </div>
  );
};

// --- Reminder Edit Form Component --- //
interface ReminderEditFormProps {
  reminder: Reminder | null;
  onFinish: (values: any) => void;
  isLoading: boolean;
  form: FormInstance;
}

const ReminderEditForm: React.FC<ReminderEditFormProps> = ({ reminder, onFinish, isLoading, form }) => {
  const { t } = useTranslation();
  
  // Status options with translations
  const STATUS_OPTIONS = [
    { value: 'scheduled', label: t('pages.reminders.status.scheduled') },
    { value: 'sent', label: t('pages.reminders.status.sent') },
    { value: 'responded', label: t('pages.reminders.status.responded') },
    { value: 'failed', label: t('pages.reminders.status.failed') },
    { value: 'cancelled', label: t('pages.reminders.status.cancelled') },
  ];

  React.useEffect(() => {
    if (reminder) {
      form.setFieldsValue({
        status: reminder.status,
        active: reminder.active,
        comment: reminder.comment,
      });
    } else {
      form.resetFields();
    }
  }, [form, reminder]);

  return (
    <Form
      form={form}
      layout="vertical"
      name="reminder_edit_form"
      onFinish={onFinish}
      onFinishFailed={(info) => {
        if (appEnv.isDev) {
          console.log('Validate Failed:', info);
        }
      }}    >
      <Form.Item
        name="status"
        label={t('common.status')}
        rules={[{ required: true, message: t('common.required') }]}
      >
        <Select options={STATUS_OPTIONS} disabled={isLoading} />
      </Form.Item>
      
      <Form.Item
        name="active"
        label={t('pages.reminders.active')}
        valuePropName="checked"
      >
        <Switch disabled={isLoading} />
      </Form.Item>
      
      <Form.Item
        name="comment"
        label={t('pages.reminders.comment')}
      >
        <Input.TextArea rows={3} placeholder={t('pages.reminders.addComment')} disabled={isLoading} />
      </Form.Item>
    </Form>
  );
};

export default Reminders;
