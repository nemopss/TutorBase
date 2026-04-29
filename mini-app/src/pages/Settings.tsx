import React from 'react';
import { Card, Button, Avatar, Space, Typography, Tag } from 'antd';
import {
  BellOutlined,
  BgColorsOutlined,
  CreditCardOutlined,
  FieldTimeOutlined,
  GlobalOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/AuthProvider';
import PageIntro from '../components/common/PageIntro';
import LanguageSelector from '../components/common/LanguageSelector';
import ThemeSelector from '../components/common/ThemeSelector';
import { spacing } from '../theme/tokens';
import { useTheme } from '../theme/ThemeProvider';

const { Title, Text } = Typography;

const Settings: React.FC = () => {
  const { t, i18n } = useTranslation();
  const { user, tenantAccess, billing, logout } = useAuth();
  const { resolvedTheme } = useTheme();
  const colors = resolvedTheme.colors;
  const isStaff = user?.role === 'teacher' || user?.is_platform_admin;
  const shouldShowAccess = isStaff && tenantAccess && tenantAccess.status !== 'global';

  const formatAccessDate = (value?: string | null) => {
    if (!value) return null;
    return new Intl.DateTimeFormat(i18n.language || 'ru', {
      day: '2-digit',
      month: 'long',
      year: 'numeric',
    }).format(new Date(value));
  };

  const accessUntil = formatAccessDate(tenantAccess?.access_until);
  const graceUntil = formatAccessDate(tenantAccess?.grace_until);
  const accessDaysLeft = tenantAccess?.access_until
    ? Math.ceil((new Date(tenantAccess.access_until).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
    : null;

  const accessStatusConfig = (() => {
    if (!shouldShowAccess) {
      return null;
    }

    if (tenantAccess.is_lifetime || tenantAccess.status === 'lifetime') {
      return {
        color: 'green',
        label: t('pages.settings.access.statusLifetime'),
        title: t('pages.settings.access.lifetimeTitle'),
        description: t('pages.settings.access.lifetimeDescription'),
      };
    }

    if (tenantAccess.status === 'trial') {
      return {
        color: 'blue',
        label: t('pages.settings.access.statusTrial'),
        title: accessUntil
          ? t('pages.settings.access.trialTitleWithDate', { date: accessUntil })
          : t('pages.settings.access.trialTitle'),
        description: accessDaysLeft !== null
          ? t('pages.settings.access.trialDescriptionWithDays', { count: Math.max(accessDaysLeft, 0) })
          : t('pages.settings.access.trialDescription'),
      };
    }

    if (tenantAccess.status === 'active') {
      return {
        color: 'green',
        label: t('pages.settings.access.statusActive'),
        title: accessUntil
          ? t('pages.settings.access.activeTitleWithDate', { date: accessUntil })
          : t('pages.settings.access.activeTitle'),
        description: t('pages.settings.access.activeDescription'),
      };
    }

    if (tenantAccess.status === 'grace') {
      return {
        color: 'gold',
        label: t('pages.settings.access.statusGrace'),
        title: graceUntil
          ? t('pages.settings.access.graceTitleWithDate', { date: graceUntil })
          : t('pages.settings.access.graceTitle'),
        description: t('pages.settings.access.graceDescription'),
      };
    }

    if (tenantAccess.status === 'suspended') {
      return {
        color: 'red',
        label: t('pages.settings.access.statusSuspended'),
        title: t('pages.settings.access.suspendedTitle'),
        description: t('pages.settings.access.suspendedDescription'),
      };
    }

    if (tenantAccess.status === 'expired') {
      return {
        color: 'red',
        label: t('pages.settings.access.statusExpired'),
        title: t('pages.settings.access.expiredTitle'),
        description: graceUntil
          ? t('pages.settings.access.expiredDescriptionWithDate', { date: graceUntil })
          : t('pages.settings.access.expiredDescription'),
      };
    }

    return {
      color: 'default',
      label: tenantAccess.status,
      title: t('pages.settings.access.unknownTitle'),
      description: t('pages.settings.access.unknownDescription'),
    };
  })();

  const learnerUsagePercent = billing?.active_learners_limit
    ? Math.min(100, Math.round((billing.active_learners_count / billing.active_learners_limit) * 100))
    : 0;
  const learnerUsageColor = !billing?.can_create_learner
    ? '#fa8c16'
    : colors.accentPrimary;

  return (
    <div>
      <PageIntro
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
        style={{ marginBottom: spacing.lg }}
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

      {isStaff && (accessStatusConfig || billing) && (
        <Card
          bordered={false}
          style={{
            marginBottom: spacing.lg,
            background: `linear-gradient(135deg, ${colors.bgSecondary} 0%, ${colors.bgPrimary} 100%)`,
            borderRadius: 8,
            border: `1px solid ${colors.borderPrimary}`,
          }}
        >
          <div style={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: spacing.md,
          }}>
            <Space align="start" size={spacing.md}>
              <div style={{
                width: 44,
                height: 44,
                borderRadius: 8,
                background: colors.bgTertiary,
                color: colors.accentPrimary,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 22,
                flex: '0 0 auto',
              }}>
                <FieldTimeOutlined />
              </div>
              <div>
                <Text style={{
                  display: 'block',
                  color: colors.textSecondary,
                  marginBottom: spacing.xs,
                }}>
                  Доступ к сервису
                </Text>
                {accessStatusConfig && (
                  <>
                    <Title level={4} style={{ margin: 0, color: colors.textPrimary }}>
                      {accessStatusConfig.title}
                    </Title>
                    <Text style={{
                      display: 'block',
                      color: colors.textSecondary,
                      marginTop: spacing.xs,
                    }}>
                      {accessStatusConfig.description}
                    </Text>
                  </>
                )}
              </div>
            </Space>
            <Space wrap size={8} style={{ justifyContent: 'flex-end' }}>
              {accessStatusConfig && (
                <Tag color={accessStatusConfig.color} style={{ margin: 0 }}>
                  {accessStatusConfig.label}
                </Tag>
              )}
              {billing && (
                <Tag color={billing.notifications_allowed ? 'green' : 'gold'} style={{ margin: 0 }}>
                  {billing.plan_name}
                </Tag>
              )}
            </Space>
          </div>

          {billing && (
            <>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                gap: spacing.md,
                marginTop: spacing.lg,
              }}>
                <div style={{
                  padding: spacing.md,
                  borderRadius: 8,
                  background: colors.bgSecondary,
                  border: `1px solid ${colors.borderPrimary}`,
                }}>
                  <Space align="start" size={spacing.sm}>
                    <CreditCardOutlined style={{ color: colors.accentPrimary, fontSize: 18, marginTop: 2 }} />
                    <div>
                      <Text type="secondary" style={{ display: 'block' }}>Тариф</Text>
                      <Text strong style={{ display: 'block', color: colors.textPrimary }}>{billing.plan_name}</Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {billing.monthly_price_rub > 0 ? `${billing.monthly_price_rub} ₽/мес.` : 'Бесплатно'}
                      </Text>
                    </div>
                  </Space>
                </div>
                <div style={{
                  padding: spacing.md,
                  borderRadius: 8,
                  background: colors.bgSecondary,
                  border: `1px solid ${colors.borderPrimary}`,
                }}>
                  <Space align="start" size={spacing.sm}>
                    <TeamOutlined style={{ color: learnerUsageColor, fontSize: 18, marginTop: 2 }} />
                    <div style={{ width: '100%' }}>
                      <Text type="secondary" style={{ display: 'block' }}>Ученики</Text>
                      <Text strong style={{ display: 'block', color: colors.textPrimary }}>
                        {billing.active_learners_count}/{billing.active_learners_limit} активных
                      </Text>
                      <div style={{
                        height: 6,
                        borderRadius: 6,
                        background: colors.bgTertiary,
                        overflow: 'hidden',
                        marginTop: 8,
                      }}>
                        <div style={{
                          width: `${learnerUsagePercent}%`,
                          height: '100%',
                          borderRadius: 6,
                          background: learnerUsageColor,
                        }} />
                      </div>
                    </div>
                  </Space>
                </div>
                <div style={{
                  padding: spacing.md,
                  borderRadius: 8,
                  background: colors.bgSecondary,
                  border: `1px solid ${colors.borderPrimary}`,
                }}>
                  <Space align="start" size={spacing.sm}>
                    <BellOutlined
                      style={{
                        color: billing.notifications_allowed ? colors.accentPrimary : '#fa8c16',
                        fontSize: 18,
                        marginTop: 2,
                      }}
                    />
                    <div>
                      <Text type="secondary" style={{ display: 'block' }}>Уведомления</Text>
                      <Text strong style={{ display: 'block', color: colors.textPrimary }}>
                        {billing.notifications_allowed ? 'Работают' : 'Отключены'}
                      </Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        Telegram-сценарии
                      </Text>
                    </div>
                  </Space>
                </div>
              </div>
              {!billing.notifications_allowed && (
                <div style={{
                  marginTop: spacing.md,
                  padding: spacing.md,
                  borderRadius: 8,
                  background: 'rgba(250, 173, 20, 0.12)',
                  border: '1px solid #faad14',
                }}>
                  <Text type="warning">
                    Подписка не действует, а активных учеников больше бесплатного лимита. Данные доступны, но Telegram-уведомления отключены.
                  </Text>
                </div>
              )}
              <Text type="secondary" style={{ display: 'block', marginTop: spacing.md, fontSize: 12 }}>
                Онлайн-оплата платных тарифов пока не подключена. Сейчас тарифы показываются справочно, доступ управляется сервисной поддержкой.
              </Text>
            </>
          )}
        </Card>
      )}
      {/* Preferences Section */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: spacing.md,
          marginBottom: spacing.lg,
        }}
      >
        <Card
          title={
            <Space>
              <GlobalOutlined />
              <span>{t('pages.settings.preferences')}</span>
            </Space>
          }
        >
          <div>
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
        >
          <div>
            <Text strong style={{ display: 'block', marginBottom: 12 }}>
              {t('pages.settings.theme')}
            </Text>
            <ThemeSelector />
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 8 }}>
              {t('pages.settings.themeHelp')}
            </Text>
          </div>
        </Card>
      </div>

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
