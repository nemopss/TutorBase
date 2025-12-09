import React, { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
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
  Space,
} from 'antd';
import {
  ArrowLeftOutlined,
  EditOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import api from '../services/api';
import SegmentedProgress from '../components/common/SegmentedProgress';
import WeekCalendar from '../components/common/WeekCalendar';
import PackageForm from '../components/forms/PackageForm';
import RescheduleForm from '../components/forms/RescheduleForm';
import LessonForm from '../components/forms/LessonForm';
import { formatDate } from '../utils/datetime';
import { spacing } from '../theme/tokens';
import { useThemeMode } from '../theme/ThemeProvider';

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

const getPaymentStatusLabel = (status?: string): string => {
  switch (status) {
    case 'paid': return 'Paid';
    case 'partial': return 'Partial';
    case 'unpaid': return 'Unpaid';
    default: return '—';
  }
};

const getStatusColor = (status: string): string => {
  return status === 'active' ? 'green' : 'volcano';
};

// --- Component --- //
const PackageDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { resolvedTheme } = useThemeMode();
  const isDark = resolvedTheme === 'dark';
  const [paymentForm] = Form.useForm();

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
    enabled: !!id,
  });

  const { data: lessonsData, isLoading: isLoadingLessons } = useQuery<LessonListResponse, Error>({
    queryKey: ['packageLessons', id],
    queryFn: () => fetchPackageLessons(id!),
    enabled: !!id,
  });

  // Mutations
  const createLessonMutation = useMutation({
    mutationFn: async (values: any) => {
      const { data } = await api.post(`/lessons/packages/${id}`, values);
      return data;
    },
    onSuccess: () => {
      message.success('Lesson created');
      queryClient.invalidateQueries({ queryKey: ['packageLessons', id] });
      queryClient.invalidateQueries({ queryKey: ['package', id] });
      setIsAddLessonModalOpen(false);
      setNewLessonDate(null);
    },
    onError: (error: Error) => {
      message.error(`Error: ${error.message}`);
    },
  });

  const updateLessonMutation = useMutation({
    mutationFn: updateLesson,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['packageLessons', id] });
      queryClient.invalidateQueries({ queryKey: ['package', id] });
    },
    onError: (error: Error) => {
      message.error(`Error: ${error.message}`);
    },
  });

  const deleteLessonMutation = useMutation({
    mutationFn: deleteLesson,
    onSuccess: () => {
      message.success('Lesson deleted');
      queryClient.invalidateQueries({ queryKey: ['packageLessons', id] });
      queryClient.invalidateQueries({ queryKey: ['package', id] });
      setIsDeleteLessonModalOpen(false);
      setSelectedLessonId(null);
    },
    onError: (error: Error) => {
      message.error(`Error: ${error.message}`);
    },
  });

  const deletePackageMutation = useMutation({
    mutationFn: deletePackage,
    onSuccess: () => {
      message.success('Package deleted');
      navigate('/packages');
    },
    onError: (error: Error) => {
      message.error(`Error: ${error.message}`);
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
      message.success('Payment recorded');
      queryClient.invalidateQueries({ queryKey: ['package', id] });
      setIsPaymentModalOpen(false);
      paymentForm.resetFields();
    },
    onError: (error: Error) => {
      message.error(`Error: ${error.message}`);
    },
  });

  const updatePackageMutation = useMutation({
    mutationFn: async (values: any) => {
      const { data } = await api.patch(`/packages/${id}`, values);
      return data;
    },
    onSuccess: () => {
      message.success('Package updated');
      queryClient.invalidateQueries({ queryKey: ['package', id] });
      setIsEditModalOpen(false);
    },
    onError: (error: Error) => {
      message.error(`Error: ${error.message}`);
    },
  });

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
          message.success('Lesson rescheduled');
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
          message.success('Lesson marked as completed');
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
          message.success('Lesson cancelled');
          setIsCancelLessonModalOpen(false);
          setSelectedLessonId(null);
        },
      }
    );
  };

  const handleDelete = (lessonId: number) => {
    setSelectedLessonId(lessonId);
    setIsDeleteLessonModalOpen(true);
  };

  const confirmDeleteLesson = () => {
    if (selectedLessonId) {
      deleteLessonMutation.mutate(selectedLessonId);
    }
  };

  const confirmDeletePackage = () => {
    if (id) {
      deletePackageMutation.mutate(parseInt(id));
    }
  };

  // Loading/Error states
  if (!id || isLoadingPackage) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (isErrorPackage) {
    return <Alert message="Error" description={errorPackage.message} type="error" />;
  }

  const progress = packageData?.progress || { total: 0, completed: 0, cancelled: 0 };
  const remaining = progress.total - progress.completed - progress.cancelled;

  // Tab content
  const detailsContent = (
    <div style={{ maxWidth: 600 }}>
      {/* Edit button */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: spacing.md }}>
        <Button icon={<EditOutlined />} onClick={() => setIsEditModalOpen(true)}>
          Edit
        </Button>
      </div>

      {/* Dates section */}
      <div style={{ marginBottom: spacing.lg }}>
        <Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase' }}>
          Dates
        </Text>
        <div style={{ marginTop: spacing.xs }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
            <Text>Start Date</Text>
            <Text>{packageData?.start_date ? formatDate(packageData.start_date, { timezone: packageData.timezone }) : '—'}</Text>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
            <Text>End Date</Text>
            <Text>{packageData?.end_date ? formatDate(packageData.end_date, { timezone: packageData.timezone }) : '—'}</Text>
          </div>
        </div>
      </div>

      {/* Lessons section */}
      <div style={{ marginBottom: spacing.lg }}>
        <Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase' }}>
          Lessons
        </Text>
        <div style={{ marginTop: spacing.xs }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
            <Text>Total</Text>
            <Text>{progress.total}</Text>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
            <Text>Completed</Text>
            <Text style={{ color: '#52c41a' }}>{progress.completed}</Text>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
            <Text>Cancelled</Text>
            <Text style={{ color: '#ff4d4f' }}>{progress.cancelled}</Text>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
            <Text>Remaining</Text>
            <Text>{remaining}</Text>
          </div>
        </div>
      </div>

      {/* Payment section */}
      <div style={{ marginBottom: spacing.lg }}>
        <Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase' }}>
          Payment
        </Text>
        <div style={{ marginTop: spacing.xs }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
            <Text>Price</Text>
            <Text>{packageData?.price ? formatCurrency(packageData.price) : '—'}</Text>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0' }}>
            <Text>Status</Text>
            <Space>
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
                Add Payment
              </Button>
            </Space>
          </div>
          {packageData?.total_paid !== undefined && packageData.total_paid > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
              <Text>Total Paid</Text>
              <Text>{formatCurrency(packageData.total_paid)}</Text>
            </div>
          )}
        </div>
      </div>

      {/* Notes section */}
      <div style={{ marginBottom: spacing.lg }}>
        <Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase' }}>
          Notes
        </Text>
        <div style={{ marginTop: spacing.xs }}>
          <Text type={packageData?.notes ? undefined : 'secondary'}>
            {packageData?.notes || 'No notes'}
          </Text>
        </div>
      </div>

      {/* Delete link */}
      <div style={{ textAlign: 'center', marginTop: spacing.xl }}>
        <Button
          type="link"
          danger
          style={{ fontSize: 12 }}
          onClick={() => setIsDeletePackageModalOpen(true)}
        >
          Delete Package
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
    setNewLessonDate(date);
    setIsAddLessonModalOpen(true);
  };

  const lessonsContent = (
    <div>
      {isLoadingLessons ? (
        <Spin />
      ) : (
        <WeekCalendar
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
    { key: 'lessons', label: 'Lessons', children: lessonsContent },
    { key: 'details', label: 'Details', children: detailsContent },
  ];

  return (
    <div>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: spacing.md,
          marginBottom: spacing.lg,
          flexWrap: 'wrap',
        }}
      >
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/packages')}>
          Back
        </Button>
        <SegmentedProgress
          total={progress.total}
          completed={progress.completed}
          cancelled={progress.cancelled}
          size={80}
        />
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
        title="Add Payment"
        open={isPaymentModalOpen}
        onOk={() => paymentForm.validateFields().then((values) => createPaymentMutation.mutate(values))}
        onCancel={() => setIsPaymentModalOpen(false)}
        confirmLoading={createPaymentMutation.isPending}
        okText="Add"
        cancelText="Cancel"
      >
        <Form form={paymentForm} layout="vertical">
          <Form.Item
            name="amount"
            label="Amount"
            rules={[{ required: true, message: 'Enter amount' }]}
          >
            <InputNumber style={{ width: '100%' }} min={1} />
          </Form.Item>
          <Form.Item
            name="paid_at"
            label="Date"
            rules={[{ required: true, message: 'Select date' }]}
          >
            <DatePicker style={{ width: '100%' }} format="DD.MM.YYYY" />
          </Form.Item>
          <Form.Item name="notes" label="Notes">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Edit Package Modal */}
      <PackageForm
        open={isEditModalOpen}
        onCancel={() => setIsEditModalOpen(false)}
        onFinish={(values) => updatePackageMutation.mutate(values)}
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
        title="Delete Package"
        open={isDeletePackageModalOpen}
        onOk={confirmDeletePackage}
        onCancel={() => setIsDeletePackageModalOpen(false)}
        okText="Delete"
        okButtonProps={{ danger: true, loading: deletePackageMutation.isPending }}
      >
        <p>Are you sure you want to delete this package?</p>
        <p style={{ color: '#8c8c8c' }}>This action cannot be undone.</p>
      </Modal>

      {/* Delete Lesson Modal */}
      <Modal
        title="Delete Lesson"
        open={isDeleteLessonModalOpen}
        onOk={confirmDeleteLesson}
        onCancel={() => {
          setIsDeleteLessonModalOpen(false);
          setSelectedLessonId(null);
        }}
        okText="Delete"
        okButtonProps={{ danger: true, loading: deleteLessonMutation.isPending }}
      >
        <p>Are you sure you want to delete this lesson?</p>
        <p style={{ color: '#8c8c8c' }}>This action cannot be undone.</p>
      </Modal>

      {/* Complete Lesson Modal */}
      <Modal
        title="Mark as Completed"
        open={isCompleteLessonModalOpen}
        onOk={confirmComplete}
        onCancel={() => {
          setIsCompleteLessonModalOpen(false);
          setSelectedLessonId(null);
        }}
        okText="Complete"
        confirmLoading={updateLessonMutation.isPending}
      >
        <p>Mark this lesson as completed?</p>
      </Modal>

      {/* Cancel Lesson Modal */}
      <Modal
        title="Cancel Lesson"
        open={isCancelLessonModalOpen}
        onOk={confirmCancel}
        onCancel={() => {
          setIsCancelLessonModalOpen(false);
          setSelectedLessonId(null);
        }}
        okText="Yes, Cancel"
        okButtonProps={{ danger: true }}
        confirmLoading={updateLessonMutation.isPending}
      >
        <p>Are you sure you want to cancel this lesson?</p>
      </Modal>

      {/* Add Lesson Modal */}
      <LessonForm
        open={isAddLessonModalOpen}
        onCancel={() => {
          setIsAddLessonModalOpen(false);
          setNewLessonDate(null);
        }}
        onFinish={(values) => createLessonMutation.mutate(values)}
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
