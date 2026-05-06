import React, { useEffect, useRef, useState } from 'react';
import { Button, Collapse, ConfigProvider } from 'antd';
import type { CollapseProps } from 'antd';
import {
  ArrowRightOutlined,
  BellOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  CreditCardOutlined,
  MoonOutlined,
  ScheduleOutlined,
  SunOutlined,
  TeamOutlined,
  UserAddOutlined,
} from '@ant-design/icons';
import { generateAntdTheme } from '../theme/antdTokens';
import { useTheme } from '../theme/ThemeProvider';
import './LandingPage.css';

const CTA_TEXT = 'Начать бесплатно';
const FREE_PLAN = 'Бесплатно до 3 учеников';
const SELLER_NAME = 'Гладилин Алексей Алексеевич';
const SELLER_INN = '621305194552';
const SUPPORT_EMAIL = 'tutorbase@mail.ru';
const TELEGRAM_BOT_URL = 'https://t.me/tutorbaserobot';
const APP_REGISTER_URL = 'https://app.tutorbase.su/register/tutor';

const getRegisterUrl = () => {
  if (typeof window === 'undefined') {
    return APP_REGISTER_URL;
  }
  const { hostname } = window.location;
  if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname.startsWith('app.')) {
    return '/register/tutor';
  }
  return APP_REGISTER_URL;
};

const pricingPlans = [
  {
    name: 'Старт',
    range: '0-3 активных ученика',
    price: '0 ₽',
    note: 'Можно спокойно попробовать TutorBase на реальных учениках.',
    accent: true,
  },
  {
    name: 'Базовый',
    range: '4-10 активных учеников',
    price: '349 ₽',
    note: 'Для репетитора, у которого уже есть стабильное расписание.',
  },
  {
    name: 'Про',
    range: '11-20 активных учеников',
    price: '649 ₽',
    note: 'Для плотной загрузки, пакетов уроков и регулярного учёта оплат.',
  },
  {
    name: 'Бизнес',
    range: '21+ активных учеников',
    price: '1190 ₽',
    note: 'Для преподавателей и небольших студий с большим количеством учеников.',
  },
];

const usefulScenarios = [
  {
    title: 'Учеников стало больше, чем помещается в голове',
    text: 'Нужен порядок в расписании, пакетах и оплатах без ручного контроля в таблицах.',
  },
  {
    title: 'Оплаты теряются в переписках',
    text: 'Видно, кто оплатил, кто должен и где пора напомнить о платеже.',
  },
  {
    title: 'Переносы, отмены и разные форматы путаются',
    text: 'Онлайн- и офлайн-занятия, переносы и история уроков остаются в одном кабинете.',
  },
  {
    title: 'Есть регулярные занятия и долгие программы',
    text: 'Удобно вести пакеты, заметки, прогресс и повторяющиеся занятия.',
  },
  {
    title: 'Ученики забывают про уроки',
    text: 'Telegram-напоминания помогают снизить количество забытых занятий.',
  },
  {
    title: 'Хочется меньше держать в голове',
    text: 'TutorBase собирает ежедневные задачи репетитора в понятный рабочий обзор.',
  },
];

const productScreens = [
  {
    title: 'Главная',
    kicker: 'Сегодня',
    lead: 'Открыли кабинет и сразу видите, с чего начать день.',
    details: [
      ['10:00', 'Анна · пакет 7/8'],
      ['13:30', 'Марк · есть долг'],
      ['18:00', 'София · напоминание готово'],
    ],
  },
  {
    title: 'Карточка ученика',
    kicker: 'Контекст',
    lead: 'Вся история ученика рядом: занятия, пакеты, заметки и оплаты.',
    details: [
      ['Пакет', 'осталось 2 урока'],
      ['Оплата', 'задолженность 4 000 ₽'],
      ['Заметка', 'повторить speaking'],
    ],
  },
  {
    title: 'Уведомления',
    kicker: 'Telegram',
    lead: 'Понятно, что уже запланировано и где нужна реакция преподавателя.',
    details: [
      ['Запланировано', 'урок завтра в 18:00'],
      ['Ответ ученика', 'подтвердил занятие'],
      ['Доставка', 'ошибки видны отдельно'],
    ],
  },
];

