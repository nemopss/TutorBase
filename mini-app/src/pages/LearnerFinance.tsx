import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card,
  Col,
  Row,
  Statistic,
  Spin,
  Alert,
  Button,
  Tag,
  Space,
  Modal,
  Form,
  InputNumber,
  DatePicker,
  Input,
  Select,
  message,
  Typography,
} from 'antd';
import {
  DollarOutlined,
  ArrowLeftOutlined,
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  CalendarOutlined,
  CopyOutlined,
} from '@ant-design/icons';
import type { TableProps } from 'antd';
import dayjs from 'dayjs';
import api from '../services/api';
import PageHeader from '../components/common/PageHeader';
import ResponsiveDataView from '../components/common/ResponsiveDataView';
import { useResponsiveStyles } from '../hooks/useResponsiveStyles';
import { useThemeMode } from '../theme/ThemeProvider';
import { spacing } from '../theme/tokens';

const { Text } = Typography;

// --- Types --- //
interface Payment {
  id: number;
  learner_id: number;
  learner_name: string | null;
  package_id: number | null;
  package_title: string | null;
  amount: number;
  currency: string;
  paid_at: string;
  notes: string | null;
}

interface LearnerFinance {
  learner_id: number;
  lesson_rate: number | null;
  outstanding_balance: number;
  total_paid: number;
  payment_history: Payment[];
}

interface Package {
  id: number;
  title: string;
  price?: number | null;
  total_paid?: number;
  payment_status?: string;
}

