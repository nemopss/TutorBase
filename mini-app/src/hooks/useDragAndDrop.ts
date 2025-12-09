import { useState, useCallback, useRef, useEffect } from "react";

const LONG_PRESS_DELAY = 500; // ms - required hold time before drag on mobile

export interface DragState {
  isDragging: boolean;
  draggedId: number | null;
  dropTargetDate: string | null;
  dragPosition: { x: number; y: number } | null;
}

interface UseDragAndDropOptions {
  onDragStart?: (id: number) => void;
  onDragEnd?: (id: number, targetDate: string | null) => void;
  onDrop?: (
    id: number,
    targetDate: string,
    position: { x: number; y: number }
  ) => void;
  // Global ref to track if drag was performed (to prevent click after drag)
  wasDragPerformedRef?: React.MutableRefObject<boolean>;
}

interface UseDragAndDropResult {
  dragState: DragState;
  // Handlers for draggable items
  getDragHandlers: (id: number) => {
    onMouseDown: (e: React.MouseEvent) => void;
    onTouchStart: (e: React.TouchEvent) => void;
  };
  // Handlers for drop targets (day columns)
  getDropTargetHandlers: (date: string) => {
    onMouseEnter: () => void;
    onMouseLeave: () => void;
    onMouseUp: (e: React.MouseEvent) => void;
    onTouchMove: (e: React.TouchEvent) => void;
    onTouchEnd: () => void;
  };
  // Cancel drag operation
  cancelDrag: () => void;
}

/**
 * Hook for drag and drop functionality supporting both mouse and touch.
 * On touch devices, requires a long-press (500ms) before drag starts.
 *
 * @example
 * const { dragState, getDragHandlers, getDropTargetHandlers } = useDragAndDrop({
 *   onDrop: (id, date) => rescheduleLesson(id, date),
 * });
 *
 * // On draggable item:
 * <div {...getDragHandlers(lesson.id)}>Lesson</div>
 *
 * // On drop target:
 * <div {...getDropTargetHandlers('2024-01-15')}>Day Column</div>
 */
