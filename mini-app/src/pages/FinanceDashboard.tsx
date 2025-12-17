import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card, Col, Row, Statistic, Spin, Alert, List, Button, Tag } from 'antd';
import {
  DollarOutlined,
  RiseOutlined,
  FallOutlined,
  UserOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { useTranslation } from 'react-i18next';
import api from '../services/api';
import PageHeader from '../components/common/PageHeader';
import { useResponsiveStyles } from '../hooks/useResponsiveStyles';
import { useResponsive } from '../hooks/useResponsive';
import { chartHeight } from '../theme/tokens';

// --- Types --- //
interface MonthlyIncome {
  month: string;
  amount: number;
}

interface DashboardMetrics {
  current_month_income: number;
  previous_month_income: number;
  total_outstanding: number;
  unpaid_learners_count: number;
  income_chart: MonthlyIncome[];
}

interface LearnerWithBalance {
  learner_id: number;
  learner_name: string;
  outstanding_balance: number;
}

// --- API Fetchers --- //
const fetchDashboardMetrics = async (): Promise<DashboardMetrics> => {
  const { data } = await api.get('/finance/dashboard');
  return data;
};

const fetchLearnersWithBalance = async (): Promise<LearnerWithBalance[]> => {
  const { data } = await api.get('/learners');
  // Filter learners with outstanding balance from finance endpoint
  const learnersWithBalance: LearnerWithBalance[] = [];
  for (const learner of data.items.slice(0, 10)) {
    try {
      const financeData = await api.get(`/learners/${learner.id}/finance`);
      if (financeData.data.outstanding_balance > 0) {
        learnersWithBalance.push({
          learner_id: learner.id,
          learner_name: learner.display_name,
          outstanding_balance: financeData.data.outstanding_balance,
        });
      }
    } catch {
      // Skip learners without finance data
    }
  }
  return learnersWithBalance;
};

// --- Helpers --- //
const formatCurrency = (value: number): string => {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
};

const formatMonth = (month: string): string => {
  const [year, m] = month.split('-');
  const date = new Date(parseInt(year), parseInt(m) - 1);
  return date.toLocaleDateString('ru-RU', { month: 'short' });
};

// --- Component --- //
const FinanceDashboard: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { cardStyle, textColor, chartGridColor, tooltipStyle } = useResponsiveStyles();
  const { isMobile } = useResponsive();
  const currentChartHeight = isMobile ? chartHeight.mobile : chartHeight.desktop;

  const {
    data: metrics,
    isLoading,
    isError,
    error,
  } = useQuery<DashboardMetrics, Error>({
    queryKey: ['financeDashboard'],
    queryFn: fetchDashboardMetrics,
  });

  const { data: learnersWithBalance } = useQuery<LearnerWithBalance[], Error>({
    queryKey: ['learnersWithBalance'],
    queryFn: fetchLearnersWithBalance,
    enabled: !!metrics,
  });

  if (isLoading) {
    return <Spin size="large" />;
  }

  if (isError) {
    return <Alert message={t('errors.loadFailed', { message: '' })} description={error.message} type="error" />;
  }

  // Calculate income change percentage, handling edge cases
  const calculateIncomeChange = (): number => {
    const current = metrics?.current_month_income || 0;
    const previous = metrics?.previous_month_income || 0;
    
    if (previous === 0) {
      // No previous income - can't calculate percentage
      return 0;
    }
    return ((current - previous) / previous) * 100;
  };
  
  const incomeChange = calculateIncomeChange();
  const showPercentage = (metrics?.previous_month_income || 0) > 0;

  const chartData = metrics?.income_chart.map((item) => ({
    month: formatMonth(item.month),
    income: item.amount,
  })) || [];

  return (
    <div>
      <PageHeader
        title={t('pages.finance.title')}
        subtitle={t('pages.finance.subtitle')}
        actions={
          <Button
            type="primary"
            icon={<FileTextOutlined />}
            onClick={() => navigate('/finance/reports')}
          >
            {t('pages.finance.reports')}
          </Button>
        }
      />

      {/* Key Metrics */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card style={cardStyle}>
            <Statistic
              title={t('pages.finance.currentMonthIncome')}
              value={metrics?.current_month_income || 0}
              prefix={<DollarOutlined />}
              formatter={(value) => formatCurrency(Number(value))}
              valueStyle={{ color: textColor }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={cardStyle}>
            <Statistic
              title={t('pages.finance.previousMonthIncome')}
              value={metrics?.previous_month_income || 0}
              prefix={incomeChange >= 0 ? <RiseOutlined /> : <FallOutlined />}
              formatter={(value) => formatCurrency(Number(value))}
              valueStyle={{ color: incomeChange >= 0 ? '#52c41a' : '#ff4d4f' }}
              suffix={
                showPercentage ? (
                  <span style={{ fontSize: 14 }}>
                    {incomeChange >= 0 ? '+' : ''}{incomeChange.toFixed(1)}%
                  </span>
                ) : null
              }
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={cardStyle}>
            <Statistic
              title={t('pages.finance.totalOutstanding')}
              value={metrics?.total_outstanding || 0}
              prefix={<DollarOutlined />}
              formatter={(value) => formatCurrency(Number(value))}
              valueStyle={{ color: (metrics?.total_outstanding || 0) > 0 ? '#faad14' : textColor }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={cardStyle}>
            <Statistic
              title={t('pages.finance.debtorsCount')}
              value={metrics?.unpaid_learners_count || 0}
              prefix={<UserOutlined />}
              valueStyle={{ color: (metrics?.unpaid_learners_count || 0) > 0 ? '#ff4d4f' : textColor }}
            />
          </Card>
        </Col>
      </Row>

      {/* Chart and Outstanding List */}
      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} lg={16}>
          <Card title={t('pages.finance.incomeChart')} bordered={false} style={cardStyle}>
            <ResponsiveContainer width="100%" height={currentChartHeight}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke={chartGridColor} />
                <XAxis dataKey="month" stroke={textColor} tick={{ fontSize: isMobile ? 10 : 12 }} />
                <YAxis
                  stroke={textColor}
                  tick={{ fontSize: isMobile ? 10 : 12 }}
                  tickFormatter={(value) => `${(value / 1000).toFixed(0)}k`}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(value: number) => [formatCurrency(value), t('pages.finance.income')]}
                />
                <Line
                  type="monotone"
                  dataKey="income"
                  stroke="#52c41a"
                  strokeWidth={2}
                  dot={{ fill: '#52c41a' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card
            title={t('pages.finance.learnersWithDebt')}
            bordered={false}
            style={cardStyle}
            extra={
              <Button type="link" onClick={() => navigate('/learners')}>
                {t('pages.finance.all')}
              </Button>
            }
          >
            <List
              dataSource={learnersWithBalance || []}
              locale={{ emptyText: t('pages.finance.noDebts') }}
              renderItem={(item) => (
                <List.Item
                  key={item.learner_id}
                  actions={[
                    <Button
                      key="pay"
                      type="primary"
                      size="small"
                      icon={<DollarOutlined />}
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/learners/${item.learner_id}/finance`);
                      }}
                    >
                      {t('pages.finance.payment')}
                    </Button>,
                  ]}
                >
                  <List.Item.Meta
                    avatar={<UserOutlined style={{ fontSize: 20, color: '#faad14' }} />}
                    title={
                      <span
                        style={{ cursor: 'pointer' }}
                        onClick={() => navigate(`/learners/${item.learner_id}/finance`)}
                      >
                        {item.learner_name}
                      </span>
                    }
                    description={
                      <Tag color="orange">{formatCurrency(item.outstanding_balance)}</Tag>
                    }
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default FinanceDashboard;
