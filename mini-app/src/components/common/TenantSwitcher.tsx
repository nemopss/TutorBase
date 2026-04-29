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
import { devError } from '../../utils/safeLogging';

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

interface TenantSwitcherProps {
    fullWidth?: boolean;
}

const TenantSwitcher: React.FC<TenantSwitcherProps> = ({ fullWidth = false }) => {
    const { canSwitchTenant, tenantId, switchTenant } = useAuth();
    const [tenants, setTenants] = useState<Tenant[]>([]);
    const [loading, setLoading] = useState(false);
    const [switching, setSwitching] = useState(false);

    useEffect(() => {
        if (canSwitchTenant) {
            fetchTenants();
        }
    }, [canSwitchTenant]);

    // Tenant switching is disabled for browser auth until it has a cookie-safe endpoint.
    if (!canSwitchTenant) {
        return null;
    }

    const fetchTenants = async () => {
        setLoading(true);
        try {
            const response = await api.get<TenantListResponse>('/tenants');
            setTenants(response.data.items);
        } catch (error: any) {
            devError('Failed to fetch tenants:', error);
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
            message.success(
                targetTenantId === null
                    ? 'Switched to global view'
                    : `Switched to ${tenants.find(t => t.id === targetTenantId)?.name}`
            );
            setSwitching(false);
        } catch (error: any) {
            devError('Tenant switch failed:', error);
            message.error(error.message || 'Failed to switch tenant');
            setSwitching(false);
        }
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
                style={fullWidth ? { width: '100%' } : { minWidth: 200 }}
                placeholder="Select tenant context"
                suffixIcon={<SwapOutlined />}
                options={selectOptions}
                showSearch
                filterOption={(input, option) => {
                    if (!option) return false;
                    const tenant = tenants.find(t => t.id === option.value);
                    if (tenant) {
                        return tenant.name.toLowerCase().includes(input.toLowerCase());
                    }
                    return option.value === 'global' && 'global'.includes(input.toLowerCase());
                }}
            />
        </Tooltip>
    );
};

export default TenantSwitcher;