const tariffRules = [
  'Активный ученик - тот, кто не находится в архиве.',
  'Архив освобождает место в тарифе и сохраняет историю занятий, пакетов и оплат.',
  'Если подписка закончилась, данные остаются доступны.',
  'Если активных учеников больше бесплатного лимита, Telegram-уведомления отключаются до продления подписки или уменьшения активных учеников.',
];

const trustItems = [
  {
    title: 'Данные не пропадают',
    text: 'История учеников, занятий, пакетов и оплат остаётся в кабинете даже после окончания подписки.',
  },
  {
    title: 'Ученикам бесплатно',
    text: 'Преподаватель создаёт приглашение, а ученик подключается к своему кабинету без оплаты.',
  },
  {
    title: 'Без банковской карты на старте',
    text: 'Можно создать кабинет и проверить TutorBase бесплатно.',
  },
  {
    title: 'Можно начать постепенно',
    text: 'Не обязательно сразу переносить всю работу. Добавьте первых учеников и занятия, а остальное подключайте по мере необходимости.',
  },
];

const useRevealOnScroll = () => {
  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') {
      document.querySelectorAll('[data-reveal]').forEach((node) => {
        node.classList.add('is-visible');
      });
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.16, rootMargin: '0px 0px -48px 0px' },
    );

    document.querySelectorAll('[data-reveal]').forEach((node) => {
      observer.observe(node);
    });

    return () => observer.disconnect();
  }, []);
};

const Reveal = ({
  delay = 0,
  className,
  children,
  ...props
}: {
  delay?: number;
  className?: string;
  children: React.ReactNode;
} & React.HTMLAttributes<HTMLDivElement>) => (
  <div
    data-reveal
    className={className}
    style={{ '--reveal-delay': `${delay}ms`, ...props.style } as React.CSSProperties}
    {...props}
  >
    {children}
  </div>
);

const LessonRow = ({
  time,
  name,
}: {
  time: string;
  name: string;
}) => (
  <div className="landing-lesson-row">
    <span className="landing-lesson-dot" />
    <span className="landing-lesson-time">{time}</span>
    <strong>{name}</strong>
  </div>
);

const DashboardMockup = () => (
  <div className="landing-mockup" aria-label="Мокап главной страницы TutorBase">
    <div className="landing-mockup-main">
      <div className="landing-mockup-header">
        <div>
          <span>ГЛАВНАЯ</span>
          <strong>Сегодня</strong>
        </div>
        <Button size="small">Новый пакет</Button>
      </div>

      <div className="landing-mockup-grid">
        <div className="landing-mockup-panel landing-mockup-panel--lessons">
          <div className="landing-panel-title">Ближайшие уроки</div>
          <LessonRow time="10:00" name="Анна" />
          <LessonRow time="13:30" name="Марк" />
          <LessonRow time="18:00" name="София" />
        </div>

        <div className="landing-mockup-panel landing-mockup-panel--calendar">
          <div className="landing-panel-title">Неделя</div>
          <div className="landing-week-grid">
            {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((day, dayIndex) => (
              <div key={day} className="landing-week-day">
                <span>{day}</span>
                {[0, 1, 2, 3].map((slot) => (
                  <i
                    key={slot}
                    className={(dayIndex + slot) % 3 === 0 ? 'has-lesson' : ''}
                    style={{ height: `${22 + ((dayIndex + slot) % 2) * 10}px` }}
                  />
                ))}
              </div>
            ))}
          </div>
        </div>

        <div className="landing-mockup-panel landing-mockup-panel--attention">
          <div className="landing-panel-title">Требует внимания</div>
          <div className="landing-attention-row">
            <CheckCircleOutlined />
            <span>Пакет Анны заканчивается в пятницу</span>
          </div>
        </div>

        <div className="landing-mockup-panel landing-mockup-panel--finance">
          <div>
            <div className="landing-panel-title">Финансы</div>
            <strong>+120 000 ₽</strong>
          </div>
          <span>2 ученика с долгом</span>
        </div>
      </div>
    </div>
  </div>
);

