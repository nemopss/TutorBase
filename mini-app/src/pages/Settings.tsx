import React, { useEffect, useState } from 'react';
import { Avatar, Button, Card, Form, Input, Typography, message } from 'antd';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/AuthProvider';
import PageIntro from '../components/common/PageIntro';
import LanguageSelector from '../components/common/LanguageSelector';
import ThemeSelector from '../components/common/ThemeSelector';
import { spacing } from '../theme/tokens';
import { useTheme } from '../theme/ThemeProvider';
import api from '../services/api';

const { Title, Text } = Typography;

const PAID_PLAN_OPTIONS = [
  { value: 'basic', name: 'Базовый', price: 349, limit: 10, order: 20 },
  { value: 'pro', name: 'Про', price: 649, limit: 20, order: 30 },
  { value: 'studio', name: 'Бизнес', price: 1190, limit: 50, order: 40 },
];

type CheckoutPreview = {
  plan_code: string;
  plan_name: string;
  billing_action: 'new' | 'renewal' | 'upgrade' | string;
  amount_due: string;
  full_amount: string;
  credit_amount: string;
  current_plan_name?: string | null;
  resulting_period_end: string;
  message: string;
};

const getApiDetail = (error: unknown): unknown => (
  (error as { response?: { data?: { detail?: unknown } } } | undefined)?.response?.data?.detail
);

const planOrderByCode = Object.fromEntries(PAID_PLAN_OPTIONS.map((plan) => [plan.value, plan.order]));

