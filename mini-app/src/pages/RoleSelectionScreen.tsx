import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Typography, Space, Tag, theme } from 'antd';
import { UserOutlined, TeamOutlined, RightOutlined } from '@ant-design/icons';
import { useThemeMode } from '../theme/ThemeProvider';

const { Title, Text } = Typography;

interface RoleCardProps {
    icon: React.ReactNode;
    title: string;
    description: string;
    badge?: string;
    onClick: () => void;
}

const RoleCard: React.FC<RoleCardProps> = ({
    icon,
    title,
    description,
    badge,
    onClick,
}) => {
    return (
        <Card
            hoverable
            onClick={onClick}
            style={{ marginBottom: 16 }}
        >
            <Space align="start" size="middle" style={{ width: '100%' }}>
                <div style={{ fontSize: 48, lineHeight: 1 }}>{icon}</div>
                <div style={{ flex: 1 }}>
                    <Title level={4} style={{ marginBottom: 4 }}>{title}</Title>
                    <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                        {description}
                    </Text>
                    {badge && (
                        <Tag color="success">{badge}</Tag>
                    )}
                </div>
                <RightOutlined style={{ fontSize: 20, color: '#bfbfbf' }} />
            </Space>
        </Card>
    );
};

const RoleSelectionScreen: React.FC = () => {
    const navigate = useNavigate();
    const { resolvedTheme } = useThemeMode();
    const { token } = theme.useToken();
    const isDark = resolvedTheme === 'dark';

    return (
        <div style={{
            minHeight: '100vh',
            display: 'flex',
            flexDirection: 'column',
            background: isDark ? token.colorBgContainer : '#fff',
        }}>
            {/* Header */}
            <div style={{
                padding: '24px 16px',
                textAlign: 'center'
            }}>
                <Title level={2} style={{ marginBottom: 8 }}>
                    Welcome to TutorBase!
                </Title>
                <Text type="secondary">
                    Choose your role to get started
                </Text>
            </div>

            {/* Content */}
            <div style={{
                flex: 1,
                maxWidth: 600,
                width: '100%',
                margin: '0 auto',
                padding: '0 16px 24px'
            }}>
                <RoleCard
                    icon={<UserOutlined />}
                    title="I'm a Tutor"
                    description="Create your school and manage students"
                    badge="14-day free trial"
                    onClick={() => navigate('/register/tutor')}
                />

                <RoleCard
                    icon={<TeamOutlined />}
                    title="I'm a Student"
                    description="Join your tutor's school with an invite code"
                    badge="Always free"
                    onClick={() => navigate('/register/student')}
                />
            </div>
        </div>
    );
};

export default RoleSelectionScreen;
