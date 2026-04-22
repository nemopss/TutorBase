import React, { useMemo } from 'react';
import { Typography } from 'antd';
import dayjs from 'dayjs';
import { useTranslation } from 'react-i18next';
import { useResponsive } from '../../hooks/useResponsive';
import { useTheme } from '../../theme/ThemeProvider';

const { Text } = Typography;

interface DashboardHistoryWeekPoint {
  week_start: string;
  hours: number;
  lessons_count: number;
}

interface DashboardWeeklyLoadProps {
  weeks: DashboardHistoryWeekPoint[];
}

const MOBILE_WEEKS = 8;

const formatHours = (value: number): string => {
  if (Number.isInteger(value)) {
    return String(value);
  }
  return value.toFixed(1).replace(/\.0$/, '');
};

const getBarColor = (hours: number, colors: ReturnType<typeof useTheme>['resolvedTheme']['colors']): string => {
  if (hours <= 6) {
    return colors.accentSuccess;
  }
  if (hours <= 12) {
    return '#d9a441';
  }
  return colors.accentError;
};

const DashboardWeeklyLoad: React.FC<DashboardWeeklyLoadProps> = ({ weeks }) => {
  const { t } = useTranslation();
  const { isMobile } = useResponsive();
  const { resolvedTheme } = useTheme();
  const colors = resolvedTheme.colors;

  const visibleWeeks = useMemo(
    () => (isMobile ? weeks.slice(-MOBILE_WEEKS) : weeks),
    [isMobile, weeks],
  );

  const maxHours = useMemo(
    () => Math.max(0, ...visibleWeeks.map((week) => week.hours)),
    [visibleWeeks],
  );

  if (maxHours <= 0) {
    return (
      <div
        style={{
          flex: 1,
          minHeight: 180,
          borderRadius: 8,
          background: colors.bgTertiary,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 16,
        }}
      >
        <Text type="secondary">{t('pages.dashboard.level3.weeklyLoad.empty')}</Text>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {visibleWeeks.map((week) => {
        const weekStart = dayjs(week.week_start);
        const weekEnd = weekStart.add(6, 'day');
        const width = maxHours > 0 ? `${Math.max((week.hours / maxHours) * 100, week.hours > 0 ? 8 : 0)}%` : '0%';

        return (
          <div key={week.week_start} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'baseline' }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {weekStart.format('D MMM')} - {weekEnd.format('D MMM')}
              </Text>
              <Text strong style={{ whiteSpace: 'nowrap' }}>
                {t('pages.dashboard.level3.weeklyLoad.hoursLabel', { hours: formatHours(week.hours) })}
              </Text>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div
                style={{
                  flex: 1,
                  minWidth: 0,
                  height: 8,
                  borderRadius: 999,
                  background: colors.bgTertiary,
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    width,
                    height: '100%',
                    borderRadius: 999,
                    background: getBarColor(week.hours, colors),
                  }}
                />
              </div>
              <Text type="secondary" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>
                {t('pages.dashboard.level3.weeklyLoad.lessonsLabel', {
                  count: week.lessons_count,
                })}
              </Text>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default DashboardWeeklyLoad;
