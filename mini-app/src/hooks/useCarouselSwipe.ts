import { useCallback, useRef, useState } from "react";

const SWIPE_THRESHOLD = 50; // Minimum swipe distance to trigger navigation
const ANIMATION_DURATION = 300; // ms

interface UseCarouselSwipeOptions {
  onSwipeLeft: () => void;
  onSwipeRight: () => void;
  containerWidth: number;
  threshold?: number;
}

interface UseCarouselSwipeResult {
  onTouchStart: (e: React.TouchEvent) => void;
  onTouchMove: (e: React.TouchEvent) => void;
  onTouchEnd: () => void;
  offset: number; // Pixel offset during drag
  isAnimating: boolean;
  // Current panel index: -1 = prev, 0 = current, 1 = next
  activePanel: number;
  // For final animation: -1 = animating to prev, 0 = center, 1 = animating to next
  animatingTo: number;
}

/**
 * Hook for carousel-style swipe navigation with pre-rendered panels.
 * Renders 3 panels (prev, current, next) and animates between them.
 */
export function useCarouselSwipe({
  onSwipeLeft,
  onSwipeRight,
  containerWidth,
  threshold = SWIPE_THRESHOLD,
}: UseCarouselSwipeOptions): UseCarouselSwipeResult {
  const startXRef = useRef<number | null>(null);
  const startYRef = useRef<number | null>(null);
  const [offset, setOffset] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);
  const [animatingTo, setAnimatingTo] = useState(0); // -1 = prev, 0 = center, 1 = next
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [activePanel, _setActivePanel] = useState(0);
  const isHorizontalSwipeRef = useRef<boolean | null>(null);
  const isDraggingRef = useRef(false);

  const onTouchStart = useCallback(
    (e: React.TouchEvent) => {
      if (isAnimating) return;

      const touch = e.touches[0];
      startXRef.current = touch.clientX;
      startYRef.current = touch.clientY;
      isHorizontalSwipeRef.current = null;
      isDraggingRef.current = false;
    },
    [isAnimating]
  );

  const onTouchMove = useCallback(
    (e: React.TouchEvent) => {
      if (
        isAnimating ||
        startXRef.current === null ||
        startYRef.current === null
      )
        return;

      const touch = e.touches[0];
      const deltaX = touch.clientX - startXRef.current;
      const deltaY = touch.clientY - startYRef.current;

      // Determine if this is a horizontal or vertical swipe on first significant movement
      if (isHorizontalSwipeRef.current === null) {
        const absX = Math.abs(deltaX);
        const absY = Math.abs(deltaY);

        if (absX > 10 || absY > 10) {
          isHorizontalSwipeRef.current = absX > absY;
        }
      }

      // Only track horizontal swipes
      if (isHorizontalSwipeRef.current === true) {
        isDraggingRef.current = true;
        // Allow dragging up to full container width
        const clampedOffset = Math.max(
          -containerWidth,
          Math.min(containerWidth, deltaX)
        );
        setOffset(clampedOffset);
      }
    },
    [isAnimating, containerWidth]
  );

  const onTouchEnd = useCallback(() => {
    if (startXRef.current === null || !isDraggingRef.current) {
      startXRef.current = null;
      startYRef.current = null;
      return;
    }

    const shouldNavigate = Math.abs(offset) >= threshold;

    if (shouldNavigate) {
      setIsAnimating(true);
      setOffset(0); // Reset pixel offset

      if (offset < 0) {
        // Swiped left → animate to next panel
        setAnimatingTo(1);
        setTimeout(() => {
          onSwipeLeft();
          setAnimatingTo(0);
          setIsAnimating(false);
        }, ANIMATION_DURATION);
      } else {
        // Swiped right → animate to prev panel
        setAnimatingTo(-1);
        setTimeout(() => {
          onSwipeRight();
          setAnimatingTo(0);
          setIsAnimating(false);
        }, ANIMATION_DURATION);
      }
    } else {
      // Snap back to center
      setIsAnimating(true);
      setOffset(0);
      setAnimatingTo(0);
      setTimeout(() => {
        setIsAnimating(false);
      }, ANIMATION_DURATION);
    }

    // Reset state
    startXRef.current = null;
    startYRef.current = null;
    isHorizontalSwipeRef.current = null;
    isDraggingRef.current = false;
  }, [offset, threshold, containerWidth, onSwipeLeft, onSwipeRight]);

  return {
    onTouchStart,
    onTouchMove,
    onTouchEnd,
    offset,
    isAnimating,
    activePanel,
    animatingTo,
  };
}

export default useCarouselSwipe;