interface Learner {
  id: number;
  display_name: string;
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

// --- Component --- //
const LearnerFinance: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { cardStyle, textColor } = useResponsiveStyles();
  const { resolvedTheme } = useThemeMode();
  const isDark = resolvedTheme === 'dark';
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
  const [isRateModalOpen, setIsRateModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [paymentToDelete, setPaymentToDelete] = useState<Payment | null>(null);
  const [editingPayment, setEditingPayment] = useState<Payment | null>(null);
  const [form] = Form.useForm();
  const [rateForm] = Form.useForm();

  const learnerId = parseInt(id || '0');

  // Fetch learner info
  const { data: learner } = useQuery<Learner>({
    queryKey: ['learner', learnerId],
    queryFn: async () => {
      const { data } = await api.get(`/learners/${learnerId}`);
      return data;
    },
    enabled: !!learnerId,
  });

  // Fetch finance data
  const {
    data: finance,
    isLoading,
    isError,
    error,
  } = useQuery<LearnerFinance, Error>({
    queryKey: ['learnerFinance', learnerId],
    queryFn: async () => {
      const { data } = await api.get(`/learners/${learnerId}/finance`);
      return data;
    },
    enabled: !!learnerId,
  });

  // Fetch packages for payment form
  const { data: packages } = useQuery<{ items: Package[] }>({
    queryKey: ['learnerPackages', learnerId],
    queryFn: async () => {
      const { data } = await api.get('/packages', {
        params: { learner_id: learnerId },
      });
      return data;
    },
    enabled: !!learnerId,
  });

  // Create/Update payment mutation
  const createPaymentMutation = useMutation({
    mutationFn: async (values: any) => {
      if (editingPayment) {
        // Update existing payment - delete and recreate since no PATCH endpoint
        await api.delete(`/payments/${editingPayment.id}`);
      }
      const { data } = await api.post('/payments', {
        learner_id: learnerId,
        package_id: values.package_id || null,
        amount: values.amount,
        paid_at: values.paid_at.toISOString(),
        notes: values.notes || null,
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learnerFinance', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      queryClient.invalidateQueries({ queryKey: ['financeDashboard'] });
      message.success(editingPayment ? 'Платёж обновлён' : 'Платёж записан');
      setIsPaymentModalOpen(false);
      setEditingPayment(null);
      form.resetFields();
    },
    onError: (err: Error) => {
      message.error(`Ошибка: ${err.message}`);
    },
  });

  // Update lesson rate mutation
  const updateRateMutation = useMutation({
    mutationFn: async (values: { lesson_rate: number | null }) => {
      const { data } = await api.patch(`/learners/${learnerId}`, {
        lesson_rate: values.lesson_rate,
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learnerFinance', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['learners'] });
      message.success('Тариф обновлён');
      setIsRateModalOpen(false);
      rateForm.resetFields();
    },
    onError: (err: Error) => {
      message.error(`Ошибка: ${err.message}`);
    },
  });

  const handleCreatePayment = async () => {
    try {
      const values = await form.validateFields();
      createPaymentMutation.mutate(values);
    } catch {
      // Validation error
    }
  };

  const handleUpdateRate = async () => {
    try {
      const values = await rateForm.validateFields();
      updateRateMutation.mutate(values);
    } catch {
      // Validation error
    }
  };

  const handleEditPayment = (payment: Payment) => {
    setEditingPayment(payment);
    form.setFieldsValue({
      amount: Number(payment.amount),
      paid_at: dayjs(payment.paid_at),
      package_id: payment.package_id,
      notes: payment.notes,
    });
    setIsPaymentModalOpen(true);
  };

  const handlePackageSelect = (packageId: number | undefined) => {
    if (!packageId || editingPayment) return;
    
    const selectedPackage = packages?.items.find((pkg) => pkg.id === packageId);
    if (selectedPackage && selectedPackage.price) {
      const price = Number(selectedPackage.price);
      const totalPaid = Number(selectedPackage.total_paid || 0);
      const remaining = Math.max(0, price - totalPaid);
      
      if (remaining > 0) {
        form.setFieldsValue({ amount: remaining });
      }
    }
  };

  const handleRepeatPayment = (payment: Payment) => {
    form.setFieldsValue({
      amount: Number(payment.amount),
      paid_at: dayjs(),
      package_id: payment.package_id,
      notes: payment.notes,
    });
    setIsPaymentModalOpen(true);
  };

  const openRateModal = () => {
    rateForm.setFieldsValue({ lesson_rate: finance?.lesson_rate });
    setIsRateModalOpen(true);
  };

  // Delete payment mutation
  const deletePaymentMutation = useMutation({
    mutationFn: async (paymentId: number) => {
      await api.delete(`/payments/${paymentId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learnerFinance', learnerId] });
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      queryClient.invalidateQueries({ queryKey: ['financeDashboard'] });
      message.success('Платёж удалён');
      setDeleteModalOpen(false);
      setPaymentToDelete(null);
    },
    onError: (err: Error) => {
      message.error(`Ошибка: ${err.message}`);
    },
  });

  const handleDeletePayment = (payment: Payment) => {
    setPaymentToDelete(payment);
    setDeleteModalOpen(true);
  };

  const confirmDeletePayment = () => {
    if (paymentToDelete) {
      deletePaymentMutation.mutate(paymentToDelete.id);
    }
  };

  const paymentColumns: TableProps<Payment>['columns'] = [
    {
      title: 'Дата',
      dataIndex: 'paid_at',
      key: 'paid_at',
      render: (date: string) => dayjs(date).format('DD.MM.YYYY'),
      sorter: (a, b) => dayjs(a.paid_at).unix() - dayjs(b.paid_at).unix(),
      defaultSortOrder: 'descend',
    },
    {
      title: 'Сумма',
      dataIndex: 'amount',
      key: 'amount',
      render: (amount: number) => (
        <Tag color="green">{formatCurrency(amount)}</Tag>
      ),
      align: 'right',
    },
    {
      title: 'Пакет',
      dataIndex: 'package_title',
      key: 'package_title',
      render: (title: string | null) => title || '—',
    },
    {
      title: 'Примечание',
      dataIndex: 'notes',
      key: 'notes',
      render: (notes: string | null) => notes || '—',
      ellipsis: true,
    },
    {
      title: '',
      key: 'actions',
      width: 140,
      render: (_, record: Payment) => (
        <Space>
          <Button
            type="text"
            icon={<CopyOutlined />}
            onClick={() => handleRepeatPayment(record)}
            title="Повторить"
          />
          <Button
            type="text"
            icon={<EditOutlined />}
            onClick={() => handleEditPayment(record)}
            title="Редактировать"
          />
          <Button
            type="text"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDeletePayment(record)}
            title="Удалить"
          />
        </Space>
      ),
    },
  ];

  if (isLoading) {
    return <Spin size="large" />;
  }

  if (isError) {
    return <Alert message="Ошибка загрузки" description={error.message} type="error" />;
  }

  return (
    <div>
      <PageHeader
        title={`Финансы: ${learner?.display_name || 'Ученик'}`}
        subtitle="История платежей и задолженность"
        actions={
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/learners')}>
              Назад
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setIsPaymentModalOpen(true)}
            >
              Записать платёж
            </Button>
          </Space>
        }
      />

      {/* Summary Cards */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={8}>
          <Card style={cardStyle}>
            <Statistic
              title="Тариф за урок"
              value={finance?.lesson_rate || 0}
              prefix={<DollarOutlined />}
              formatter={(value) => (value ? formatCurrency(Number(value)) : 'Не задан')}
              valueStyle={{ color: textColor }}
            />
            <Button
              type="link"
              icon={<EditOutlined />}
              onClick={openRateModal}
              style={{ padding: 0, marginTop: 8 }}
            >
              {finance?.lesson_rate ? 'Изменить' : 'Задать тариф'}
            </Button>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card style={cardStyle}>
            <Statistic
              title="Задолженность"
              value={finance?.outstanding_balance || 0}
              prefix={<DollarOutlined />}
              formatter={(value) => formatCurrency(Number(value))}
              valueStyle={{
                color: (finance?.outstanding_balance || 0) > 0 ? '#faad14' : '#52c41a',
              }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card style={cardStyle}>
            <Statistic
              title="Всего оплачено"
              value={finance?.total_paid || 0}
              prefix={<DollarOutlined />}
              formatter={(value) => formatCurrency(Number(value))}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
      </Row>

      {/* Payment History */}
      <Card title="История платежей" style={{ ...cardStyle, marginTop: 24 }}>
        <ResponsiveDataView<Payment>
          data={finance?.payment_history || []}
          columns={paymentColumns}
          rowKey="id"
          emptyText="Нет платежей"
          emptyDescription="Записи о платежах появятся здесь"
          emptyActionText="Записать платёж"
          onEmptyAction={() => setIsPaymentModalOpen(true)}
          pagination={{ pageSize: 10 }}
          renderCard={(payment) => (
            <Card
              key={payment.id}
              size="small"
              style={{
                marginBottom: spacing.sm,
                background: isDark ? '#1f1f1f' : '#ffffff',
                borderColor: isDark ? '#3a3a3a' : '#e8e8e8',
              }}
              actions={[
                <Button
                  key="repeat"
                  type="text"
                  icon={<CopyOutlined />}
                  onClick={() => handleRepeatPayment(payment)}
                >
                  Повторить
                </Button>,
                <Button
                  key="edit"
                  type="text"
                  icon={<EditOutlined />}
                  onClick={() => handleEditPayment(payment)}
                >
                  Изменить
                </Button>,
                <Button
                  key="delete"
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => handleDeletePayment(payment)}
                >
                  Удалить
                </Button>,
              ]}
            >
              <Space direction="vertical" size={spacing.xs} style={{ width: '100%' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Tag color="green" style={{ fontSize: 16, padding: '4px 12px' }}>
                    {formatCurrency(payment.amount)}
                  </Tag>
                  <Space>
                    <CalendarOutlined style={{ color: '#8c8c8c' }} />
                    <Text type="secondary">{dayjs(payment.paid_at).format('DD.MM.YYYY')}</Text>
                  </Space>
                </div>
                {payment.package_title && (
                  <Text type="secondary">Пакет: {payment.package_title}</Text>
                )}
                {payment.notes && (
                  <Text type="secondary" style={{ fontStyle: 'italic' }}>
                    {payment.notes}
                  </Text>
                )}
              </Space>
            </Card>
          )}
        />
      </Card>

      {/* Payment Modal */}
      <Modal
        title={editingPayment ? 'Редактировать платёж' : 'Записать платёж'}
        open={isPaymentModalOpen}
        onOk={handleCreatePayment}
        onCancel={() => {
          setIsPaymentModalOpen(false);
          setEditingPayment(null);
          form.resetFields();
        }}
        confirmLoading={createPaymentMutation.isPending}
        okText={editingPayment ? 'Сохранить' : 'Записать'}
        cancelText="Отмена"
      >
        <Form form={form} layout="vertical" initialValues={{ paid_at: dayjs() }}>
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

          <Form.Item name="package_id" label="Пакет (опционально)">
            <Select
              placeholder="Выберите пакет"
              allowClear
              onChange={handlePackageSelect}
              options={packages?.items.map((pkg) => {
                const price = Number(pkg.price || 0);
                const totalPaid = Number(pkg.total_paid || 0);
                const remaining = Math.max(0, price - totalPaid);
                const statusLabel = pkg.payment_status === 'paid' ? ' ✓' : remaining > 0 ? ` (${formatCurrency(remaining)})` : '';
                return {
                  value: pkg.id,
                  label: `${pkg.title}${statusLabel}`,
                };
              })}
            />
          </Form.Item>

          <Form.Item name="notes" label="Примечание">
            <Input.TextArea rows={2} placeholder="Комментарий к платежу" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        title="Удалить платёж"
        open={deleteModalOpen}
        onOk={confirmDeletePayment}
        onCancel={() => {
          setDeleteModalOpen(false);
          setPaymentToDelete(null);
        }}
        okText="Удалить"
        cancelText="Отмена"
        okButtonProps={{ danger: true, loading: deletePaymentMutation.isPending }}
      >
        <p>Вы уверены, что хотите удалить платёж?</p>
        {paymentToDelete && (
          <p>
            <strong>{formatCurrency(paymentToDelete.amount)}</strong> от{' '}
            {dayjs(paymentToDelete.paid_at).format('DD.MM.YYYY')}
          </p>
        )}
        <p style={{ color: '#8c8c8c' }}>Статус оплаты пакета будет пересчитан.</p>
      </Modal>

      {/* Rate Edit Modal */}
      <Modal
        title="Тариф за урок"
        open={isRateModalOpen}
        onOk={handleUpdateRate}
        onCancel={() => {
          setIsRateModalOpen(false);
          rateForm.resetFields();
        }}
        confirmLoading={updateRateMutation.isPending}
        okText="Сохранить"
        cancelText="Отмена"
      >
        <Form form={rateForm} layout="vertical">
          <Form.Item
            name="lesson_rate"
            label="Стоимость одного урока (₽)"
            rules={[
              { type: 'number', min: 0, message: 'Стоимость должна быть положительной' },
            ]}
          >
            <InputNumber
              style={{ width: '100%' }}
              placeholder="например, 1500"
              min={0}
              precision={2}
            />
          </Form.Item>
          <p style={{ color: '#8c8c8c', fontSize: 12 }}>
            Новый тариф будет применяться только к новым пакетам. Существующие пакеты сохранят свою цену.
          </p>
        </Form>
      </Modal>
    </div>
  );
};

export default LearnerFinance;
