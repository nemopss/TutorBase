import React, { useState, useEffect, useCallback } from 'react';
import { Alert, Card, Button, Tag, message, Space, Typography, Tooltip, Empty, Modal } from 'antd';
import { PlusOutlined, CopyOutlined, CheckCircleOutlined, ClockCircleOutlined, DeleteOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import PageHeader from '../components/common/PageHeader';
import ResponsiveDataView from '../components/common/ResponsiveDataView';
import InviteCodeCard from '../components/cards/InviteCodeCard';
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
    const { t } = useTranslation();
    const { user, tenantId, isSuperAdmin, tenantAccess } = useAuth();
    const canUseFullActions = !tenantAccess || tenantAccess.mode === 'full' || tenantAccess.bypass_access_restrictions;
    const [tokens, setTokens] = useState<InviteToken[]>([]);
    const [loading, setLoading] = useState(false);
    const [creating, setCreating] = useState(false);
    const [deleteModalOpen, setDeleteModalOpen] = useState(false);
    const [tokenToDelete, setTokenToDelete] = useState<InviteToken | null>(null);
    const [deleting, setDeleting] = useState(false);

    const fetchTokens = useCallback(async () => {
        if (!tenantId) {
            console.error('No tenant_id available');
            return;
        }

        setLoading(true);
        try {
            const response = await api.get(`/tenants/${tenantId}/invitations`);
            setTokens(response.data.items || []);
        } catch (error: any) {
            message.error(t('errors.loadFailed', { message: '' }));
            console.error('Failed to fetch tokens:', error);
        } finally {
            setLoading(false);
        }
    }, [tenantId, t]);

    useEffect(() => {
        fetchTokens();
    }, [fetchTokens]);

    const handleCreateToken = async () => {
        if (!canUseFullActions) {
            message.warning('Создание инвайт-кодов недоступно в grace-периоде.');
            return;
        }
        if (!tenantId) {
            message.error(t('errors.serverError'));
            return;
        }

        setCreating(true);
        try {
            const response = await api.post(`/tenants/${tenantId}/invitations`, {});
            message.success(t('pages.inviteCodes.inviteCodeCreated'));
            setTokens([response.data, ...tokens]);
        } catch (error: any) {
            message.error(error.response?.data?.detail || t('errors.createFailed', { message: '' }));
        } finally {
            setCreating(false);
        }
    };

    const handleCopyToken = (token: string) => {
        navigator.clipboard.writeText(token);
        message.success(t('pages.inviteCodes.inviteCodeCopied'));
    };

    const handleCopyLink = (token: string) => {
        const link = `${window.location.origin}/register/student?code=${token}`;
        navigator.clipboard.writeText(link);
        message.success(t('pages.inviteCodes.inviteLinkCopied'));
    };

    const handleDelete = (tokenId: number) => {
        if (!canUseFullActions) {
            message.warning('Удаление инвайт-кодов недоступно в grace-периоде.');
            return;
        }
        const token = tokens.find(t => t.id === tokenId);
        if (token) {
            setTokenToDelete(token);
            setDeleteModalOpen(true);
        }
    };

    const confirmDelete = async () => {
        if (!tokenToDelete || !tenantId) return;
        
        setDeleting(true);
        try {
            await api.delete(`/tenants/${tenantId}/invitations/${tokenToDelete.id}`);
            message.success(t('pages.inviteCodes.inviteCodeDeleted'));
            setTokens(tokens.filter(t => t.id !== tokenToDelete.id));
            setDeleteModalOpen(false);
            setTokenToDelete(null);
        } catch (error: any) {
            message.error(error.response?.data?.detail || t('errors.deleteFailed', { message: '' }));
        } finally {
            setDeleting(false);
        }
    };

    const columns = [
        {
            title: t('pages.inviteCodes.inviteCode'),
            dataIndex: 'token',
            key: 'token',
            render: (token: string) => (
                <Space>
                    <Text code copyable={{ text: token }}>{token.substring(0, 20)}...</Text>
                </Space>
            ),
        },
        {
            title: t('common.status'),
            key: 'status',
            render: (_: any, record: InviteToken) => {
                if (record.used_at) {
                    return (
                        <Tag icon={<CheckCircleOutlined />} color="success">
                            {t('pages.inviteCodes.status.used')} {dayjs(record.used_at).fromNow()}
                        </Tag>
                    );
                }

                const isExpired = dayjs(record.expires_at).isBefore(dayjs());
                if (isExpired) {
                    return (
                        <Tag icon={<ClockCircleOutlined />} color="default">
                            {t('pages.inviteCodes.status.expired')}
                        </Tag>
                    );
                }

                return (
                    <Tag icon={<ClockCircleOutlined />} color="processing">
                        {t('pages.inviteCodes.status.active')}
                    </Tag>
                );
            },
        },
        {
            title: t('pages.inviteCodes.expires'),
            dataIndex: 'expires_at',
            key: 'expires_at',
            render: (expires_at: string) => (
                <Tooltip title={dayjs(expires_at).format('YYYY-MM-DD HH:mm')}>
                    <Text type="secondary">{dayjs(expires_at).fromNow()}</Text>
                </Tooltip>
            ),
        },
        {
            title: t('pages.inviteCodes.created'),
            dataIndex: 'created_at',
            key: 'created_at',
            render: (created_at: string) => (
                <Text type="secondary">{dayjs(created_at).format('MMM D, YYYY')}</Text>
            ),
        },
        {
            title: t('common.actions'),
            key: 'actions',
            render: (_: any, record: InviteToken) => {
                const isUsed = !!record.used_at;
                const isExpired = dayjs(record.expires_at).isBefore(dayjs());

                return (
                    <Space>
                        {!isUsed && !isExpired && (
                            <>
                                <Tooltip title={t('pages.inviteCodes.copyCode')}>
                                    <Button
                                        type="text"
                                        size="small"
                                        icon={<CopyOutlined />}
                                        onClick={() => handleCopyToken(record.token)}
                                    />
                                </Tooltip>
                                <Tooltip title={t('pages.inviteCodes.copyLink')}>
                                    <Button
                                        type="text"
                                        size="small"
                                        onClick={() => handleCopyLink(record.token)}
                                    >
                                        {t('pages.inviteCodes.copyLink')}
                                    </Button>
                                </Tooltip>
                            </>
                        )}
                        {!isUsed && (
                            <Tooltip title={t('common.delete')}>
                                <Button
                                    type="text"
                                    size="small"
                                    danger
                                    icon={<DeleteOutlined />}
                                    disabled={!canUseFullActions}
                                    onClick={() => handleDelete(record.id)}
                                />
                            </Tooltip>
                        )}
                        {isUsed && <Text type="secondary">—</Text>}
                    </Space>
                );
            },
        },
    ];

    // Check if user has permission
    const hasPermission = isSuperAdmin || user?.role === 'teacher';

    if (!hasPermission) {
        return (
            <div>
                <PageHeader
                    title={t('pages.inviteCodes.title')}
                    subtitle={t('pages.inviteCodes.subtitle')}
                />
                <Card>
                    <Empty
                        description={t('pages.inviteCodes.noPermission')}
                    />
                </Card>
            </div>
        );
    }

    return (
        <div>
            <PageHeader
                title={t('pages.inviteCodes.title')}
                subtitle={t('pages.inviteCodes.subtitle')}
                actions={
                    <Button
                        type="primary"
                        icon={<PlusOutlined />}
                        onClick={handleCreateToken}
                        loading={creating}
                        disabled={!canUseFullActions}
                    >
                        {t('pages.inviteCodes.createInviteCode')}
                    </Button>
                }
            />

            {!canUseFullActions && (
                <Alert
                    type="warning"
                    showIcon
                    message="Grace-период"
                    description="Создание и удаление инвайт-кодов временно недоступны."
                    style={{ marginBottom: 16 }}
                />
            )}

            <Card>
                <ResponsiveDataView<InviteToken>
                    data={tokens}
                    loading={loading}
                    columns={columns}
                    rowKey="id"
                    emptyText={t('pages.inviteCodes.noInviteCodes')}
                    emptyActionText={canUseFullActions ? t('pages.inviteCodes.createFirstInviteCode') : undefined}
                    onEmptyAction={canUseFullActions ? handleCreateToken : undefined}
                    renderCard={(inviteCode) => (
                        <InviteCodeCard
                            key={inviteCode.id}
                            inviteCode={inviteCode}
                            onCopyToken={handleCopyToken}
                            onCopyLink={handleCopyLink}
                            onDelete={handleDelete}
                        />
                    )}
                    pagination={{
                        pageSize: 10,
                        showSizeChanger: false,
                        showTotal: (total) => t('pages.inviteCodes.totalInviteCodes', { count: total }),
                    }}
                />
            </Card>

            <Card style={{ marginTop: 16 }} title={t('pages.inviteCodes.howToUse.title')}>
                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                    <div>
                        <Text strong>{t('pages.inviteCodes.howToUse.step1Title')}</Text>
                        <br />
                        <Text type="secondary">
                            {t('pages.inviteCodes.howToUse.step1Description')}
                        </Text>
                    </div>
                    <div>
                        <Text strong>{t('pages.inviteCodes.howToUse.step2Title')}</Text>
                        <br />
                        <Text type="secondary">
                            {t('pages.inviteCodes.howToUse.step2Description')}
                        </Text>
                    </div>
                    <div>
                        <Text strong>{t('pages.inviteCodes.howToUse.step3Title')}</Text>
                        <br />
                        <Text type="secondary">
                            {t('pages.inviteCodes.howToUse.step3Description')}
                        </Text>
                    </div>
                    <div>
                        <Text strong>{t('pages.inviteCodes.howToUse.step4Title')}</Text>
                        <br />
                        <Text type="secondary">
                            {t('pages.inviteCodes.howToUse.step4Description')}
                        </Text>
                    </div>
                </Space>
            </Card>

            <Modal
                open={deleteModalOpen}
                title={t('pages.inviteCodes.deleteTitle')}
                onCancel={() => { setDeleteModalOpen(false); setTokenToDelete(null); }}
                onOk={confirmDelete}
                okText={t('common.delete')}
                cancelText={t('common.cancel')}
                okButtonProps={{ danger: true, loading: deleting }}
                cancelButtonProps={{ disabled: deleting }}
            >
                <p>{t('pages.inviteCodes.deleteConfirm')}</p>
                <p style={{ color: '#8c8c8c' }}>{t('pages.inviteCodes.deleteIrreversible')}</p>
            </Modal>
        </div>
    );
};

export default InviteCodes;
