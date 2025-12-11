import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { Button, Typography } from 'antd';
import { LeftOutlined, RightOutlined, PlusOutlined } from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import weekOfYear from 'dayjs/plugin/weekOfYear';
import isoWeek from 'dayjs/plugin/isoWeek';
import isSameOrAfter from 'dayjs/plugin/isSameOrAfter';
import isSameOrBefore from 'dayjs/plugin/isSameOrBefore';
import { useThemeMode } from '../../theme/ThemeProvider';
import { spacing } from '../../theme/tokens';
import { useResponsive } from '../../hooks/useResponsive';
import { useLongPress } from '../../hooks/useLongPress';
import { useCarouselSwipe } from '../../hooks/useCarouselSwipe';
import { useDragAndDrop } from '../../hooks/useDragAndDrop';
import TimeScale, { PIXELS_PER_HOUR, TIME_SCALE_WIDTH, TOTAL_HEIGHT } from './TimeScale';
import LessonContextMenu from './LessonContextMenu';
import CurrentTimeIndicator from './CurrentTimeIndicator';
import type { Lesson } from './calendar-types';
import { statusColors, DEFAULT_DURATION, DAYS_FULL } from './calendar-types';

dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.extend(weekOfYear);
dayjs.extend(isoWeek);
dayjs.extend(isSameOrAfter);
dayjs.extend(isSameOrBefore);

const { Text } = Typography;

interface WeekCalendarProps {
  lessons: Lesson[];
  timezone: string;
  onLessonClick: (lessonId: number) => void;
  onAddLesson?: (date: string) => void;
  onReschedule?: (lessonId: number, newDate?: string) => void;
  onComplete?: (lessonId: number) => void;
  onCancel?: (lessonId: number) => void;
  onDelete?: (lessonId: number) => void;
}

// Responsive constants
const MOBILE_DAY_COUNT = 3;
const DESKTOP_DAY_COUNT = 7;

// Time-based positioning constants
const MIN_LESSON_HEIGHT = 30; // Minimum height for very short lessons
const DEFAULT_SCROLL_HOUR = 8; // Default scroll to 08:00

/**
 * Calculate lesson height based on duration.
 * Height = (duration_minutes / 60) * PIXELS_PER_HOUR
 */
const getLessonHeight = (duration?: number): number => {
  const mins = duration || DEFAULT_DURATION;
  return Math.max(MIN_LESSON_HEIGHT, (mins / 60) * PIXELS_PER_HOUR);
};

/**
 * Calculate lesson top position based on scheduled time.
 * Top = (hour * PIXELS_PER_HOUR) + (minutes / 60 * PIXELS_PER_HOUR)
 */
const getLessonTop = (scheduledAt: string, tz: string): number => {
  const time = dayjs(scheduledAt).tz(tz);
  const hour = time.hour();
  const minutes = time.minute();
  return (hour * PIXELS_PER_HOUR) + (minutes / 60 * PIXELS_PER_HOUR);
};

/**
 * Day column component with time-based lesson positioning.
 */
interface DayColumnProps {
  dateKey: string;
  lessons: Lesson[];
  isToday: boolean;
  isDark: boolean;
  timezone: string;
  onLessonClick: (lessonId: number) => void;
  onAddLesson?: (date: string) => void;
  onContextMenu: (lessonId: number, position: { x: number; y: number }) => void;
  // Drag & drop props
  isDropTarget?: boolean;
  draggedLessonId?: number | null;
  getDragHandlers?: (id: number) => {
    onMouseDown: (e: React.MouseEvent) => void;
    onTouchStart: (e: React.TouchEvent) => void;
  };
  // Drag preview
  dragPreview?: {
    hour: number;
    minute: number;
    duration: number;
  } | null;
  // Global drag flag
  wasDragPerformedRef?: React.MutableRefObject<boolean>;
  onMouseEnter?: (e: React.MouseEvent) => void;
  onMouseLeave?: (e: React.MouseEvent) => void;
  onMouseUp?: (e: React.MouseEvent) => void;
  onTouchMove?: (e: React.TouchEvent) => void;
  onTouchEnd?: (e: React.TouchEvent) => void;
}

