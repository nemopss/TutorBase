import axios, { type AxiosRequestConfig } from "axios";

type RetryableRequestConfig = AxiosRequestConfig & {
  _retry?: boolean;
};

type RefreshSubscriber = (token: string | null) => void;

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1",
  timeout: 15000, // 15 second timeout for Android
});

let refreshTokenRequest: Promise<string | null> | null = null;
const refreshSubscribers: RefreshSubscriber[] = [];

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
  delete api.defaults.headers.common.Authorization;
};

const refreshAccessToken = async (): Promise<string | null> => {
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
    if (import.meta.env.DEV) {
      console.log(
        `API Request: ${config.method?.toUpperCase()} ${config.url}`,
        {
          headers: config.headers,
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
      originalRequest.url !== "/auth/refresh"
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
