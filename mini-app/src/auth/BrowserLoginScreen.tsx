import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import type {
  BrowserTutorRegistrationPayload,
  EmailPasswordPayload,
  TelegramLoginWidgetPayload,
} from './browserSession';
import { getTelegramBotUsername } from './browserSession';
import './BrowserLoginScreen.css';

type BrowserAuthView = 'login' | 'register' | 'telegram';

interface BrowserLoginScreenProps {
  error: string | null;
  initialView?: BrowserAuthView;
  isSubmitting: boolean;
  onEmailLogin: (payload: EmailPasswordPayload) => void;
  onEmailRegister: (payload: BrowserTutorRegistrationPayload) => void;
  onTelegramAuth: (payload: TelegramLoginWidgetPayload) => void;
}

export const BrowserLoginScreen = ({
  error,
  initialView = 'login',
  isSubmitting,
  onEmailLogin,
  onEmailRegister,
  onTelegramAuth,
}: BrowserLoginScreenProps) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [view, setView] = useState<BrowserAuthView>(initialView);
  const [widgetError, setWidgetError] = useState<string | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [schoolName, setSchoolName] = useState('');
  const [tutorName, setTutorName] = useState('');
  const [offerAccepted, setOfferAccepted] = useState(false);
  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const botUsername = getTelegramBotUsername();

  useEffect(() => {
    if (view !== 'telegram') {
      return undefined;
    }

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
  }, [botUsername, onTelegramAuth, view]);

  const submitEmailLogin = (event: FormEvent) => {
    event.preventDefault();
    onEmailLogin({ email: email.trim(), password });
  };

  const submitEmailRegister = (event: FormEvent) => {
    event.preventDefault();
    onEmailRegister({
      email: email.trim(),
      password,
      school_name: schoolName.trim(),
      tutor_name: tutorName.trim() || undefined,
      offer_accepted: offerAccepted,
      privacy_accepted: privacyAccepted,
    });
  };

  const authError = error || widgetError;

  return (
    <main className="browser-auth">
      <section className="browser-auth__panel" aria-labelledby="browser-auth-title">
        <div className="browser-auth__intro">
          <p className="browser-auth__eyebrow">Кабинет преподавателя</p>
          <h1 id="browser-auth-title">TutorBase</h1>
          <p>Вход по email работает в браузере, Telegram остаётся доступен для подключённых аккаунтов.</p>
        </div>

        <div className="browser-auth__tabs" role="tablist" aria-label="Способ входа">
          {[
            ['login', 'Войти'],
            ['register', 'Регистрация'],
            ['telegram', 'Telegram'],
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setView(key as BrowserAuthView)}
              className={view === key ? 'browser-auth__tab browser-auth__tab--active' : 'browser-auth__tab'}
              role="tab"
              aria-selected={view === key}
            >
              {label}
            </button>
          ))}
        </div>

        {view === 'login' && (
          <form onSubmit={submitEmailLogin} className="browser-auth__form">
            <label className="browser-auth__field">
              <span>Email</span>
              <input
                type="email"
                autoComplete="email"
                required
                placeholder="name@example.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <label className="browser-auth__field">
              <span>Пароль</span>
              <input
                type="password"
                autoComplete="current-password"
                minLength={8}
                required
                placeholder="Минимум 8 символов"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            <button type="submit" disabled={isSubmitting} className="browser-auth__primary">
              {isSubmitting ? 'Входим...' : 'Войти'}
            </button>
          </form>
        )}

        {view === 'register' && (
          <form onSubmit={submitEmailRegister} className="browser-auth__form">
            <label className="browser-auth__field">
              <span>Название кабинета</span>
              <input
                required
                minLength={2}
                placeholder="Например, занятия с Анной"
                value={schoolName}
                onChange={(event) => setSchoolName(event.target.value)}
              />
            </label>
            <label className="browser-auth__field">
              <span>Ваше имя</span>
              <input
                placeholder="Как вас видят ученики"
                value={tutorName}
                onChange={(event) => setTutorName(event.target.value)}
              />
            </label>
            <label className="browser-auth__field">
              <span>Email</span>
              <input
                type="email"
                autoComplete="email"
                required
                placeholder="name@example.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <label className="browser-auth__field">
              <span>Пароль</span>
              <input
                type="password"
                autoComplete="new-password"
                minLength={8}
                required
                placeholder="Минимум 8 символов"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            <label className="browser-auth__checkbox">
              <input
                type="checkbox"
                checked={offerAccepted}
                onChange={(event) => setOfferAccepted(event.target.checked)}
                required
              />
              <span>
                Принимаю <a href="/offer" target="_blank" rel="noreferrer">публичную оферту</a>
              </span>
            </label>
            <label className="browser-auth__checkbox">
              <input
                type="checkbox"
                checked={privacyAccepted}
                onChange={(event) => setPrivacyAccepted(event.target.checked)}
                required
              />
              <span>
                Согласен на обработку персональных данных и ознакомлен с{' '}
                <a href="/privacy" target="_blank" rel="noreferrer">политикой</a>
              </span>
            </label>
            <button type="submit" disabled={isSubmitting} className="browser-auth__primary">
              {isSubmitting ? 'Создаём...' : 'Создать кабинет'}
            </button>
          </form>
        )}

        {view === 'telegram' && (
          <div className="browser-auth__telegram">
            <p>
              Подходит для аккаунтов, уже привязанных к Telegram.
            </p>
            {!botUsername ? (
              <p className="browser-auth__error" role="alert">
                Не задан VITE_TELEGRAM_BOT_USERNAME для Telegram Login Widget.
              </p>
            ) : (
              <div ref={containerRef} className="browser-auth__telegram-widget" />
            )}
          </div>
        )}

        {authError && (
          <p className="browser-auth__error" role="alert">
            {authError}
          </p>
        )}
      </section>
    </main>
  );
};