const featureItems = [
  {
    icon: <TeamOutlined />,
    title: 'Ученики',
    text: 'Карточки учеников, история занятий, заметки и архив.',
  },
  {
    icon: <CalendarOutlined />,
    title: 'Расписание',
    text: 'Понятный календарь уроков, переносов и отмен.',
  },
  {
    icon: <ScheduleOutlined />,
    title: 'Пакеты',
    text: 'Абонементы, остаток занятий, стоимость и статус оплаты.',
  },
  {
    icon: <BellOutlined />,
    title: 'Напоминания',
    text: 'Сообщения ученикам в Telegram перед уроками и важными событиями.',
  },
  {
    icon: <CreditCardOutlined />,
    title: 'Финансы',
    text: 'Оплаты, долги, доход за месяц и история платежей.',
  },
  {
    icon: <UserAddOutlined />,
    title: 'Приглашения',
    text: 'Подключение учеников по приглашению к нужной карточке.',
  },
];

const faqItems: CollapseProps['items'] = [
  {
    key: 'audience',
    label: 'Для кого TutorBase?',
    children: 'Для преподавателей и репетиторов, которые ведут индивидуальные занятия и хотят держать расписание, учеников и оплаты в порядке.',
  },
  {
    key: 'free',
    label: 'Можно ли пользоваться бесплатно?',
    children: 'Да. Тариф «Старт» бесплатный для кабинета с 0-3 активными учениками. Можно проверить учеников, расписание, пакеты, напоминания и финансовый учёт без оплаты и банковской карты.',
  },
  {
    key: 'payer',
    label: 'Кто оплачивает TutorBase?',
    children: 'Доступ оплачивает преподаватель. Ученики подключаются по приглашению и пользуются TutorBase бесплатно.',
  },
  {
    key: 'student-payments',
    label: 'Можно ли учитывать оплаты учеников?',
    children: 'Да, TutorBase помогает записывать платежи, видеть задолженности и историю оплат. Это внутренний учёт преподавателя.',
  },
  {
    key: 'telegram-notifications',
    label: 'Как работают Telegram-уведомления?',
    children: 'Уведомления отправляются ученикам в Telegram после подключения ученика по приглашению. В кабинете видно ближайшие отправки и проблемы доставки.',
  },
  {
    key: 'price',
    label: 'Сколько стоит TutorBase?',
    children: 'Стоимость зависит от количества активных учеников: Старт - бесплатно до 3 учеников, Базовый - 349 ₽, Про - 649 ₽, Бизнес - 1190 ₽ за 30 календарных дней.',
  },
  {
    key: 'active-learners',
    label: 'Что считается активным учеником?',
    children: 'Активный ученик - тот, кто не находится в архиве. Архив помогает освободить место в тарифе и при этом сохранить историю занятий и оплат.',
  },
  {
    key: 'subscription-ended',
    label: 'Что происходит, если подписка заканчивается?',
    children: 'Данные остаются доступны. Если активных учеников больше бесплатного лимита, Telegram-уведомления отключаются до продления подписки или уменьшения количества активных учеников.',
  },
  {
    key: 'invite',
    label: 'Как подключается ученик?',
    children: 'Преподаватель создаёт приглашение и отправляет ученику код. Так ученик попадает в нужный кабинет.',
  },
  {
    key: 'beginner',
    label: 'Подойдёт ли TutorBase начинающему репетитору?',
    children: 'Да. Можно начать бесплатно, без карты, с первых учеников и постепенно перенести расписание, пакеты и оплаты в один кабинет.',
  },
  {
    key: 'upgrade-later',
    label: 'Можно ли перейти на платный тариф позже?',
    children: 'Да. Тариф зависит от количества активных учеников. До 3 активных учеников кабинет работает бесплатно, а на платный тариф можно перейти позже.',
  },
  {
    key: 'learner-stopped',
    label: 'Что если ученик перестал заниматься?',
    children: 'Его можно отправить в архив. История занятий, пакетов и оплат сохраняется, а место в лимите активных учеников освобождается.',
  },
  {
    key: 'app-install',
    label: 'Нужно ли устанавливать отдельное приложение?',
    children: 'Отдельное приложение устанавливать не нужно. TutorBase открывается из Telegram, а ученики подключаются по приглашению.',
  },
  {
    key: 'schedule-only',
    label: 'Можно ли вести только расписание?',
    children: 'Да. Можно начать с расписания и карточек учеников, а пакеты, оплаты и напоминания подключать по мере необходимости.',
  },
];

