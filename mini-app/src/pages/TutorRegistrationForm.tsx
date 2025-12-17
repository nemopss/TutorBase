import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Form, Input, Button, Typography, Space, Alert, Card, List, theme } from 'antd';
import { ArrowLeftOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/AuthProvider';
import { useThemeMode } from '../theme/ThemeProvider';

const { Title, Text } = Typography;

interface FormData {
    school_name: string;
    contact_email?: string;
    tutor_name?: string;
}

const TutorRegistrationForm: React.FC = () => {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const { registerTutor } = useAuth();
    const { resolvedTheme } = useThemeMode();
    const { token } = theme.useToken();
    const isDark = resolvedTheme === 'dark';
    const [form] = Form.useForm();

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (values: FormData) => {
        setLoading(true);
        setError(null);

        try {
            await registerTutor({
                school_name: values.school_name.trim(),
                contact_email: values.contact_email?.trim() || undefined,
                tutor_name: values.tutor_name?.trim() || undefined,
            });

            // Success - AuthProvider will handle redirect

        } catch (err: any) {
            console.error('Registration failed:', err);
            setError(err.response?.data?.detail || t('pages.tutorRegistration.genericError'));
        } finally {
            setLoading(false);
        }
    };

    const benefits = [
        t('pages.tutorRegistration.benefit1'),
        t('pages.tutorRegistration.benefit2'),
        t('pages.tutorRegistration.benefit3'),
        t('pages.tutorRegistration.benefit4'),
    ];

    return (
        <div style={{
            minHeight: '100vh',
            background: isDark ? token.colorBgContainer : '#fff',
        }}>
            {/* Header */}
            <div style={{
                padding: '16px',
                position: 'sticky',
                top: 0,
                zIndex: 10,
                backdropFilter: 'blur(8px)',
                background: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.8)',
            }}>
                <Space align="center">
                    <Button
                        type="text"
                        icon={<ArrowLeftOutlined />}
                        onClick={() => navigate(-1)}
                    />
                    <div>
                        <Title level={4} style={{ margin: 0 }}>
                            {t('pages.tutorRegistration.title')}
                        </Title>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                            {t('pages.tutorRegistration.subtitle')}
                        </Text>
                    </div>
                </Space>
            </div>

            {/* Content */}
            <div style={{
                maxWidth: 600,
                margin: '0 auto',
                padding: '24px 16px'
            }}>
                <Form
                    form={form}
                    layout="vertical"
                    onFinish={handleSubmit}
                    autoComplete="off"
                >
                    <Form.Item
                        label={t('pages.tutorRegistration.schoolNameLabel')}
                        name="school_name"
                        rules={[
                            { required: true, message: t('pages.tutorRegistration.schoolNameRequired') },
                            { min: 2, message: t('pages.tutorRegistration.schoolNameMinLength') }
                        ]}
                    >
                        <Input
                            placeholder={t('pages.tutorRegistration.schoolNamePlaceholder')}
                            size="large"
                            autoFocus
                        />
                    </Form.Item>

                    <Form.Item
                        label={t('pages.tutorRegistration.contactEmailLabel')}
                        name="contact_email"
                        rules={[
                            { type: 'email', message: t('pages.tutorRegistration.contactEmailInvalid') }
                        ]}
                    >
                        <Input
                            placeholder={t('pages.tutorRegistration.contactEmailPlaceholder')}
                            size="large"
                            type="email"
                        />
                    </Form.Item>

                    <Form.Item
                        label={t('pages.tutorRegistration.yourNameLabel')}
                        name="tutor_name"
                    >
                        <Input
                            placeholder={t('pages.tutorRegistration.yourNamePlaceholder')}
                            size="large"
                        />
                    </Form.Item>

                    <Form.Item>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                            {t('pages.tutorRegistration.termsText')}{' '}
                            <a href="/terms">{t('pages.tutorRegistration.termsOfService')}</a>
                            {' '}{t('pages.tutorRegistration.and')}{' '}
                            <a href="/privacy">{t('pages.tutorRegistration.privacyPolicy')}</a>
                        </Text>
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
                            />
                        </Form.Item>
                    )}

                    <Form.Item>
                        <Button
                            type="primary"
                            htmlType="submit"
                            size="large"
                            loading={loading}
                            block
                        >
                            {loading ? t('pages.tutorRegistration.submitting') : t('pages.tutorRegistration.submit')}
                        </Button>
                    </Form.Item>
                </Form>

                {/* Benefits Card */}
                <Card
                    title={t('pages.tutorRegistration.trialBenefits')}
                    style={{ marginTop: 24 }}
                >
                    <List
                        dataSource={benefits}
                        renderItem={(item) => (
                            <List.Item>
                                <Space>
                                    <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 16 }} />
                                    <Text>{item}</Text>
                                </Space>
                            </List.Item>
                        )}
                    />
                </Card>
            </div>
        </div>
    );
};

export default TutorRegistrationForm;
