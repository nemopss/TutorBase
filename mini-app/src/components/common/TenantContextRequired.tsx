import React from 'react';
import { Alert, Card, Empty, Space, Typography } from 'antd';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../auth/AuthProvider';

interface TenantContextRequiredProps {
  sectionLabel: string;
}

const TenantContextRequired: React.FC<TenantContextRequiredProps> = ({ sectionLabel }) => {
  const { t } = useTranslation();
  const { canSwitchTenant, tenantId } = useAuth();

  const hintKey = canSwitchTenant
    ? 'common.tenantContextRequired.switchHint'
    : 'common.tenantContextRequired.noSwitcherHint';

  return (
    <Card>
      <Empty description={t('common.tenantContextRequired.title')}>
        <Space direction="vertical" size={12} style={{ width: '100%', maxWidth: 560 }}>
          {tenantId === null && (
            <Typography.Text type="secondary">
              {t('common.tenantContextRequired.globalContextNotice')}
            </Typography.Text>
          )}

          <Typography.Text>
            {t('common.tenantContextRequired.description', { section: sectionLabel })}
          </Typography.Text>

          <Alert
            type={canSwitchTenant ? 'info' : 'warning'}
            showIcon
            message={t(hintKey)}
          />
        </Space>
      </Empty>
    </Card>
  );
};

export default TenantContextRequired;
