import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Alert, Button, Form, Input, Space, Typography } from 'antd';
import {
    ArrowLeftOutlined,
    CopyOutlined,
    QuestionCircleOutlined,
    TeamOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/AuthProvider';
import { useResponsive } from '../hooks/useResponsive';
import { useTheme } from '../theme/ThemeProvider';
import { spacing } from '../theme/tokens';

const { Text } = Typography;

interface FormData {
    invite_token: string;
    student_name?: string;
}

const StudentRegistrationForm: React.FC = () => {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const { registerStudent } = useAuth();
    const { resolvedTheme } = useTheme();
    const { isMobile } = useResponsive();
    const colors = resolvedTheme.colors;
    const [form] = Form.useForm();

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const code = searchParams.get('code');
        if (code) {
            form.setFieldsValue({ invite_token: code });
        }
    }, [searchParams, form]);

    const handlePasteInviteCode = async () => {
        try {
            const text = await navigator.clipboard.readText();
            if (text && text.length > 10) {
                form.setFieldsValue({ invite_token: text.trim() });
            }
        } catch (error) {
            console.log('Clipboard access not available');
        }
    };

    const getErrorMessage = (err: any): string => {
        if (err.response?.status === 404) {
            return t('pages.studentRegistration.inviteCodeInvalid');
        }
        if (err.response?.status === 409) {
            return t('pages.inviteCodes.status.used');
        }
        if (err.response?.status === 410) {
            return t('pages.studentRegistration.expiredCode');
        }
        return err.response?.data?.detail || t('pages.studentRegistration.genericError');
    };

    const handleSubmit = async (values: FormData) => {
        setLoading(true);
        setError(null);

        try {
            await registerStudent({
                invite_token: values.invite_token.trim(),
                student_name: values.student_name?.trim() || undefined,
            });
        } catch (err: any) {
            console.error('Registration failed:', err);
            setError(getErrorMessage(err));
        } finally {
            setLoading(false);
        }
    };

    const helpItems = [
        {
            question: t('pages.studentRegistration.noCodeQuestion'),
            answer: t('pages.studentRegistration.noCodeAnswer'),
        },
        {
            question: t('pages.studentRegistration.codeNotWorkingQuestion'),
            answer: t('pages.studentRegistration.codeNotWorkingAnswer'),
        },
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
                            alignItems: 'center',
                            gap: spacing.xs,
                            marginBottom: spacing.md,
                            color: colors.accentPrimary,
                            fontWeight: 700,
                        }}>
                            <TeamOutlined />
                            {t('pages.studentRegistration.badge', { defaultValue: 'По приглашению' })}
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
                            {t('pages.studentRegistration.title')}
                        </h1>
                        <p style={{
                            margin: `${spacing.md}px 0 0`,
                            color: colors.textSecondary,
                            fontSize: isMobile ? 15 : 17,
                            lineHeight: 1.55,
                            maxWidth: 540,
                        }}>
                            {t('pages.studentRegistration.subtitle')}
                        </p>

                        <div style={{
                            marginTop: isMobile ? spacing.xl : 40,
                            display: 'grid',
                            gap: spacing.sm,
                            maxWidth: 560,
                        }}>
                            {helpItems.map((item) => (
                                <details
                                    key={item.question}
                                    style={{
                                        background: colors.bgSecondary,
                                        borderRadius: 8,
                                        padding: `${spacing.md}px ${spacing.lg}px`,
                                    }}
                                >
                                    <summary style={{
                                        cursor: 'pointer',
                                        color: colors.textPrimary,
                                        fontWeight: 700,
                                        listStylePosition: 'outside',
                                    }}>
                                        {item.question}
                                    </summary>
                                    <Text style={{
                                        display: 'block',
                                        color: colors.textSecondary,
                                        marginTop: spacing.sm,
                                    }}>
                                        {item.answer}
                                    </Text>
                                </details>
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
                            {t('pages.studentRegistration.formTitle', { defaultValue: 'Введите код приглашения' })}
                        </h2>
                        <Text style={{
                            display: 'block',
                            color: colors.textSecondary,
                            marginBottom: spacing.lg,
                        }}>
                            {t('pages.studentRegistration.formSubtitle', { defaultValue: 'Код выдаёт ваш преподаватель.' })}
                        </Text>

                        <Form
                            form={form}
                            layout="vertical"
                            onFinish={handleSubmit}
                            autoComplete="off"
                            requiredMark={false}
                        >
                            <Form.Item
                                label={t('pages.studentRegistration.inviteCodeLabel')}
                                name="invite_token"
                                rules={[
                                    { required: true, message: t('pages.studentRegistration.inviteCodeRequired') },
                                    { min: 10, message: t('pages.studentRegistration.inviteCodeInvalid') },
                                ]}
                            >
                                <Input
                                    placeholder={t('pages.studentRegistration.inviteCodePlaceholder')}
                                    size="large"
                                    autoFocus={!searchParams.get('code')}
                                    variant="filled"
                                    suffix={
                                        <Button
                                            type="text"
                                            icon={<CopyOutlined />}
                                            onClick={handlePasteInviteCode}
                                            size="small"
                                            aria-label={t('common.copy')}
                                        />
                                    }
                                />
                            </Form.Item>

                            <Form.Item
                                label={t('forms.learner.displayNameLabel')}
                                name="student_name"
                            >
                                <Input
                                    placeholder={t('forms.learner.displayNamePlaceholder')}
                                    size="large"
                                    variant="filled"
                                />
                            </Form.Item>

                            {error && (
                                <Form.Item>
                                    <Alert
                                        message={t('pages.studentRegistration.registrationFailed')}
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
                                        {loading ? t('common.loading') : t('pages.studentRegistration.submit')}
                                    </Button>
                                    <Button
                                        type="text"
                                        icon={<QuestionCircleOutlined />}
                                        onClick={() => navigate('/register/tutor')}
                                        block
                                        style={{ color: colors.textSecondary }}
                                    >
                                        {t('pages.studentRegistration.areTutorAnswer')}
                                    </Button>
                                </Space>
                            </Form.Item>
                        </Form>
                    </div>
                </section>
            </div>
        </main>
    );
};

export default StudentRegistrationForm;