const OverviewGraphic = () => (
  <div className="landing-overview-graphic" aria-label="Рабочий обзор TutorBase">
    <div className="landing-overview-card landing-overview-card--schedule">
      <div className="landing-overview-card-head">
        <div>
          <span>Сегодня</span>
          <strong>3 урока</strong>
        </div>
        <CalendarOutlined />
      </div>
      <div className="landing-overview-lesson">
        <span>10:00</span>
        <strong>Анна</strong>
        <em>пакет 7/8</em>
      </div>
      <div className="landing-overview-lesson">
        <span>13:30</span>
        <strong>Марк</strong>
        <em>оплачен</em>
      </div>
      <div className="landing-overview-lesson">
        <span>18:00</span>
        <strong>София</strong>
        <em>перенос</em>
      </div>
    </div>

    <div className="landing-overview-side">
      <div className="landing-overview-card landing-overview-card--attention">
        <div className="landing-overview-card-head">
          <div>
            <span>Требует внимания</span>
            <strong>Пакет заканчивается</strong>
          </div>
          <CheckCircleOutlined />
        </div>
        <p>У Анны остался 1 урок. TutorBase подскажет, когда пора обсудить продление.</p>
      </div>

      <div className="landing-overview-card landing-overview-card--money">
        <div className="landing-overview-card-head">
          <div>
            <span>Финансы</span>
            <strong>+120 000 ₽ за месяц</strong>
          </div>
          <CreditCardOutlined />
        </div>
        <p>Оплаты, долги и история по ученикам остаются рядом с расписанием.</p>
      </div>

      <div className="landing-overview-card landing-overview-card--notify">
        <BellOutlined />
        <span>Напоминание к уроку Софии запланировано</span>
      </div>
    </div>
  </div>
);

