import type { Lesson } from '../components/common/calendar-types';
import api from './api';


export const fetchAllScheduleLessons = async (): Promise<{ items: Lesson[]; total: number }> => {
  const limit = 100;
  const items: Lesson[] = [];
  let total = 0;

  do {
    const { data } = await api.get<{ items: Lesson[]; total: number }>('/lessons', {
      params: {
        limit,
        offset: items.length,
        sort_by: 'scheduled_at',
        sort_order: 'asc',
      },
    });
    total = data.total;
    items.push(...data.items);
    if (data.items.length === 0) break;
  } while (items.length < total);

  return { items, total };
};
