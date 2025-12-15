import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Tabs, message, Alert, Card } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import api from '../services/api';
import PackageForm from '../components/forms/PackageForm';
import PageHeader from '../components/common/PageHeader';
import PackageCard from '../components/cards/PackageCard';
import PackageGrid from '../components/common/PackageGrid';
import FloatingActionButton from '../components/common/FloatingActionButton';
import { useThemeMode } from '../theme/ThemeProvider';
import { spacing } from '../theme/tokens';

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
  const { data } = await api.post('/packages/create', values);
  return data;
};

// --- Component --- //
const Packages: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { resolvedTheme } = useThemeMode();
  const isDark = resolvedTheme === 'dark';
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
      message.success('Package created successfully!');
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      setIsModalOpen(false);
    },
    onError: (error: Error) => {
      message.error(`An error occurred: ${error.message}`);
    },
  });

  const handleFormFinish = (values: any) => {
    createMutation.mutate(values);
  };

  const hasPackages = sortedPackages.length > 0;

  const tabItems = [
    { key: 'active', label: 'Active' },
    { key: 'completed', label: 'Completed' },
    { key: 'draft', label: 'Drafts' },
    { key: 'cancelled', label: 'Cancelled' },
  ];

  return (
    <div>
      <PageHeader
        title="Packages"
        subtitle="Manage lesson packages for your students"
      />

      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as 'active' | 'completed' | 'draft' | 'cancelled')}
        items={tabItems}
        style={{ marginBottom: spacing.md }}
      />

      {isError && (
        <Alert
          message="Error loading packages"
          description={error?.message || 'Failed to load packages'}
          type="error"
          showIcon
          style={{ marginBottom: spacing.md }}
        />
      )}

      <PackageGrid loading={isLoading}>
        {!hasPackages && !isLoading ? (
          <Card
            hoverable
            onClick={() => setIsModalOpen(true)}
            style={{
              minHeight: 140,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '2px dashed',
              borderColor: isDark ? '#3a3a3a' : '#d9d9d9',
              background: 'transparent',
            }}
            bodyStyle={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
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

      {hasPackages && (
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
