import React from 'react';
import { Progress } from 'antd';

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
  const totalProgress = completedPercent + cancelledPercent;
  const displayPercent = Math.round(totalProgress);

  // Build stroke color array for segments
  // Ant Design Progress uses gradient stops for strokeColor
  const getStrokeColor = () => {
    if (total === 0) return '#d9d9d9';
    
    const colors: Record<string, string> = {};
    let currentPosition = 0;

    // Completed segment (green)
    if (completedPercent > 0) {
      colors[`${currentPosition}%`] = '#52c41a';
      currentPosition = completedPercent;
      colors[`${currentPosition}%`] = '#52c41a';
    }

    // Cancelled segment (red)
    if (cancelledPercent > 0) {
      colors[`${currentPosition}%`] = '#ff4d4f';
      currentPosition += cancelledPercent;
      colors[`${currentPosition}%`] = '#ff4d4f';
    }

    return colors;
  };

  return (
    <Progress
      type="circle"
      percent={totalProgress}
      size={size}
      strokeColor={getStrokeColor()}
      trailColor="#d9d9d9"
      format={() => (showPercent ? `${displayPercent}%` : '')}
      strokeWidth={8}
    />
  );
};

export default SegmentedProgress;
