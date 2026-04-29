import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Space, Modal, message, Alert } from 'antd';
import type { TableProps } from 'antd';
import { useTranslation } from 'react-i18next';
import api from '../services/api';
import { appEnv } from '../env';
import { devError, devLog } from '../utils/safeLogging';
import TemplateForm from '../components/forms/TemplateForm';
import PageHeader from '../components/common/PageHeader';
import ResponsiveDataView from '../components/common/ResponsiveDataView';
import TemplateCard from '../components/cards/TemplateCard';
import TenantContextRequired from '../components/common/TenantContextRequired';
import { useAuth } from '../auth/AuthProvider';

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
  const { t } = useTranslation();
  const { tenantId } = useAuth();
  const requiresTenantContext = tenantId === null;
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<Template | null>(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [templateToDelete, setTemplateToDelete] = useState<number | null>(null);

  const { data, isLoading, isError, error } = useQuery<TemplateListResponse, Error>({
    queryKey: ['templates'],
    queryFn: fetchTemplates,
    enabled: !requiresTenantContext,
  });

  // Debug logging for Android
  React.useEffect(() => {
    if (appEnv.isDev) {
      devLog('Templates Debug:', { 
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
      message.error(t('errors.serverError') + `: ${error.message}`);
    }
  };

  const createMutation = useMutation({ 
    mutationFn: createTemplate, 
    ...mutationOptions, 
    onSuccess: () => { 
      message.success(t('pages.templates.templateCreated')); 
      mutationOptions.onSuccess();
      setIsModalOpen(false);
    }
  });

  const updateMutation = useMutation({ 
    mutationFn: updateTemplate, 
    ...mutationOptions, 
    onSuccess: () => { 
      message.success(t('pages.templates.templateUpdated')); 
      mutationOptions.onSuccess();
      setIsModalOpen(false);
    }
  });

  const deleteMutation = useMutation({ 
    mutationFn: deleteTemplate, 
    onSuccess: () => { 
      queryClient.invalidateQueries({ queryKey: ['templates'] });
      message.success(t('pages.templates.templateDeleted'));
    },
    onError: (error: any) => {
      devError('Delete error:', error);
      message.error(t('errors.deleteFailed', { message: error.response?.data?.detail || error.message }));
    }
  });
  
  const duplicateMutation = useMutation({ 
    mutationFn: duplicateTemplate, 
    ...mutationOptions, 
    onSuccess: () => { 
      message.success(t('pages.templates.templateDuplicated')); 
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
      title: t('pages.templates.name'),
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: t('pages.templates.description'),
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: t('pages.templates.lessonCount'),
      dataIndex: 'lesson_count',
      key: 'lesson_count',
    },
    {
      title: t('pages.templates.durationDays'),
      dataIndex: 'duration_days',
      key: 'duration_days',
    },
    {
      title: t('common.actions'),
      key: 'actions',
      render: (_, record) => (
        <Space size="middle">
          <Button type="link" onClick={() => { setEditingTemplate(record); setIsModalOpen(true); }}>{t('common.edit')}</Button>
          <Button type="link" onClick={() => duplicateMutation.mutate(record.id)}>{t('pages.templates.duplicate')}</Button>
          <Button type="link" danger onClick={() => handleDelete(record.id)}>{t('common.delete')}</Button>
        </Space>
      ),
    },
  ];

  // Show error inline instead of blocking entire page
  const showError = isError && error;

  if (requiresTenantContext) {
    return (
      <div>
        <PageHeader
          title={t('pages.templates.title')}
          subtitle={t('pages.templates.subtitle')}
          actions={
            <Button type="primary" disabled>
              {t('pages.templates.createTemplate')}
            </Button>
          }
        />
        <TenantContextRequired sectionLabel={t('pages.templates.title')} />
      </div>
    );
  }

  return (
    <div>
      <PageHeader 
        title={t('pages.templates.title')}
        subtitle={t('pages.templates.subtitle')}
        actions={
          <Button type="primary" onClick={() => { setEditingTemplate(null); setIsModalOpen(true); }}>
            {t('pages.templates.createTemplate')}
          </Button>
        }
      />
      {showError && (
        <Alert 
          message={t('errors.loadFailed', { message: '' })} 
          description={error.message} 
          type="error" 
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}
      <ResponsiveDataView<Template>
        data={data?.items || []}
        loading={isLoading}
        columns={columns}
        rowKey="id"
        emptyText={t('pages.templates.noTemplates')}
        emptyDescription={t('pages.templates.noTemplatesDescription')}
        emptyActionText={t('pages.templates.createTemplate')}
        onEmptyAction={() => { setEditingTemplate(null); setIsModalOpen(true); }}
        renderCard={(template) => (
          <TemplateCard
            key={template.id}
            template={template}
            onEdit={(tmpl) => {
              setEditingTemplate(tmpl);
              setIsModalOpen(true);
            }}
            onDuplicate={(id) => duplicateMutation.mutate(id)}
            onDelete={handleDelete}
          />
        )}
        tableProps={{
          scroll: { x: 700 },
          bordered: true,
        }}
        pagination={false}
      />
      <TemplateForm 
        open={isModalOpen}
        onCancel={() => setIsModalOpen(false)}
        onFinish={handleFormFinish}
        isLoading={createMutation.isPending || updateMutation.isPending}
        initialValues={editingTemplate}
      />

      <Modal
        open={deleteModalOpen}
        title={t('pages.templates.deleteTitle')}
        onCancel={() => setDeleteModalOpen(false)}
        onOk={confirmDelete}
        okText={t('common.delete')}
        cancelText={t('common.cancel')}
        okType="danger"
        confirmLoading={deleteMutation.isPending}
      >
        <p>{t('pages.templates.deleteConfirm')}</p>
        <p style={{ color: '#8c8c8c' }}>{t('pages.templates.deleteIrreversible')}</p>
      </Modal>
    </div>
  );
};

export default Templates;
