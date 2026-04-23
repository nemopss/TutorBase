import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Tabs, message, Alert, Card } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import api from '../services/api';
import PackageForm from '../components/forms/PackageForm';
import PageHeader from '../components/common/PageHeader';
import PackageCard from '../components/cards/PackageCard';
import PackageGrid from '../components/common/PackageGrid';
import FloatingActionButton from '../components/common/FloatingActionButton';
import { useTheme } from '../theme/ThemeProvider';
import { spacing } from '../theme/tokens';
import { useAuth } from '../auth/AuthProvider';

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
  created_at?: string;
  next_lesson_date?: string | null;
}

interface PackageListResponse {
  total: number;
  items: Package[];
}

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

const createPackage = async (values: any) => {
  const { data } = await api.post('/packages', values);
  return data;
};

// --- Component --- //
const Packages: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { resolvedTheme } = useTheme();
  const { tenantAccess } = useAuth();
  const isDark = resolvedTheme.colorScheme === 'dark';
  const canUseFullActions = !tenantAccess || tenantAccess.mode === 'full' || tenantAccess.bypass_access_restrictions;
  const [activeTab, setActiveTab] = useState<'active' | 'completed' | 'draft' | 'cancelled'>('active');
  const [isModalOpen, setIsModalOpen] = useState(false);

  const { data, isLoading, error, isError } = useQuery<PackageListResponse, Error>({
    queryKey: ['packages', activeTab],
    queryFn: () => fetchPackages(activeTab),
  });

  const packagesData = data?.items ?? [];

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
    onSuccess: () => {
      message.success(t('success.created'));
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      setIsModalOpen(false);
    },
    onError: (error: Error) => {
      message.error(t('errors.createFailed', { message: error.message }));
    },
  });

  const handleFormFinish = (values: any) => {
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

  return (
    <div>
      <PageHeader
        title={t('pages.packages.title')}
        subtitle={t('pages.packages.subtitle')}
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
        onChange={(key) => setActiveTab(key as 'active' | 'completed' | 'draft' | 'cancelled')}
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

      <PackageGrid loading={isLoading}>
        {!hasPackages && !isLoading ? (
          <Card
            hoverable={canUseFullActions}
            onClick={() => canUseFullActions && setIsModalOpen(true)}
            style={{
              minHeight: 140,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '2px dashed',
              borderColor: isDark ? '#3a3a3a' : '#d9d9d9',
              background: 'transparent',
              opacity: canUseFullActions ? 1 : 0.5,
            }}
            styles={{
              body: {
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              },
            }}
          >
            <PlusOutlined style={{ fontSize: 32, color: '#8c8c8c' }} />
          </Card>
        ) : (
          sortedPackages.map((pkg) => (
            <PackageCard
              key={pkg.id}
              package={pkg}
              onClick={() => navigate(`/packages/${pkg.id}`)}
            />
          ))
        )}
      </PackageGrid>

      {hasPackages && canUseFullActions && (
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
    </div>
  );
};

export default Packages;
