import { useCallback, useRef, useState } from "react";

const SWIPE_THRESHOLD = 50; // Minimum swipe distance in pixels

interface UseSwipeNavigationOptions {
  onSwipeLeft: () => void;
  onSwipeRight: () => void;
  threshold?: number;
}

interface UseSwipeNavigationResult {
  onTouchStart: (e: React.TouchEvent) => void;
  onTouchMove: (e: React.TouchEvent) => void;
  onTouchEnd: (e: React.TouchEvent) => void;
  swipeOffset: number;
  isSwiping: boolean;
}

/**
 * Hook for detecting horizontal swipe gestures for navigation.
 *
 * @param options.onSwipeLeft - Callback fired when swiping left (next)
 * @param options.onSwipeRight - Callback fired when swiping right (previous)
 * @param options.threshold - Minimum swipe distance to trigger navigation (default 50px)
 *
 * @returns Touch event handlers and swipe state for animation
 *
 * @example
 * const { onTouchStart, onTouchMove, onTouchEnd, swipeOffset, isSwiping } = useSwipeNavigation({
 *   onSwipeLeft: () => goToNextWeek(),
 *   onSwipeRight: () => goToPrevWeek(),
 * });
 *
 * <div
 *   onTouchStart={onTouchStart}
 *   onTouchMove={onTouchMove}
 *   onTouchEnd={onTouchEnd}
 *   style={{ transform: `translateX(${swipeOffset}px)` }}
 * >
 *   Calendar content
 * </div>
 */
export function useSwipeNavigation({
  onSwipeLeft,
  onSwipeRight,
  threshold = SWIPE_THRESHOLD,
}: UseSwipeNavigationOptions): UseSwipeNavigationResult {
  const startXRef = useRef<number | null>(null);
  const startYRef = useRef<number | null>(null);
  const [swipeOffset, setSwipeOffset] = useState(0);
  const [isSwiping, setIsSwiping] = useState(false);
  const isHorizontalSwipeRef = useRef<boolean | null>(null);

  const onTouchStart = useCallback((e: React.TouchEvent) => {
    const touch = e.touches[0];
    startXRef.current = touch.clientX;
    startYRef.current = touch.clientY;
    isHorizontalSwipeRef.current = null;
    setIsSwiping(false);
  }, []);

  const onTouchMove = useCallback((e: React.TouchEvent) => {
    if (startXRef.current === null || startYRef.current === null) return;

    const touch = e.touches[0];
    const deltaX = touch.clientX - startXRef.current;
    const deltaY = touch.clientY - startYRef.current;

    // Determine if this is a horizontal or vertical swipe on first significant movement
    if (isHorizontalSwipeRef.current === null) {
      const absX = Math.abs(deltaX);
      const absY = Math.abs(deltaY);

      // Need at least 10px movement to determine direction
      if (absX > 10 || absY > 10) {
        isHorizontalSwipeRef.current = absX > absY;
      }
    }

    // Only track horizontal swipes
    if (isHorizontalSwipeRef.current === true) {
      setIsSwiping(true);
      // Limit swipe offset to prevent over-scrolling
      const maxOffset = 150;
      const clampedOffset = Math.max(-maxOffset, Math.min(maxOffset, deltaX));
      setSwipeOffset(clampedOffset);
    }
  }, []);

  const onTouchEnd = useCallback(() => {
    if (startXRef.current === null) return;

    // Check if swipe exceeded threshold
    if (Math.abs(swipeOffset) >= threshold) {
      if (swipeOffset < 0) {
        // Swiped left → go to next
        onSwipeLeft();
      } else {
        // Swiped right → go to previous
        onSwipeRight();
      }
    }

    // Reset state
    startXRef.current = null;
    startYRef.current = null;
    isHorizontalSwipeRef.current = null;
    setSwipeOffset(0);
    setIsSwiping(false);
  }, [swipeOffset, threshold, onSwipeLeft, onSwipeRight]);

  return {
    onTouchStart,
    onTouchMove,
    onTouchEnd,
    swipeOffset,
    isSwiping,
  };
}

export default useSwipeNavigation;
