import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Typography } from 'antd';
import { RightOutlined, TeamOutlined, UserOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useResponsive } from '../hooks/useResponsive';
import { useTheme } from '../theme/ThemeProvider';
import { spacing } from '../theme/tokens';

const { Text } = Typography;

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
    const { resolvedTheme } = useTheme();
    const colors = resolvedTheme.colors;

    return (
        <button
            type="button"
            onClick={onClick}
            style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: spacing.md,
                minHeight: 112,
                padding: spacing.lg,
                margin: 0,
                border: 0,
                borderRadius: 8,
                background: colors.bgSecondary,
                color: colors.textPrimary,
                cursor: 'pointer',
                textAlign: 'left',
                font: 'inherit',
            }}
        >
            <span style={{
                width: 48,
                height: 48,
                borderRadius: 8,
                background: colors.bgTertiary,
                color: colors.accentPrimary,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 24,
                flex: '0 0 auto',
            }}>
                {icon}
            </span>
            <span style={{ flex: 1, minWidth: 0 }}>
                {badge && (
                    <Text style={{
                        display: 'block',
                        color: colors.accentPrimary,
                        fontSize: 12,
                        fontWeight: 700,
                        marginBottom: spacing.xs,
                    }}>
                        {badge}
                    </Text>
                )}
                <span style={{
                    display: 'block',
                    color: colors.textPrimary,
                    fontSize: 20,
                    fontWeight: 720,
                    lineHeight: 1.2,
                    letterSpacing: 0,
                    marginBottom: spacing.xs,
                }}>
                    {title}
                </span>
                <Text style={{ color: colors.textSecondary }}>
                    {description}
                </Text>
            </span>
            <RightOutlined style={{ color: colors.textTertiary, fontSize: 18, flex: '0 0 auto' }} />
        </button>
    );
};

const RoleSelectionScreen: React.FC = () => {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const { resolvedTheme } = useTheme();
    const { isMobile } = useResponsive();
    const colors = resolvedTheme.colors;

    return (
        <main style={{
            minHeight: '100vh',
            background: colors.bgPrimary,
            color: colors.textPrimary,
            display: 'flex',
            alignItems: isMobile ? 'stretch' : 'center',
            justifyContent: 'center',
            boxSizing: 'border-box',
            padding: isMobile ? `${spacing.xl}px ${spacing.md}px` : `${spacing.xl}px`,
        }}>
            <section style={{
                width: '100%',
                maxWidth: 720,
            }}>
                <Text style={{
                    display: 'block',
                    color: colors.accentPrimary,
                    fontWeight: 700,
                    marginBottom: spacing.md,
                }}>
                    TutorBase
                </Text>
                <h1 style={{
                    margin: 0,
                    color: colors.textPrimary,
                    fontSize: isMobile ? 34 : 46,
                    lineHeight: 1.05,
                    fontWeight: 760,
                    letterSpacing: 0,
                    maxWidth: 620,
                }}>
                    {t('pages.roleSelection.title')}
                </h1>
                <p style={{
                    margin: `${spacing.md}px 0 ${isMobile ? spacing.xl : 40}px`,
                    color: colors.textSecondary,
                    fontSize: isMobile ? 15 : 17,
                    lineHeight: 1.55,
                    maxWidth: 560,
                }}>
                    {t('pages.roleSelection.subtitle')}
                </p>

                <div style={{
                    display: 'grid',
                    gridTemplateColumns: isMobile ? '1fr' : 'repeat(2, minmax(0, 1fr))',
                    gap: spacing.md,
                }}>
                    <RoleCard
                        icon={<UserOutlined />}
                        title={t('pages.roleSelection.tutorTitle')}
                        description={t('pages.roleSelection.tutorDescription')}
                        badge={t('pages.roleSelection.tutorBadge')}
                        onClick={() => navigate('/register/tutor')}
                    />

                    <RoleCard
                        icon={<TeamOutlined />}
                        title={t('pages.roleSelection.studentTitle')}
                        description={t('pages.roleSelection.studentDescription')}
                        badge={t('pages.roleSelection.studentBadge')}
                        onClick={() => navigate('/register/student')}
                    />
                </div>
            </section>
        </main>
    );
};

export default RoleSelectionScreen;
