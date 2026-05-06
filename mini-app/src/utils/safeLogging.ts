import { appEnv } from '../env';

interface LoggableAxiosConfig {
  data?: unknown;
  method?: string;
  url?: string;
  params?: unknown;
}

interface LoggableAxiosResponse {
  status?: number;
  data?: unknown;
}

type LoggableAxiosError = {
  isAxiosError?: boolean;
  message?: string;
} & (
  | { isAxiosError: boolean; config?: LoggableAxiosConfig; response?: LoggableAxiosResponse }
  | { config: LoggableAxiosConfig; isAxiosError?: boolean; response?: LoggableAxiosResponse }
  | { response: LoggableAxiosResponse; isAxiosError?: boolean; config?: LoggableAxiosConfig }
);

const SENSITIVE_KEY_PARTS = [
  'authorization',
  'cookie',
  'token',
  'refresh',
  'access',
  'init_data',
  'initdata',
  'telegram-init-data',
  'hash',
  'password',
  'secret',
  'api_key',
  'apikey',
];

const isSensitiveKey = (key: string) => {
  const normalized = key.toLowerCase().replace(/[-\s]/g, '_');
  return SENSITIVE_KEY_PARTS.some((part) => normalized.includes(part));
};

const JWT_PATTERN = /^[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}$/;
const URL_SCHEME_PATTERN = /^[a-z][a-z\d+\-.]*:/i;

const redactSearchParams = (params: URLSearchParams) => {
  const redacted = new URLSearchParams();

  params.forEach((item, key) => {
    redacted.append(key, isSensitiveKey(key) ? '[redacted]' : item);
  });

  return redacted.toString();
};

export const sanitizeUrl = (value: string): string => {
  const isAbsolute = URL_SCHEME_PATTERN.test(value);

  if (!isAbsolute && !value.startsWith('/') && !value.includes('?')) {
    if (!value.includes('=')) {
      return value;
    }

    const params = new URLSearchParams(value);
    return redactSearchParams(params);
  }

  try {
    const url = new URL(value, 'http://tutorbase.local');
    const query = redactSearchParams(url.searchParams);
    const hash = url.hash ? '#[redacted]' : '';

    if (isAbsolute) {
      url.search = query;
      url.hash = hash;
      return url.toString();
    }

    return `${url.pathname}${query ? `?${query}` : ''}${hash}`;
  } catch {
    if (!value.includes('=')) {
      return value;
    }

    const query = value.startsWith('?') ? value.slice(1) : value;
    const params = new URLSearchParams(query);
    const redacted = redactSearchParams(params);
    return value.startsWith('?') ? `?${redacted}` : redacted;
  }
};

const tryParseJson = (value: string): unknown => {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
};

export const redactSensitive = (value: unknown, depth = 0, seen = new WeakSet<object>()): unknown => {
  if (value === null || value === undefined) {
    return value;
  }

  if (typeof value === 'string') {
    if (JWT_PATTERN.test(value)) {
      return '[redacted]';
    }

    const sanitized = value.includes('?') || value.includes('=') ? sanitizeUrl(value) : value;
    return sanitized.length > 512 ? `${sanitized.slice(0, 512)}...[truncated]` : sanitized;
  }

  if (typeof value !== 'object') {
    return value;
  }

  if (seen.has(value)) {
    return '[circular]';
  }
  if (depth > 5) {
    return '[max-depth]';
  }
  seen.add(value);

  if (Array.isArray(value)) {
    return value.map((item) => redactSensitive(item, depth + 1, seen));
  }

  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).map(([key, item]) => {
      if (isSensitiveKey(key)) {
        return [key, '[redacted]'];
      }
      return [key, redactSensitive(item, depth + 1, seen)];
    })
  );
};

const isLoggableAxiosError = (value: unknown): value is LoggableAxiosError => {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const candidate = value as Partial<LoggableAxiosError>;
  return Boolean(candidate.isAxiosError || candidate.config || candidate.response);
};

const sanitizeAxiosError = (error: LoggableAxiosError) => {
  const data = typeof error?.config?.data === 'string'
    ? tryParseJson(error.config.data)
    : error?.config?.data;

  return redactSensitive({
    message: error?.message,
    status: error?.response?.status,
    method: error?.config?.method,
    url: typeof error?.config?.url === 'string' ? sanitizeUrl(error.config.url) : error?.config?.url,
    params: error?.config?.params,
    request_data: data,
    response_data: error?.response?.data,
  });
};

const sanitizeArg = (arg: unknown): unknown => {
  if (arg instanceof Error) {
    if (isLoggableAxiosError(arg)) {
      return sanitizeAxiosError(arg);
    }
    return { name: arg.name, message: arg.message };
  }

  if (isLoggableAxiosError(arg)) {
    return sanitizeAxiosError(arg);
  }

  return redactSensitive(arg);
};

export const devLog = (...args: unknown[]) => {
  if (appEnv.isDev) {
    console.log(...args.map(sanitizeArg));
  }
};

export const devWarn = (...args: unknown[]) => {
  if (appEnv.isDev) {
    console.warn(...args.map(sanitizeArg));
  }
};

export const devError = (...args: unknown[]) => {
  if (appEnv.isDev) {
    console.error(...args.map(sanitizeArg));
  }
};
