import React from 'react';
import { Card, Select, Button, Avatar, Space, Typography } from 'antd';
import { UserOutlined, GlobalOutlined, BgColorsOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/AuthProvider';
import PageHeader from '../components/common/PageHeader';
import LanguageSelector from '../components/common/LanguageSelector';
import { useThemeMode } from '../theme/ThemeProvider';
import type { ThemeMode } from '../theme/ThemeProvider';

const { Title, Text } = Typography;

const Settings: React.FC = () => {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const { mode, setMode } = useThemeMode();

  return (
    <div>
      <PageHeader
        title={t('pages.settings.title')}
        subtitle={t('pages.settings.subtitle')}
      />

      {/* Profile Section */}
      <Card
        title={
          <Space>
            <UserOutlined />
            <span>{t('pages.settings.profile')}</span>
          </Space>
        }
        style={{ marginBottom: 24 }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <Avatar size={64} icon={<UserOutlined />} />
          <div>
            <Title level={4} style={{ margin: 0 }}>{user?.display_name || 'User'}</Title>
            <Text type="secondary">{t('pages.settings.role')}: {user?.role || 'viewer'}</Text>
          </div>
        </div>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 16 }}>
          {t('pages.settings.profileSyncNote')}
        </Text>
      </Card>

      {/* Preferences Section */}
      <Card
        title={
          <Space>
            <GlobalOutlined />
            <span>{t('pages.settings.preferences')}</span>
          </Space>
        }
        style={{ marginBottom: 24 }}
      >
        <div style={{ marginBottom: 16 }}>
          <Text strong style={{ display: 'block', marginBottom: 8 }}>
            {t('pages.settings.language')}
          </Text>
          <LanguageSelector />
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
            {t('pages.settings.languageHelp')}
          </Text>
        </div>
      </Card>

      {/* Appearance Section */}
      <Card
        title={
          <Space>
            <BgColorsOutlined />
            <span>{t('pages.settings.appearance')}</span>
          </Space>
        }
        style={{ marginBottom: 24 }}
      >
        <div>
          <Text strong style={{ display: 'block', marginBottom: 8 }}>
            {t('pages.settings.theme')}
          </Text>
          <Select
            value={mode}
            onChange={(value: ThemeMode) => setMode(value)}
            style={{ width: '100%' }}
            options={[
              { value: 'auto', label: t('pages.settings.themeAuto') },
              { value: 'light', label: t('pages.settings.themeLight') },
              { value: 'dark', label: t('pages.settings.themeDark') },
            ]}
          />
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
            {t('pages.settings.themeHelp')}
          </Text>
        </div>
      </Card>

      {/* Account Section */}
      <Card title={t('pages.settings.account')}>
        <div>
          <Title level={5} style={{ marginBottom: 8 }}>{t('pages.settings.signOut')}</Title>
          <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
            {t('pages.settings.signOutDescription')}
          </Text>
          <Button danger onClick={logout}>
            {t('pages.settings.signOut')}
          </Button>
        </div>
      </Card>
    </div>
  );
};

export default Settings;
