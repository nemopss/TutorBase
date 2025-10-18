/**
 * TenantIndicator Component
 * 
 * Displays the current tenant context in the UI.
 * Features:
 * - Shows tenant name or "Global View" for super-admins
 * - Visual badge with color coding
 * - Compact design for header/sidebar
 * - Responsive to theme changes
 */

import React, { useState, useEffect } from 'react';
import { Tag, Tooltip } from 'antd';
import { GlobalOutlined, TeamOutlined, CrownOutlined } from '@ant-design/icons';
import { useAuth } from '../../auth/AuthProvider';
import { useThemeMode } from '../../theme/ThemeProvider';
import api from '../../services/api';

interface Tenant {
    id: number;
    name: string;
    slug: string;
    is_active: boolean;
}

const TenantIndicator: React.FC = () => {
    const { tenantId, isSuperAdmin } = useAuth();
    const { resolvedTheme } = useThemeMode();
    const isDark = resolvedTheme === 'dark';
    const [tenantName, setTenantName] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (tenantId !== null) {
            fetchTenantName();
        } else {
            setTenantName(null);
        }
    }, [tenantId]);

    const fetchTenantName = async () => {
        if (tenantId === null) return;

        setLoading(true);
        try {
            const response = await api.get<Tenant>(`/tenants/${tenantId}`);
            setTenantName(response.data.name);
        } catch (error) {
            console.error('Failed to fetch tenant name:', error);
            setTenantName(`Tenant ${tenantId}`);
        } finally {
            setLoading(false);
        }
    };

    // Don't show for regular users (they can only see their own tenant)
    if (!isSuperAdmin) {
        return null;
    }

    const getDisplayContent = () => {
        if (tenantId === null) {
            return {
                icon: <GlobalOutlined />,
                text: 'Global View',
                color: 'blue',
                tooltip: 'Viewing all tenants (Super Admin)',
            };
        }

        return {
            icon: <TeamOutlined />,
            text: loading ? 'Loading...' : (tenantName || `Tenant ${tenantId}`),
            color: 'green',
            tooltip: `Current tenant context: ${tenantName || tenantId}`,
        };
    };

    const { icon, text, color, tooltip } = getDisplayContent();

    return (
        <Tooltip title={tooltip}>
            <Tag
                icon={icon}
                color={color}
                style={{
                    margin: 0,
                    padding: '4px 12px',
                    fontSize: '13px',
                    fontWeight: 500,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    border: isDark ? '1px solid #3a3a3a' : '1px solid #d9d9d9',
                    background: isDark ? '#252525' : '#ffffff',
                }}
            >
                {isSuperAdmin && <CrownOutlined style={{ fontSize: '12px', color: '#faad14' }} />}
                {text}
            </Tag>
        </Tooltip>
    );
};

export default TenantIndicator;
