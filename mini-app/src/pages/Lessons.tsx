import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { message, Modal } from 'antd';
import dayjs from 'dayjs';
import updateLocale from 'dayjs/plugin/updateLocale';
import 'dayjs/locale/ru';
import { useTranslation } from 'react-i18next';
import api from '../services/api';
import LessonForm from '../components/forms/LessonForm';
import RescheduleForm from '../components/forms/RescheduleForm';
import PageHeader from '../components/common/PageHeader';
import CalendarContainer from '../components/common/CalendarContainer';
import { DEFAULT_TIMEZONE } from '../utils/datetime';
import { useAuth } from '../auth/AuthProvider';

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
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { tenantAccess } = useAuth();
  const canUseFullActions = !tenantAccess || tenantAccess.mode === 'full' || tenantAccess.bypass_access_restrictions;
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

  const { data: calendarData } = useQuery<LessonListResponse, Error>({
    queryKey: ['lessons', 'calendar', 'all'],
    queryFn: fetchAllLessons,
  });

  const updateMutation = useMutation({
    mutationFn: updateLesson,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lessons'] });
      setIsModalOpen(false);
      setEditingLesson(null);
      message.success(t('success.updated'));
    },
    onError: (error: Error) => {
      message.error(t('errors.updateFailed', { message: error.message }));
    }
  });

  const deleteMutation = useMutation({
    mutationFn: deleteLesson,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lessons'] });
      message.success(t('success.deleted'));
    },
    onError: (error: Error) => {
      console.error('Delete lesson error:', error);
      message.error(t('errors.deleteFailed', { message: error.message }));
    }
  });

  const handleFormFinish = (values: any) => {
    if (editingLesson) {
      updateMutation.mutate({ lessonId: editingLesson.id, values });
    }
  };

  const confirmDelete = () => {
    if (lessonToDelete) {
      deleteMutation.mutate(lessonToDelete);
      setDeleteModalOpen(false);
      setLessonToDelete(null);
    }
  };

  // Calendar handlers
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
          message.success(t('pages.lessons.lessonRescheduled'));
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
          message.success(t('pages.lessons.lessonCompleted'));
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
          message.success(t('pages.lessons.lessonCancelled'));
          setIsCancelLessonModalOpen(false);
          setSelectedLessonId(null);
        },
      }
    );
  };

  const handleDeleteFromCalendar = (lessonId: number) => {
    if (!canUseFullActions) {
      message.warning('Удаление уроков недоступно в grace-периоде. Можно отменить урок через смену статуса.');
      return;
    }
    setLessonToDelete(lessonId);
    setDeleteModalOpen(true);
  };

  return (
    <div>
      <PageHeader 
        title={t('pages.lessons.title')}
        subtitle={t('pages.lessons.subtitle')}
      />

      <CalendarContainer
        lessons={calendarData?.items || []}
        timezone={DEFAULT_TIMEZONE}
        onLessonClick={handleLessonClick}
        onReschedule={handleReschedule}
        onComplete={handleComplete}
        onCancel={handleCancel}
        onDelete={handleDeleteFromCalendar}
      />

      <LessonForm
        open={isModalOpen}
        onCancel={() => { setIsModalOpen(false); setEditingLesson(null); }}
        onFinish={handleFormFinish}
        isLoading={updateMutation.isPending}
        initialValues={editingLesson}
      />

      <Modal
        open={deleteModalOpen}
        title={t('pages.lessons.deleteTitle')}
        onCancel={() => setDeleteModalOpen(false)}
        onOk={confirmDelete}
        okText={t('common.delete')}
        cancelText={t('common.cancel')}
        okButtonProps={{ danger: true, loading: deleteMutation.isPending }}
      >
        <p>{t('pages.lessons.deleteConfirm')}</p>
        <p style={{ color: '#8c8c8c' }}>{t('pages.lessons.deleteIrreversible')}</p>
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
        title={t('pages.lessons.markCompleted')}
        open={isCompleteLessonModalOpen}
        onOk={confirmComplete}
        onCancel={() => {
          setIsCompleteLessonModalOpen(false);
          setSelectedLessonId(null);
        }}
        okText={t('common.confirm')}
        cancelText={t('common.cancel')}
        confirmLoading={updateMutation.isPending}
      >
        <p>{t('pages.lessons.markCompletedConfirm')}</p>
      </Modal>

      {/* Cancel Lesson Modal */}
      <Modal
        title={t('pages.lessons.cancelLesson')}
        open={isCancelLessonModalOpen}
        onOk={confirmCancel}
        onCancel={() => {
          setIsCancelLessonModalOpen(false);
          setSelectedLessonId(null);
        }}
        okText={t('common.yes')}
        cancelText={t('common.cancel')}
        okButtonProps={{ danger: true }}
        confirmLoading={updateMutation.isPending}
      >
        <p>{t('pages.lessons.cancelConfirm')}</p>
      </Modal>
    </div>
  );
};

export default Lessons;
