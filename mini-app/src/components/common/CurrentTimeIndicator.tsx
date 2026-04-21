import React, { useState, useEffect } from 'react';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import { DEFAULT_PIXELS_PER_HOUR } from './TimeScale';

dayjs.extend(utc);
dayjs.extend(timezone);

interface CurrentTimeIndicatorProps {
  timezone: string;
  visible: boolean;
  /** Left offset in pixels (for positioning within day column) */
  leftOffset?: number;
  pixelsPerHour?: number;
}

/**
 * Calculate indicator top position based on current time.
 * Top = (hour * PIXELS_PER_HOUR) + (minutes / 60 * PIXELS_PER_HOUR)
 */
const getTimePosition = (tz: string, pixelsPerHour: number): number => {
  const now = dayjs().tz(tz);
  const hour = now.hour();
  const minutes = now.minute();
  return (hour * pixelsPerHour) + (minutes / 60 * pixelsPerHour);
};

/**
 * Current time indicator - a red horizontal line showing the current time.
 * Updates position every minute.
 */
const CurrentTimeIndicator: React.FC<CurrentTimeIndicatorProps> = ({
  timezone: tz,
  visible,
  leftOffset = 0,
  pixelsPerHour = DEFAULT_PIXELS_PER_HOUR,
}) => {
  const [position, setPosition] = useState(() => getTimePosition(tz, pixelsPerHour));

  // Update position every minute
  useEffect(() => {
    if (!visible) return;

    // Update immediately
    setPosition(getTimePosition(tz, pixelsPerHour));

    // Set up interval to update every minute
    const interval = setInterval(() => {
      setPosition(getTimePosition(tz, pixelsPerHour));
    }, 60000); // 60 seconds

    return () => clearInterval(interval);
  }, [visible, tz, pixelsPerHour]);

  if (!visible) return null;

  return (
    <div
      style={{
        position: 'absolute',
        top: position,
        left: leftOffset,
        right: 0,
        height: 2,
        background: '#ff4d4f',
        zIndex: 20,
        pointerEvents: 'none',
      }}
    >
      {/* Dot marker on the left */}
      <div
        style={{
          position: 'absolute',
          left: -4,
          top: -3,
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: '#ff4d4f',
        }}
      />
    </div>
  );
};

export default CurrentTimeIndicator;