const Settings: React.FC = () => {
  const { t, i18n } = useTranslation();
  const { user, tenantAccess, billing, logout, setEmailPassword } = useAuth();
  const { resolvedTheme } = useTheme();
  const colors = resolvedTheme.colors;
  const isStaff = user?.role === 'teacher' || user?.is_platform_admin;
  const shouldShowAccess = isStaff && tenantAccess && tenantAccess.status !== 'global';
  const tileRadius = 10;
  const tileStyle = {
    background: colors.bgSecondary,
    border: `0px solid ${colors.borderPrimary}`,
    borderRadius: tileRadius,
    boxShadow: 'none',
  };
  const cardHeaderStyle = { borderBottom: 0 };

  const [checkoutPlanCode, setCheckoutPlanCode] = useState('basic');
  const [isCheckoutLoading, setIsCheckoutLoading] = useState(false);
  const [checkoutPreview, setCheckoutPreview] = useState<CheckoutPreview | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [checkoutPreviewError, setCheckoutPreviewError] = useState<string | null>(null);
  const [emailForm] = Form.useForm();
  const [isEmailSaving, setIsEmailSaving] = useState(false);
  const [isVerificationSending, setIsVerificationSending] = useState(false);

  const formatDate = (value?: string | null) => {
    if (!value) return null;
    return new Intl.DateTimeFormat(i18n.language || 'ru', {
      day: '2-digit',
      month: 'long',
      year: 'numeric',
    }).format(new Date(value));
  };

  const formatCurrency = (value: string | number) => (
    `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(Number(value))} ₽`
  );

  const accessUntil = formatDate(tenantAccess?.access_until);
  const graceUntil = formatDate(tenantAccess?.grace_until);
  const accessDaysLeft = tenantAccess?.access_until
    ? Math.ceil((new Date(tenantAccess.access_until).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
    : null;

  const accessStatusConfig = (() => {
    if (!shouldShowAccess) return null;

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
  const activePaidPlanCode = billing?.plan_code && billing.plan_code !== 'start' ? billing.plan_code : null;
  const activePaidPlanOrder = activePaidPlanCode ? planOrderByCode[activePaidPlanCode] : undefined;
  const selectedPlan = PAID_PLAN_OPTIONS.find((plan) => plan.value === checkoutPlanCode) ?? PAID_PLAN_OPTIONS[0];
  const selectedPlanOrder = planOrderByCode[checkoutPlanCode];
  const hasActivePaidPeriod = Boolean(
    activePaidPlanCode
    && billing?.current_period_end
    && new Date(billing.current_period_end).getTime() > Date.now(),
  );
  const hasLifetimePaidSubscription = Boolean(
    billing?.subscription_plan_code
    && billing.subscription_plan_code !== 'start'
    && !billing.current_period_end
    && (billing.subscription_status === 'manual' || billing.subscription_status === 'active'),
  );
  const tariffPeriodConfig = (() => {
    if (!billing) return null;

    const hasPaidSubscription = Boolean(
      billing.subscription_plan_code && billing.subscription_plan_code !== 'start',
    );
    const periodEnd = billing.current_period_end ? new Date(billing.current_period_end) : null;
    const periodEndLabel = formatDate(billing.current_period_end);

    if (!periodEnd) {
      return {
        value: 'Бессрочно',
        hint: billing.plan_code === 'start'
          ? 'Старт до 3 активных'
          : 'Выдано владельцем сервиса',
      };
    }

    const daysLeft = Math.ceil((periodEnd.getTime() - Date.now()) / (1000 * 60 * 60 * 24));
    if (daysLeft >= 0 && billing.plan_code !== 'start') {
      return {
        value: `до ${periodEndLabel}`,
        hint: `Осталось дней: ${Math.max(daysLeft, 0)}`,
      };
    }

    return {
      value: hasPaidSubscription && periodEndLabel ? `закончился ${periodEndLabel}` : 'Бессрочно',
      hint: hasPaidSubscription ? 'Сейчас применяются условия Старт' : 'Старт до 3 активных',
    };
  })();
  const isDowngradeBlocked = Boolean(
    hasActivePaidPeriod
    && activePaidPlanOrder
    && selectedPlanOrder
    && selectedPlanOrder < activePaidPlanOrder,
  );

  useEffect(() => {
    if (!billing) return;
    setCheckoutPlanCode(billing.plan_code && billing.plan_code !== 'start' ? billing.plan_code : 'basic');
  }, [billing]);

  useEffect(() => {
    if (!isStaff || !billing || isDowngradeBlocked || hasLifetimePaidSubscription) {
      setCheckoutPreview(null);
      setCheckoutPreviewError(isDowngradeBlocked ? 'Переход на тариф ниже доступен после окончания текущего оплаченного периода.' : null);
      return;
    }

    let cancelled = false;
    setIsPreviewLoading(true);
    setCheckoutPreviewError(null);
    api.post<CheckoutPreview>('/billing/checkout/preview', {
      plan_code: checkoutPlanCode,
      billing_period: 'month',
    })
      .then((response) => {
        if (!cancelled) setCheckoutPreview(response.data);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          const detail = getApiDetail(error);
          setCheckoutPreview(null);
          setCheckoutPreviewError(typeof detail === 'string' ? detail : 'Не удалось рассчитать оплату');
        }
      })
      .finally(() => {
        if (!cancelled) setIsPreviewLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [billing, checkoutPlanCode, hasLifetimePaidSubscription, isDowngradeBlocked, isStaff]);

  const ctaText = (() => {
    if (checkoutPreview?.billing_action === 'renewal') return 'Продлить на 30 дней';
    if (checkoutPreview?.billing_action === 'upgrade') return `Перейти на ${checkoutPreview.plan_name}`;
    return `Оплатить ${selectedPlan.name}`;
  })();

  const actionLabel = (() => {
    if (checkoutPreview?.billing_action === 'upgrade') return 'Переход';
    if (checkoutPreview?.billing_action === 'renewal') return 'Продление';
    return 'Новый период';
  })();

  const handleCheckout = async () => {
    setIsCheckoutLoading(true);
    try {
      const response = await api.post<{
        payment_id: string;
        status: string;
        confirmation_url: string;
        amount_due: string;
        billing_action: string;
      }>('/billing/checkout', {
        plan_code: checkoutPlanCode,
        billing_period: 'month',
      });
      window.location.assign(response.data.confirmation_url);
    } catch (error: unknown) {
      const detail = getApiDetail(error);
      message.error(typeof detail === 'string' ? detail : 'Не удалось создать платёж');
    } finally {
      setIsCheckoutLoading(false);
    }
  };

  const handleEmailPasswordSubmit = async (values: { email: string; password: string }) => {
    setIsEmailSaving(true);
    try {
      await setEmailPassword({
        email: values.email.trim(),
        password: values.password,
      });
      emailForm.resetFields(['password']);
      message.success('Email и пароль сохранены. Теперь подтвердите email письмом.');
    } catch (error: unknown) {
      const detail = getApiDetail(error);
      message.error(typeof detail === 'string' ? detail : 'Не удалось сохранить email и пароль');
    } finally {
      setIsEmailSaving(false);
    }
  };

  const handleSendEmailVerification = async () => {
    setIsVerificationSending(true);
    try {
      await api.post('/auth/email/verification/send');
      message.success('Письмо для подтверждения отправлено');
    } catch (error: unknown) {
      const detail = getApiDetail(error);
      message.error(typeof detail === 'string' ? detail : 'Не удалось отправить письмо');
    } finally {
      setIsVerificationSending(false);
    }
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const verificationResult = params.get('email_verified');
    if (!verificationResult) {
      return;
    }
    if (verificationResult === '1') {
      message.success('Email подтверждён');
    } else {
      message.error('Не удалось подтвердить email. Запросите новое письмо.');
    }
    params.delete('email_verified');
    const query = params.toString();
    window.history.replaceState(null, '', `${window.location.pathname}${query ? `?${query}` : ''}`);
  }, []);

  return (
    <div>
      <PageIntro
        title={t('pages.settings.title')}
        subtitle={t('pages.settings.subtitle')}
      />

      <div style={{ display: 'grid', gap: spacing.lg }}>
        <Card bordered={false} style={tileStyle} styles={{ header: cardHeaderStyle }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: spacing.md }}>
            <Avatar
              size={56}
              style={{
                background: colors.bgTertiary,
                color: colors.textPrimary,
                fontWeight: 600,
              }}
            >
              {(user?.display_name || 'U').slice(0, 1).toUpperCase()}
            </Avatar>
            <div>
              <Title level={4} style={{ margin: 0, color: colors.textPrimary }}>
                {user?.display_name || 'User'}
              </Title>
              <Text type="secondary">{t('pages.settings.role')}: {user?.role || 'viewer'}</Text>
            </div>
          </div>
          <Text type="secondary" style={{ display: 'block', marginTop: spacing.md, fontSize: 12 }}>
            {t('pages.settings.profileSyncNote')}
          </Text>
        </Card>

        {isStaff && (
          <Card bordered={false} style={tileStyle} styles={{ header: cardHeaderStyle }}>
            <Title level={4} style={{ marginTop: 0, color: colors.textPrimary }}>
              Email для входа
            </Title>
            <Text type="secondary" style={{ display: 'block', marginBottom: spacing.md }}>
              {user?.email
                ? `Подключён: ${user.email}${user.email_verified_at ? ' · подтверждён' : ' · не подтверждён'}`
                : 'Добавьте email и пароль, чтобы входить в браузерный кабинет без Telegram.'}
            </Text>
            {user?.email && !user.email_verified_at && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: spacing.md,
                flexWrap: 'wrap',
                padding: spacing.md,
                borderRadius: tileRadius,
                background: colors.bgTertiary,
                marginBottom: spacing.md,
              }}>
                <Text style={{ color: colors.textPrimary }}>
                  Подтвердите email, чтобы позже восстановить доступ к аккаунту.
                </Text>
                <Button loading={isVerificationSending} onClick={handleSendEmailVerification}>
                  Отправить письмо
                </Button>
              </div>
            )}
            <Form
              form={emailForm}
              layout="vertical"
              requiredMark={false}
              initialValues={{ email: user?.email ?? '' }}
              onFinish={handleEmailPasswordSubmit}
            >
              <Form.Item
                label="Email"
                name="email"
                rules={[
                  { required: true, message: 'Введите email' },
                  { type: 'email', message: 'Введите корректный email' },
                ]}
              >
                <Input type="email" autoComplete="email" size="large" variant="filled" />
              </Form.Item>
              <Form.Item
                label="Новый пароль"
                name="password"
                rules={[
                  { required: true, message: 'Введите пароль' },
                  { min: 8, message: 'Пароль должен быть не короче 8 символов' },
                ]}
              >
                <Input.Password autoComplete="new-password" size="large" variant="filled" />
              </Form.Item>
              <Button type="primary" htmlType="submit" loading={isEmailSaving}>
                Сохранить email и пароль
              </Button>
            </Form>
          </Card>
        )}

        {isStaff && (accessStatusConfig || billing) && (
          <Card bordered={false} style={tileStyle} styles={{ header: cardHeaderStyle }}>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              gap: spacing.md,
              alignItems: 'flex-start',
              flexWrap: 'wrap',
            }}>
              <div>
                <Text type="secondary" style={{ display: 'block', marginBottom: spacing.xs }}>
                  Доступ к сервису
                </Text>
                <Title level={4} style={{ margin: 0, color: colors.textPrimary }}>
                  {accessStatusConfig?.title || billing?.plan_name}
                </Title>
                {accessStatusConfig && (
                  <Text type="secondary" style={{ display: 'block', marginTop: spacing.xs }}>
                    {accessStatusConfig.description}
                  </Text>
                )}
              </div>
            </div>

            {billing && (
              <>
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                  gap: spacing.md,
                  marginTop: spacing.lg,
                }}>
                  {[
                    ['Тариф', billing.plan_name, billing.monthly_price_rub > 0 ? `${billing.monthly_price_rub} ₽ / 30 дней` : 'Бесплатно'],
                    ['Период', tariffPeriodConfig?.value ?? '—', tariffPeriodConfig?.hint ?? ''],
                    ['Ученики', `${billing.active_learners_count}/${billing.active_learners_limit} активных`, `${learnerUsagePercent}% лимита занято`],
                    ['Уведомления', billing.notifications_allowed ? 'Работают' : 'Отключены', 'Telegram-сценарии'],
                  ].map(([label, value, hint]) => (
                    <div key={label} style={{ padding: spacing.md, borderRadius: tileRadius, background: colors.bgTertiary }}>
                      <Text type="secondary" style={{ display: 'block', fontSize: 12 }}>{label}</Text>
                      <Text strong style={{ display: 'block', marginTop: spacing.xs, color: colors.textPrimary }}>
                        {value}
                      </Text>
                      <Text type="secondary" style={{ display: 'block', marginTop: spacing.xs, fontSize: 12 }}>
                        {hint}
                      </Text>
                    </div>
                  ))}
                </div>

                {!billing.notifications_allowed && (
                  <div style={{ marginTop: spacing.md, padding: spacing.md, borderRadius: tileRadius, background: colors.bgTertiary }}>
                    <Text type="warning">
                      Подписка не действует, а активных учеников больше бесплатного лимита. Данные доступны, но Telegram-уведомления отключены.
                    </Text>
                  </div>
                )}

                {!hasLifetimePaidSubscription && (
                <div style={{ marginTop: spacing.lg }}>
                  <div style={{ marginBottom: spacing.md }}>
                    <Title level={5} style={{ margin: 0, color: colors.textPrimary }}>Оплата тарифа</Title>
                    <Text type="secondary" style={{ display: 'block', marginTop: spacing.xs }}>
                      Сумма и срок тарифа рассчитываются до перехода в ЮKassa.
                    </Text>
                  </div>

                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                    gap: spacing.sm,
                  }}>
                    {PAID_PLAN_OPTIONS.map((plan) => {
                      const isSelected = checkoutPlanCode === plan.value;
                      const isCurrent = billing.plan_code === plan.value;
                      const isBlocked = Boolean(hasActivePaidPeriod && activePaidPlanOrder && plan.order < activePaidPlanOrder);
                      return (
                        <button
                          key={plan.value}
                          type="button"
                          onClick={() => !isBlocked && setCheckoutPlanCode(plan.value)}
                          disabled={isBlocked}
                          style={{
                            textAlign: 'left',
                            padding: spacing.md,
                            borderRadius: tileRadius,
                            border: 0,
                            background: isSelected ? colors.textPrimary : colors.bgTertiary,
                            color: isSelected ? colors.bgPrimary : colors.textPrimary,
                            cursor: isBlocked ? 'not-allowed' : 'pointer',
                            opacity: isBlocked ? 0.45 : 1,
                          }}
                        >
                          <span style={{ display: 'flex', justifyContent: 'space-between', gap: spacing.sm, alignItems: 'center' }}>
                            <span style={{ fontWeight: 700 }}>{plan.name}</span>
                            {isCurrent && (
                              <span style={{
                                fontSize: 11,
                                color: isSelected ? colors.bgPrimary : colors.textSecondary,
                                opacity: 0.8,
                              }}>
                                текущий
                              </span>
                            )}
                          </span>
                          <span style={{
                            display: 'block',
                            marginTop: spacing.xs,
                            color: isSelected ? colors.bgPrimary : colors.textSecondary,
                            opacity: isSelected ? 0.85 : 1,
                          }}>
                            до {plan.limit} активных
                          </span>
                          <span style={{ display: 'block', marginTop: spacing.sm, fontWeight: 600 }}>
                            {formatCurrency(plan.price)}
                          </span>
                        </button>
                      );
                    })}
                  </div>

                  <div style={{
                    marginTop: spacing.md,
                    padding: spacing.md,
                    borderRadius: tileRadius,
                    background: colors.bgTertiary,
                    display: 'grid',
                    gap: spacing.sm,
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: spacing.md, alignItems: 'baseline' }}>
                      <div>
                        <Text type="secondary" style={{ display: 'block' }}>К оплате</Text>
                        <Title level={3} style={{ margin: 0, color: colors.textPrimary }}>
                          {checkoutPreview ? formatCurrency(checkoutPreview.amount_due) : formatCurrency(selectedPlan.price)}
                        </Title>
                      </div>
                      <Text type="secondary">{actionLabel}</Text>
                    </div>

                    <div style={{ display: 'grid', gap: 4 }}>
                      {checkoutPreview?.billing_action === 'upgrade' && (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          Остаток текущего тарифа учтён: {formatCurrency(checkoutPreview.credit_amount)}. Доплата считается за оставшиеся оплаченные дни.
                        </Text>
                      )}
                      <Text type={checkoutPreviewError ? 'danger' : 'secondary'} style={{ fontSize: 12 }}>
                        {checkoutPreviewError
                          || checkoutPreview?.message
                          || `Тариф «${selectedPlan.name}» включится после подтверждения платежа.`}
                      </Text>
                      {checkoutPreview && (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          Тариф будет действовать до {formatDate(checkoutPreview.resulting_period_end)}.
                        </Text>
                      )}
                    </div>

                    <Button
                      loading={isCheckoutLoading || isPreviewLoading}
                      disabled={Boolean(checkoutPreviewError) || isPreviewLoading}
                      onClick={handleCheckout}
                      style={{
                        width: 'fit-content',
                        minWidth: 190,
                        height: 40,
                        borderRadius: 8,
                        background: colors.textPrimary,
                        borderColor: colors.textPrimary,
                        color: colors.bgPrimary,
                        fontWeight: 700,
                      }}
                    >
                      {ctaText}
                    </Button>
                  </div>
                </div>
                )}
              </>
            )}
          </Card>
        )}

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: spacing.lg,
        }}>
          <Card bordered={false} style={tileStyle} styles={{ header: cardHeaderStyle }}>
            <Title level={5} style={{ marginTop: 0, color: colors.textPrimary }}>
              {t('pages.settings.preferences')}
            </Title>
            <Text strong style={{ display: 'block', marginBottom: spacing.sm }}>
              {t('pages.settings.language')}
            </Text>
            <LanguageSelector />
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: spacing.sm }}>
              {t('pages.settings.languageHelp')}
            </Text>
          </Card>

          <Card bordered={false} style={tileStyle} styles={{ header: cardHeaderStyle }}>
            <Title level={5} style={{ marginTop: 0, color: colors.textPrimary }}>
              {t('pages.settings.appearance')}
            </Title>
            <Text strong style={{ display: 'block', marginBottom: spacing.md }}>
              {t('pages.settings.theme')}
            </Text>
            <ThemeSelector />
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: spacing.sm }}>
              {t('pages.settings.themeHelp')}
            </Text>
          </Card>
        </div>

        <Card bordered={false} style={tileStyle} styles={{ header: cardHeaderStyle }}>
          <Title level={5} style={{ marginTop: 0, color: colors.textPrimary }}>
            {t('pages.settings.account')}
          </Title>
          <Text type="secondary" style={{ display: 'block', marginBottom: spacing.md }}>
            {t('pages.settings.signOutDescription')}
          </Text>
          <Button danger onClick={logout}>
            {t('pages.settings.signOut')}
          </Button>
        </Card>
      </div>
    </div>
  );
};

export default Settings;