const DayColumn: React.FC<DayColumnProps> = ({
  dateKey,
  lessons,
  isToday,
  isDark,
  timezone: tz,
  onLessonClick,
  onAddLesson,
  onContextMenu,
  isDropTarget,
  draggedLessonId,
  getDragHandlers,
  dragPreview,
  wasDragPerformedRef,
  onMouseEnter: onDropMouseEnter,
  onMouseLeave: onDropMouseLeave,
  onMouseUp: onDropMouseUp,
  onTouchMove: onDropTouchMove,
  onTouchEnd: onDropTouchEnd,
}) => {
  const [isHovered, setIsHovered] = useState(false);

  // Determine background color based on drop target state
  const getBackground = () => {
    if (isDropTarget) {
      return isDark ? 'rgba(24, 144, 255, 0.2)' : 'rgba(24, 144, 255, 0.1)';
    }
    if (isToday) {
      return isDark ? '#1a1a2e' : '#f0f7ff';
    }
    return isDark ? '#141414' : '#ffffff';
  };

  const handleMouseEnter = (e: React.MouseEvent) => {
    setIsHovered(true);
    onDropMouseEnter?.(e);
  };

  const handleMouseLeave = (e: React.MouseEvent) => {
    setIsHovered(false);
    onDropMouseLeave?.(e);
  };

  // Handle click on empty space to add lesson
  const handleColumnClick = (e: React.MouseEvent) => {
    // Only add lesson if clicking on empty space AND not after a drag operation
    const wasDragged = wasDragPerformedRef?.current || false;
    if (wasDragged) {
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    if (e.target === e.currentTarget && onAddLesson) {
      onAddLesson(dateKey);
    }
  };

  return (
    <div
      data-drop-date={dateKey}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onMouseUp={onDropMouseUp}
      onTouchMove={onDropTouchMove}
      onTouchEnd={onDropTouchEnd}
      onClick={handleColumnClick}
      style={{
        background: getBackground(),
        position: 'relative',
        height: TOTAL_HEIGHT,
        cursor: onAddLesson ? 'pointer' : 'default',
        transition: 'background 0.15s ease',
        border: isDropTarget ? '2px dashed #1890ff' : '2px solid transparent',
      }}
    >
      {/* Hour grid lines */}
      {Array.from({ length: 24 }, (_, hour) => (
        <div
          key={`grid-${hour}`}
          style={{
            position: 'absolute',
            top: hour * PIXELS_PER_HOUR,
            left: 0,
            right: 0,
            borderTop: `1px solid ${isDark ? '#303030' : '#e8e8e8'}`,
          }}
        />
      ))}

      {/* Current time indicator - only show on today */}
      <CurrentTimeIndicator
        timezone={tz}
        visible={isToday}
      />

      {/* Add lesson button - shows on hover */}
      {onAddLesson && isHovered && (
        <Button
          type="dashed"
          size="small"
          icon={<PlusOutlined />}
          onClick={(e) => {
            e.stopPropagation();
            onAddLesson(dateKey);
          }}
          style={{
            position: 'absolute',
            top: 4,
            right: 4,
            zIndex: 10,
            opacity: 0.8,
          }}
        />
      )}

      {/* Drag preview ghost */}
      {dragPreview && (
        <div
          style={{
            position: 'absolute',
            top: (dragPreview.hour * PIXELS_PER_HOUR) + (dragPreview.minute / 60 * PIXELS_PER_HOUR),
            left: 4,
            right: 4,
            height: Math.max(MIN_LESSON_HEIGHT, (dragPreview.duration / 60) * PIXELS_PER_HOUR),
            background: 'rgba(24, 144, 255, 0.2)',
            border: '2px dashed #1890ff',
            borderRadius: 6,
            pointerEvents: 'none',
            zIndex: 50,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#1890ff',
            fontSize: 12,
            fontWeight: 600,
            // Smooth animation when snapping to 30-min intervals
            transition: 'top 0.1s ease-out',
          }}
        >
          {String(dragPreview.hour).padStart(2, '0')}:{String(dragPreview.minute).padStart(2, '0')}
        </div>
      )}

      {/* Lessons positioned by time */}
      {lessons.map(lesson => {
        const dragHandlers = getDragHandlers?.(lesson.id);
        return (
          <LessonBlock
            key={lesson.id}
            lesson={lesson}
            isDark={isDark}
            timezone={tz}
            onLessonClick={onLessonClick}
            onContextMenu={onContextMenu}
            isDragging={draggedLessonId === lesson.id}
            dragHandlers={dragHandlers}
            wasDragPerformedRef={wasDragPerformedRef}
          />
        );
      })}
    </div>
  );
};

/**
 * Individual lesson block with context menu and drag support.
 */
interface LessonBlockProps {
  lesson: Lesson;
  isDark: boolean;
  timezone: string;
  onLessonClick: (lessonId: number) => void;
  onContextMenu: (lessonId: number, position: { x: number; y: number }) => void;
  isDragging?: boolean;
  dragHandlers?: {
    onMouseDown: (e: React.MouseEvent) => void;
    onTouchStart: (e: React.TouchEvent) => void;
  };
  wasDragPerformedRef?: React.MutableRefObject<boolean>;
}

const LessonBlock: React.FC<LessonBlockProps> = ({
  lesson,
  isDark,
  timezone: tz,
  onLessonClick,
  onContextMenu,
  isDragging,
  dragHandlers,
  wasDragPerformedRef,
}) => {
  // Track if we're dragging to prevent click
  const isDraggingRef = useRef(false);
  const mouseDownPosRef = useRef<{ x: number; y: number } | null>(null);
  
  const lessonTime = dayjs(lesson.scheduled_at).tz(tz);
  const duration = lesson.duration_minutes || DEFAULT_DURATION;
  const endTime = lessonTime.add(duration, 'minute');
  const colors = statusColors[lesson.status];
  const statusLabel = lesson.status.charAt(0).toUpperCase() + lesson.status.slice(1);
  const top = getLessonTop(lesson.scheduled_at, tz);
  const height = getLessonHeight(lesson.duration_minutes);

  // Track if context menu was opened (to prevent click after right-click)
  const contextMenuOpenedRef = useRef(false);

  // Track if touch interaction happened (to prevent double click on desktop)
  const isTouchRef = useRef(false);

  // Long press handler for mobile context menu (longer delay to avoid accidental triggers)
  const longPressHandlers = useLongPress({
    onLongPress: (e) => {
      e.preventDefault();
      contextMenuOpenedRef.current = true;
      // Set global flag to prevent click after long press
      if (wasDragPerformedRef) {
        wasDragPerformedRef.current = true;
      }
      let x: number, y: number;
      if ('touches' in e && e.touches.length > 0) {
        x = e.touches[0].clientX;
        y = e.touches[0].clientY;
      } else if ('clientX' in e) {
        x = e.clientX;
        y = e.clientY;
      } else {
        return;
      }
      onContextMenu(lesson.id, { x, y });
    },
    onClick: () => {
      // Short tap on mobile opens lesson details (reschedule modal)
      // Only handle touch clicks here, mouse clicks are handled by onClick event
      if (isTouchRef.current && !contextMenuOpenedRef.current) {
        onLessonClick(lesson.id);
      }
      contextMenuOpenedRef.current = false;
      isTouchRef.current = false;
    },
    delay: 800, // Longer delay to distinguish from regular tap
  });

  // Track touch start to distinguish touch from mouse
  const handleTouchStart = (e: React.TouchEvent) => {
    isTouchRef.current = true;
    longPressHandlers.onTouchStart(e);
  };

  // Right-click handler for desktop context menu
  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    contextMenuOpenedRef.current = true;
    onContextMenu(lesson.id, { x: e.clientX, y: e.clientY });
  };

  // Click handler - only fires if we didn't drag
  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    // Only trigger click if we didn't drag and didn't open context menu
    const wasDragged = wasDragPerformedRef?.current || false;
    if (!wasDragged && !isDraggingRef.current && !contextMenuOpenedRef.current && !isDragging) {
      onLessonClick(lesson.id);
    }
    // Reset context menu flag only - wasDragPerformedRef is reset in onDragEnd with delay
    contextMenuOpenedRef.current = false;
  };

  // Mouse down handler - start tracking for drag
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return; // Only left click
    mouseDownPosRef.current = { x: e.clientX, y: e.clientY };
    isDraggingRef.current = false;
    longPressHandlers.onMouseDown(e);
  };

  // Mouse move handler - detect drag start
  const handleMouseMove = (e: React.MouseEvent) => {
    if (mouseDownPosRef.current && !isDraggingRef.current) {
      const dx = Math.abs(e.clientX - mouseDownPosRef.current.x);
      const dy = Math.abs(e.clientY - mouseDownPosRef.current.y);
      // Start drag if moved more than 5px
      if (dx > 5 || dy > 5) {
        isDraggingRef.current = true;
        // Set global flag to prevent click after drag
        if (wasDragPerformedRef) {
          wasDragPerformedRef.current = true;
        }
        dragHandlers?.onMouseDown(e);
      }
    }
  };

  // Drag styles - pointer-events: none prevents click from firing after drag
  const dragStyles: React.CSSProperties = isDragging ? {
    opacity: 0.6,
    boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
    transform: 'scale(1.05)',
    zIndex: 100,
    pointerEvents: 'none',
  } : {};

  // Combined mouse leave handler
  const handleMouseLeave = (e: React.MouseEvent<HTMLDivElement>) => {
    mouseDownPosRef.current = null;
    longPressHandlers.onMouseLeave(e);
    if (!isDragging) {
      e.currentTarget.style.transform = 'scale(1)';
      e.currentTarget.style.boxShadow = 'none';
      e.currentTarget.style.zIndex = '1';
    }
  };

  // Mouse up handler
  const handleMouseUp = () => {
    mouseDownPosRef.current = null;
    isDraggingRef.current = false;
  };

  return (
    <div
      onTouchStart={handleTouchStart}
      onTouchEnd={longPressHandlers.onTouchEnd}
      onTouchMove={longPressHandlers.onTouchMove}
      onClick={handleClick}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeave}
      onContextMenu={handleContextMenu}
      draggable={false}
      style={{
        position: 'absolute',
        top,
        left: 2,
        right: 2,
        height,
        background: isDark ? colors.bgDark : colors.bg,
        borderLeft: `3px solid ${colors.border}`,
        borderRadius: 4,
        padding: '2px 4px',
        cursor: isDragging ? 'grabbing' : 'grab',
        // Smooth animation for position changes (when lesson is rescheduled)
        transition: isDragging 
          ? 'opacity 0.15s ease, box-shadow 0.15s ease' 
          : 'top 0.3s ease-out, left 0.3s ease-out, transform 0.15s ease, box-shadow 0.15s ease, opacity 0.15s ease',
        overflow: 'hidden',
        zIndex: isDragging ? 100 : 1,
        userSelect: 'none',
        WebkitUserSelect: 'none',
        ...dragStyles,
      }}
      onMouseEnter={(e) => {
        if (!isDragging) {
          e.currentTarget.style.transform = 'scale(1.02)';
          e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)';
          e.currentTarget.style.zIndex = '10';
        }
      }}
    >
      {/* Time range */}
      <Text 
        strong 
        style={{ 
          fontSize: 11, 
          color: isDark ? '#fff' : colors.text,
          display: 'block',
          lineHeight: 1.2,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {lessonTime.format('HH:mm')}–{endTime.format('HH:mm')}
      </Text>
      {/* Duration - only show if enough space */}
      {height > 40 && (
        <Text 
          style={{ 
            fontSize: 9, 
            color: isDark ? 'rgba(255,255,255,0.65)' : 'rgba(0,0,0,0.55)',
            display: 'block',
            lineHeight: 1.2,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {duration} min
        </Text>
      )}
      {/* Status badge - only show if enough space */}
      {height > 55 && (
        <div
          style={{
            fontSize: 8,
            color: isDark ? 'rgba(255,255,255,0.85)' : colors.text,
            background: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.05)',
            padding: '1px 3px',
            borderRadius: 3,
            display: 'inline-block',
            marginTop: 2,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            maxWidth: '100%',
          }}
        >
          {statusLabel}
        </div>
      )}
    </div>
  );
};

/**
 * Week calendar view for lessons in Google Calendar style.
 */
const WeekCalendar: React.FC<WeekCalendarProps> = ({
  lessons,
  timezone: tz,
  onLessonClick,
  onAddLesson,
  onReschedule,
  onComplete,
  onCancel,
  onDelete,
}) => {
  const { resolvedTheme } = useThemeMode();
  const isDark = resolvedTheme === 'dark';
  const { isMobile } = useResponsive();
  
  // Context menu state
  const [contextMenu, setContextMenu] = useState<{
    visible: boolean;
    position: { x: number; y: number };
    lessonId: number | null;
  }>({
    visible: false,
    position: { x: 0, y: 0 },
    lessonId: null,
  });

  // Check if any edit actions are available
  const hasEditActions = !!(onReschedule || onComplete || onCancel || onDelete);

  // Context menu handlers - only show if edit actions are available
  const handleContextMenu = useCallback((lessonId: number, position: { x: number; y: number }) => {
    if (!hasEditActions) return; // Don't show context menu in read-only mode
    setContextMenu({
      visible: true,
      position,
      lessonId,
    });
  }, [hasEditActions]);

  const handleCloseContextMenu = useCallback(() => {
    setContextMenu(prev => ({ ...prev, visible: false }));
  }, []);

  const handleReschedule = useCallback(() => {
    if (contextMenu.lessonId && onReschedule) {
      onReschedule(contextMenu.lessonId);
    }
  }, [contextMenu.lessonId, onReschedule]);

  const handleComplete = useCallback(() => {
    if (contextMenu.lessonId && onComplete) {
      onComplete(contextMenu.lessonId);
    }
  }, [contextMenu.lessonId, onComplete]);

  const handleCancel = useCallback(() => {
    if (contextMenu.lessonId && onCancel) {
      onCancel(contextMenu.lessonId);
    }
  }, [contextMenu.lessonId, onCancel]);

  const handleDelete = useCallback(() => {
    if (contextMenu.lessonId && onDelete) {
      onDelete(contextMenu.lessonId);
    }
  }, [contextMenu.lessonId, onDelete]);

  // Ref for scrollable container (moved up for use in onDrop)
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Preview state for drag & drop
  const [dragPreview, setDragPreview] = useState<{
    date: string;
    hour: number;
    minute: number;
    duration: number;
  } | null>(null);

  // Global flag to track if any drag happened (prevents click after drag)
  const wasDragPerformedRef = useRef(false);

  // Calculate time from Y position (snapped to 30 min)
  // Adjusts for lesson duration to position from center of card
  const calculateTimeFromY = useCallback((y: number, durationMinutes: number = DEFAULT_DURATION): { hour: number; minute: number } => {
    if (!scrollContainerRef.current) return { hour: 8, minute: 0 };
    
    const containerRect = scrollContainerRef.current.getBoundingClientRect();
    const scrollTop = scrollContainerRef.current.scrollTop;
    
    // Y position relative to the scrollable content
    const relativeY = y - containerRect.top + scrollTop;
    
    // Adjust for half the lesson height (so we position from center, not top)
    const halfLessonHeight = (durationMinutes / 60 * PIXELS_PER_HOUR) / 2;
    const adjustedY = relativeY - halfLessonHeight;
    
    // Convert Y to minutes (PIXELS_PER_HOUR = 60px per hour = 1px per minute)
    const totalMinutes = Math.max(0, Math.min(24 * 60 - 1, adjustedY));
    
    // Snap to 30-minute intervals
    const snappedMinutes = Math.round(totalMinutes / 30) * 30;
    const hour = Math.floor(snappedMinutes / 60);
    const minute = snappedMinutes % 60;
    
    return { hour: Math.min(23, hour), minute };
  }, []);

  // Track original lesson date for same-column detection
  const originalLessonDateRef = useRef<string | null>(null);

  // Drag and drop for rescheduling
  const { dragState, getDragHandlers, getDropTargetHandlers } = useDragAndDrop({
    wasDragPerformedRef,
    onDragStart: (lessonId) => {
      const lesson = lessons.find(l => l.id === lessonId);
      if (lesson) {
        originalLessonDateRef.current = dayjs(lesson.scheduled_at).tz(tz).format('YYYY-MM-DD');
      }
    },
    onDragEnd: () => {
      setDragPreview(null);
      originalLessonDateRef.current = null;
      // Reset the flag after a short delay to allow click event to check it
      setTimeout(() => {
        wasDragPerformedRef.current = false;
      }, 100);
    },
    onDrop: (lessonId, targetDate, position) => {
      // Find the original lesson
      const lesson = lessons.find(l => l.id === lessonId);
      if (lesson && onReschedule) {
        const duration = lesson.duration_minutes || DEFAULT_DURATION;
        const { hour, minute } = calculateTimeFromY(position.y, duration);
        
        // Check if anything actually changed
        const originalTime = dayjs(lesson.scheduled_at).tz(tz);
        const originalDate = originalTime.format('YYYY-MM-DD');
        const sameDate = originalDate === targetDate;
        const sameTime = originalTime.hour() === hour && originalTime.minute() === minute;
        
        // Only reschedule if something changed
        if (!sameDate || !sameTime) {
          const newDateTime = dayjs(targetDate)
            .tz(tz)
            .hour(hour)
            .minute(minute)
            .second(0)
            .toISOString();
          onReschedule(lessonId, newDateTime);
        }
      }
      setDragPreview(null);
    },
  });

  // Update preview on mouse move during drag
  useEffect(() => {
    if (!dragState.isDragging || !dragState.draggedId) return;

    const lesson = lessons.find(l => l.id === dragState.draggedId);
    const duration = lesson?.duration_minutes || DEFAULT_DURATION;

    const handleMouseMove = (e: MouseEvent) => {
      const { hour, minute } = calculateTimeFromY(e.clientY, duration);
      
      // Find which column we're over
      const element = document.elementFromPoint(e.clientX, e.clientY);
      const dropTarget = element?.closest('[data-drop-date]');
      const targetDate = dropTarget?.getAttribute('data-drop-date');
      
      if (targetDate) {
        setDragPreview({ date: targetDate, hour, minute, duration });
      }
    };

    document.addEventListener('mousemove', handleMouseMove);
    return () => document.removeEventListener('mousemove', handleMouseMove);
  }, [dragState.isDragging, dragState.draggedId, calculateTimeFromY, lessons]);
  
  // Number of days to show based on viewport
  const dayCount = isMobile ? MOBILE_DAY_COUNT : DESKTOP_DAY_COUNT;

  // View start date - for mobile, center on today; for desktop, start of week
  const [viewStart, setViewStart] = useState<Dayjs>(() => {
    const today = dayjs().tz(tz);
    if (isMobile) {
      // Center on today: show yesterday, today, tomorrow
      return today.subtract(1, 'day');
    }
    return today.startOf('isoWeek');
  });

  // Container width for swipe calculations
  const [containerWidth, setContainerWidth] = useState(300);
  const carouselContainerRef = useRef<HTMLDivElement>(null);

  // Measure carousel container width (excluding time scale)
  useEffect(() => {
    const updateWidth = () => {
      if (carouselContainerRef.current) {
        setContainerWidth(carouselContainerRef.current.offsetWidth);
      }
    };
    // Initial measurement after render
    const timer = setTimeout(updateWidth, 0);
    window.addEventListener('resize', updateWidth);
    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', updateWidth);
    };
  }, []);

  // Carousel swipe for mobile with pre-rendered panels
  const swipeHandlers = useCarouselSwipe({
    onSwipeLeft: () => setViewStart(prev => prev.add(dayCount, 'day')),
    onSwipeRight: () => setViewStart(prev => prev.subtract(dayCount, 'day')),
    containerWidth,
  });

  // Update view start when switching between mobile/desktop
  useMemo(() => {
    const today = dayjs().tz(tz);
    if (isMobile) {
      setViewStart(today.subtract(1, 'day'));
    } else {
      setViewStart(today.startOf('isoWeek'));
    }
  }, [isMobile, tz]);

  // Generate visible days for current, prev, and next panels (for smooth swiping)
  const weekDays = useMemo(() => {
    return Array.from({ length: dayCount }, (_, i) => viewStart.add(i, 'day'));
  }, [viewStart, dayCount]);

  // Pre-render prev and next panels for smooth animation
  const prevWeekDays = useMemo(() => {
    return Array.from({ length: dayCount }, (_, i) => viewStart.subtract(dayCount, 'day').add(i, 'day'));
  }, [viewStart, dayCount]);

  const nextWeekDays = useMemo(() => {
    return Array.from({ length: dayCount }, (_, i) => viewStart.add(dayCount, 'day').add(i, 'day'));
  }, [viewStart, dayCount]);

  // Group lessons by day (including prev and next panels for smooth swiping)
  const lessonsByDay = useMemo(() => {
    const map: Record<string, Lesson[]> = {};
    // Include all days from prev, current, and next panels
    const allDays = [...prevWeekDays, ...weekDays, ...nextWeekDays];
    allDays.forEach(day => {
      map[day.format('YYYY-MM-DD')] = [];
    });
    
    lessons.forEach(lesson => {
      const lessonDate = dayjs(lesson.scheduled_at).tz(tz).format('YYYY-MM-DD');
      if (map[lessonDate]) {
        map[lessonDate].push(lesson);
      }
    });

    // Sort lessons by time within each day
    Object.keys(map).forEach(date => {
      map[date].sort((a, b) => 
        dayjs(a.scheduled_at).valueOf() - dayjs(b.scheduled_at).valueOf()
      );
    });

    return map;
  }, [lessons, weekDays, prevWeekDays, nextWeekDays, tz]);

  // Navigation: move by dayCount (3 on mobile, 7 on desktop)
  const goToPrev = () => setViewStart(prev => prev.subtract(dayCount, 'day'));
  const goToNext = () => setViewStart(prev => prev.add(dayCount, 'day'));
  const goToToday = () => {
    const today = dayjs().tz(tz);
    if (isMobile) {
      setViewStart(today.subtract(1, 'day'));
    } else {
      setViewStart(today.startOf('isoWeek'));
    }
  };

  const viewEnd = viewStart.add(dayCount - 1, 'day');
  const today = dayjs().tz(tz);
  const isTodayVisible = today.isSameOrAfter(viewStart, 'day') && today.isSameOrBefore(viewEnd, 'day');

  // Calculate week stats - only for currently visible days
  const weekStats = useMemo(() => {
    let totalLessons = 0;
    let totalMinutes = 0;
    // Only count lessons from currently visible weekDays, not prev/next panels
    weekDays.forEach(day => {
      const dateKey = day.format('YYYY-MM-DD');
      const dayLessons = lessonsByDay[dateKey] || [];
      totalLessons += dayLessons.length;
      dayLessons.forEach(l => {
        totalMinutes += l.duration_minutes || DEFAULT_DURATION;
      });
    });
    return { totalLessons, totalHours: Math.round(totalMinutes / 60 * 10) / 10 };
  }, [lessonsByDay, weekDays]);

  // Calculate initial scroll position (earliest lesson or 08:00)
  const initialScrollTop = useMemo(() => {
    let earliestHour = DEFAULT_SCROLL_HOUR;
    
    // Find earliest lesson time across all visible days
    Object.values(lessonsByDay).forEach(dayLessons => {
      dayLessons.forEach(lesson => {
        const lessonHour = dayjs(lesson.scheduled_at).tz(tz).hour();
        if (lessonHour < earliestHour) {
          earliestHour = lessonHour;
        }
      });
    });
    
    // Scroll to 30 minutes before the earliest hour for padding
    return Math.max(0, (earliestHour * PIXELS_PER_HOUR) - 30);
  }, [lessonsByDay, tz]);

  // Auto-scroll to initial position on mount and when lessons change
  useEffect(() => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = initialScrollTop;
    }
  }, [initialScrollTop]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 280px)', minHeight: 400 }}>
      {/* Header with navigation */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: spacing.md,
        flexWrap: 'wrap',
        gap: spacing.sm,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: spacing.xs }}>
          <Button 
            icon={<LeftOutlined />} 
            onClick={goToPrev}
            size="small"
          />
          <Button 
            icon={<RightOutlined />} 
            onClick={goToNext}
            size="small"
          />
          <Button 
            size="small" 
            onClick={goToToday}
            style={{ 
              visibility: isTodayVisible ? 'hidden' : 'visible',
              // Keep space reserved to prevent layout shift
            }}
          >
            Today
          </Button>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: spacing.md }}>
          {weekStats.totalLessons > 0 && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              {weekStats.totalLessons} lessons • {weekStats.totalHours}h
            </Text>
          )}
          <Text strong style={{ fontSize: 14 }}>
            {viewStart.format('MMM D')} – {viewEnd.format('MMM D, YYYY')}
          </Text>
        </div>
      </div>

      {/* Day headers - fixed at top */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: `${TIME_SCALE_WIDTH}px repeat(${dayCount}, 1fr)`,
        gap: 1,
        background: isDark ? '#303030' : '#e8e8e8',
        borderRadius: '8px 8px 0 0',
        overflow: 'hidden',
      }}>
        {/* Empty cell above time scale */}
        <div style={{ background: isDark ? '#1f1f1f' : '#fafafa' }} />
        
        {/* Day headers */}
        {weekDays.map((day, index) => {
          const isToday = day.isSame(dayjs().tz(tz), 'day');
          const dayOfWeek = day.day();
          const dayIndex = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
          return (
            <div
              key={`header-${index}`}
              style={{
                background: isDark ? '#1f1f1f' : '#fafafa',
                padding: `${spacing.xs}px ${spacing.xs}px`,
                textAlign: 'center',
              }}
            >
              <Text 
                type="secondary" 
                style={{ fontSize: 11, display: 'block' }}
              >
                {DAYS_FULL[dayIndex]}
              </Text>
              <Text 
                strong={isToday}
                style={{ 
                  fontSize: 16,
                  color: isToday ? '#1890ff' : undefined,
                  background: isToday ? 'rgba(24, 144, 255, 0.1)' : undefined,
                  borderRadius: '50%',
                  width: 28,
                  height: 28,
                  lineHeight: '28px',
                  display: 'inline-block',
                }}
              >
                {day.format('D')}
              </Text>
            </div>
          );
        })}
      </div>

      {/* Scrollable calendar body with time scale and carousel */}
      <div
        ref={scrollContainerRef}
        style={{
          display: 'flex',
          flex: 1,
          overflow: 'auto',
          background: isDark ? '#303030' : '#e8e8e8',
          borderRadius: '0 0 8px 8px',
          position: 'relative',
        }}
      >
        {/* Time scale on the left - fixed */}
        <TimeScale />

        {/* Carousel container for swipe */}
        <div
          ref={carouselContainerRef}
          onTouchStart={isMobile ? swipeHandlers.onTouchStart : undefined}
          onTouchMove={isMobile ? swipeHandlers.onTouchMove : undefined}
          onTouchEnd={isMobile ? swipeHandlers.onTouchEnd : undefined}
          style={{
            flex: 1,
            position: 'relative',
            overflow: 'hidden',
            height: TOTAL_HEIGHT,
          }}
        >
          {/* Carousel track with 3 panels */}
          <div
            style={{
              display: 'flex',
              width: isMobile ? '300%' : '100%',
              height: TOTAL_HEIGHT,
              transform: isMobile 
                ? swipeHandlers.isAnimating
                  ? `translateX(calc(-33.333% + ${swipeHandlers.animatingTo * -33.333}%))`
                  : `translateX(calc(-33.333% + ${swipeHandlers.offset}px))`
                : undefined,
              transition: swipeHandlers.isAnimating ? 'transform 0.3s ease-out' : 'none',
            }}
          >
            {/* Previous panel (only on mobile) */}
            {isMobile && (
              <div style={{ width: '33.333%', flexShrink: 0 }}>
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: `repeat(${dayCount}, 1fr)`,
                  gap: 1,
                  height: TOTAL_HEIGHT,
                }}>
                  {prevWeekDays.map((day, index) => {
                    const dateKey = day.format('YYYY-MM-DD');
                    const dayLessons = lessonsByDay[dateKey] || [];
                    const isToday = day.isSame(dayjs().tz(tz), 'day');
                    return (
                      <DayColumn
                        key={`prev-${index}`}
                        dateKey={dateKey}
                        lessons={dayLessons}
                        isToday={isToday}
                        isDark={isDark}
                        timezone={tz}
                        onLessonClick={onLessonClick}
                        onAddLesson={onAddLesson}
                        onContextMenu={handleContextMenu}
                        wasDragPerformedRef={wasDragPerformedRef}
                      />
                    );
                  })}
                </div>
              </div>
            )}

            {/* Current panel */}
            <div style={{ width: isMobile ? '33.333%' : '100%', flexShrink: 0 }}>
              <div style={{
                display: 'grid',
                gridTemplateColumns: `repeat(${dayCount}, 1fr)`,
                gap: 1,
                height: TOTAL_HEIGHT,
              }}>
                {weekDays.map((day, index) => {
                  const dateKey = day.format('YYYY-MM-DD');
                  const dayLessons = lessonsByDay[dateKey] || [];
                  const isToday = day.isSame(dayjs().tz(tz), 'day');
                  const dropTargetHandlers = getDropTargetHandlers(dateKey);

                  return (
                    <DayColumn
                      key={`cell-${index}`}
                      dateKey={dateKey}
                      lessons={dayLessons}
                      isToday={isToday}
                      isDark={isDark}
                      timezone={tz}
                      onLessonClick={onLessonClick}
                      onAddLesson={onAddLesson}
                      onContextMenu={handleContextMenu}
                      isDropTarget={!isMobile && dragState.dropTargetDate === dateKey}
                      draggedLessonId={!isMobile ? dragState.draggedId : null}
                      getDragHandlers={!isMobile ? getDragHandlers : undefined}
                      dragPreview={!isMobile && dragPreview?.date === dateKey ? dragPreview : null}
                      wasDragPerformedRef={wasDragPerformedRef}
                      {...(!isMobile ? dropTargetHandlers : {})}
                    />
                  );
                })}
              </div>
            </div>

            {/* Next panel (only on mobile) */}
            {isMobile && (
              <div style={{ width: '33.333%', flexShrink: 0 }}>
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: `repeat(${dayCount}, 1fr)`,
                  gap: 1,
                  height: TOTAL_HEIGHT,
                }}>
                  {nextWeekDays.map((day, index) => {
                    const dateKey = day.format('YYYY-MM-DD');
                    const dayLessons = lessonsByDay[dateKey] || [];
                    const isToday = day.isSame(dayjs().tz(tz), 'day');
                    return (
                      <DayColumn
                        key={`next-${index}`}
                        dateKey={dateKey}
                        lessons={dayLessons}
                        isToday={isToday}
                        isDark={isDark}
                        timezone={tz}
                        onLessonClick={onLessonClick}
                        onAddLesson={onAddLesson}
                        onContextMenu={handleContextMenu}
                        wasDragPerformedRef={wasDragPerformedRef}
                      />
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Context menu - only render if edit actions are available */}
      {hasEditActions && (
        <LessonContextMenu
          visible={contextMenu.visible}
          position={contextMenu.position}
          lessonId={contextMenu.lessonId || 0}
          onReschedule={onReschedule ? handleReschedule : undefined}
          onComplete={onComplete ? handleComplete : undefined}
          onCancel={onCancel ? handleCancel : undefined}
          onDelete={onDelete ? handleDelete : undefined}
          onClose={handleCloseContextMenu}
        />
      )}

      {/* Legend */}
      <div style={{
        display: 'flex',
        gap: spacing.md,
        marginTop: spacing.sm,
        flexWrap: 'wrap',
        justifyContent: 'center',
      }}>
        {Object.entries(statusColors).map(([status, colors]) => (
          <div key={status} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{
              width: 12,
              height: 12,
              borderRadius: 2,
              background: isDark ? colors.bgDark : colors.bg,
              borderLeft: `3px solid ${colors.border}`,
            }} />
            <Text type="secondary" style={{ fontSize: 11 }}>
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </Text>
          </div>
        ))}
      </div>
    </div>
  );
};

export default WeekCalendar;
