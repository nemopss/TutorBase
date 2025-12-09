import { useCallback, useRef } from "react";

const LONG_PRESS_DELAY = 500; // ms

interface UseLongPressOptions {
  onLongPress: (event: React.TouchEvent | React.MouseEvent) => void;
  onClick?: (event: React.TouchEvent | React.MouseEvent) => void;
  delay?: number;
}

interface UseLongPressResult {
  onTouchStart: (e: React.TouchEvent) => void;
  onTouchEnd: (e: React.TouchEvent) => void;
  onTouchMove: (e: React.TouchEvent) => void;
  onMouseDown: (e: React.MouseEvent) => void;
  onMouseUp: (e: React.MouseEvent) => void;
  onMouseLeave: (e: React.MouseEvent) => void;
}

/**
 * Hook for detecting long-press gestures on both touch and mouse devices.
 *
 * @param options.onLongPress - Callback fired after holding for delay ms
 * @param options.onClick - Optional callback for regular clicks
 * @param options.delay - Long press delay in ms (default 500)
 *
 * @example
 * const longPressHandlers = useLongPress({
 *   onLongPress: (e) => showContextMenu(e),
 *   onClick: (e) => handleClick(e),
 * });
 *
 * <div {...longPressHandlers}>Press me</div>
 */
export function useLongPress({
  onLongPress,
  onClick,
  delay = LONG_PRESS_DELAY,
}: UseLongPressOptions): UseLongPressResult {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isLongPressRef = useRef(false);
  const startPosRef = useRef<{ x: number; y: number } | null>(null);

  const start = useCallback(
    (event: React.TouchEvent | React.MouseEvent) => {
      isLongPressRef.current = false;

      // Store start position for move detection
      if ("touches" in event) {
        startPosRef.current = {
          x: event.touches[0].clientX,
          y: event.touches[0].clientY,
        };
      } else {
        startPosRef.current = {
          x: event.clientX,
          y: event.clientY,
        };
      }

      timerRef.current = setTimeout(() => {
        isLongPressRef.current = true;
        onLongPress(event);
      }, delay);
    },
    [onLongPress, delay]
  );

  const clear = useCallback(
    (event: React.TouchEvent | React.MouseEvent, shouldClick = true) => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }

      // If it wasn't a long press and we have an onClick handler, call it
      if (shouldClick && !isLongPressRef.current && onClick) {
        onClick(event);
      }

      startPosRef.current = null;
    },
    [onClick]
  );

  const handleMove = useCallback((event: React.TouchEvent) => {
    // Cancel long press if user moves finger more than 10px
    if (startPosRef.current && timerRef.current) {
      const touch = event.touches[0];
      const dx = Math.abs(touch.clientX - startPosRef.current.x);
      const dy = Math.abs(touch.clientY - startPosRef.current.y);

      if (dx > 10 || dy > 10) {
        if (timerRef.current) {
          clearTimeout(timerRef.current);
          timerRef.current = null;
        }
      }
    }
  }, []);

  return {
    onTouchStart: (e: React.TouchEvent) => start(e),
    onTouchEnd: (e: React.TouchEvent) => clear(e),
    onTouchMove: handleMove,
    onMouseDown: (e: React.MouseEvent) => start(e),
    onMouseUp: (e: React.MouseEvent) => clear(e),
    onMouseLeave: (e: React.MouseEvent) => clear(e, false),
  };
}

export default useLongPress;
