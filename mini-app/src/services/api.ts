import axios, { type AxiosRequestConfig } from "axios";
import { clearCachedUser } from "../auth/userCache";
import { appEnv } from "../env";

type RetryableRequestConfig = AxiosRequestConfig & {
  _retry?: boolean;
};

type RefreshSubscriber = (token: string | null) => void;
type BrowserRefreshHandler = () => Promise<string | null>;

const api = axios.create({
  baseURL: appEnv.apiBaseUrl,
  timeout: appEnv.apiTimeoutMs,
});

let refreshTokenRequest: Promise<string | null> | null = null;
let browserRefreshHandler: BrowserRefreshHandler | null = null;
const refreshSubscribers: RefreshSubscriber[] = [];

export const setBrowserRefreshHandler = (handler: BrowserRefreshHandler | null) => {
  browserRefreshHandler = handler;
};

const subscribeTokenRefresh = (callback: RefreshSubscriber) => {
  refreshSubscribers.push(callback);
};

const notifyRefreshSubscribers = (token: string | null) => {
  refreshSubscribers.forEach((callback) => callback(token));
  refreshSubscribers.length = 0;
};

const clearStoredTokens = () => {
  localStorage.removeItem("accessToken");
  localStorage.removeItem("refreshToken");
  clearCachedUser();
  delete api.defaults.headers.common.Authorization;
};

const redactHeaders = (headers: AxiosRequestConfig["headers"]) => {
  if (!headers) {
    return headers;
  }

  return Object.fromEntries(
    Object.entries(headers).map(([key, value]) => {
      const normalized = key.toLowerCase();
      if (
        normalized === "authorization" ||
        normalized === "cookie" ||
        normalized === "set-cookie" ||
        normalized.includes("token") ||
        normalized.includes("telegram-init-data")
      ) {
        return [key, "[redacted]"];
      }
      return [key, value];
    })
  );
};

const refreshAccessToken = async (): Promise<string | null> => {
  if (browserRefreshHandler) {
    return browserRefreshHandler();
  }

  const refreshToken = localStorage.getItem("refreshToken");
  if (!refreshToken) {
    return null;
  }

  const { data } = await api.post("/auth/refresh", {
    refresh_token: refreshToken,
  });

  localStorage.setItem("accessToken", data.access_token);
  localStorage.setItem("refreshToken", data.refresh_token);
  api.defaults.headers.common.Authorization = `Bearer ${data.access_token}`;

  return data.access_token as string;
};

// Request interceptor for debugging
api.interceptors.request.use(
  (config) => {
    if (appEnv.isDev) {
      console.log(
        `API Request: ${config.method?.toUpperCase()} ${config.url}`,
        {
          headers: redactHeaders(config.headers),
          params: config.params,
        }
      );
    }
    return config;
  },
  (error) => {
    console.error("API Request Error:", error);
    return Promise.reject(error);
  }
);

// Response interceptor for token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as RetryableRequestConfig;

    if (
      error.response &&
      error.response.status === 401 &&
      !originalRequest._retry &&
      originalRequest.url !== "/auth/refresh" &&
      originalRequest.url !== "/auth/browser/refresh"
    ) {
      originalRequest._retry = true;

      if (!refreshTokenRequest) {
        refreshTokenRequest = refreshAccessToken()
          .then((token) => {
            notifyRefreshSubscribers(token);
            return token;
          })
          .catch((refreshError) => {
            notifyRefreshSubscribers(null);
            clearStoredTokens();
            throw refreshError;
          })
          .finally(() => {
            refreshTokenRequest = null;
          });
      }

      return new Promise((resolve, reject) => {
        subscribeTokenRefresh((token) => {
          if (!token) {
            reject(error);
            return;
          }

          originalRequest.headers = {
            ...(originalRequest.headers ?? {}),
            Authorization: `Bearer ${token}`,
          };

          resolve(api(originalRequest));
        });
      });
    }

    return Promise.reject(error);
  }
);

export default api;
