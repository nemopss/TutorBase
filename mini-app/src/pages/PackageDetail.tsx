import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Descriptions, Spin, Alert, Tag, Button, message, Space, Tabs, Progress, Card, Statistic, Row, Col, Grid, Typography, Modal, Form, InputNumber, DatePicker, Input } from 'antd';
import type { TableProps } from 'antd';
import { 
  ArrowLeftOutlined, 
  ReloadOutlined, 
  CheckCircleOutlined, 
  CloseCircleOutlined,
  ClockCircleOutlined,
  EditOutlined,
  DeleteOutlined,
  DollarOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import api from '../services/api';
import LessonForm from '../components/forms/LessonForm';
import PageHeader from '../components/common/PageHeader';
import ResponsiveDataView from '../components/common/ResponsiveDataView';
import { formatDate, formatDateTime } from '../utils/datetime';
import { spacing } from '../theme/tokens';
import { useThemeMode } from '../theme/ThemeProvider';

const { Text } = Typography;

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
  status: string;
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

const createLesson = async ({ packageId, values }: { packageId: string; values: any }) => {
  const { data } = await api.post(`/lessons/packages/${packageId}`, values);
  return data;
};

const updateLesson = async ({ lessonId, values }: { lessonId: number; values: any }) => {
  const { data } = await api.patch(`/lessons/${lessonId}`, values);
  return data;
};

const deleteLesson = async (lessonId: number) => {
  await api.delete(`/lessons/${lessonId}`);
};

// --- Helper functions --- //
const getStatusColor = (status: string) => {
  switch (status) {
    case 'scheduled': return 'blue';
    case 'rescheduled': return 'gold';
    case 'completed': return 'green';
    case 'cancelled': return 'red';
    default: return 'default';
  }
};

// --- Component --- //
const PackageDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingLesson, setEditingLesson] = useState<Lesson | null>(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [lessonToDelete, setLessonToDelete] = useState<number | null>(null);
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
  const [paymentForm] = Form.useForm();
  const screens = Grid.useBreakpoint();
  const isMobile = !screens?.md;
  const { resolvedTheme } = useThemeMode();
  const isDark = resolvedTheme === 'dark';

  const { 
    data: packageData, 
    isLoading: isLoadingPackage, 
    isError: isErrorPackage, 
    error: errorPackage 
  } = useQuery<PackageDetails, Error>({
    queryKey: ['package', id],
    queryFn: () => fetchPackage(id!),
    enabled: !!id,
  });

  const { 
    data: lessonsData, 
    isLoading: isLoadingLessons 
  } = useQuery<LessonListResponse, Error>({
    queryKey: ['packageLessons', id],
    queryFn: () => fetchPackageLessons(id!),
    enabled: !!id,
  });

  const mutationOptions = {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['packageLessons', id] });
      setIsModalOpen(false);
      setEditingLesson(null);
    },
    onError: (error: Error) => {
      message.error(`An error occurred: ${error.message}`);
    }
  };

  const createLessonMutation = useMutation({ 
    mutationFn: createLesson,
    ...mutationOptions,
    onSuccess: () => {
      message.success('Lesson created successfully!');
      mutationOptions.onSuccess();
    }
  });

  const updateLessonMutation = useMutation({ 
    mutationFn: updateLesson,
    ...mutationOptions,
    onSuccess: () => {
      message.success('Lesson updated successfully!');
      mutationOptions.onSuccess();
    }
  });

  const deleteLessonMutation = useMutation({
    mutationFn: deleteLesson,
    onSuccess: () => {
      message.success('Lesson deleted successfully!');
      queryClient.invalidateQueries({ queryKey: ['packageLessons', id] });
      queryClient.invalidateQueries({ queryKey: ['package', id] });
      setDeleteModalOpen(false);
      setLessonToDelete(null);
    },
    onError: (error: Error) => {
      message.error(`Failed to delete lesson: ${error.message}`);
    }
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
      message.success('Платёж записан!');
      queryClient.invalidateQueries({ queryKey: ['package', id] });
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      setIsPaymentModalOpen(false);
      paymentForm.resetFields();
    },
    onError: (error: Error) => {
      message.error(`Ошибка: ${error.message}`);
    },
  });

  const handleDeleteLesson = (lessonId: number) => {
    setLessonToDelete(lessonId);
    setDeleteModalOpen(true);
  };

  const confirmDeleteLesson = () => {
    if (lessonToDelete) {
      deleteLessonMutation.mutate(lessonToDelete);
    }
  };

  const handleCreatePayment = async () => {
    try {
      const values = await paymentForm.validateFields();
      createPaymentMutation.mutate(values);
    } catch {
      // Validation error
    }
  };

  const openPaymentModal = () => {
    // Calculate remaining amount to pay
    const price = packageData?.price || 0;
    const totalPaid = packageData?.total_paid || 0;
    const remaining = Math.max(0, price - totalPaid);
    
    paymentForm.setFieldsValue({
      amount: remaining > 0 ? remaining : undefined,
      paid_at: dayjs(),
    });
    setIsPaymentModalOpen(true);
  };

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

  const getPaymentStatusLabel = (status?: string): string => {
    switch (status) {
      case 'paid': return 'Оплачен';
      case 'partial': return 'Частично';
      case 'unpaid': return 'Не оплачен';
      default: return '—';
    }
  };

  const handleFormFinish = (values: any) => {
    if (editingLesson) {
      updateLessonMutation.mutate({ lessonId: editingLesson.id, values });
    } else {
      createLessonMutation.mutate({ packageId: id!, values });
    }
  };

  const handleCancel = () => {
    setIsModalOpen(false);
    setEditingLesson(null);
  };

  const lessonColumns: TableProps<Lesson>['columns'] = [
    {
      title: 'Scheduled At',
      dataIndex: 'scheduled_at',
      key: 'scheduled_at',
      render: (text: string) => formatDateTime(text, { timezone: packageData?.timezone }),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => <Tag color={getStatusColor(status)}>{status.toUpperCase()}</Tag>,
    },
    {
      title: 'Duration (min)',
      dataIndex: 'duration_minutes',
      key: 'duration_minutes',
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => (
        <Space size="middle">
          <Button type="link" onClick={() => { setEditingLesson(record); setIsModalOpen(true); }}>Edit</Button>
          <Button type="link" danger onClick={() => handleDeleteLesson(record.id)}>Delete</Button>
        </Space>
      ),
    },
  ];

  // Render lesson card for mobile view
  const renderLessonCard = (lesson: Lesson) => (
    <Card
      size="small"
      style={{
        marginBottom: spacing.sm,
        background: isDark ? '#1f1f1f' : '#ffffff',
        borderColor: isDark ? '#3a3a3a' : '#e8e8e8',
      }}
      actions={[
        <Button
          key="edit"
          type="text"
          icon={<EditOutlined />}
          onClick={(e) => {
            e.stopPropagation();
            setEditingLesson(lesson);
            setIsModalOpen(true);
          }}
        >
          Edit
        </Button>,
        <Button
          key="delete"
          type="text"
          danger
          icon={<DeleteOutlined />}
          onClick={(e) => {
            e.stopPropagation();
            handleDeleteLesson(lesson.id);
          }}
        >
          Delete
        </Button>,
      ]}
    >
      <Space direction="vertical" size={spacing.xs} style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Text strong style={{ fontSize: 14 }}>
            {formatDateTime(lesson.scheduled_at, { timezone: packageData?.timezone })}
          </Text>
          <Tag color={getStatusColor(lesson.status)}>{lesson.status.toUpperCase()}</Tag>
        </div>
        
        {lesson.duration_minutes && (
          <Space size={spacing.xs}>
            <ClockCircleOutlined style={{ color: '#8c8c8c' }} />
            <Text type="secondary">{lesson.duration_minutes} min</Text>
          </Space>
        )}
      </Space>
    </Card>
  );

  if (!id || isLoadingPackage) {
    return <Spin size="large" />;
  }

  if (isErrorPackage) {
    return <Alert message="Error fetching package details" description={errorPackage.message} type="error" />;
  }

  const handleRegenerateReminders = async () => {
    try {
      await api.post(`/packages/${id}/regenerate`);
      message.success('Reminders regenerated successfully!');
      queryClient.invalidateQueries({ queryKey: ['packageReminders', id] });
    } catch (error: any) {
      message.error(`Failed to regenerate reminders: ${error.message}`);
    }
  };

  const progressPercent = packageData && packageData.progress.total > 0
    ? Math.round(((packageData.progress.completed + packageData.progress.cancelled) / packageData.progress.total) * 100)
    : 0;

  const tabItems = [
    {
      key: 'lessons',
      label: `Lessons (${lessonsData?.items.length || 0})`,
      children: (
        <div>
          <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
            <div style={{ color: '#8c8c8c', fontSize: 14 }}>
              {packageData?.progress.completed} completed, {packageData?.progress.cancelled} cancelled
            </div>
            <Button type="primary" onClick={() => { setEditingLesson(null); setIsModalOpen(true); }}>
              Add Lesson
            </Button>
          </div>
          <ResponsiveDataView<Lesson>
            data={lessonsData?.items || []}
            loading={isLoadingLessons}
            columns={lessonColumns}
            rowKey="id"
            emptyText="No lessons yet"
            emptyDescription="Add your first lesson to this package"
            emptyActionText="Add Lesson"
            onEmptyAction={() => { setEditingLesson(null); setIsModalOpen(true); }}
            renderCard={renderLessonCard}
            pagination={false}
            tableProps={{
              bordered: true,
              size: 'middle',
            }}
          />
        </div>
      ),
    },
    {
      key: 'reminders',
      label: 'Reminders',
      children: (
        <div>
          <Space style={{ marginBottom: 16 }}>
            <Button type="primary" icon={<ReloadOutlined />} onClick={handleRegenerateReminders}>
              Regenerate All Reminders
            </Button>
            <Button onClick={() => queryClient.invalidateQueries({ queryKey: ['packageReminders', id] })}>
              Refresh
            </Button>
          </Space>
          <Alert 
            message="Reminders Management" 
            description="Use the Reminders page to view and manage all reminders for this package. Click 'Regenerate' to recreate all reminders based on current lessons."
            type="info" 
            showIcon
          />
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader 
        title={packageData?.title || 'Package Details'}
        subtitle={`Learner: ${packageData?.learner_name || '-'} • Status: ${packageData?.status || '-'}`}
        actions={
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/packages')}>
            Back to Packages
          </Button>
        }
      />

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={6}>
          <Card>
            <Statistic
              title="Total Lessons"
              value={packageData?.progress.total || 0}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={6}>
          <Card>
            <Statistic
              title="Completed"
              value={packageData?.progress.completed || 0}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={6}>
          <Card>
            <Statistic
              title="Cancelled"
              value={packageData?.progress.cancelled || 0}
              prefix={<CloseCircleOutlined />}
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={6}>
          <Card>
            <Statistic
              title="Стоимость"
              value={packageData?.price || 0}
              prefix={<DollarOutlined />}
              formatter={(value) => value ? formatCurrency(Number(value)) : '—'}
            />
            <div style={{ marginTop: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Tag color={getPaymentStatusColor(packageData?.payment_status)}>
                {getPaymentStatusLabel(packageData?.payment_status)}
              </Tag>
              <Button
                type="primary"
                size="small"
                icon={<PlusOutlined />}
                onClick={openPaymentModal}
                disabled={!packageData?.price}
              >
                Платёж
              </Button>
            </div>
          </Card>
        </Col>
      </Row>

      <Card style={{ marginBottom: 24 }}>
        <h3>Progress</h3>
        <Progress 
          percent={progressPercent} 
          status={progressPercent === 100 ? 'success' : 'active'}
          strokeColor={{
            '0%': '#108ee9',
            '100%': '#87d068',
          }}
        />
        <Descriptions 
          bordered 
          column={isMobile ? 1 : 2} 
          size={isMobile ? 'small' : 'middle'} 
          style={{ marginTop: 16 }}
        >
          <Descriptions.Item label="Start Date">
            {packageData?.start_date ? formatDate(packageData.start_date, { timezone: packageData?.timezone }) : 'N/A'}
          </Descriptions.Item>
          <Descriptions.Item label="End Date">
            {packageData?.end_date ? formatDate(packageData.end_date, { timezone: packageData?.timezone }) : 'N/A'}
          </Descriptions.Item>
          <Descriptions.Item label="Timezone">{packageData?.timezone}</Descriptions.Item>
          <Descriptions.Item label="Total Lessons">{packageData?.total_lessons || '-'}</Descriptions.Item>
          <Descriptions.Item label="Notes" span={2}>{packageData?.notes || '-'}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Tabs items={tabItems} defaultActiveKey="lessons" />

      <LessonForm
        open={isModalOpen}
        onCancel={handleCancel}
        onFinish={handleFormFinish}
        isLoading={createLessonMutation.isPending || updateLessonMutation.isPending}
        initialValues={editingLesson}
      />

      <Modal
        open={deleteModalOpen}
        title="Delete Lesson"
        onCancel={() => { setDeleteModalOpen(false); setLessonToDelete(null); }}
        onOk={confirmDeleteLesson}
        okText="Delete"
        okButtonProps={{ danger: true, loading: deleteLessonMutation.isPending }}
        cancelButtonProps={{ disabled: deleteLessonMutation.isPending }}
      >
        <p>Are you sure you want to delete this lesson?</p>
        <p style={{ color: '#8c8c8c' }}>This action cannot be undone.</p>
      </Modal>

      {/* Payment Modal */}
      <Modal
        title="Записать платёж"
        open={isPaymentModalOpen}
        onOk={handleCreatePayment}
        onCancel={() => {
          setIsPaymentModalOpen(false);
          paymentForm.resetFields();
        }}
        confirmLoading={createPaymentMutation.isPending}
        okText="Записать"
        cancelText="Отмена"
      >
        <Form form={paymentForm} layout="vertical" initialValues={{ paid_at: dayjs() }}>
          <Form.Item
            name="amount"
            label="Сумма"
            rules={[
              { required: true, message: 'Введите сумму' },
              { type: 'number', min: 1, message: 'Сумма должна быть положительной' },
            ]}
          >
            <InputNumber
              style={{ width: '100%' }}
              placeholder="например, 5000"
              min={1}
              precision={2}
            />
          </Form.Item>

          <Form.Item
            name="paid_at"
            label="Дата платежа"
            rules={[{ required: true, message: 'Выберите дату' }]}
          >
            <DatePicker style={{ width: '100%' }} format="DD.MM.YYYY" />
          </Form.Item>

          <Form.Item name="notes" label="Примечание">
            <Input.TextArea rows={2} placeholder="Комментарий к платежу" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default PackageDetail;
