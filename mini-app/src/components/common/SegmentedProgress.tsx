import React from 'react';

interface SegmentedProgressProps {
  /** Total number of lessons */
  total: number;
  /** Number of completed lessons */
  completed: number;
  /** Number of cancelled lessons */
  cancelled: number;
  /** Diameter in pixels (default: 80) */
  size?: number;
  /** Show percentage in center (default: true) */
  showPercent?: boolean;
}

/**
 * Circular progress indicator with three colored segments:
 * - Green: completed lessons
 * - Red: cancelled lessons  
 * - Gray: remaining lessons
 * 
 * Uses custom SVG for precise segment control without color mixing.
 */
const SegmentedProgress: React.FC<SegmentedProgressProps> = ({
  total,
  completed,
  cancelled,
  size = 80,
  showPercent = true,
}) => {
  // Calculate percentages
  const completedPercent = total > 0 ? (completed / total) * 100 : 0;
  const cancelledPercent = total > 0 ? (cancelled / total) * 100 : 0;
  const remainingPercent = 100 - completedPercent - cancelledPercent;
  const displayPercent = Math.round(completedPercent + cancelledPercent);

  // SVG circle parameters
  const strokeWidth = 8;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const center = size / 2;

  // Calculate stroke dash arrays for each segment
  // Segments are drawn starting from top (12 o'clock position)
  const completedLength = (completedPercent / 100) * circumference;
  const cancelledLength = (cancelledPercent / 100) * circumference;
  const remainingLength = (remainingPercent / 100) * circumference;

  // Gap between segments (small gap for visual separation)
  const gap = total > 0 ? 2 : 0;

  // Calculate offsets for each segment
  // Start from top (-90 degrees rotation)
  const completedOffset = 0;
  const cancelledOffset = completedLength + gap;
  const remainingOffset = completedLength + cancelledLength + gap * 2;

  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <svg
        width={size}
        height={size}
        style={{ transform: 'rotate(-90deg)' }}
      >
        {/* Background circle (gray) */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="#d9d9d9"
          strokeWidth={strokeWidth}
        />

        {/* Remaining segment (gray, drawn first as background) */}
        {remainingPercent > 0 && total > 0 && (
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="#d9d9d9"
            strokeWidth={strokeWidth}
            strokeDasharray={`${remainingLength - gap} ${circumference}`}
            strokeDashoffset={-remainingOffset}
            strokeLinecap="round"
          />
        )}

        {/* Completed segment (green) */}
        {completedPercent > 0 && (
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="#52c41a"
            strokeWidth={strokeWidth}
            strokeDasharray={`${completedLength - gap} ${circumference}`}
            strokeDashoffset={-completedOffset}
            strokeLinecap="round"
          />
        )}

        {/* Cancelled segment (red) */}
        {cancelledPercent > 0 && (
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="#ff4d4f"
            strokeWidth={strokeWidth}
            strokeDasharray={`${cancelledLength - gap} ${circumference}`}
            strokeDashoffset={-cancelledOffset}
            strokeLinecap="round"
          />
        )}
      </svg>

      {/* Center text */}
      {showPercent && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: size,
            height: size,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: size * 0.22,
            fontWeight: 600,
            color: 'inherit',
          }}
        >
          {displayPercent}%
        </div>
      )}
    </div>
  );
};

export default SegmentedProgress;
