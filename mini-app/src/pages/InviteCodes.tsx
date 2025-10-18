import React, { useState, useEffect } from 'react';
import { Card, Button, Table, Tag, message, Space, Typography, Tooltip, Empty } from 'antd';
import { PlusOutlined, CopyOutlined, CheckCircleOutlined, ClockCircleOutlined } from '@ant-design/icons';
import PageHeader from '../components/common/PageHeader';
import api from '../services/api';
import { useAuth } from '../auth/AuthProvider';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';

dayjs.extend(relativeTime);

const { Text } = Typography;

interface InviteToken {
    id: number;
    token: string;
    expires_at: string;
    used_at: string | null;
    created_at: string;
}

const InviteCodes: React.FC = () => {
    const { user, tenantId } = useAuth();
    const [tokens, setTokens] = useState<InviteToken[]>([]);
    const [loading, setLoading] = useState(false);
    const [creating, setCreating] = useState(false);

    const fetchTokens = async () => {
        if (!tenantId) {
            console.error('No tenant_id available');
            return;
        }

        setLoading(true);
        try {
            const response = await api.get(`/tenants/${tenantId}/invitations`);
            setTokens(response.data.tokens || []);
        } catch (error: any) {
            message.error('Failed to load invite codes');
            console.error('Failed to fetch tokens:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchTokens();
    }, [tenantId]);

    const handleCreateToken = async () => {
        if (!tenantId) {
            message.error('No tenant context available');
            return;
        }

        setCreating(true);
        try {
            const response = await api.post(`/tenants/${tenantId}/invitations`, {});
            message.success('Invite code created successfully!');
            setTokens([response.data, ...tokens]);
        } catch (error: any) {
            message.error(error.response?.data?.detail || 'Failed to create invite code');
        } finally {
            setCreating(false);
        }
    };

    const handleCopyToken = (token: string) => {
        navigator.clipboard.writeText(token);
        message.success('Invite code copied to clipboard!');
    };

    const handleCopyLink = (token: string) => {
        const link = `${window.location.origin}/register/student?code=${token}`;
        navigator.clipboard.writeText(link);
        message.success('Invite link copied to clipboard!');
    };

    const columns = [
        {
            title: 'Invite Code',
            dataIndex: 'token',
            key: 'token',
            render: (token: string) => (
                <Space>
                    <Text code copyable={{ text: token }}>{token.substring(0, 20)}...</Text>
                </Space>
            ),
        },
        {
            title: 'Status',
            key: 'status',
            render: (_: any, record: InviteToken) => {
                if (record.used_at) {
                    return (
                        <Tag icon={<CheckCircleOutlined />} color="success">
                            Used {dayjs(record.used_at).fromNow()}
                        </Tag>
                    );
                }

                const isExpired = dayjs(record.expires_at).isBefore(dayjs());
                if (isExpired) {
                    return (
                        <Tag icon={<ClockCircleOutlined />} color="default">
                            Expired
                        </Tag>
                    );
                }

                return (
                    <Tag icon={<ClockCircleOutlined />} color="processing">
                        Active
                    </Tag>
                );
            },
        },
        {
            title: 'Expires',
            dataIndex: 'expires_at',
            key: 'expires_at',
            render: (expires_at: string) => (
                <Tooltip title={dayjs(expires_at).format('YYYY-MM-DD HH:mm')}>
                    <Text type="secondary">{dayjs(expires_at).fromNow()}</Text>
                </Tooltip>
            ),
        },
        {
            title: 'Created',
            dataIndex: 'created_at',
            key: 'created_at',
            render: (created_at: string) => (
                <Text type="secondary">{dayjs(created_at).format('MMM D, YYYY')}</Text>
            ),
        },
        {
            title: 'Actions',
            key: 'actions',
            render: (_: any, record: InviteToken) => {
                const isUsed = !!record.used_at;
                const isExpired = dayjs(record.expires_at).isBefore(dayjs());

                if (isUsed || isExpired) {
                    return <Text type="secondary">—</Text>;
                }

                return (
                    <Space>
                        <Tooltip title="Copy code">
                            <Button
                                type="text"
                                size="small"
                                icon={<CopyOutlined />}
                                onClick={() => handleCopyToken(record.token)}
                            />
                        </Tooltip>
                        <Tooltip title="Copy invite link">
                            <Button
                                type="text"
                                size="small"
                                onClick={() => handleCopyLink(record.token)}
                            >
                                Copy Link
                            </Button>
                        </Tooltip>
                    </Space>
                );
            },
        },
    ];

    // Check if user has permission
    const hasPermission = user?.role === 'admin' || user?.role === 'teacher';

    if (!hasPermission) {
        return (
            <div>
                <PageHeader
                    title="Invite Codes"
                    subtitle="Manage student invitations"
                />
                <Card>
                    <Empty
                        description="You don't have permission to manage invite codes"
                    />
                </Card>
            </div>
        );
    }

    return (
        <div>
            <PageHeader
                title="Invite Codes"
                subtitle="Create and manage student invitation codes"
                actions={
                    <Button
                        type="primary"
                        icon={<PlusOutlined />}
                        onClick={handleCreateToken}
                        loading={creating}
                    >
                        Create Invite Code
                    </Button>
                }
            />

            <Card>
                <Table
                    columns={columns}
                    dataSource={tokens}
                    rowKey="id"
                    loading={loading}
                    pagination={{
                        pageSize: 10,
                        showSizeChanger: false,
                        showTotal: (total) => `Total ${total} invite codes`,
                    }}
                    locale={{
                        emptyText: (
                            <Empty
                                description="No invite codes yet"
                                image={Empty.PRESENTED_IMAGE_SIMPLE}
                            >
                                <Button
                                    type="primary"
                                    icon={<PlusOutlined />}
                                    onClick={handleCreateToken}
                                    loading={creating}
                                >
                                    Create Your First Invite Code
                                </Button>
                            </Empty>
                        ),
                    }}
                />
            </Card>

            <Card style={{ marginTop: 16 }} title="How to use invite codes">
                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                    <div>
                        <Text strong>1. Create an invite code</Text>
                        <br />
                        <Text type="secondary">
                            Click "Create Invite Code" to generate a new invitation for a student.
                        </Text>
                    </div>
                    <div>
                        <Text strong>2. Share with your student</Text>
                        <br />
                        <Text type="secondary">
                            Copy the code or the full invite link and send it to your student via Telegram or any other messenger.
                        </Text>
                    </div>
                    <div>
                        <Text strong>3. Student registers</Text>
                        <br />
                        <Text type="secondary">
                            The student opens the link or enters the code during registration. The code can only be used once.
                        </Text>
                    </div>
                    <div>
                        <Text strong>4. Code expires in 7 days</Text>
                        <br />
                        <Text type="secondary">
                            Unused codes automatically expire after 7 days. You can create new codes anytime.
                        </Text>
                    </div>
                </Space>
            </Card>
        </div>
    );
};

export default InviteCodes;
