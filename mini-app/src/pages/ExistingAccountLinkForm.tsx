import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Button, Form, Input, Typography } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { useAuth } from '../auth/AuthProvider';
import { useResponsive } from '../hooks/useResponsive';
import { useTheme } from '../theme/ThemeProvider';
import { spacing } from '../theme/tokens';
import { devError } from '../utils/safeLogging';

const { Text } = Typography;

type FormData = {
  email: string;
  password: string;
};

const getApiDetail = (error: unknown): unknown => (
  (error as { response?: { data?: { detail?: unknown } } } | undefined)?.response?.data?.detail
);

const ExistingAccountLinkForm: React.FC = () => {
  const navigate = useNavigate();
  const { linkExistingEmailAccount } = useAuth();
  const { resolvedTheme } = useTheme();
  const { isMobile } = useResponsive();
  const colors = resolvedTheme.colors;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (values: FormData) => {
    setLoading(true);
    setError(null);
    try {
      await linkExistingEmailAccount({
        email: values.email.trim(),
        password: values.password,
      });
    } catch (err: unknown) {
      devError('Account linking failed:', err);
      const detail = getApiDetail(err);
      setError(typeof detail === 'string' ? detail : 'Не удалось привязать аккаунт');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main style={{
      minHeight: '100vh',
      background: colors.bgPrimary,
      color: colors.textPrimary,
      boxSizing: 'border-box',
      padding: isMobile ? `${spacing.md}px ${spacing.md}px ${spacing.xl}px` : `${spacing.xl}px`,
    }}>
      <div style={{ maxWidth: 520, margin: '0 auto' }}>
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate(-1)}
          style={{ marginBottom: spacing.xl, color: colors.textSecondary }}
        >
          Назад
        </Button>

        <section style={{
          background: colors.bgSecondary,
          borderRadius: 8,
          padding: isMobile ? spacing.lg : spacing.xl,
        }}>
          <Text style={{ display: 'block', color: colors.accentPrimary, fontWeight: 700, marginBottom: spacing.sm }}>
            TutorBase
          </Text>
          <h1 style={{
            margin: 0,
            color: colors.textPrimary,
            fontSize: isMobile ? 28 : 34,
            lineHeight: 1.1,
            fontWeight: 760,
            letterSpacing: 0,
          }}>
            Войти в существующий аккаунт
          </h1>
          <p style={{ color: colors.textSecondary, lineHeight: 1.55, margin: `${spacing.md}px 0 ${spacing.lg}px` }}>
            Введите email и пароль браузерного аккаунта. Текущий Telegram будет привязан к этому кабинету.
          </p>

          <Form layout="vertical" requiredMark={false} onFinish={handleSubmit}>
            <Form.Item
              label="Email"
              name="email"
              rules={[
                { required: true, message: 'Введите email' },
                { type: 'email', message: 'Введите корректный email' },
              ]}
            >
              <Input type="email" autoComplete="email" size="large" variant="filled" />
            </Form.Item>
            <Form.Item
              label="Пароль"
              name="password"
              rules={[
                { required: true, message: 'Введите пароль' },
                { min: 8, message: 'Пароль должен быть не короче 8 символов' },
              ]}
            >
              <Input.Password autoComplete="current-password" size="large" variant="filled" />
            </Form.Item>

            {error && (
              <Form.Item>
                <Alert type="error" showIcon message="Не удалось войти" description={error} />
              </Form.Item>
            )}

            <Form.Item style={{ marginBottom: 0 }}>
              <Button type="primary" htmlType="submit" loading={loading} size="large" block>
                Привязать Telegram и войти
              </Button>
            </Form.Item>
          </Form>
        </section>
      </div>
    </main>
  );
};

export default ExistingAccountLinkForm;
