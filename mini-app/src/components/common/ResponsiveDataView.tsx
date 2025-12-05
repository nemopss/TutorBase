import React from 'react';
import { Table, List, Spin, Pagination } from 'antd';
import type { TableProps, TablePaginationConfig } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useResponsive } from '../../hooks/useResponsive';
import { spacing } from '../../theme/tokens';
import EmptyState from './EmptyState';

export interface ResponsiveDataViewProps<T> {
  /** Data array to display */
  data: T[];
  /** Loading state */
  loading?: boolean;
  /** Table columns for desktop view */
  columns: ColumnsType<T>;
  /** Additional table props for desktop */
  tableProps?: Omit<TableProps<T>, 'dataSource' | 'columns' | 'loading' | 'pagination'>;
  /** Render function for mobile card view */
  renderCard: (item: T, index: number) => React.ReactNode;
  /** Empty state text */
  emptyText?: string;
  /** Empty state description */
  emptyDescription?: string;
  /** Empty state action button text */
  emptyActionText?: string;
  /** Empty state action callback */
  onEmptyAction?: () => void;
  /** Row key extractor */
  rowKey?: string | ((record: T) => string);
  /** Pagination config (false to disable) */
  pagination?: TablePaginationConfig | false;
  /** Click handler for items */
  onItemClick?: (item: T) => void;
}

/**
 * Responsive data display component that shows Table on desktop and Cards on mobile.
 * Automatically switches based on viewport width (768px breakpoint).
 */
function ResponsiveDataView<T extends object>({
  data,
  loading = false,
  columns,
  tableProps,
  renderCard,
  emptyText = 'No data',
  emptyDescription,
  emptyActionText,
  onEmptyAction,
  rowKey = 'id',
  pagination,
  onItemClick,
}: ResponsiveDataViewProps<T>): React.ReactElement {
  const { isMobile } = useResponsive();

  // Loading state
  if (loading) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        minHeight: 200,
        padding: spacing.lg,
      }}>
        <Spin size="large" />
      </div>
    );
  }

  // Empty state
  if (!data || data.length === 0) {
    return (
      <EmptyState
        title={emptyText}
        description={emptyDescription}
        actionText={emptyActionText}
        onAction={onEmptyAction}
      />
    );
  }

  // Mobile: Card list view
  if (isMobile) {
    return (
      <div>
        <List
          dataSource={data}
          renderItem={(item, index) => (
            <div
              key={typeof rowKey === 'function' ? rowKey(item) : String((item as Record<string, unknown>)[rowKey])}
              onClick={() => onItemClick?.(item)}
              style={{ cursor: onItemClick ? 'pointer' : 'default' }}
            >
              {renderCard(item, index)}
            </div>
          )}
          split={false}
          style={{ marginBottom: spacing.md }}
        />
        {pagination !== false && data.length > 0 && (
          <div style={{ display: 'flex', justifyContent: 'center', padding: spacing.md }}>
            <Pagination
              {...(typeof pagination === 'object' ? pagination : {})}
              total={pagination && typeof pagination === 'object' ? pagination.total : data.length}
              size="small"
              showSizeChanger={false}
            />
          </div>
        )}
      </div>
    );
  }

  // Desktop: Table view
  return (
    <Table<T>
      dataSource={data}
      columns={columns}
      rowKey={rowKey}
      pagination={pagination}
      onRow={onItemClick ? (record) => ({
        onClick: () => onItemClick(record),
        style: { cursor: 'pointer' },
      }) : undefined}
      scroll={{ x: 'max-content' }}
      {...tableProps}
    />
  );
}

export default ResponsiveDataView;
