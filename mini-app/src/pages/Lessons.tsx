import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Tag, Select, Space, Input, Button, message, Modal } from 'antd';
import type { TableProps } from 'antd';
import { CalendarOutlined, UnorderedListOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import updateLocale from 'dayjs/plugin/updateLocale';
import 'dayjs/locale/ru';
import api from '../services/api';
import { useDebounce } from '../hooks/useDebounce';
import LessonForm from '../components/forms/LessonForm';
import RescheduleForm from '../components/forms/RescheduleForm';
import PageHeader from '../components/common/PageHeader';
import ResponsiveDataView from '../components/common/ResponsiveDataView';
import LessonCard from '../components/cards/LessonCard';
import WeekCalendar from '../components/common/WeekCalendar';
import { dayjsInTimezone, formatDateTime, DEFAULT_TIMEZONE } from '../utils/datetime';

dayjs.extend(updateLocale);
dayjs.updateLocale('ru', { week: { dow: 1 } });
dayjs.locale('ru');

// --- Types --- //
type LessonStatus = 'scheduled' | 'rescheduled' | 'completed' | 'cancelled';

interface Lesson {
  id: number;
  package_id: number;
  package_title?: string;
  learner_name?: string;
  scheduled_at: string;
  status: LessonStatus;
  duration_minutes?: number;
  teacher_notes?: string;
  sequence_index?: number;
  timezone: string;
}

interface LessonListResponse {
  total: number;
  items: Lesson[];
}

const STATUS_OPTIONS = [
  { value: 'scheduled', label: 'Scheduled' },
  { value: 'rescheduled', label: 'Rescheduled' },
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

// Fetch all lessons with pagination (API limit is 100 per request)
const fetchAllLessons = async (): Promise<LessonListResponse> => {
  const limit = 100;
  let allItems: Lesson[] = [];
  let offset = 0;
  let total = 0;
  
  // First request to get total count
  const firstResponse = await fetchLessons(null, '', limit, 0);
  allItems = [...firstResponse.items];
  total = firstResponse.total;
  offset = limit;
  
  // Fetch remaining pages if needed
  while (offset < total && offset < 1000) { // Safety limit of 1000
    const response = await fetchLessons(null, '', limit, offset);
    allItems = [...allItems, ...response.items];
    offset += limit;
  }
  
  return { items: allItems, total };
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
  const [viewMode, setViewMode] = useState<'table' | 'calendar'>('calendar');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingLesson, setEditingLesson] = useState<Lesson | null>(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [lessonToDelete, setLessonToDelete] = useState<number | null>(null);
  
  // Reschedule modal state
  const [isRescheduleModalOpen, setIsRescheduleModalOpen] = useState(false);
  const [selectedLessonId, setSelectedLessonId] = useState<number | null>(null);
  const [selectedLesson, setSelectedLesson] = useState<Lesson | null>(null);
  
  // Complete/Cancel confirmation modals
  const [isCompleteLessonModalOpen, setIsCompleteLessonModalOpen] = useState(false);
  const [isCancelLessonModalOpen, setIsCancelLessonModalOpen] = useState(false);

  const debouncedSearchTerm = useDebounce(searchTerm, 500);

  // Data for table view (with pagination and filters)
  const { data, isLoading } = useQuery<LessonListResponse, Error>({
    queryKey: ['lessons', currentPage, pageSize, statusFilter, debouncedSearchTerm],
    queryFn: () => fetchLessons(statusFilter, debouncedSearchTerm, pageSize, (currentPage - 1) * pageSize),
    placeholderData: (previousData) => previousData,
  });

  // Data for calendar view (all lessons with pagination - API limit is 100)
  const { data: calendarData } = useQuery<LessonListResponse, Error>({
    queryKey: ['lessons', 'calendar', 'all'],
    queryFn: fetchAllLessons,
    enabled: viewMode === 'calendar', // Only fetch when calendar is visible
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
      console.error('Delete lesson error:', error);
      message.error(`Failed to delete lesson: ${error.message}`);
    }
  });

  const handleFormFinish = (values: any) => {
    if (editingLesson) {
      updateMutation.mutate({ lessonId: editingLesson.id, values });
    }
  };

  const handleDelete = (id: number) => {
    setLessonToDelete(id);
    setDeleteModalOpen(true);
  };

  const confirmDelete = () => {
    if (lessonToDelete) {
      deleteMutation.mutate(lessonToDelete);
      setDeleteModalOpen(false);
      setLessonToDelete(null);
    }
  };

  // WeekCalendar handlers
  const handleLessonClick = (lessonId: number) => {
    const lesson = calendarData?.items.find((l: Lesson) => l.id === lessonId);
    if (lesson) {
      setEditingLesson(lesson);
      setIsModalOpen(true);
    }
  };

  const handleReschedule = (lessonId: number, newDate?: string) => {
    const lesson = calendarData?.items.find((l: Lesson) => l.id === lessonId);
    if (newDate && lesson) {
      // Drag & drop reschedule - update directly
      updateMutation.mutate({
        lessonId,
        values: { scheduled_at: newDate, status: 'rescheduled' },
      });
    } else {
      // Context menu reschedule - open modal
      setSelectedLesson(lesson || null);
      setSelectedLessonId(lessonId);
      setIsRescheduleModalOpen(true);
    }
  };

  const handleRescheduleSubmit = (values: { date: dayjs.Dayjs; time: dayjs.Dayjs; duration_minutes?: number }) => {
    if (!selectedLessonId) return;
    const newDateTime = values.date
      .hour(values.time.hour())
      .minute(values.time.minute())
      .second(0);
    const updateValues: any = { 
      scheduled_at: newDateTime.toISOString(), 
      status: 'rescheduled' 
    };
    if (values.duration_minutes) {
      updateValues.duration_minutes = values.duration_minutes;
    }
    updateMutation.mutate(
      { lessonId: selectedLessonId, values: updateValues },
      {
        onSuccess: () => {
          message.success('Lesson rescheduled');
          setIsRescheduleModalOpen(false);
          setSelectedLessonId(null);
          setSelectedLesson(null);
        },
      }
    );
  };

  const handleComplete = (lessonId: number) => {
    setSelectedLessonId(lessonId);
    setIsCompleteLessonModalOpen(true);
  };

  const confirmComplete = () => {
    if (!selectedLessonId) return;
    updateMutation.mutate(
      { lessonId: selectedLessonId, values: { status: 'completed' } },
      {
        onSuccess: () => {
          message.success('Lesson marked as completed');
          setIsCompleteLessonModalOpen(false);
          setSelectedLessonId(null);
        },
      }
    );
  };

  const handleCancel = (lessonId: number) => {
    setSelectedLessonId(lessonId);
    setIsCancelLessonModalOpen(true);
  };

  const confirmCancel = () => {
    if (!selectedLessonId) return;
    updateMutation.mutate(
      { lessonId: selectedLessonId, values: { status: 'cancelled' } },
      {
        onSuccess: () => {
          message.success('Lesson cancelled');
          setIsCancelLessonModalOpen(false);
          setSelectedLessonId(null);
        },
      }
    );
  };

  const handleDeleteFromCalendar = (lessonId: number) => {
    setLessonToDelete(lessonId);
    setDeleteModalOpen(true);
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'scheduled': return 'blue';
      case 'rescheduled': return 'gold';
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
      render: (_: string, record) => formatDateTime(record.scheduled_at, { timezone: record.timezone }),
      sorter: (a, b) => dayjsInTimezone(a.scheduled_at, a.timezone).valueOf() - dayjsInTimezone(b.scheduled_at, b.timezone).valueOf(),
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
    setCurrentPage(pagination.current || 1);
    setPageSize(pagination.pageSize || 10);
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

          <ResponsiveDataView<Lesson>
            data={data?.items || []}
            loading={isLoading}
            columns={columns}
            rowKey="id"
            emptyText="No lessons found"
            emptyDescription="Lessons will appear here once you create packages and schedule lessons"
            renderCard={(lesson) => (
              <LessonCard
                key={lesson.id}
                lesson={lesson}
                timezone={lesson.timezone || DEFAULT_TIMEZONE}
                onReschedule={(id) => {
                  const l = data?.items.find((item: Lesson) => item.id === id);
                  if (l) {
                    setSelectedLesson(l);
                    setSelectedLessonId(id);
                    setIsRescheduleModalOpen(true);
                  }
                }}
                onComplete={handleComplete}
                onCancel={handleCancel}
                onDelete={handleDelete}
                onClick={(id) => {
                  const l = data?.items.find((item: Lesson) => item.id === id);
                  if (l) {
                    setEditingLesson(l);
                    setIsModalOpen(true);
                  }
                }}
              />
            )}
            tableProps={{
              scroll: { x: 900 },
              onChange: handleTableChange,
              bordered: true,
            }}
            pagination={{
              current: currentPage,
              pageSize: pageSize,
              total: data?.total,
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total, range) => `${range[0]}-${range[1]} of ${total} lessons`,
            }}
          />
        </>
      ) : (
        <WeekCalendar
          lessons={calendarData?.items || []}
          timezone={DEFAULT_TIMEZONE}
          onLessonClick={handleLessonClick}
          onReschedule={handleReschedule}
          onComplete={handleComplete}
          onCancel={handleCancel}
          onDelete={handleDeleteFromCalendar}
        />
      )}

      <LessonForm
        open={isModalOpen}
        onCancel={() => { setIsModalOpen(false); setEditingLesson(null); }}
        onFinish={handleFormFinish}
        isLoading={updateMutation.isPending}
        initialValues={editingLesson}
      />

      <Modal
        open={deleteModalOpen}
        title="Delete Lesson"
        onCancel={() => setDeleteModalOpen(false)}
        onOk={confirmDelete}
        okText="Delete"
        okButtonProps={{ danger: true, loading: deleteMutation.isPending }}
      >
        <p>Are you sure you want to delete this lesson?</p>
        <p style={{ color: '#8c8c8c' }}>This action cannot be undone.</p>
      </Modal>

      {/* Reschedule Modal */}
      <RescheduleForm
        open={isRescheduleModalOpen}
        onCancel={() => {
          setIsRescheduleModalOpen(false);
          setSelectedLessonId(null);
          setSelectedLesson(null);
        }}
        onFinish={handleRescheduleSubmit}
        isLoading={updateMutation.isPending}
        currentDateTime={selectedLesson?.scheduled_at}
        currentDuration={selectedLesson?.duration_minutes}
      />

      {/* Complete Lesson Modal */}
      <Modal
        title="Mark as Completed"
        open={isCompleteLessonModalOpen}
        onOk={confirmComplete}
        onCancel={() => {
          setIsCompleteLessonModalOpen(false);
          setSelectedLessonId(null);
        }}
        okText="Complete"
        confirmLoading={updateMutation.isPending}
      >
        <p>Mark this lesson as completed?</p>
      </Modal>

      {/* Cancel Lesson Modal */}
      <Modal
        title="Cancel Lesson"
        open={isCancelLessonModalOpen}
        onOk={confirmCancel}
        onCancel={() => {
          setIsCancelLessonModalOpen(false);
          setSelectedLessonId(null);
        }}
        okText="Yes, Cancel"
        okButtonProps={{ danger: true }}
        confirmLoading={updateMutation.isPending}
      >
        <p>Are you sure you want to cancel this lesson?</p>
      </Modal>
    </div>
  );
};

export default Lessons;
