import React from 'react';
import { Typography } from 'antd';
import { useTheme } from '../../theme/ThemeProvider';

const { Text } = Typography;

// Layout constants
export const DEFAULT_PIXELS_PER_HOUR = 60;
export const TIME_SCALE_WIDTH = 50;

interface TimeScaleProps {
  startHour?: number;
  endHour?: number;
  pixelsPerHour?: number;
  totalHeight?: number;
}

/**
 * Vertical time scale component showing hour markers (00:00 to 23:00).
 * Used alongside the calendar grid to show time-based positioning.
 */
const TimeScale: React.FC<TimeScaleProps> = ({
  startHour = 0,
  endHour = 24,
  pixelsPerHour = DEFAULT_PIXELS_PER_HOUR,
  totalHeight = 24 * pixelsPerHour,
}) => {
  const { resolvedTheme } = useTheme();
  const colors = resolvedTheme.colors;
  
  const hours = Array.from(
    { length: endHour - startHour },
    (_, i) => startHour + i
  );

  return (
    <div
      style={{
        width: TIME_SCALE_WIDTH,
        height: totalHeight,
        position: 'relative',
        flexShrink: 0,
        borderRight: `1px solid ${colors.borderPrimary}`,
        background: colors.bgSecondary,
      }}
    >
      {hours.map((hour) => (
        <div
          key={hour}
          style={{
            position: 'absolute',
            top: hour * pixelsPerHour,
            left: 0,
            right: 0,
            height: pixelsPerHour,
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'flex-end',
            paddingRight: 8,
            paddingTop: 2,
          }}
        >
          <Text
            type="secondary"
            style={{
              fontSize: 10,
              lineHeight: 1,
            }}
          >
            {hour.toString().padStart(2, '0')}:00
          </Text>
        </div>
      ))}
    </div>
  );
};

export default TimeScale;
