import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Tag, Select, Space, Input, Button, message, Card, Calendar, Badge, Modal, List, theme } from 'antd';
import type { TableProps } from 'antd';
import { CalendarOutlined, UnorderedListOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import type { Dayjs } from 'dayjs';
import updateLocale from 'dayjs/plugin/updateLocale';
import 'dayjs/locale/ru';
import calendarLocale from 'antd/es/calendar/locale/ru_RU';
import api from '../services/api';
import { useDebounce } from '../hooks/useDebounce';
import { useResponsive } from '../hooks/useResponsive';
import LessonForm from '../components/forms/LessonForm';
import PageHeader from '../components/common/PageHeader';
import ResponsiveDataView from '../components/common/ResponsiveDataView';
import LessonCard from '../components/cards/LessonCard';
import { dayjsInTimezone, formatDate, formatDateTime, formatTime, DEFAULT_TIMEZONE } from '../utils/datetime';
import { spacing } from '../theme/tokens';

dayjs.extend(updateLocale);
dayjs.updateLocale('ru', { week: { dow: 1 } });
dayjs.locale('ru');

const calendarLocaleWithMonday = {
  ...calendarLocale,
  lang: {
    ...calendarLocale.lang,
    firstDayOfWeek: 1,
  },
};

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
  timezone: string;
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
  const { isMobile } = useResponsive();
  const { token } = theme.useToken();
  const [viewMode, setViewMode] = useState<'table' | 'calendar'>('table');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingLesson, setEditingLesson] = useState<Lesson | null>(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [lessonToDelete, setLessonToDelete] = useState<number | null>(null);
  const [selectedCalendarDate, setSelectedCalendarDate] = useState<Dayjs | null>(null);
  const [dayModalOpen, setDayModalOpen] = useState(false);

  const debouncedSearchTerm = useDebounce(searchTerm, 500);

  // Data for table view (with pagination and filters)
  const { data, isLoading } = useQuery<LessonListResponse, Error>({
    queryKey: ['lessons', currentPage, pageSize, statusFilter, debouncedSearchTerm],
    queryFn: () => fetchLessons(statusFilter, debouncedSearchTerm, pageSize, (currentPage - 1) * pageSize),
    placeholderData: (previousData) => previousData,
  });

  // Data for calendar view (all lessons, no pagination)
  const { data: calendarData } = useQuery<LessonListResponse, Error>({
    queryKey: ['lessons', 'calendar'],
    queryFn: () => fetchLessons(null, '', 1000, 0), // Load up to 1000 lessons for calendar
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
  }

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

  // Group lessons by date for calendar performance (use calendarData for calendar view)
  const lessonsByDate = useMemo(() => {
    const items = calendarData?.items || [];
    if (items.length === 0) return new Map<string, Lesson[]>();
    
    const grouped = new Map<string, Lesson[]>();
    items.forEach(lesson => {
      const dateKey = dayjsInTimezone(lesson.scheduled_at, lesson.timezone).format('YYYY-MM-DD');
      if (!grouped.has(dateKey)) {
        grouped.set(dateKey, []);
      }
      grouped.get(dateKey)!.push(lesson);
    });
    return grouped;
  }, [calendarData?.items]);

  // Get lessons content for a specific date (used in cellRender)
  const getLessonsContent = (dateKey: string) => {
    const lessonsOnDate = lessonsByDate.get(dateKey) || [];
    if (lessonsOnDate.length === 0) return null;

    // Mobile: Show dots only
    if (isMobile) {
      return (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 2, flexWrap: 'wrap' }}>
          {lessonsOnDate.slice(0, 3).map(lesson => (
            <Badge
              key={lesson.id}
              status={lesson.status === 'completed' ? 'success' : lesson.status === 'cancelled' ? 'error' : 'processing'}
            />
          ))}
          {lessonsOnDate.length > 3 && (
            <span style={{ fontSize: 10, color: token.colorTextSecondary }}>+{lessonsOnDate.length - 3}</span>
          )}
        </div>
      );
    }

    // Desktop: Show lesson list
    return (
      <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {lessonsOnDate.slice(0, 3).map(lesson => (
          <li key={lesson.id}>
            <Badge 
              status={lesson.status === 'completed' ? 'success' : lesson.status === 'cancelled' ? 'error' : 'processing'} 
              text={formatTime(lesson.scheduled_at, { timezone: lesson.timezone })} 
            />
          </li>
        ))}
        {lessonsOnDate.length > 3 && <li style={{ fontSize: 12, color: '#8c8c8c' }}>+{lessonsOnDate.length - 3} more</li>}
      </ul>
    );
  };

  // Calendar cell renderer - returns CONTENT to add to the cell (not replacing the date number)
  // In Ant Design 5.x cellRender, return null for no extra content, or JSX to add below the date
  const dateCellRender = (value: Dayjs) => {
    const dateKey = value.format('YYYY-MM-DD');
    return getLessonsContent(dateKey);
  };

  // Wrapper for cellRender that handles different cell types
  const cellRender = (current: Dayjs, info: { type: string }) => {
    if (info.type === 'date') return dateCellRender(current);
    return null;
  };

  const onCalendarSelect = (date: Dayjs) => {
    const dateKey = date.format('YYYY-MM-DD');
    const lessonsOnDate = lessonsByDate.get(dateKey) || [];
    
    if (lessonsOnDate.length > 0) {
      if (isMobile) {
        setSelectedCalendarDate(date);
        setDayModalOpen(true);
      } else {
        Modal.info({
          title: `Lessons on ${formatDate(date, { timezone: DEFAULT_TIMEZONE, format: 'YYYY-MM-DD' })}`,
          content: (
            <div>
              {lessonsOnDate.map(lesson => (
                <div key={lesson.id} style={{ marginBottom: 8 }}>
                  <Tag color={getStatusColor(lesson.status)}>{lesson.status}</Tag>
                  {formatTime(lesson.scheduled_at, { timezone: lesson.timezone })} - {lesson.duration_minutes || 60} min
                </div>
              ))}
            </div>
          ),
          width: 500,
        });
      }
    }
  };

  const selectedDateLessons = selectedCalendarDate 
    ? lessonsByDate.get(selectedCalendarDate.format('YYYY-MM-DD')) || []
    : [];

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
                onEdit={(l) => {
                  setEditingLesson(l);
                  setIsModalOpen(true);
                }}
                onDelete={handleDelete}
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
        <Card>
          <Calendar 
            locale={calendarLocaleWithMonday}
            cellRender={cellRender}
            onSelect={onCalendarSelect}
            fullscreen={!isMobile}
          />
        </Card>
      )}

      {/* Mobile: Day details modal for calendar */}
      <Modal
        open={dayModalOpen}
        title={selectedCalendarDate?.format('dddd, D MMMM')}
        onCancel={() => setDayModalOpen(false)}
        footer={null}
        width={isMobile ? '100%' : 400}
      >
        <List
          dataSource={selectedDateLessons}
          renderItem={(lesson) => (
            <List.Item
              onClick={() => {
                setDayModalOpen(false);
                setEditingLesson(lesson);
                setIsModalOpen(true);
              }}
              style={{ cursor: 'pointer', padding: spacing.sm }}
            >
              <Space>
                <Badge 
                  status={lesson.status === 'completed' ? 'success' : lesson.status === 'cancelled' ? 'error' : 'processing'} 
                />
                <span>{formatTime(lesson.scheduled_at, { timezone: lesson.timezone })}</span>
                <Tag color={getStatusColor(lesson.status)}>{lesson.status}</Tag>
                <span>{lesson.duration_minutes || 60} min</span>
              </Space>
            </List.Item>
          )}
        />
      </Modal>

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
        okButtonProps={{loading: deleteMutation.isPending }}
        >
        <p>Are you sure you want to delete this lesson?</p>
        <p style={{ color: '#8c8c8c' }}>This action cannot be undone.</p>
      </Modal>
    </div>
  );
};

export default Lessons;
