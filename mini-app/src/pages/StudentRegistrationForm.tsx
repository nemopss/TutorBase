import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Form, Input, Button, Typography, Space, Alert, Card, Collapse } from 'antd';
import { ArrowLeftOutlined, CopyOutlined, QuestionCircleOutlined } from '@ant-design/icons';
import { useAuth } from '../auth/AuthProvider';

const { Title, Text, Paragraph } = Typography;
const { Panel } = Collapse;

interface FormData {
    invite_token: string;
    student_name?: string;
}

const StudentRegistrationForm: React.FC = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const { registerStudent } = useAuth();
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
            return 'Invalid invite code. Please check the code and try again.';
        }
        if (err.response?.status === 409) {
            return 'This invite code has already been used.';
        }
        if (err.response?.status === 410) {
            return 'This invite code has expired. Please ask your tutor for a new one.';
        }
        return err.response?.data?.detail || 'Registration failed. Please try again.';
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
            minHeight: '100vh'
        }}>
            {/* Header */}
            <div style={{
                padding: '16px',
                position: 'sticky',
                top: 0,
                zIndex: 10,
                backdropFilter: 'blur(8px)'
            }}>
                <Space align="center">
                    <Button
                        type="text"
                        icon={<ArrowLeftOutlined />}
                        onClick={() => navigate(-1)}
                    />
                    <div>
                        <Title level={4} style={{ margin: 0 }}>
                            Join Your School
                        </Title>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                            Enter your invite code to get started
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
                        label="Invite Code"
                        name="invite_token"
                        rules={[
                            { required: true, message: 'Please enter your invite code' },
                            { min: 10, message: 'Please enter a valid invite code' }
                        ]}
                    >
                        <Input
                            placeholder="Enter the code from your tutor"
                            size="large"
                            autoFocus={!searchParams.get('code')}
                            suffix={
                                <Button
                                    type="text"
                                    icon={<CopyOutlined />}
                                    onClick={handlePasteInviteCode}
                                    size="small"
                                >
                                    Paste
                                </Button>
                            }
                        />
                    </Form.Item>

                    <Form.Item
                        label="Your Name"
                        name="student_name"
                    >
                        <Input
                            placeholder="Leave empty to use your Telegram name"
                            size="large"
                        />
                    </Form.Item>

                    {error && (
                        <Form.Item>
                            <Alert
                                message="Registration Failed"
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
                            {loading ? 'Joining School...' : 'Join School'}
                        </Button>
                    </Form.Item>
                </Form>

                {/* Help Section */}
                <Card
                    title={
                        <Space>
                            <QuestionCircleOutlined />
                            <span>Need help?</span>
                        </Space>
                    }
                    style={{ marginTop: 24 }}
                >
                    <Collapse ghost>
                        <Panel header="Don't have an invite code?" key="1">
                            <Paragraph type="secondary">
                                Ask your tutor to send you an invite link or code.
                            </Paragraph>
                        </Panel>
                        <Panel header="Code not working?" key="2">
                            <Paragraph type="secondary">
                                Make sure you copied the entire code. Codes are case-sensitive.
                            </Paragraph>
                        </Panel>
                        <Panel header="Are you a tutor?" key="3">
                            <Paragraph type="secondary">
                                <Button
                                    type="link"
                                    onClick={() => navigate('/register/tutor')}
                                    style={{ padding: 0 }}
                                >
                                    Create your own school instead →
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
