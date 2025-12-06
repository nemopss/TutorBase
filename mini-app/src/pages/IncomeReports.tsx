import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Card,
  Col,
  Row,
  Statistic,
  Spin,
  Alert,
  Table,
  Button,
  Select,
  DatePicker,
  Space,
  message,
} from 'antd';
import {
  DollarOutlined,
  DownloadOutlined,
  RiseOutlined,
  FallOutlined,
} from '@ant-design/icons';
import type { TableProps } from 'antd';
import dayjs, { Dayjs } from 'dayjs';
import api from '../services/api';
import PageHeader from '../components/common/PageHeader';
import { useResponsiveStyles } from '../hooks/useResponsiveStyles';

const { RangePicker } = DatePicker;

// --- Types --- //
type PeriodType = 'month' | 'quarter' | 'custom' | 'all';

interface LearnerIncome {
  learner_id: number;
  learner_name: string;
  amount: number;
}

interface PackageIncome {
  package_id: number;
  package_title: string;
  amount: number;
}

interface IncomeReport {
  period_start: string;
  period_end: string;
  total: number;
  by_learner: LearnerIncome[];
  by_package: PackageIncome[];
  previous_period_total: number;
  change_percent: number;
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

const getDefaultDates = (period: PeriodType): [Dayjs, Dayjs] => {
  const now = dayjs();
  switch (period) {
    case 'month':
      return [now.startOf('month'), now.endOf('month')];
    case 'quarter': {
      // Calculate quarter manually
      const quarterMonth = Math.floor(now.month() / 3) * 3;
      const quarterStart = now.month(quarterMonth).startOf('month');
      const quarterEnd = now.month(quarterMonth + 2).endOf('month');
      return [quarterStart, quarterEnd];
    }
    case 'all':
      // Far past to now for "all time"
      return [dayjs('2020-01-01'), now.endOf('day')];
    default:
      return [now.startOf('month'), now.endOf('month')];
  }
};

// --- Component --- //
const IncomeReports: React.FC = () => {
  const { cardStyle, textColor } = useResponsiveStyles();
  const [period, setPeriod] = useState<PeriodType>('month');
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs]>(getDefaultDates('month'));
  const [selectedMonth, setSelectedMonth] = useState<Dayjs>(dayjs());
  const [isExporting, setIsExporting] = useState(false);

  const getEffectiveDateRange = (): [Dayjs, Dayjs] => {
    if (period === 'month') {
      return [selectedMonth.startOf('month'), selectedMonth.endOf('month')];
    }
    if (period === 'all') {
      return [dayjs('2020-01-01'), dayjs().endOf('day')];
    }
    if (period === 'quarter') {
      const now = dayjs();
      const quarterMonth = Math.floor(now.month() / 3) * 3;
      const quarterStart = now.month(quarterMonth).startOf('month');
      const quarterEnd = now.month(quarterMonth + 2).endOf('month');
      return [quarterStart, quarterEnd];
    }
    return dateRange;
  };

  const fetchIncomeReport = async (): Promise<IncomeReport> => {
    const effectiveRange = getEffectiveDateRange();
    const params: Record<string, string> = {
      period: 'custom',
      from_date: effectiveRange[0].toISOString(),
      to_date: effectiveRange[1].toISOString(),
    };
    const { data } = await api.get('/finance/reports/income', { params });
    return data;
  };

  const effectiveDateRange = getEffectiveDateRange();

  const {
    data: report,
    isLoading,
    isError,
    error,
  } = useQuery<IncomeReport, Error>({
    queryKey: ['incomeReport', period, effectiveDateRange[0].toISOString(), effectiveDateRange[1].toISOString()],
    queryFn: fetchIncomeReport,
  });

  const handlePeriodChange = (value: PeriodType) => {
    setPeriod(value);
    if (value !== 'custom' && value !== 'month') {
      setDateRange(getDefaultDates(value));
    }
  };

  const handleMonthChange = (date: Dayjs | null) => {
    if (date) {
      setSelectedMonth(date);
    }
  };

