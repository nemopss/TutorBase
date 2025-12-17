import { Card, Typography, Button } from 'antd';
import { LockOutlined, ReloadOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useTelegram } from '../hooks/useTelegram';
import { useAuth } from '../auth/AuthProvider';

const AccessDenied = () => {
  const { t } = useTranslation();
  const { tg } = useTelegram();
  const { user } = useAuth();

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
        background: 'var(--tg-theme-bg-color, #f7f7f5)',
      }}
    >
      <Card
        style={{ maxWidth: 420, width: '100%', textAlign: 'center' }}
        bordered={false}
      >
        <LockOutlined style={{ fontSize: 48, color: '#fa8c16' }} />
        <Typography.Title level={3} style={{ marginTop: 16 }}>
          {t('pages.accessDenied.title')}
        </Typography.Title>
        <Typography.Paragraph type="secondary">
          {t('pages.accessDenied.restrictedMessage', { name: user?.display_name })}
        </Typography.Paragraph>
        <Button
          type="primary"
          icon={<ReloadOutlined />}
          onClick={() => window.location.reload()}
          block
        >
          {t('pages.accessDenied.refresh')}
        </Button>
        {tg && (
          <Button
            style={{ marginTop: 12 }}
            onClick={() => tg.close()}
            block
          >
            {t('pages.accessDenied.closeMiniApp')}
          </Button>
        )}
      </Card>
    </div>
  );
};

export default AccessDenied;
