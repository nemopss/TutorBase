import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Table, Button, Space, Modal, message, Alert } from 'antd';
import type { TableProps } from 'antd';
import api from '../services/api';
import TemplateForm from '../components/forms/TemplateForm';
import PageHeader from '../components/common/PageHeader';
import EmptyState from '../components/common/EmptyState';

// --- Types --- //
interface Template {
  id: number;
  name: string;
  description?: string;
  lesson_count?: number;
  duration_days?: number;
}

interface TemplateListResponse {
  total: number;
  items: Template[];
}

// --- API Fetchers --- //
const fetchTemplates = async (): Promise<TemplateListResponse> => {
  const { data } = await api.get('/templates');
  return data;
};

const createTemplate = async (values: any) => {
  const { data } = await api.post('/templates/create', values);
  return data;
};

const updateTemplate = async ({ id, values }: { id: number; values: any }) => {
  const { data } = await api.patch(`/templates/${id}`, values);
  return data;
};

const deleteTemplate = async (id: number) => {
  await api.delete(`/templates/${id}`);
};

const duplicateTemplate = async (id: number) => {
  const { data } = await api.post(`/templates/${id}/duplicate`);
  return data;
};

// --- Component --- //
const Templates: React.FC = () => {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<Template | null>(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [templateToDelete, setTemplateToDelete] = useState<number | null>(null);

  const { data, isLoading, isError, error } = useQuery<TemplateListResponse, Error>({
    queryKey: ['templates'],
    queryFn: fetchTemplates,
  });

  // Debug logging for Android
  React.useEffect(() => {
    if (import.meta.env.DEV) {
      console.log('Templates Debug:', { 
        isLoading, 
        isError, 
        error: error?.message,
        hasData: !!data, 
        itemsCount: data?.items?.length || 0,
        userAgent: navigator.userAgent 
      });
    }
  }, [data, isLoading, isError, error]);

  const mutationOptions = {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['templates'] });
    },
    onError: (error: Error) => {
      message.error(`An error occurred: ${error.message}`);
    }
  };

  const createMutation = useMutation({ 
    mutationFn: createTemplate, 
    ...mutationOptions, 
    onSuccess: () => { 
      message.success('Template created!'); 
      mutationOptions.onSuccess();
      setIsModalOpen(false);
    }
  });

  const updateMutation = useMutation({ 
    mutationFn: updateTemplate, 
    ...mutationOptions, 
    onSuccess: () => { 
      message.success('Template updated!'); 
      mutationOptions.onSuccess();
      setIsModalOpen(false);
    }
  });

  const deleteMutation = useMutation({ 
    mutationFn: deleteTemplate, 
    onSuccess: () => { 
      queryClient.invalidateQueries({ queryKey: ['templates'] });
      message.success('Template deleted!');
    },
    onError: (error: any) => {
      console.error('Delete error:', error);
      message.error(`Failed to delete template: ${error.response?.data?.detail || error.message}`);
    }
  });
  
  const duplicateMutation = useMutation({ 
    mutationFn: duplicateTemplate, 
    ...mutationOptions, 
    onSuccess: () => { 
      message.success('Template duplicated!'); 
      mutationOptions.onSuccess();
    }
  });

  const handleFormFinish = (values: any) => {
    if (editingTemplate) {
      updateMutation.mutate({ id: editingTemplate.id, values });
    } else {
      createMutation.mutate(values);
    }
  };

  const handleDelete = (id: number) => {
    setTemplateToDelete(id);
    setDeleteModalOpen(true);
  };

  const confirmDelete = () => {
    if (templateToDelete) {
      deleteMutation.mutate(templateToDelete);
      setDeleteModalOpen(false);
      setTemplateToDelete(null);
    }
  };

  const columns: TableProps<Template>['columns'] = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: 'Lessons',
      dataIndex: 'lesson_count',
      key: 'lesson_count',
    },
    {
      title: 'Duration (days)',
      dataIndex: 'duration_days',
      key: 'duration_days',
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_, record) => (
        <Space size="middle">
          <Button type="link" onClick={() => { setEditingTemplate(record); setIsModalOpen(true); }}>Edit</Button>
          <Button type="link" onClick={() => duplicateMutation.mutate(record.id)}>Duplicate</Button>
          <Button type="link" danger onClick={() => handleDelete(record.id)}>Delete</Button>
        </Space>
      ),
    },
  ];

  // Show error inline instead of blocking entire page
  const showError = isError && error;

  return (
    <div>
      <PageHeader 
        title="Templates"
        subtitle="Manage lesson package templates"
        actions={
          <Button type="primary" onClick={() => { setEditingTemplate(null); setIsModalOpen(true); }}>
            Create Template
          </Button>
        }
      />
      {showError && (
        <Alert 
          message="Error loading templates" 
          description={error.message} 
          type="error" 
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}
      {!isLoading && !isError && (!data?.items || data.items.length === 0) ? (
        <EmptyState 
          title="No templates yet"
          description="Create a template to quickly generate lesson packages with predefined schedules"
          actionText="Create Template"
          onAction={() => { setEditingTemplate(null); setIsModalOpen(true); }}
        />
      ) : (
        <Table
          columns={columns}
          dataSource={data?.items}
          rowKey="id"
          loading={isLoading}
          pagination={false}
          scroll={{ x: 700 }}
          bordered
        />
      )}
      <TemplateForm 
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        onFinish={handleFormFinish}
        isLoading={createMutation.isPending || updateMutation.isPending}
        initialValues={editingTemplate}
      />

      <Modal
        open={deleteModalOpen}
        title="Delete Template"
        onCancel={() => setDeleteModalOpen(false)}
        onOk={confirmDelete}
        okText="Delete"
        okType="danger"
        confirmLoading={deleteMutation.isPending}
      >
        <p>Are you sure you want to delete this template?</p>
        <p style={{ color: '#8c8c8c' }}>This action cannot be undone.</p>
      </Modal>
    </div>
  );
};

export default Templates;
