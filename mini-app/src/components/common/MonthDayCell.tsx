import React, { useState } from 'react';
import { Button, Typography } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import type { Lesson } from './calendar-types';
import { statusColors, DEFAULT_DURATION } from './calendar-types';
import { spacing } from '../../theme/tokens';

const { Text } = Typography;

interface MonthDayCellProps {
  date: Dayjs;
  lessons: Lesson[];
  isToday: boolean;
  isCurrentMonth: boolean;
  isDark: boolean;
  isMobile: boolean;
  timezone: string;
  onDayClick: (date: Dayjs) => void;
  onAddLesson?: (date: string) => void;
}

/** Maximum lessons to show as dots on mobile */
const MAX_MOBILE_DOTS = 3;
/** Maximum lessons to show as blocks on desktop */
const MAX_DESKTOP_BLOCKS = 3;

const MonthDayCell: React.FC<MonthDayCellProps> = ({
  date,
  lessons,
  isToday,
  isCurrentMonth,
  isDark,
  isMobile,
  timezone,
  onDayClick,
  onAddLesson,
}) => {
  const [isHovered, setIsHovered] = useState(false);

  const handleClick = (e: React.MouseEvent) => {
    // If clicking on add button, don't trigger day click
    if ((e.target as HTMLElement).closest('button')) {
      return;
    }
    onDayClick(date);
  };

  const handleAddClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onAddLesson) {
      onAddLesson(date.format('YYYY-MM-DD'));
    }
  };

  // Background color
  const getBackground = () => {
    if (isToday) {
      return isDark ? 'rgba(24, 144, 255, 0.15)' : 'rgba(24, 144, 255, 0.08)';
    }
    if (!isCurrentMonth) {
      return isDark ? '#1a1a1a' : '#fafafa';
    }
    return isDark ? '#141414' : '#ffffff';
  };

  // Day number styling
  const getDayNumberStyle = (): React.CSSProperties => {
    const base: React.CSSProperties = {
      fontSize: isMobile ? 12 : 14,
      fontWeight: isToday ? 600 : 400,
      width: isMobile ? 22 : 26,
      height: isMobile ? 22 : 26,
      lineHeight: isMobile ? '22px' : '26px',
      textAlign: 'center',
      borderRadius: '50%',
      display: 'inline-block',
    };

    if (isToday) {
      return {
        ...base,
        background: '#1890ff',
        color: '#fff',
      };
    }

    if (!isCurrentMonth) {
      return {
        ...base,
        color: isDark ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.25)',
      };
    }

    return {
      ...base,
      color: isDark ? 'rgba(255,255,255,0.85)' : 'rgba(0,0,0,0.85)',
    };
  };

  // Render mobile dots
  const renderMobileDots = () => {
    if (lessons.length === 0) return null;

    const dotsToShow = lessons.slice(0, MAX_MOBILE_DOTS);
    const remaining = lessons.length - MAX_MOBILE_DOTS;

    return (
      <div style={{ 
        display: 'flex', 
        flexDirection: 'column',
        alignItems: 'center',
        gap: 2,
        marginTop: 2,
      }}>
        {/* Dots row */}
        <div style={{ display: 'flex', gap: 2 }}>
          {dotsToShow.map((lesson) => {
            const colors = statusColors[lesson.status];
            return (
              <div
                key={lesson.id}
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: colors.border,
                }}
              />
            );
          })}
        </div>
        {/* Count below dots */}
        {remaining > 0 && (
          <Text style={{ fontSize: 8, lineHeight: 1, color: isDark ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.45)' }}>
            +{remaining}
          </Text>
        )}
      </div>
    );
  };

  // Render desktop mini-blocks
  const renderDesktopBlocks = () => {
    if (lessons.length === 0) return null;

    const blocksToShow = lessons.slice(0, MAX_DESKTOP_BLOCKS);
    const remaining = lessons.length - MAX_DESKTOP_BLOCKS;

    return (
      <div style={{ 
        display: 'flex', 
        flexDirection: 'column', 
        gap: 2,
        marginTop: 4,
        overflow: 'hidden',
      }}>
        {blocksToShow.map((lesson) => {
          const colors = statusColors[lesson.status];
          const time = dayjs(lesson.scheduled_at).tz(timezone).format('HH:mm');
          const name = lesson.learner_name;
          
          return (
            <div
              key={lesson.id}
              style={{
                fontSize: 10,
                padding: '1px 4px',
                borderRadius: 3,
                background: isDark ? colors.bgDark : colors.bg,
                borderLeft: `2px solid ${colors.border}`,
                color: isDark ? 'rgba(255,255,255,0.85)' : colors.text,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {time}{name ? ` ${name}` : ''}
            </div>
          );
        })}
        {remaining > 0 && (
          <Text style={{ 
            fontSize: 10, 
            color: isDark ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.45)',
            textAlign: 'center',
          }}>
            +{remaining} ещё
          </Text>
        )}
      </div>
    );
  };

  return (
    <div
      onClick={handleClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        background: getBackground(),
        padding: isMobile ? 4 : spacing.xs,
        minHeight: isMobile ? 50 : 80,
        height: '100%',
        cursor: 'pointer',
        position: 'relative',
        transition: 'background 0.15s ease',
        borderBottom: `1px solid ${isDark ? '#303030' : '#f0f0f0'}`,
        borderRight: `1px solid ${isDark ? '#303030' : '#f0f0f0'}`,
        overflow: 'hidden',
      }}
    >
      {/* Day number */}
      <div style={{ textAlign: isMobile ? 'center' : 'left' }}>
        <span style={getDayNumberStyle()}>
          {date.date()}
        </span>
      </div>

      {/* Lessons */}
      {isMobile ? renderMobileDots() : renderDesktopBlocks()}

      {/* Add button on hover (desktop only) */}
      {!isMobile && onAddLesson && isHovered && (
        <Button
          type="text"
          size="small"
          icon={<PlusOutlined style={{ fontSize: 10 }} />}
          onClick={handleAddClick}
          style={{
            position: 'absolute',
            top: 2,
            right: 2,
            width: 20,
            height: 20,
            minWidth: 20,
            padding: 0,
            opacity: 0.6,
          }}
        />
      )}
    </div>
  );
};

export default MonthDayCell;
