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

  const { data, isLoading, isError, error } = useQuery<TemplateListResponse, Error>({
    queryKey: ['templates'],
    queryFn: fetchTemplates,
  });

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

  const deleteMutation = useMutation({ mutationFn: deleteTemplate, ...mutationOptions, onSuccess: () => message.success('Template deleted!') });
  const duplicateMutation = useMutation({ mutationFn: duplicateTemplate, ...mutationOptions, onSuccess: () => message.success('Template duplicated!') });

  const handleFormFinish = (values: any) => {
    if (editingTemplate) {
      updateMutation.mutate({ id: editingTemplate.id, values });
    } else {
      createMutation.mutate(values);
    }
  };

  const handleDelete = (id: number) => {
    Modal.confirm({
      title: 'Are you sure you want to delete this template?',
      content: 'This action cannot be undone.',
      okText: 'Yes, delete it',
      okType: 'danger',
      onOk: () => deleteMutation.mutate(id),
    });
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

  if (isError) {
    return <Alert message="Error fetching templates" description={error.message} type="error" />;
  }

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
      {!isLoading && (!data?.items || data.items.length === 0) ? (
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
    </div>
  );
};

export default Templates;
