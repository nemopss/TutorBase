import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Card, Form, Input, message, Modal, Select, Space, Tag } from 'antd';
import type { TableProps } from 'antd';
import { PlusOutlined, TeamOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import PageHeader from '../components/common/PageHeader';
import ResponsiveDataView from '../components/common/ResponsiveDataView';
import api from '../services/api';

interface Learner {
  id: number;
  display_name: string;
}

interface LearnerListResponse {
  items: Learner[];
}

interface LearnerGroupMember {
  learner_id: number;
  display_name: string;
  status: string;
}

interface LearnerGroup {
  id: number;
  name: string;
  description?: string | null;
  color?: string | null;
  status: string;
  member_count: number;
  members: LearnerGroupMember[];
}

interface LearnerGroupFormValues {
  name: string;
  description?: string;
  color?: string;
  learner_ids?: number[];
}

const fetchGroups = async (): Promise<LearnerGroup[]> => {
  const { data } = await api.get('/groups');
  return data;
};

const fetchLearners = async (): Promise<Learner[]> => {
  const { data } = await api.get<LearnerListResponse>('/learners');
  return data.items;
};

const createGroup = async (values: LearnerGroupFormValues): Promise<LearnerGroup> => {
  const { data } = await api.post('/groups', {
    name: values.name,
    description: values.description || null,
    color: values.color || null,
    learner_ids: values.learner_ids ?? [],
  });
  return data;
};

const archiveGroup = async (groupId: number): Promise<LearnerGroup> => {
  const { data } = await api.patch(`/groups/${groupId}`, { status: 'archived' });
  return data;
};

const removeGroupMember = async ({ groupId, learnerId }: { groupId: number; learnerId: number }): Promise<LearnerGroup> => {
  const { data } = await api.delete(`/groups/${groupId}/members/${learnerId}`);
  return data;
};

const Groups: React.FC = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [form] = Form.useForm<LearnerGroupFormValues>();

  const groupsQuery = useQuery<LearnerGroup[], Error>({
    queryKey: ['learnerGroups'],
    queryFn: fetchGroups,
  });

  const learnersQuery = useQuery<Learner[], Error>({
    queryKey: ['learnersForGroups'],
    queryFn: fetchLearners,
  });

  const createMutation = useMutation({
    mutationFn: createGroup,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learnerGroups'] });
      message.success(t('pages.groups.groupCreated'));
      form.resetFields();
      setCreateModalOpen(false);
    },
    onError: (error: Error) => message.error(t('errors.createFailed', { message: error.message })),
  });

  const archiveMutation = useMutation({
    mutationFn: archiveGroup,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learnerGroups'] });
      message.success(t('pages.groups.groupArchived'));
    },
    onError: (error: Error) => message.error(t('errors.updateFailed', { message: error.message })),
  });

  const removeMemberMutation = useMutation({
    mutationFn: removeGroupMember,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['learnerGroups'] });
      message.success(t('pages.groups.memberRemoved'));
    },
    onError: (error: Error) => message.error(t('errors.updateFailed', { message: error.message })),
  });

  const learnerOptions = useMemo(
    () => (learnersQuery.data ?? []).map((learner) => ({ value: learner.id, label: learner.display_name })),
    [learnersQuery.data],
  );

  const columns: TableProps<LearnerGroup>['columns'] = [
    {
      title: t('pages.groups.name'),
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record) => (
        <Space>
          <span
            style={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              background: record.color || '#1677ff',
              display: 'inline-block',
            }}
          />
          <span>{name}</span>
        </Space>
      ),
    },
    {
      title: t('pages.groups.status'),
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => <Tag color={status === 'active' ? 'green' : 'default'}>{t(`pages.groups.statuses.${status}`)}</Tag>,
    },
    {
      title: t('pages.groups.members'),
      dataIndex: 'member_count',
      key: 'member_count',
    },
    {
      title: t('pages.groups.memberNames'),
      key: 'memberNames',
      render: (_, record) => record.members.length ? (
        <Space wrap>
          {record.members.map((member) => (
            <Tag key={member.learner_id}>{member.display_name}</Tag>
          ))}
        </Space>
      ) : '-',
    },
    {
      title: t('common.actions'),
      key: 'actions',
      render: (_, record) => (
        <Space wrap>
          {record.members.map((member) => (
            <Button
              key={member.learner_id}
              size="small"
              danger
              disabled={removeMemberMutation.isPending}
              onClick={() => removeMemberMutation.mutate({ groupId: record.id, learnerId: member.learner_id })}
            >
              {t('pages.groups.removeMember', { name: member.display_name })}
            </Button>
          ))}
          {record.status !== 'archived' && (
            <Button
              size="small"
              danger
              loading={archiveMutation.isPending}
              onClick={() => archiveMutation.mutate(record.id)}
            >
              {t('pages.groups.archive')}
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title={t('pages.groups.title')}
        subtitle={t('pages.groups.subtitle')}
        actions={(
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>
            {t('pages.groups.createGroup')}
          </Button>
        )}
      />

      <Alert
        type="info"
        showIcon
        message={t('pages.groups.noticeTitle')}
        description={t('pages.groups.noticeDescription')}
        style={{ marginBottom: 16 }}
      />

      {groupsQuery.error && (
        <Alert
          type="error"
          showIcon
          message={t('errors.loadFailed', { message: '' })}
          description={groupsQuery.error.message}
          style={{ marginBottom: 16 }}
        />
      )}

      <ResponsiveDataView<LearnerGroup>
        data={groupsQuery.data ?? []}
        loading={groupsQuery.isLoading}
        columns={columns}
        rowKey="id"
        emptyText={t('pages.groups.noGroups')}
        emptyDescription={t('pages.groups.noGroupsDescription')}
        emptyActionText={t('pages.groups.createGroup')}
        onEmptyAction={() => setCreateModalOpen(true)}
        renderCard={(group) => (
          <Card key={group.id} title={group.name} size="small" style={{ marginBottom: 12 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Tag color={group.status === 'active' ? 'green' : 'default'}>{t(`pages.groups.statuses.${group.status}`)}</Tag>
              <span>{group.description || t('pages.groups.noDescription')}</span>
              <Space wrap>
                {group.members.map((member) => (
                  <Tag key={member.learner_id}>{member.display_name}</Tag>
                ))}
              </Space>
              {group.status !== 'archived' && (
                <Button size="small" danger loading={archiveMutation.isPending} onClick={() => archiveMutation.mutate(group.id)}>
                  {t('pages.groups.archive')}
                </Button>
              )}
            </Space>
          </Card>
        )}
        pagination={false}
      />

      <Modal
        open={createModalOpen}
        title={t('pages.groups.createGroup')}
        okText={t('common.create')}
        cancelText={t('common.cancel')}
        confirmLoading={createMutation.isPending}
        onCancel={() => setCreateModalOpen(false)}
        onOk={() => form.submit()}
        destroyOnHidden
      >
        <Form<LearnerGroupFormValues>
          form={form}
          layout="vertical"
          onFinish={(values) => createMutation.mutate(values)}
        >
          <Form.Item name="name" label={t('pages.groups.name')} rules={[{ required: true }]}>
            <Input prefix={<TeamOutlined />} />
          </Form.Item>
          <Form.Item name="description" label={t('pages.groups.description')}>
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="color" label={t('pages.groups.color')}>
            <Input type="color" />
          </Form.Item>
          <Form.Item name="learner_ids" label={t('pages.groups.members')}>
            <Select
              mode="multiple"
              loading={learnersQuery.isLoading}
              options={learnerOptions}
              placeholder={t('pages.groups.selectLearners')}
              optionFilterProp="label"
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Groups;