const LandingPage: React.FC = () => {
  const { resolvedTheme, setThemeId } = useTheme();
  const isDark = resolvedTheme.colorScheme === 'dark';
  const registerUrl = getRegisterUrl();
  const [scrolled, setScrolled] = useState(false);
  const firstSectionRef = useRef<HTMLElement | null>(null);

  useRevealOnScroll();

  useEffect(() => {
    document.documentElement.lang = 'ru';
    document.title = 'TutorBase - кабинет преподавателя для учеников, расписания и оплат';

    const description = 'TutorBase помогает репетиторам вести учеников, расписание занятий, пакеты, напоминания и учёт оплат в одном кабинете.';
    let meta = document.querySelector<HTMLMetaElement>('meta[name="description"]');
    if (!meta) {
      meta = document.createElement('meta');
      meta.name = 'description';
      document.head.appendChild(meta);
    }
    meta.content = description;
  }, []);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 8);
    };
    handleScroll();
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleScrollToProduct = () => {
    firstSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const handleAnchorClick = (event: React.MouseEvent<HTMLAnchorElement>, targetId: string) => {
    event.preventDefault();
    const target = document.getElementById(targetId);
    if (!target) {
      return;
    }

    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    window.history.pushState(null, '', `#${targetId}`);
  };

  return (
    <ConfigProvider theme={generateAntdTheme(resolvedTheme)}>
      <div className="landing-page" data-theme={isDark ? 'dark' : 'light'}>
        <header className={`landing-header ${scrolled ? 'is-scrolled' : ''}`}>
          <a className="landing-brand" href="#top" aria-label="TutorBase" onClick={(event) => handleAnchorClick(event, 'top')}>
            <span className="landing-brand-mark">
              <img src="/favicon.svg" alt="" aria-hidden="true" />
            </span>
            <span>TutorBase</span>
          </a>

          <nav className="landing-nav" aria-label="Навигация лендинга">
            <a href="#scenarios" onClick={(event) => handleAnchorClick(event, 'scenarios')}>КОГДА ПОЛЕЗЕН</a>
            <a href="#overview" onClick={(event) => handleAnchorClick(event, 'overview')}>ОБЗОР</a>
            <a href="#inside" onClick={(event) => handleAnchorClick(event, 'inside')}>ВНУТРИ</a>
            <a href="#features" onClick={(event) => handleAnchorClick(event, 'features')}>ВОЗМОЖНОСТИ</a>
            <a href="#pricing" onClick={(event) => handleAnchorClick(event, 'pricing')}>ТАРИФЫ</a>
            <a href="#faq" onClick={(event) => handleAnchorClick(event, 'faq')}>FAQ</a>
          </nav>

          <div className="landing-header-actions">
            <button
              type="button"
              className="landing-theme-toggle"
              onClick={() => setThemeId(isDark ? 'light' : 'dark')}
              aria-label={isDark ? 'Включить светлую тему' : 'Включить тёмную тему'}
            >
              {isDark ? <SunOutlined /> : <MoonOutlined />}
            </button>
            <Button type="primary" href={registerUrl}>
              {CTA_TEXT}
            </Button>
          </div>
        </header>

        <main id="top">
          <section className="landing-hero">
            <div className="landing-shell landing-hero-grid">
              <Reveal className="landing-hero-copy">
                <span className="landing-eyebrow">{FREE_PLAN}</span>
                <h1>Ученики, оплаты и расписание без таблиц</h1>
                <p className="landing-hero-lead">
                  Ученики, занятия, оплаты, пакеты и напоминания в одном понятном рабочем пространстве.
                </p>
                <p className="landing-hero-text">
                  TutorBase помогает вести ежедневную работу без Excel, заметок в чатах
                  и ручного контроля.
                </p>
                <div className="landing-hero-actions">
                  <Button
                    type="primary"
                    size="large"
                    href={registerUrl}
                    icon={<ArrowRightOutlined />}
                    className="landing-content-cta"
                  >
                    {CTA_TEXT}
                  </Button>
                  <Button size="large" onClick={handleScrollToProduct} className="landing-hero-secondary">
                    Посмотреть возможности
                  </Button>
                  <Button size="large" href={TELEGRAM_BOT_URL} className="landing-hero-secondary">
                    Открыть в Telegram
                  </Button>
                </div>
                <p className="landing-hero-note">
                  Бесплатно до 3 активных учеников. Без карты и обязательств.
                </p>
              </Reveal>

              <Reveal className="landing-hero-mockup" delay={120}>
                <DashboardMockup />
              </Reveal>
            </div>
          </section>

          <section id="scenarios" className="landing-section landing-scenarios-section">
            <div className="landing-shell">
              <Reveal className="landing-section-heading">
                <span className="landing-section-kicker">КОГДА ПОЛЕЗЕН</span>
                <h2>Когда ручной порядок начинает занимать слишком много времени</h2>
              </Reveal>

              <div className="landing-scenario-grid">
                {usefulScenarios.map((item, index) => (
                  <Reveal className="landing-scenario-card" key={item.title} delay={index * 60}>
                    <CheckCircleOutlined />
                    <div>
                      <h3>{item.title}</h3>
                      <p>{item.text}</p>
                    </div>
                  </Reveal>
                ))}
              </div>
            </div>
          </section>

          <section id="overview" className="landing-section" ref={firstSectionRef}>
            <div className="landing-shell landing-section-grid">
              <Reveal className="landing-section-copy">
                <span className="landing-section-kicker">РАБОЧИЙ ОБЗОР</span>
                <h2>Главное видно сразу</h2>
                <p className="landing-section-aside">
                  На главном экране видно ближайшие занятия, финансовые подсказки,
                  статусы пакетов и то, что требует внимания до следующего урока.
                </p>
              </Reveal>
              <Reveal className="landing-section-text" delay={80}>
                <OverviewGraphic />
              </Reveal>
            </div>
          </section>

          <section id="inside" className="landing-section landing-inside-section">
            <div className="landing-shell">
              <Reveal className="landing-section-heading">
                <span className="landing-section-kicker">ВНУТРИ</span>
                <h2>Кабинет выглядит как рабочий инструмент, а не как витрина</h2>
                <p className="landing-section-heading-text">
                  TutorBase создан для ежедневной работы репетитора. Всё нужное видно сразу:
                  занятия, ученики, оплаты, напоминания и то, что требует внимания.
                </p>
              </Reveal>

              <div className="landing-product-preview-grid">
                {productScreens.map((screen, index) => (
                  <Reveal className="landing-product-preview" key={screen.title} delay={index * 80}>
                    <div className="landing-product-preview-head">
                      <span>{screen.kicker}</span>
                      <strong>{screen.title}</strong>
                    </div>
                    <p>{screen.lead}</p>
                    <div className="landing-product-preview-body">
                      {screen.details.map(([label, value]) => (
                        <div className="landing-product-preview-row" key={`${label}-${value}`}>
                          <span>{label}</span>
                          <strong>{value}</strong>
                        </div>
                      ))}
                    </div>
                  </Reveal>
                ))}
              </div>
            </div>
          </section>

          <section id="features" className="landing-section">
            <div className="landing-shell">
              <Reveal className="landing-section-heading">
                <span className="landing-section-kicker">ВОЗМОЖНОСТИ</span>
                <h2>Всё, что нужно репетитору для ежедневной работы</h2>
              </Reveal>

              <div className="landing-feature-grid">
                {featureItems.map((item, index) => (
                  <Reveal className="landing-feature-card" key={item.title} delay={index * 70}>
                    <span className="landing-feature-icon">{item.icon}</span>
                    <h3>{item.title}</h3>
                    <p>{item.text}</p>
                  </Reveal>
                ))}
              </div>
            </div>
          </section>

          <section className="landing-section landing-founder-section">
            <div className="landing-shell">
              <Reveal className="landing-founder-card">
                <span className="landing-section-kicker">ИСТОРИЯ</span>
                <h2>Почему появился TutorBase</h2>
                <p>
                  TutorBase появился из практической задачи: спокойно вести учеников,
                  занятия, оплаты и напоминания без таблиц и лишней ручной работы.
                </p>
                <p>
                  Сейчас мы открываем его для других преподавателей, которым нужен такой же
                  порядок в ежедневной работе.
                </p>
              </Reveal>
            </div>
          </section>

          <section id="workflow" className="landing-section landing-workflow-section">
            <div className="landing-shell landing-section-grid">
              <Reveal className="landing-section-copy">
                <span className="landing-section-kicker">КАК РАБОТАЕТ</span>
                <h2>От первого ученика до понятного расписания</h2>
              </Reveal>

              <div className="landing-steps">
                {[
                  ['Создайте кабинет', 'Укажите название кабинета и имя преподавателя.'],
                  ['Добавьте учеников', 'Создайте карточки учеников. Приглашение можно выдать позже, когда нужен доступ ученика.'],
                  ['Соберите расписание', 'Добавьте отдельные занятия или пакеты уроков.'],
                  ['Ведите занятия спокойно', 'Расписание, напоминания, оплаты и история остаются в одном месте.'],
                ].map(([title, text], index) => (
                  <Reveal className="landing-step-card" key={title} delay={index * 80}>
                    <span>{index + 1}</span>
                    <div>
                      <h3>{title}</h3>
                      <p>{text}</p>
                    </div>
                  </Reveal>
                ))}
              </div>
            </div>
          </section>

          <section id="pricing" className="landing-section">
            <div className="landing-shell">
              <Reveal className="landing-pricing-card">
                <div className="landing-pricing-copy">
                  <span className="landing-section-kicker">ТАРИФ</span>
                  <h2>Попробуйте TutorBase на своём расписании</h2>
                  <p>
                    Начните бесплатно с небольшим количеством учеников. Когда расписание растёт,
                    тариф меняется по понятной шкале активных учеников.
                  </p>
                  <p className="landing-pricing-note">
                    Стоимость считается по активным ученикам. Ученики подключаются бесплатно.
                  </p>
                </div>

                <div className="landing-plan-grid">
                  {pricingPlans.map((plan) => (
                    <div
                      className={`landing-plan-card ${plan.accent ? 'landing-plan-card--accent' : ''}`}
                      key={plan.name}
                    >
                      <span>{plan.name}</span>
                      <strong>{plan.price}</strong>
                      <small>{plan.price === '0 ₽' ? 'навсегда' : 'за 30 дней'}</small>
                      <em>{plan.range}</em>
                      <p>{plan.note}</p>
                    </div>
                  ))}
                  <div className="landing-plan-summary">
                    <ul>
                      <li><CheckCircleOutlined /> Все тарифы включают учеников, занятия и расписание</li>
                      <li><CheckCircleOutlined /> Напоминания и финансовый учёт доступны в кабинете</li>
                      <li><CheckCircleOutlined /> Ученики подключаются бесплатно по приглашению</li>
                    </ul>
                    <Button type="primary" size="large" href={registerUrl} className="landing-content-cta">
                      {CTA_TEXT}
                    </Button>
                  </div>
                </div>
              </Reveal>
            </div>
          </section>

          <section className="landing-section landing-rules-section">
            <div className="landing-shell landing-section-grid">
              <Reveal className="landing-section-copy">
                <span className="landing-section-kicker">ПРАВИЛА ТАРИФА</span>
                <h2>Бесплатный старт без потери истории</h2>
              </Reveal>

              <Reveal className="landing-rules-card" delay={80}>
                {tariffRules.map((rule) => (
                  <div className="landing-rule-row" key={rule}>
                    <CheckCircleOutlined />
                    <span>{rule}</span>
                  </div>
                ))}
              </Reveal>
            </div>
          </section>

          <section id="faq" className="landing-section">
            <div className="landing-shell landing-faq-grid">
              <Reveal className="landing-section-copy">
                <span className="landing-section-kicker">FAQ</span>
                <h2>Ответы перед стартом</h2>
              </Reveal>

              <Reveal className="landing-faq-card" delay={80}>
                <Collapse
                  items={faqItems}
                  bordered={false}
                  defaultActiveKey={['audience']}
                  expandIconPosition="end"
                />
              </Reveal>
            </div>
          </section>

          <section className="landing-section landing-trust-section">
            <div className="landing-shell">
              <Reveal className="landing-section-heading">
                <span className="landing-section-kicker">ДОВЕРИЕ</span>
                <h2>Понятные правила для преподавателя и учеников</h2>
              </Reveal>

              <div className="landing-trust-grid">
                {trustItems.map((item, index) => (
                  <Reveal className="landing-trust-card" key={item.title} delay={index * 80}>
                    <h3>{item.title}</h3>
                    <p>{item.text}</p>
                  </Reveal>
                ))}
              </div>
            </div>
          </section>

          <section className="landing-final-cta">
            <div className="landing-shell">
              <Reveal className="landing-final-card">
                <span className="landing-section-kicker">TutorBase</span>
                <h2>Попробуйте TutorBase на своих учениках</h2>
                <p>
                  Создайте кабинет преподавателя и начните бесплатно с первыми учениками уже сегодня.
                </p>
                <Button
                  type="primary"
                  size="large"
                  href={registerUrl}
                  icon={<ArrowRightOutlined />}
                  className="landing-content-cta"
                >
                  {CTA_TEXT}
                </Button>
                <small>Бесплатно до 3 активных учеников. Без карты и обязательств.</small>
              </Reveal>
            </div>
          </section>
        </main>

        <footer id="contacts" className="landing-footer">
          <div className="landing-shell landing-footer-grid">
            <div>
              <a className="landing-brand" href="#top" aria-label="TutorBase" onClick={(event) => handleAnchorClick(event, 'top')}>
                <span className="landing-brand-mark">
                  <img src="/favicon.svg" alt="" aria-hidden="true" />
                </span>
                <span>TutorBase</span>
              </a>
              <p>
                Кабинет для репетитора: расписание занятий, учёт учеников, пакеты,
                напоминания и оплаты.
              </p>
            </div>

            <div className="landing-footer-column">
              <strong>Поддержка</strong>
              <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>
            </div>

            <div className="landing-footer-column">
              <strong>Документы</strong>
              <a href="/offer">Оферта</a>
              <a href="/privacy">Политика обработки персональных данных</a>
            </div>
          </div>
          <div className="landing-shell landing-footer-bottom">
            <span>{SELLER_NAME} ИНН {SELLER_INN}</span>
            <span>2026 TutorBase. Все права защищены.</span>
          </div>
        </footer>
      </div>
    </ConfigProvider>
  );
};

export default LandingPage;