export function useDragAndDrop({
  onDragStart,
  onDragEnd,
  onDrop,
  wasDragPerformedRef,
}: UseDragAndDropOptions = {}): UseDragAndDropResult {
  const [dragState, setDragState] = useState<DragState>({
    isDragging: false,
    draggedId: null,
    dropTargetDate: null,
    dragPosition: null,
  });

  // Refs for tracking touch/mouse state
  const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startPosRef = useRef<{ x: number; y: number } | null>(null);
  const pendingDragIdRef = useRef<number | null>(null);
  const originalDateRef = useRef<string | null>(null);

  // Use refs to avoid stale closures
  const dragStateRef = useRef(dragState);
  dragStateRef.current = dragState;

  // Clear long press timer
  const clearLongPressTimer = useCallback(() => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
    pendingDragIdRef.current = null;
  }, []);

  // Start drag operation
  const startDrag = useCallback(
    (id: number, position: { x: number; y: number }) => {
      // Set global flag immediately to prevent click after drag
      if (wasDragPerformedRef) {
        wasDragPerformedRef.current = true;
      }
      setDragState({
        isDragging: true,
        draggedId: id,
        dropTargetDate: null,
        dragPosition: position,
      });
      onDragStart?.(id);
    },
    [onDragStart, wasDragPerformedRef]
  );

  // End drag operation
  const endDrag = useCallback(
    (targetDate: string | null) => {
      const { draggedId, dragPosition } = dragStateRef.current;

      if (draggedId !== null) {
        // Always trigger drop if we have a target and position
        // The consumer will decide if anything actually changed
        if (targetDate && dragPosition) {
          onDrop?.(draggedId, targetDate, dragPosition);
        }
        onDragEnd?.(draggedId, targetDate);
      }

      setDragState({
        isDragging: false,
        draggedId: null,
        dropTargetDate: null,
        dragPosition: null,
      });
      originalDateRef.current = null;
    },
    [onDrop, onDragEnd]
  );

  // Cancel drag operation
  const cancelDrag = useCallback(() => {
    clearLongPressTimer();
    endDrag(null);
  }, [clearLongPressTimer, endDrag]);

  // Update drag position
  const updateDragPosition = useCallback((x: number, y: number) => {
    setDragState((prev) => ({
      ...prev,
      dragPosition: { x, y },
    }));
  }, []);

  // Set drop target
  const setDropTarget = useCallback((date: string | null) => {
    setDragState((prev) => ({
      ...prev,
      dropTargetDate: date,
    }));
  }, []);

  // Mouse handlers for draggable items
  const handleMouseDown = useCallback(
    (id: number, e: React.MouseEvent) => {
      // Only left click
      if (e.button !== 0) return;

      e.preventDefault();
      startPosRef.current = { x: e.clientX, y: e.clientY };
      startDrag(id, { x: e.clientX, y: e.clientY });
    },
    [startDrag]
  );

  // Touch handlers for draggable items (requires long press)
  const handleTouchStart = useCallback(
    (id: number, e: React.TouchEvent) => {
      const touch = e.touches[0];
      startPosRef.current = { x: touch.clientX, y: touch.clientY };
      pendingDragIdRef.current = id;

      // Start long press timer
      longPressTimerRef.current = setTimeout(() => {
        if (pendingDragIdRef.current === id) {
          startDrag(id, { x: touch.clientX, y: touch.clientY });
        }
      }, LONG_PRESS_DELAY);
    },
    [startDrag]
  );

  // Track if we need to block the next click
  const blockNextClickRef = useRef(false);

  // Global mouse move handler
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (dragStateRef.current.isDragging) {
        updateDragPosition(e.clientX, e.clientY);
      }
    };

    const handleMouseUp = () => {
      if (dragStateRef.current.isDragging) {
        // Set flag to block the next click event
        blockNextClickRef.current = true;
        endDrag(dragStateRef.current.dropTargetDate);
      }
    };

    // Block click events that happen right after drag
    const handleClick = (e: MouseEvent) => {
      if (blockNextClickRef.current) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        blockNextClickRef.current = false;
      }
    };

    // Handle touch move for canceling long press
    const handleTouchMove = (e: TouchEvent) => {
      if (startPosRef.current && pendingDragIdRef.current !== null) {
        const touch = e.touches[0];
        const dx = Math.abs(touch.clientX - startPosRef.current.x);
        const dy = Math.abs(touch.clientY - startPosRef.current.y);

        // Cancel long press if moved more than 10px
        if (dx > 10 || dy > 10) {
          clearLongPressTimer();
        }
      }

      // Update position if dragging
      if (dragStateRef.current.isDragging && e.touches.length > 0) {
        const touch = e.touches[0];
        updateDragPosition(touch.clientX, touch.clientY);

        // Find element under touch point for drop target
        const element = document.elementFromPoint(touch.clientX, touch.clientY);
        const dropTarget = element?.closest("[data-drop-date]");
        if (dropTarget) {
          const targetDate = dropTarget.getAttribute("data-drop-date");
          if (targetDate) {
            setDropTarget(targetDate);
          }
        }
      }
    };

    const handleTouchEnd = () => {
      clearLongPressTimer();
      if (dragStateRef.current.isDragging) {
        endDrag(dragStateRef.current.dropTargetDate);
      }
    };

    // Handle escape key to cancel drag
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && dragStateRef.current.isDragging) {
        cancelDrag();
      }
    };

    // Always add listeners when component mounts
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
    // Use capture phase to intercept click before it reaches any element
    document.addEventListener("click", handleClick, true);
    document.addEventListener("touchmove", handleTouchMove, {
      passive: false,
    });
    document.addEventListener("touchend", handleTouchEnd);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
      document.removeEventListener("click", handleClick, true);
      document.removeEventListener("touchmove", handleTouchMove);
      document.removeEventListener("touchend", handleTouchEnd);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [
    updateDragPosition,
    endDrag,
    cancelDrag,
    clearLongPressTimer,
    setDropTarget,
  ]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clearLongPressTimer();
    };
  }, [clearLongPressTimer]);

  // Get handlers for a draggable item
  const getDragHandlers = useCallback(
    (id: number) => ({
      onMouseDown: (e: React.MouseEvent) => handleMouseDown(id, e),
      onTouchStart: (e: React.TouchEvent) => handleTouchStart(id, e),
    }),
    [handleMouseDown, handleTouchStart]
  );

  // Get handlers for a drop target
  const getDropTargetHandlers = useCallback(
    (date: string) => ({
      onMouseEnter: () => {
        if (dragState.isDragging) {
          setDropTarget(date);
        }
      },
      onMouseLeave: () => {
        if (dragState.isDragging && dragState.dropTargetDate === date) {
          setDropTarget(null);
        }
      },
      onMouseUp: (e: React.MouseEvent) => {
        if (dragState.isDragging) {
          e.preventDefault();
          e.stopPropagation();
          endDrag(date);
        }
      },
      onTouchMove: (e: React.TouchEvent) => {
        // Find element under touch point
        if (dragState.isDragging && e.touches.length > 0) {
          const touch = e.touches[0];
          const element = document.elementFromPoint(
            touch.clientX,
            touch.clientY
          );
          const dropTarget = element?.closest("[data-drop-date]");
          if (dropTarget) {
            const targetDate = dropTarget.getAttribute("data-drop-date");
            if (targetDate) {
              setDropTarget(targetDate);
            }
          }
        }
      },
      onTouchEnd: () => {
        if (dragState.isDragging) {
          endDrag(date);
        }
      },
    }),
    [dragState.isDragging, dragState.dropTargetDate, setDropTarget, endDrag]
  );

  return {
    dragState,
    getDragHandlers,
    getDropTargetHandlers,
    cancelDrag,
  };
}

export default useDragAndDrop;