  const handleDateRangeChange = (dates: [Dayjs | null, Dayjs | null] | null) => {
    if (dates && dates[0] && dates[1]) {
      setDateRange([dates[0], dates[1]]);
      setPeriod('custom');
    }
  };

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const effectiveRange = getEffectiveDateRange();
      const params: Record<string, string> = {
        period: 'custom',
        from_date: effectiveRange[0].toISOString(),
        to_date: effectiveRange[1].toISOString(),
      };
      const response = await api.get('/finance/reports/income/export', {
        params,
        responseType: 'blob',
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `income_report_${dayjs().format('YYYY-MM-DD')}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      message.success('Отчёт экспортирован');
    } catch {
      message.error('Ошибка экспорта отчёта');
    } finally {
      setIsExporting(false);
    }
  };

  const learnerColumns: TableProps<LearnerIncome>['columns'] = [
    {
      title: 'Ученик',
      dataIndex: 'learner_name',
      key: 'learner_name',
    },
    {
      title: 'Сумма',
      dataIndex: 'amount',
      key: 'amount',
      render: (amount: number) => formatCurrency(amount),
      align: 'right',
      sorter: (a, b) => a.amount - b.amount,
      defaultSortOrder: 'descend',
    },
  ];

  const packageColumns: TableProps<PackageIncome>['columns'] = [
    {
      title: 'Пакет',
      dataIndex: 'package_title',
      key: 'package_title',
    },
    {
      title: 'Сумма',
      dataIndex: 'amount',
      key: 'amount',
      render: (amount: number) => formatCurrency(amount),
      align: 'right',
      sorter: (a, b) => a.amount - b.amount,
      defaultSortOrder: 'descend',
    },
  ];

  if (isLoading) {
    return <Spin size="large" />;
  }

  if (isError) {
    return <Alert message="Ошибка загрузки отчёта" description={error.message} type="error" />;
  }

  const changePercent = report?.change_percent || 0;

  return (
    <div>
      <PageHeader
        title="Отчёты о доходах"
        subtitle="Анализ доходов по периодам"
        actions={
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            onClick={handleExport}
            loading={isExporting}
          >
            Экспорт CSV
          </Button>
        }
      />

      {/* Period Selector */}
      <Card style={{ ...cardStyle, marginBottom: 16 }}>
        <Space wrap>
          <Select
            value={period}
            onChange={handlePeriodChange}
            style={{ width: 160 }}
            options={[
              { value: 'month', label: 'По месяцам' },
              { value: 'quarter', label: 'Текущий квартал' },
              { value: 'all', label: 'За всё время' },
              { value: 'custom', label: 'Произвольный' },
            ]}
          />
          {period === 'month' && (
            <DatePicker
              value={selectedMonth}
              onChange={handleMonthChange}
              picker="month"
              format="MMMM YYYY"
              allowClear={false}
            />
          )}
          {period === 'custom' && (
            <RangePicker
              value={dateRange}
              onChange={handleDateRangeChange}
              format="DD.MM.YYYY"
            />
          )}
        </Space>
      </Card>

      {/* Summary Cards */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={8}>
          <Card style={cardStyle}>
            <Statistic
              title="Общий доход"
              value={report?.total || 0}
              prefix={<DollarOutlined />}
              formatter={(value) => formatCurrency(Number(value))}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card style={cardStyle}>
            <Statistic
              title="Предыдущий период"
              value={report?.previous_period_total || 0}
              formatter={(value) => formatCurrency(Number(value))}
              valueStyle={{ color: textColor }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card style={cardStyle}>
            <Statistic
              title="Изменение"
              value={Math.abs(changePercent)}
              precision={1}
              prefix={changePercent >= 0 ? <RiseOutlined /> : <FallOutlined />}
              suffix="%"
              valueStyle={{ color: changePercent >= 0 ? '#52c41a' : '#ff4d4f' }}
            />
          </Card>
        </Col>
      </Row>

      {/* Breakdown Tables */}
      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} lg={12}>
          <Card title="По ученикам" bordered={false} style={cardStyle}>
            <Table
              dataSource={report?.by_learner || []}
              columns={learnerColumns}
              rowKey="learner_id"
              pagination={false}
              size="small"
              locale={{ emptyText: 'Нет данных' }}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="По пакетам" bordered={false} style={cardStyle}>
            <Table
              dataSource={report?.by_package || []}
              columns={packageColumns}
              rowKey="package_id"
              pagination={false}
              size="small"
              locale={{ emptyText: 'Нет данных' }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default IncomeReports;
