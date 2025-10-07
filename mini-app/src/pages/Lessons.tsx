import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Table, Tag, Select, Space, Input, Button, message, Card, Calendar, Badge, Modal } from 'antd';
import type { TableProps } from 'antd';
import { CalendarOutlined, UnorderedListOutlined } from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';
import api from '../services/api';
import { useDebounce } from '../hooks/useDebounce';
import LessonForm from '../components/forms/LessonForm';
import PageHeader from '../components/common/PageHeader';
import EmptyState from '../components/common/EmptyState';

// --- Types --- //
interface Lesson {
  id: number;
  package_id: number;
  package_title?: string;
  learner_name?: string;
  scheduled_at: string;
  status: string;
  duration_minutes?: number;
  teacher_notes?: string;
  sequence_index?: number;
}

interface LessonListResponse {
  total: number;
  items: Lesson[];
}

const STATUS_OPTIONS = [
  { value: 'scheduled', label: 'Scheduled' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
];

// --- API Fetchers --- //
const fetchLessons = async (status: string | null, search: string, limit: number, offset: number): Promise<LessonListResponse> => {
  const { data } = await api.get('/lessons', {
    params: {
      status: status || undefined,
      search: search || undefined,
      limit,
      offset,
      sort_by: 'scheduled_at',
      sort_order: 'asc',
    },
  });
  return data;
};

const updateLesson = async ({ lessonId, values }: { lessonId: number; values: any }) => {
  const { data } = await api.patch(`/lessons/${lessonId}`, values);
  return data;
};

const deleteLesson = async (lessonId: number) => {
  await api.delete(`/lessons/${lessonId}`);
};

// --- Component --- //
const Lessons: React.FC = () => {
  const queryClient = useQueryClient();
  const [viewMode, setViewMode] = useState<'table' | 'calendar'>('table');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingLesson, setEditingLesson] = useState<Lesson | null>(null);
  const [selectedDate, setSelectedDate] = useState<Dayjs>(dayjs());

  const debouncedSearchTerm = useDebounce(searchTerm, 500);

  const { data, isLoading } = useQuery<LessonListResponse, Error>({
    queryKey: ['lessons', currentPage, pageSize, statusFilter, debouncedSearchTerm],
    queryFn: () => fetchLessons(statusFilter, debouncedSearchTerm, pageSize, (currentPage - 1) * pageSize),
    placeholderData: (previousData) => previousData,
  });

  const updateMutation = useMutation({
    mutationFn: updateLesson,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lessons'] });
      setIsModalOpen(false);
      setEditingLesson(null);
      message.success('Lesson updated successfully!');
    },
    onError: (error: Error) => {
      message.error(`An error occurred: ${error.message}`);
    }
  });

  const deleteMutation = useMutation({
    mutationFn: deleteLesson,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lessons'] });
      message.success('Lesson deleted successfully!');
    },
    onError: (error: Error) => {
      message.error(`Failed to delete lesson: ${error.message}`);
    }
  });

  const handleFormFinish = (values: any) => {
    if (editingLesson) {
      updateMutation.mutate({ lessonId: editingLesson.id, values });
    }
  };

  const handleDelete = (id: number) => {
    Modal.confirm({
      title: 'Are you sure you want to delete this lesson?',
      content: 'This action cannot be undone.',
      okText: 'Yes, delete it',
      okType: 'danger',
      onOk: () => deleteMutation.mutate(id),
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'scheduled': return 'blue';
      case 'completed': return 'green';
      case 'cancelled': return 'red';
      default: return 'default';
    }
  };

  const columns: TableProps<Lesson>['columns'] = [
    {
      title: 'Scheduled At',
      dataIndex: 'scheduled_at',
      key: 'scheduled_at',
      render: (text: string) => dayjs(text).format('YYYY-MM-DD HH:mm'),
      sorter: (a, b) => dayjs(a.scheduled_at).unix() - dayjs(b.scheduled_at).unix(),
      width: 180,
    },
    {
      title: 'Package',
      dataIndex: 'package_title',
      key: 'package_title',
      render: (title: string) => title || '-',
      ellipsis: true,
    },
    {
      title: 'Learner',
      dataIndex: 'learner_name',
      key: 'learner_name',
      render: (name: string) => name || '-',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => <Tag color={getStatusColor(status)}>{status.toUpperCase()}</Tag>,
      filters: STATUS_OPTIONS.map(option => ({ text: option.label, value: option.value })),
      onFilter: (value, record) => record.status === value,
      width: 120,
    },
    {
      title: 'Duration',
      dataIndex: 'duration_minutes',
      key: 'duration_minutes',
      render: (duration: number) => duration ? `${duration} min` : '-',
      width: 100,
    },
    {
      title: 'Notes',
      dataIndex: 'teacher_notes',
      key: 'teacher_notes',
      render: (notes: string) => notes ? notes.substring(0, 40) + (notes.length > 40 ? '...' : '') : '-',
      ellipsis: true,
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 150,
      render: (_, record) => (
        <Space size="small">
          <Button type="link" size="small" onClick={() => { setEditingLesson(record); setIsModalOpen(true); }}>Edit</Button>
          <Button type="link" size="small" danger onClick={() => handleDelete(record.id)}>Delete</Button>
        </Space>
      ),
    },
  ];

  const handleTableChange = (pagination: any) => {
    setCurrentPage(pagination.current);
    setPageSize(pagination.pageSize);
  };

  // Calendar cell renderer
  const dateCellRender = (value: Dayjs) => {
    const lessonsOnDate = data?.items.filter(lesson => 
      dayjs(lesson.scheduled_at).isSame(value, 'day')
    ) || [];
    
    return (
      <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {lessonsOnDate.slice(0, 3).map(lesson => (
          <li key={lesson.id}>
            <Badge 
              status={lesson.status === 'completed' ? 'success' : lesson.status === 'cancelled' ? 'error' : 'processing'} 
              text={dayjs(lesson.scheduled_at).format('HH:mm')} 
            />
          </li>
        ))}
        {lessonsOnDate.length > 3 && <li style={{ fontSize: 12, color: '#8c8c8c' }}>+{lessonsOnDate.length - 3} more</li>}
      </ul>
    );
  };

  const onCalendarSelect = (date: Dayjs) => {
    setSelectedDate(date);
    const lessonsOnDate = data?.items.filter(lesson => 
      dayjs(lesson.scheduled_at).isSame(date, 'day')
    ) || [];
    
    if (lessonsOnDate.length > 0) {
      Modal.info({
        title: `Lessons on ${date.format('YYYY-MM-DD')}`,
        content: (
          <div>
            {lessonsOnDate.map(lesson => (
              <div key={lesson.id} style={{ marginBottom: 8 }}>
                <Tag color={getStatusColor(lesson.status)}>{lesson.status}</Tag>
                {dayjs(lesson.scheduled_at).format('HH:mm')} - {lesson.duration_minutes || 60} min
              </div>
            ))}
          </div>
        ),
        width: 500,
      });
    }
  };

  return (
    <div>
      <PageHeader 
        title="Lessons"
        subtitle="View and manage all lessons"
        actions={
          <Space>
            <Button 
              icon={<UnorderedListOutlined />} 
              type={viewMode === 'table' ? 'primary' : 'default'}
              onClick={() => setViewMode('table')}
            >
              Table
            </Button>
            <Button 
              icon={<CalendarOutlined />} 
              type={viewMode === 'calendar' ? 'primary' : 'default'}
              onClick={() => setViewMode('calendar')}
            >
              Calendar
            </Button>
          </Space>
        }
      />

      {viewMode === 'table' ? (
        <>
          <Space style={{ marginBottom: 16 }} wrap>
            <Input.Search
              placeholder="Search lessons..."
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
              title="No lessons found"
              description="Lessons will appear here once you create packages and schedule lessons"
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
                showTotal: (total, range) => `${range[0]}-${range[1]} of ${total} lessons`,
              }}
              onChange={handleTableChange}
              bordered
            />
          )}
        </>
      ) : (
        <Card>
          <Calendar 
            cellRender={dateCellRender}
            onSelect={onCalendarSelect}
          />
        </Card>
      )}

      <LessonForm
        open={isModalOpen}
        onCancel={() => { setIsModalOpen(false); setEditingLesson(null); }}
        onFinish={handleFormFinish}
        isLoading={updateMutation.isPending}
        initialValues={editingLesson}
      />
    </div>
  );
};

export default Lessons;
