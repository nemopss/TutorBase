import { appEnv } from '../env';

const SENSITIVE_KEY_PARTS = [
  'authorization',
  'cookie',
  'token',
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
    return value.length > 512 ? `${value.slice(0, 512)}...[truncated]` : value;
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

const sanitizeAxiosError = (error: any) => {
  const data = typeof error?.config?.data === 'string'
    ? tryParseJson(error.config.data)
    : error?.config?.data;

  return redactSensitive({
    message: error?.message,
    status: error?.response?.status,
    method: error?.config?.method,
    url: error?.config?.url,
    request_data: data,
    response_data: error?.response?.data,
  });
};

const sanitizeArg = (arg: unknown): unknown => {
  if (arg instanceof Error) {
    const maybeAxiosError = arg as any;
    if (maybeAxiosError.isAxiosError || maybeAxiosError.config || maybeAxiosError.response) {
      return sanitizeAxiosError(maybeAxiosError);
    }
    return { name: arg.name, message: arg.message };
  }

  if (typeof arg === 'object' && arg !== null) {
    const maybeAxiosError = arg as any;
    if (maybeAxiosError.isAxiosError || maybeAxiosError.config || maybeAxiosError.response) {
      return sanitizeAxiosError(maybeAxiosError);
    }
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
