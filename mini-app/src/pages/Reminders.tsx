import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Table, Tag, Select, Space, Input, Button, message, Modal, Form, Switch, Alert } from 'antd';
import type { TableProps } from 'antd';
import { EditOutlined, ClockCircleOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import api from '../services/api';
import { useDebounce } from '../hooks/useDebounce';
import PageHeader from '../components/common/PageHeader';

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

const STATUS_OPTIONS = [
  { value: 'scheduled', label: 'Scheduled' },
  { value: 'sent', label: 'Sent' },
  { value: 'responded', label: 'Responded' },
  { value: 'failed', label: 'Failed' },
  { value: 'cancelled', label: 'Cancelled' },
];

// Reminder type options based on actual system types
const REMINDER_TYPE_OPTIONS = [
  { value: 'lesson_confirm', label: 'Lesson Confirmation' },
  { value: 'lesson_day_before', label: 'Lesson Day Before' },
  { value: 'payment_week', label: 'Payment Week' },
  { value: 'payment_day', label: 'Payment Day' },
  { value: 'homework', label: 'Homework' },
  { value: 'package_renewal', label: 'Package Renewal' },
];

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
  const { data } = await api.get('/packages', { params: { limit: 1000 } });
  return data;
};

const updateReminder = async ({ id, values }: { id: number; values: any }) => {
  const { data } = await api.patch(`/reminders/${id}`, values);
  return data;
};

// --- Component --- //
const Reminders: React.FC = () => {
  const queryClient = useQueryClient();
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<string | null>(null);
  const [packageFilter, setPackageFilter] = useState<number | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingReminder, setEditingReminder] = useState<Reminder | null>(null);

  const debouncedSearchTerm = useDebounce(searchTerm, 500);

  const { data, isLoading, isError, error } = useQuery<ReminderListResponse, Error>({
    queryKey: ['reminders', currentPage, pageSize, statusFilter, typeFilter, packageFilter, debouncedSearchTerm],
    queryFn: () => fetchReminders(currentPage, pageSize, statusFilter, typeFilter, packageFilter, debouncedSearchTerm),
    placeholderData: (previousData) => previousData,
  });

  const { data: packagesData } = useQuery<PackageListResponse, Error>({
    queryKey: ['packagesForReminders'],
    queryFn: fetchPackages,
  });

  const updateMutation = useMutation({
    mutationFn: updateReminder,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reminders'] });
      setIsModalOpen(false);
      setEditingReminder(null);
      message.success('Reminder updated successfully!');
    },
    onError: (error: Error) => {
      message.error(`An error occurred: ${error.message}`);
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
      title: 'Scheduled For',
      dataIndex: 'scheduled_for',
      key: 'scheduled_for',
      render: (text: string) => dayjs(text).format('YYYY-MM-DD HH:mm'),
      sorter: (a, b) => dayjs(a.scheduled_for).unix() - dayjs(b.scheduled_for).unix(),
    },
    {
      title: 'Package',
      key: 'package',
      render: (_, record) => {
        const packageInfo = packagesData?.items.find(p => p.id === record.package_id);
        return packageInfo ? `${packageInfo.title} (${packageInfo.learner_name})` : `Package ${record.package_id}`;
      },
    },
    {
      title: 'Type',
      dataIndex: 'reminder_type',
      key: 'reminder_type',
      render: (type: string) => type ? <Tag>{type.replace('_', ' ').toUpperCase()}</Tag> : '-',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={getStatusColor(status)} icon={getStatusIcon(status)}>
          {status.toUpperCase()}
        </Tag>
      ),
      filters: STATUS_OPTIONS.map(option => ({ text: option.label, value: option.value })),
      onFilter: (value, record) => record.status === value,
    },
    {
      title: 'Active',
      dataIndex: 'active',
      key: 'active',
      render: (active: boolean) => <Tag color={active ? 'green' : 'red'}>{active ? 'YES' : 'NO'}</Tag>,
      filters: [
        { text: 'Active', value: true },
        { text: 'Inactive', value: false },
      ],
      onFilter: (value, record) => record.active === value,
    },
    {
      title: 'Last Response',
      dataIndex: 'last_response',
      key: 'last_response',
      render: (response: string) => response || '-',
    },
    {
      title: 'Actions',
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
          Edit
        </Button>
      ),
    },
  ];

  const handleTableChange = (pagination: any, _filters: any) => {
    setCurrentPage(pagination.current);
    setPageSize(pagination.pageSize);
  };

  if (isError) {
    return <Alert message="Error fetching reminders" description={error.message} type="error" />;
  }

  return (
    <div>
      <PageHeader 
        title="Reminders"
        subtitle="Manage automated reminders for lessons and payments"
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
          placeholder="Filter by status"
          allowClear
          style={{ width: 200 }}
          options={STATUS_OPTIONS}
          onChange={(value) => {
            setStatusFilter(value);
            setCurrentPage(1);
          }}
        />
        <Select
          placeholder="Filter by type"
          allowClear
          style={{ width: 200 }}
          options={REMINDER_TYPE_OPTIONS}
          onChange={(value) => {
            setTypeFilter(value);
            setCurrentPage(1);
          }}
        />
        <Select
          placeholder="Filter by package"
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

      <Table
        columns={columns}
        dataSource={data?.items}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current: currentPage,
          pageSize: pageSize,
          total: data?.total,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total, range) => `${range[0]}-${range[1]} of ${total} reminders`,
        }}
        onChange={handleTableChange}
        bordered
        scroll={{ x: 1200 }}
      />

      <Modal
        open={isModalOpen}
        title="Edit Reminder"
        okText="Save"
        cancelText="Cancel"
        onCancel={handleCancel}
        onOk={() => {
          // Form submission will be handled by the form component
        }}
        confirmLoading={updateMutation.isPending}
        destroyOnClose
      >
        <ReminderEditForm
          reminder={editingReminder}
          onFinish={handleFormFinish}
          isLoading={updateMutation.isPending}
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
}

const ReminderEditForm: React.FC<ReminderEditFormProps> = ({ reminder, onFinish, isLoading }) => {
  const [form] = Form.useForm();

  React.useEffect(() => {
    if (reminder) {
      form.setFieldsValue({
        status: reminder.status,
        active: reminder.active,
        comment: reminder.comment,
      });
    }
  }, [reminder, form]);

  const handleSubmit = () => {
    form.validateFields().then((values) => {
      onFinish(values);
    }).catch((info) => {
      console.log('Validate Failed:', info);
    });
  };

  // Update the parent modal's onOk handler
  React.useEffect(() => {
    const modal = document.querySelector('.ant-modal');
    if (modal) {
      const okButton = modal.querySelector('.ant-btn-primary');
      if (okButton) {
        okButton.addEventListener('click', handleSubmit);
        return () => okButton.removeEventListener('click', handleSubmit);
      }
    }
  }, [form]);

  return (
    <Form form={form} layout="vertical" name="reminder_edit_form">
      <Form.Item
        name="status"
        label="Status"
        rules={[{ required: true, message: 'Please select a status!' }]}
      >
        <Select options={STATUS_OPTIONS} disabled={isLoading} />
      </Form.Item>
      
      <Form.Item
        name="active"
        label="Active"
        valuePropName="checked"
      >
        <Switch disabled={isLoading} />
      </Form.Item>
      
      <Form.Item
        name="comment"
        label="Comment"
      >
        <Input.TextArea rows={3} placeholder="Add a comment about this reminder..." disabled={isLoading} />
      </Form.Item>
    </Form>
  );
};

export default Reminders;

