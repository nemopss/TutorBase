import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Form, Input, Button, Typography, Space, Alert, Card, Collapse, theme } from 'antd';
import { ArrowLeftOutlined, CopyOutlined, QuestionCircleOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/AuthProvider';
import { useThemeMode } from '../theme/ThemeProvider';

const { Title, Text, Paragraph } = Typography;
const { Panel } = Collapse;

interface FormData {
    invite_token: string;
    student_name?: string;
}

const StudentRegistrationForm: React.FC = () => {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const { registerStudent } = useAuth();
    const { resolvedTheme } = useThemeMode();
    const { token } = theme.useToken();
    const isDark = resolvedTheme === 'dark';
    const [form] = Form.useForm();

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Pre-fill invite code from URL
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

            // Success - AuthProvider will handle redirect

        } catch (err: any) {
            console.error('Registration failed:', err);
            setError(getErrorMessage(err));
        } finally {
            setLoading(false);
        }
    };

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
                            {t('pages.studentRegistration.title')}
                        </Title>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                            {t('pages.studentRegistration.subtitle')}
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
                        label={t('pages.studentRegistration.inviteCodeLabel')}
                        name="invite_token"
                        rules={[
                            { required: true, message: t('pages.studentRegistration.inviteCodeRequired') },
                            { min: 10, message: t('pages.studentRegistration.inviteCodeInvalid') }
                        ]}
                    >
                        <Input
                            placeholder={t('pages.studentRegistration.inviteCodePlaceholder')}
                            size="large"
                            autoFocus={!searchParams.get('code')}
                            suffix={
                                <Button
                                    type="text"
                                    icon={<CopyOutlined />}
                                    onClick={handlePasteInviteCode}
                                    size="small"
                                >
                                    {t('common.copy')}
                                </Button>
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
                            {loading ? t('common.loading') : t('pages.studentRegistration.submit')}
                        </Button>
                    </Form.Item>
                </Form>

                {/* Help Section */}
                <Card
                    title={
                        <Space>
                            <QuestionCircleOutlined />
                            <span>{t('pages.studentRegistration.needHelp')}</span>
                        </Space>
                    }
                    style={{ marginTop: 24 }}
                >
                    <Collapse ghost>
                        <Panel header={t('pages.studentRegistration.noCodeQuestion')} key="1">
                            <Paragraph type="secondary">
                                {t('pages.studentRegistration.noCodeAnswer')}
                            </Paragraph>
                        </Panel>
                        <Panel header={t('pages.studentRegistration.codeNotWorkingQuestion')} key="2">
                            <Paragraph type="secondary">
                                {t('pages.studentRegistration.codeNotWorkingAnswer')}
                            </Paragraph>
                        </Panel>
                        <Panel header={t('pages.studentRegistration.areTutorQuestion')} key="3">
                            <Paragraph type="secondary">
                                <Button
                                    type="link"
                                    onClick={() => navigate('/register/tutor')}
                                    style={{ padding: 0 }}
                                >
                                    {t('pages.studentRegistration.areTutorAnswer')}
                                </Button>
                            </Paragraph>
                        </Panel>
                    </Collapse>
                </Card>
            </div>
        </div>
    );
};

export default StudentRegistrationForm;
