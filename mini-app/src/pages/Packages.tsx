import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Table, Tag, Select, Space, Input, Button, message, Progress } from 'antd';
import type { TableProps } from 'antd';
import api from '../services/api';
import { useDebounce } from '../hooks/useDebounce';
import PackageForm from '../components/forms/PackageForm';
import PageHeader from '../components/common/PageHeader';
import EmptyState from '../components/common/EmptyState';

// --- Types --- //
interface PackageProgress {
  total: number;
  completed: number;
  cancelled: number;
}

interface Package {
  id: number;
  learner_name: string;
  title: string;
  status: string;
  progress: PackageProgress;
}

interface PackageListResponse {
  total: number;
  items: Package[];
}

const STATUS_OPTIONS = [
  { value: 'active', label: 'Active' },
  { value: 'draft', label: 'Draft' },
  { value: 'completed', label: 'Completed' },
  { value: 'archived', label: 'Archived' },
];

// --- API Fetchers --- //
const fetchPackages = async (page: number, pageSize: number, status: string | null, search: string): Promise<PackageListResponse> => {
  const { data } = await api.get('/packages', {
    params: {
      offset: (page - 1) * pageSize,
      limit: pageSize,
      status_filter: status,
      search: search || undefined,
    },
  });
  return data;
};

const createPackage = async (values: any) => {
  const { data } = await api.post('/packages/create', values);
  return data;
};

const updatePackage = async ({ id, values }: { id: number; values: any }) => {
  const { data } = await api.patch(`/packages/${id}`, values);
  return data;
};

// --- Component --- //
const Packages: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingPackage, setEditingPackage] = useState<Package | null>(null);

  const debouncedSearchTerm = useDebounce(searchTerm, 500);

  const { data, isLoading } = useQuery<PackageListResponse, Error>({
    queryKey: ['packages', currentPage, pageSize, statusFilter, debouncedSearchTerm],
    queryFn: () => fetchPackages(currentPage, pageSize, statusFilter, debouncedSearchTerm),
    placeholderData: (previousData) => previousData,
  });

  const mutationOptions = {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['packages'] });
      setIsModalOpen(false);
      setEditingPackage(null);
    },
    onError: (error: Error) => {
      message.error(`An error occurred: ${error.message}`);
    }
  };

  const createMutation = useMutation({ 
    mutationFn: createPackage,
    ...mutationOptions,
    onSuccess: () => {
      message.success('Package created successfully!');
      mutationOptions.onSuccess();
    }
  });

  const updateMutation = useMutation({ 
    mutationFn: updatePackage,
    ...mutationOptions,
    onSuccess: () => {
      message.success('Package updated successfully!');
      mutationOptions.onSuccess();
    }
  });

  const handleFormFinish = (values: any) => {
    if (editingPackage) {
      updateMutation.mutate({ id: editingPackage.id, values });
    } else {
      createMutation.mutate(values);
    }
  };

  const columns: TableProps<Package>['columns'] = [
    {
      title: 'Title',
      dataIndex: 'title',
      key: 'title',
      render: (text, record) => <a onClick={() => navigate(`/packages/${record.id}`)}>{text}</a>,
    },
    {
      title: 'Learner',
      dataIndex: 'learner_name',
      key: 'learner_name',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => <Tag color={status === 'active' ? 'green' : 'volcano'}>{status.toUpperCase()}</Tag>,
    },
    {
      title: 'Progress',
      key: 'progress',
      width: 200,
      render: (_, record) => {
        const percent = record.progress.total > 0 
          ? Math.round((record.progress.completed / record.progress.total) * 100) 
          : 0;
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Progress 
              percent={percent} 
              size="small" 
              strokeColor="#0f7b6c"
              style={{ flex: 1, margin: 0 }}
            />
            <span style={{ fontSize: 12, color: '#8c8c8c', minWidth: 60 }}>
              {record.progress.completed}/{record.progress.total}
            </span>
          </div>
        );
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => (
        <Button type="link" onClick={(e) => { e.stopPropagation(); setEditingPackage(record); setIsModalOpen(true); }}>Edit</Button>
      ),
    },
  ];

  const handleTableChange = (pagination: any) => {
    setCurrentPage(pagination.current);
    setPageSize(pagination.pageSize);
  };

  return (
    <div>
      <PageHeader 
        title="Packages"
        subtitle="Manage lesson packages for your students"
        actions={
          <Button type="primary" onClick={() => { setEditingPackage(null); setIsModalOpen(true); }}>
            Create Package
          </Button>
        }
      />
      <Space style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="Search by title or learner"
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
      </Space>
      {!isLoading && (!data?.items || data.items.length === 0) ? (
        <EmptyState 
          title="No packages yet"
          description="Create your first lesson package to get started"
          actionText="Create Package"
          onAction={() => { setEditingPackage(null); setIsModalOpen(true); }}
        />
      ) : (
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
            showTotal: (total, range) => `${range[0]}-${range[1]} of ${total} packages`,
          }}
          onChange={handleTableChange}
          onRow={(record) => ({
            onClick: () => navigate(`/packages/${record.id}`),
            style: { cursor: 'pointer' },
          })}
          bordered
        />
      )}
      <PackageForm 
        open={isModalOpen}
        onCancel={() => { setIsModalOpen(false); setEditingPackage(null); }}
        onFinish={handleFormFinish}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />
    </div>
  );
};

export default Packages;
