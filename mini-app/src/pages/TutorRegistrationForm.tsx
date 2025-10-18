import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Form, Input, Button, Typography, Space, Alert, Card, List } from 'antd';
import { ArrowLeftOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { useAuth } from '../auth/AuthProvider';

const { Title, Text } = Typography;

interface FormData {
    school_name: string;
    contact_email?: string;
    tutor_name?: string;
}

const TutorRegistrationForm: React.FC = () => {
    const navigate = useNavigate();
    const { registerTutor } = useAuth();
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
            setError(err.response?.data?.detail || 'Registration failed. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const benefits = [
        'Up to 5 students during trial',
        'Unlimited lessons and packages',
        'Automated reminders',
        'No credit card required',
    ];

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
                            Create Your School
                        </Title>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                            Start your 14-day free trial
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
                        label="School Name"
                        name="school_name"
                        rules={[
                            { required: true, message: 'Please enter your school name' },
                            { min: 2, message: 'School name must be at least 2 characters' }
                        ]}
                    >
                        <Input
                            placeholder="e.g., Math Tutoring by John"
                            size="large"
                            autoFocus
                        />
                    </Form.Item>

                    <Form.Item
                        label="Contact Email"
                        name="contact_email"
                        rules={[
                            { type: 'email', message: 'Please enter a valid email address' }
                        ]}
                    >
                        <Input
                            placeholder="your@email.com (optional)"
                            size="large"
                            type="email"
                        />
                    </Form.Item>

                    <Form.Item
                        label="Your Name"
                        name="tutor_name"
                    >
                        <Input
                            placeholder="Leave empty to use your Telegram name"
                            size="large"
                        />
                    </Form.Item>

                    <Form.Item>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                            By creating an account, you agree to our{' '}
                            <a href="/terms">Terms of Service</a>
                            {' '}and{' '}
                            <a href="/privacy">Privacy Policy</a>
                        </Text>
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
                            {loading ? 'Creating School...' : 'Create School & Start Trial'}
                        </Button>
                    </Form.Item>
                </Form>

                {/* Benefits Card */}
                <Card
                    title="What's included in your trial:"
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
