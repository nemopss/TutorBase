import type { AuthMode } from './modes';

export const AUTH_USER_STORAGE_KEY = 'authUser';

const getStorageTargets = (mode: AuthMode): Storage[] => (
  mode === 'browser'
    ? [window.sessionStorage, window.localStorage]
    : [window.localStorage]
);

export const clearCachedUser = () => {
  window.localStorage.removeItem(AUTH_USER_STORAGE_KEY);
  window.sessionStorage.removeItem(AUTH_USER_STORAGE_KEY);
};

export const readCachedUser = <T>(mode: AuthMode): T | null => {
  for (const storage of getStorageTargets(mode)) {
    const raw = storage.getItem(AUTH_USER_STORAGE_KEY);
    if (!raw) {
      continue;
    }

    try {
      const parsed = JSON.parse(raw) as T;

      if (mode === 'browser' && storage === window.localStorage) {
        window.sessionStorage.setItem(AUTH_USER_STORAGE_KEY, raw);
        window.localStorage.removeItem(AUTH_USER_STORAGE_KEY);
      }

      return parsed;
    } catch {
      storage.removeItem(AUTH_USER_STORAGE_KEY);
    }
  }

  return null;
};

export const cacheUser = <T>(user: T | null, mode: AuthMode) => {
  clearCachedUser();

  if (user === null) {
    return;
  }

  const storage = mode === 'browser' ? window.sessionStorage : window.localStorage;
  storage.setItem(AUTH_USER_STORAGE_KEY, JSON.stringify(user));
};
