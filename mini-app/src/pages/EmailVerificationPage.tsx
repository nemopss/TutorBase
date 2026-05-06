import React, { useEffect, useState } from 'react';
import { Button, Spin, Typography } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { useTheme } from '../theme/ThemeProvider';
import { spacing } from '../theme/tokens';
import api from '../services/api';

const { Text, Title } = Typography;

type VerificationState = 'loading' | 'success' | 'error';

const getTokenFromHash = () => {
  const hash = window.location.hash.startsWith('#') ? window.location.hash.slice(1) : window.location.hash;
  return new URLSearchParams(hash).get('token');
};

const EmailVerificationPage: React.FC = () => {
  const { resolvedTheme } = useTheme();
  const colors = resolvedTheme.colors;
  const [state, setState] = useState<VerificationState>('loading');
  const [message, setMessage] = useState('Подтверждаем email...');

  useEffect(() => {
    const token = getTokenFromHash();
    window.history.replaceState(null, '', window.location.pathname);

    if (!token) {
      setState('error');
      setMessage('Ссылка подтверждения неполная. Запросите новое письмо в настройках.');
      return;
    }

    let cancelled = false;
    api.post('/auth/email/verify', { token })
      .then(() => {
        if (cancelled) return;
        setState('success');
        setMessage('Email подтверждён.');
      })
      .catch(() => {
        if (cancelled) return;
        setState('error');
        setMessage('Ссылка подтверждения недействительна или устарела. Запросите новое письмо в настройках.');
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const isSuccess = state === 'success';
  const isError = state === 'error';

  return (
    <main style={{
      minHeight: '100vh',
      background: colors.bgPrimary,
      color: colors.textPrimary,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      boxSizing: 'border-box',
      padding: spacing.lg,
    }}>
      <section style={{
        width: '100%',
        maxWidth: 520,
        padding: spacing.xl,
        borderRadius: 10,
        background: colors.bgSecondary,
        textAlign: 'center',
      }}>
        <div style={{
          width: 48,
          height: 48,
          borderRadius: 8,
          background: colors.bgTertiary,
          color: isError ? colors.accentError : colors.accentSuccess,
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 24,
          marginBottom: spacing.md,
        }}>
          {state === 'loading' ? <Spin /> : isSuccess ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
        </div>
        <Title level={3} style={{ marginTop: 0, color: colors.textPrimary }}>
          {isSuccess ? 'Email подтверждён' : isError ? 'Не удалось подтвердить email' : 'Подтверждение email'}
        </Title>
        <Text type="secondary" style={{ display: 'block', marginBottom: spacing.lg }}>
          {message}
        </Text>
        <Button type="primary" href={isSuccess ? '/settings' : '/'}>
          {isSuccess ? 'Перейти в настройки' : 'Вернуться в TutorBase'}
        </Button>
      </section>
    </main>
  );
};

export default EmailVerificationPage;
