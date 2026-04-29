import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Button, Checkbox, Form, Input, Space, Typography } from 'antd';
import {
    ArrowLeftOutlined,
    BellOutlined,
    CalendarOutlined,
    CheckCircleOutlined,
    TeamOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/AuthProvider';
import { useResponsive } from '../hooks/useResponsive';
import { useTheme } from '../theme/ThemeProvider';
import { spacing } from '../theme/tokens';
import { devError } from '../utils/safeLogging';

const { Text } = Typography;

interface FormData {
    school_name: string;
    tutor_name?: string;
    offer_accepted: boolean;
    privacy_accepted: boolean;
}

const TutorRegistrationForm: React.FC = () => {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const { registerTutor } = useAuth();
    const { resolvedTheme } = useTheme();
    const { isMobile } = useResponsive();
    const colors = resolvedTheme.colors;
    const [form] = Form.useForm();

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (values: FormData) => {
        setLoading(true);
        setError(null);

        try {
            await registerTutor({
                school_name: values.school_name.trim(),
                tutor_name: values.tutor_name?.trim() || undefined,
                offer_accepted: values.offer_accepted,
                privacy_accepted: values.privacy_accepted,
            });
        } catch (err: any) {
            devError('Registration failed:', err);
            setError(err.response?.data?.detail || t('pages.tutorRegistration.genericError'));
        } finally {
            setLoading(false);
        }
    };

    const facts = [
        { icon: <TeamOutlined />, text: t('pages.tutorRegistration.factLearners') },
        { icon: <CalendarOutlined />, text: t('pages.tutorRegistration.factSchedule') },
        { icon: <BellOutlined />, text: t('pages.tutorRegistration.factReminders') },
        { icon: <CheckCircleOutlined />, text: t('pages.tutorRegistration.factTrial') },
    ];

    return (
        <main style={{
            minHeight: '100vh',
            background: colors.bgPrimary,
            color: colors.textPrimary,
            boxSizing: 'border-box',
            padding: isMobile ? `${spacing.md}px ${spacing.md}px ${spacing.xl}px` : `${spacing.xl}px`,
        }}>
            <div style={{ maxWidth: 1040, margin: '0 auto' }}>
                <Button
                    type="text"
                    icon={<ArrowLeftOutlined />}
                    onClick={() => navigate(-1)}
                    style={{
                        marginBottom: isMobile ? spacing.lg : spacing.xl,
                        color: colors.textSecondary,
                    }}
                >
                    {t('common.back', { defaultValue: 'Назад' })}
                </Button>

                <section style={{
                    display: 'grid',
                    gridTemplateColumns: isMobile ? '1fr' : 'minmax(0, 1fr) minmax(360px, 440px)',
                    gap: isMobile ? spacing.xl : 56,
                    alignItems: 'start',
                }}>
                    <div style={{ paddingTop: isMobile ? 0 : spacing.lg }}>
                        <Text style={{
                            display: 'inline-flex',
                            marginBottom: spacing.md,
                            color: colors.accentPrimary,
                            fontWeight: 700,
                        }}>
                            {t('pages.tutorRegistration.badge')}
                        </Text>
                        <h1 style={{
                            margin: 0,
                            color: colors.textPrimary,
                            fontSize: isMobile ? 32 : 44,
                            lineHeight: 1.05,
                            fontWeight: 760,
                            letterSpacing: 0,
                            maxWidth: 560,
                        }}>
                            {t('pages.tutorRegistration.title')}
                        </h1>
                        <p style={{
                            margin: `${spacing.md}px 0 0`,
                            color: colors.textSecondary,
                            fontSize: isMobile ? 15 : 17,
                            lineHeight: 1.55,
                            maxWidth: 540,
                        }}>
                            {t('pages.tutorRegistration.subtitle')}
                        </p>

                        <div style={{
                            display: 'grid',
                            gridTemplateColumns: isMobile ? '1fr' : 'repeat(2, minmax(0, 1fr))',
                            gap: spacing.sm,
                            marginTop: isMobile ? spacing.xl : 40,
                            maxWidth: 560,
                        }}>
                            {facts.map((item) => (
                                <div
                                    key={item.text}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: spacing.sm,
                                        minHeight: 44,
                                        borderRadius: 8,
                                        background: colors.bgSecondary,
                                        padding: `${spacing.sm}px ${spacing.md}px`,
                                    }}
                                >
                                    <span style={{
                                        color: colors.accentPrimary,
                                        display: 'inline-flex',
                                        fontSize: 18,
                                    }}>
                                        {item.icon}
                                    </span>
                                    <Text style={{ color: colors.textPrimary }}>{item.text}</Text>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div style={{
                        background: colors.bgSecondary,
                        borderRadius: 8,
                        padding: isMobile ? spacing.lg : spacing.xl,
                    }}>
                        <h2 style={{
                            margin: 0,
                            marginBottom: spacing.xs,
                            color: colors.textPrimary,
                            fontSize: isMobile ? 22 : 24,
                            lineHeight: 1.2,
                            fontWeight: 720,
                            letterSpacing: 0,
                        }}>
                            {t('pages.tutorRegistration.formTitle')}
                        </h2>
                        <Text style={{
                            display: 'block',
                            color: colors.textSecondary,
                            marginBottom: spacing.lg,
                        }}>
                            {t('pages.tutorRegistration.formSubtitle')}
                        </Text>

                        <Form
                            form={form}
                            layout="vertical"
                            onFinish={handleSubmit}
                            autoComplete="off"
                            requiredMark={false}
                        >
                            <Form.Item
                                label={t('pages.tutorRegistration.schoolNameLabel')}
                                name="school_name"
                                rules={[
                                    { required: true, message: t('pages.tutorRegistration.schoolNameRequired') },
                                    { min: 2, message: t('pages.tutorRegistration.schoolNameMinLength') },
                                ]}
                            >
                                <Input
                                    placeholder={t('pages.tutorRegistration.schoolNamePlaceholder')}
                                    size="large"
                                    autoFocus
                                    variant="filled"
                                />
                            </Form.Item>

                            <Form.Item
                                label={t('pages.tutorRegistration.yourNameLabel')}
                                name="tutor_name"
                            >
                                <Input
                                    placeholder={t('pages.tutorRegistration.yourNamePlaceholder')}
                                    size="large"
                                    variant="filled"
                                />
                            </Form.Item>

                            <Form.Item
                                name="offer_accepted"
                                valuePropName="checked"
                                rules={[
                                    {
                                        validator: (_, value) => value
                                            ? Promise.resolve()
                                            : Promise.reject(new Error('Необходимо принять оферту')),
                                    },
                                ]}
                                style={{ marginBottom: spacing.xs }}
                            >
                                <Checkbox>
                                    <Text type="secondary" style={{ fontSize: 12 }}>
                                        Принимаю <a href="/offer" target="_blank" rel="noreferrer">Публичную оферту</a>
                                    </Text>
                                </Checkbox>
                            </Form.Item>

                            <Form.Item
                                name="privacy_accepted"
                                valuePropName="checked"
                                rules={[
                                    {
                                        validator: (_, value) => value
                                            ? Promise.resolve()
                                            : Promise.reject(new Error('Необходимо согласие на обработку персональных данных')),
                                    },
                                ]}
                                style={{ marginBottom: spacing.md }}
                            >
                                <Checkbox>
                                    <Text type="secondary" style={{ fontSize: 12 }}>
                                        Согласен на обработку персональных данных и ознакомлен с{' '}
                                        <a href="/privacy" target="_blank" rel="noreferrer">Политикой обработки персональных данных</a>
                                    </Text>
                                </Checkbox>
                            </Form.Item>

                            {error && (
                                <Form.Item>
                                    <Alert
                                        message={t('pages.tutorRegistration.registrationFailed')}
                                        description={error}
                                        type="error"
                                        showIcon
                                        closable
                                        onClose={() => setError(null)}
                                        style={{ border: 0 }}
                                    />
                                </Form.Item>
                            )}

                            <Form.Item style={{ marginBottom: 0 }}>
                                <Space direction="vertical" size={spacing.sm} style={{ width: '100%' }}>
                                    <Button
                                        type="primary"
                                        htmlType="submit"
                                        size="large"
                                        loading={loading}
                                        block
                                    >
                                        {loading ? t('pages.tutorRegistration.submitting') : t('pages.tutorRegistration.submit')}
                                    </Button>
                                    <Text style={{
                                        color: colors.textSecondary,
                                        fontSize: 12,
                                        textAlign: 'center',
                                        display: 'block',
                                    }}>
                                        {t('pages.tutorRegistration.telegramNameHint')}
                                    </Text>
                                </Space>
                            </Form.Item>
                        </Form>
                    </div>
                </section>
            </div>
        </main>
    );
};

export default TutorRegistrationForm;
