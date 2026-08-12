import api from '../../services/api';
import { fetchAllScheduleLessons } from '../../services/scheduleLessons';

jest.mock('../../services/api', () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
  },
}));

const getMock = api.get as jest.Mock;

describe('student schedule loading', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('loads every API page instead of silently truncating after 100 lessons', async () => {
    const firstPage = Array.from({ length: 100 }, (_, index) => ({
      id: index + 1,
      scheduled_at: '2026-01-01T09:00:00Z',
      status: 'scheduled',
    }));
    const secondPage = [{
      id: 101,
      scheduled_at: '2026-12-01T09:00:00Z',
      status: 'scheduled',
    }];
    getMock
      .mockResolvedValueOnce({ data: { items: firstPage, total: 101 } })
      .mockResolvedValueOnce({ data: { items: secondPage, total: 101 } });

    const result = await fetchAllScheduleLessons();

    expect(result.items).toHaveLength(101);
    expect(getMock).toHaveBeenNthCalledWith(1, '/lessons', {
      params: expect.objectContaining({ limit: 100, offset: 0 }),
    });
    expect(getMock).toHaveBeenNthCalledWith(2, '/lessons', {
      params: expect.objectContaining({ limit: 100, offset: 100 }),
    });
  });
});
