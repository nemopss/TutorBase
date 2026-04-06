import { useEffect, useRef, useState } from 'react';
import type { TelegramLoginWidgetPayload } from './browserSession';
import { getTelegramBotUsername } from './browserSession';

interface BrowserLoginScreenProps {
  error: string | null;
  isSubmitting: boolean;
  onTelegramAuth: (payload: TelegramLoginWidgetPayload) => void;
}

export const BrowserLoginScreen = ({
  error,
  isSubmitting,
  onTelegramAuth,
}: BrowserLoginScreenProps) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [widgetError, setWidgetError] = useState<string | null>(null);
  const botUsername = getTelegramBotUsername();

  useEffect(() => {
    window.__tutorbaseTelegramLogin = (payload) => {
      if (!payload?.id || !payload?.auth_date || !payload?.hash) {
        setWidgetError('Telegram вернул неполные данные входа. Обновите страницу и попробуйте ещё раз.');
        return;
      }

      setWidgetError(null);
      onTelegramAuth(payload);
    };

    if (!containerRef.current || !botUsername) {
      return () => {
        delete window.__tutorbaseTelegramLogin;
      };
    }

    containerRef.current.innerHTML = '';

    const script = document.createElement('script');
    script.src = 'https://telegram.org/js/telegram-widget.js?22';
    script.async = true;
    script.setAttribute('data-telegram-login', botUsername);
    script.setAttribute('data-size', 'large');
    script.setAttribute('data-userpic', 'false');
    script.setAttribute('data-request-access', 'write');
    script.setAttribute('data-onauth', 'window.__tutorbaseTelegramLogin(user)');
    script.onerror = () => {
      setWidgetError('Не удалось загрузить Telegram Login Widget. Проверьте соединение и обновите страницу.');
    };

    containerRef.current.appendChild(script);

    return () => {
      script.remove();
      delete window.__tutorbaseTelegramLogin;
    };
  }, [botUsername, onTelegramAuth]);

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      padding: '20px',
      textAlign: 'center',
      backgroundColor: '#f5f5f5',
    }}>
      <div style={{
        backgroundColor: 'white',
        padding: '32px',
        borderRadius: '12px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
        maxWidth: '420px',
        width: '100%',
      }}>
        <h1 style={{ marginTop: 0, marginBottom: '12px', fontSize: '24px' }}>
          Вход через Telegram
        </h1>
        <p style={{ color: '#555', lineHeight: 1.5, marginBottom: '24px' }}>
          Браузерный кабинет пока доступен только преподавателям и администраторам,
          уже зарегистрированным в приложении.
        </p>

        {!botUsername ? (
          <p style={{ color: '#d4380d', margin: 0 }}>
            Не задан VITE_TELEGRAM_BOT_USERNAME для Telegram Login Widget.
          </p>
        ) : (
          <div
            ref={containerRef}
            style={{ display: 'flex', justifyContent: 'center', minHeight: '44px' }}
          />
        )}

        {isSubmitting && (
          <p style={{ color: '#555', marginTop: '16px', marginBottom: 0 }}>
            Проверяем вход...
          </p>
        )}

        {error && (
          <pre style={{
            whiteSpace: 'pre-wrap',
            color: '#cf1322',
            fontFamily: 'inherit',
            marginTop: '16px',
            marginBottom: 0,
          }}>
            {error}
          </pre>
        )}

        {widgetError && (
          <pre style={{
            whiteSpace: 'pre-wrap',
            color: '#cf1322',
            fontFamily: 'inherit',
            marginTop: '16px',
            marginBottom: 0,
          }}>
            {widgetError}
          </pre>
        )}
      </div>
    </div>
  );
};
