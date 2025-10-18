/**
 * TenantSwitcher Component
 * 
 * Allows super-admins to switch between tenant contexts.
 * Features:
 * - Dropdown with all available tenants
 * - Global view option (no tenant filter)
 * - Visual indication of current tenant
 * - Loading states and error handling
 * - Professional UI with Ant Design
 */

import React, { useState, useEffect } from 'react';
import { Select, message, Spin, Badge, Tooltip } from 'antd';
import { GlobalOutlined, TeamOutlined, SwapOutlined } from '@ant-design/icons';
import { useAuth } from '../../auth/AuthProvider';
import api from '../../services/api';

interface Tenant {
    id: number;
    name: string;
    slug: string;
    is_active: boolean;
    contact_email?: string;
}

interface TenantListResponse {
    items: Tenant[];
    total: number;
}

const TenantSwitcher: React.FC = () => {
    const { isSuperAdmin, tenantId, switchTenant } = useAuth();
    const [tenants, setTenants] = useState<Tenant[]>([]);
    const [loading, setLoading] = useState(false);
    const [switching, setSwitching] = useState(false);

    // Only render for super-admins
    if (!isSuperAdmin) {
        return null;
    }

    useEffect(() => {
        fetchTenants();
    }, []);

    const fetchTenants = async () => {
        setLoading(true);
        try {
            const response = await api.get<TenantListResponse>('/tenants');
            setTenants(response.data.items);
        } catch (error: any) {
            console.error('Failed to fetch tenants:', error);
            message.error('Failed to load tenants');
        } finally {
            setLoading(false);
        }
    };

    const handleTenantSwitch = async (value: number | string) => {
        const targetTenantId = value === 'global' ? null : (value as number);

        if (targetTenantId === tenantId) {
            return; // Already in this context
        }

        setSwitching(true);
        try {
            await switchTenant(targetTenantId);
            // Page will reload after successful switch
            message.success(
                targetTenantId === null
                    ? 'Switched to global view'
                    : `Switched to ${tenants.find(t => t.id === targetTenantId)?.name}`
            );
        } catch (error: any) {
            console.error('Tenant switch failed:', error);
            message.error(error.message || 'Failed to switch tenant');
            setSwitching(false);
        }
    };

    const getCurrentTenantName = () => {
        if (tenantId === null) {
            return 'Global View';
        }
        const tenant = tenants.find(t => t.id === tenantId);
        return tenant?.name || `Tenant ${tenantId}`;
    };

    const selectOptions = [
        {
            value: 'global',
            label: (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <GlobalOutlined style={{ color: '#1890ff' }} />
                    <span>Global View (All Tenants)</span>
                </div>
            ),
        },
        ...tenants.map(tenant => ({
            value: tenant.id,
            label: (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <TeamOutlined style={{ color: tenant.is_active ? '#52c41a' : '#d9d9d9' }} />
                        <span>{tenant.name}</span>
                    </div>
                    {!tenant.is_active && (
                        <Badge status="default" text="Inactive" />
                    )}
                </div>
            ),
            disabled: !tenant.is_active,
        })),
    ];

    if (loading) {
        return (
            <div style={{ padding: '0 16px' }}>
                <Spin size="small" />
            </div>
        );
    }

    return (
        <Tooltip title="Switch tenant context (Super Admin)">
            <Select
                value={tenantId === null ? 'global' : tenantId}
                onChange={handleTenantSwitch}
                loading={switching}
                disabled={switching}
                style={{ minWidth: 200 }}
                placeholder="Select tenant context"
                suffixIcon={<SwapOutlined />}
                options={selectOptions}
                optionFilterProp="children"
                showSearch
                filterOption={(input, option) => {
                    const label = option?.label;
                    if (typeof label === 'string') {
                        return label.toLowerCase().includes(input.toLowerCase());
                    }
                    return false;
                }}
            />
        </Tooltip>
    );
};

export default TenantSwitcher;
