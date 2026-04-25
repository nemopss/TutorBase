import React from 'react';
import { Card, Col, Row, Skeleton, Space } from 'antd';
import { useResponsive } from '../../hooks/useResponsive';
import { useResponsiveStyles } from '../../hooks/useResponsiveStyles';
import { spacing } from '../../theme/tokens';

interface OverviewPageSkeletonProps {
  statCount?: 3 | 4;
}

const PlaceholderCard: React.FC<{
  rows: number;
  titleWidth?: number | string;
  style?: React.CSSProperties;
}> = ({ rows, titleWidth = '40%', style }) => {
  const { cardStyle } = useResponsiveStyles();

  return (
    <Card style={{ ...cardStyle, ...style }}>
      <Skeleton active title={{ width: titleWidth }} paragraph={{ rows }} />
    </Card>
  );
};

export const OverviewPageSkeleton: React.FC<OverviewPageSkeletonProps> = ({
  statCount = 4,
}) => {
  const { isMobile } = useResponsive();
  const statLgSpan = statCount === 3 ? 8 : 6;

  return (
    <div>
      <Row gutter={[16, 16]} style={{ marginBottom: spacing.lg }}>
        {Array.from({ length: statCount }).map((_, index) => (
          <Col key={index} xs={24} sm={12} lg={statLgSpan}>
            <PlaceholderCard rows={1} titleWidth="48%" />
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <PlaceholderCard rows={isMobile ? 6 : 9} titleWidth="34%" />
        </Col>
        <Col xs={24} lg={8}>
          <PlaceholderCard rows={isMobile ? 5 : 7} titleWidth="56%" />
        </Col>
      </Row>
    </div>
  );
};

export const ReportPageSkeleton: React.FC = () => (
  <PlaceholderReportPage />
);

const PlaceholderReportPage: React.FC = () => {
  const { cardStyle } = useResponsiveStyles();

  return (
    <div>
      <Card style={{ ...cardStyle, marginBottom: spacing.md }}>
        <Space wrap size={spacing.sm}>
          <Skeleton.Button active style={{ width: 160 }} />
          <Skeleton.Button active style={{ width: 180 }} />
        </Space>
      </Card>

      <Row gutter={[16, 16]} style={{ marginBottom: spacing.lg }}>
        {Array.from({ length: 3 }).map((_, index) => (
          <Col key={index} xs={24} sm={8}>
            <PlaceholderCard rows={1} titleWidth="50%" />
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <PlaceholderCard rows={7} titleWidth="42%" />
        </Col>
        <Col xs={24} lg={12}>
          <PlaceholderCard rows={7} titleWidth="42%" />
        </Col>
      </Row>
    </div>
  );
};

interface DetailPageSkeletonProps {
  statCount?: number;
  showTabs?: boolean;
}

export const DetailPageSkeleton: React.FC<DetailPageSkeletonProps> = ({
  statCount = 3,
  showTabs = true,
}) => {
  const { isMobile } = useResponsive();
  const statSpan = statCount >= 3 ? 8 : 12;

  return (
    <div>
      <div
        style={{
          display: 'flex',
          flexDirection: isMobile ? 'column' : 'row',
          alignItems: isMobile ? 'stretch' : 'flex-start',
          justifyContent: 'space-between',
          gap: spacing.md,
          marginBottom: spacing.md,
        }}
      >
        <Space direction="vertical" size={spacing.sm} style={{ minWidth: 0 }}>
          <Skeleton.Button active size="small" style={{ width: 112 }} />
          <Skeleton.Input active style={{ width: isMobile ? 220 : 320, maxWidth: '100%' }} />
        </Space>
        <Space size={spacing.sm} wrap>
          <Skeleton.Button active style={{ width: 108 }} />
          <Skeleton.Button active shape="circle" />
        </Space>
      </div>

      {showTabs ? (
        <Space wrap size={spacing.sm} style={{ marginBottom: spacing.lg }}>
          <Skeleton.Button active style={{ width: 120 }} />
          <Skeleton.Button active style={{ width: 120 }} />
          <Skeleton.Button active style={{ width: 120 }} />
        </Space>
      ) : null}

      <Row gutter={[16, 16]} style={{ marginBottom: spacing.lg }}>
        {Array.from({ length: statCount }).map((_, index) => (
          <Col key={index} xs={24} sm={12} lg={statSpan}>
            <PlaceholderCard rows={1} titleWidth="46%" />
          </Col>
        ))}
      </Row>

      <PlaceholderCard rows={isMobile ? 7 : 9} titleWidth="38%" style={{ marginBottom: spacing.md }} />

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <PlaceholderCard rows={6} titleWidth="44%" />
        </Col>
        <Col xs={24} lg={12}>
          <PlaceholderCard rows={6} titleWidth="44%" />
        </Col>
      </Row>
    </div>
  );
};
