import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 15000, // 15 second timeout for Android
});

// Request interceptor for debugging
api.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`, {
      headers: config.headers,
      params: config.params,
    });
    return config;
  },
  (error) => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor for token refresh
api.interceptors.response.use(
  (response) => response, // Simply return response if it's successful
  async (error) => {
    const originalRequest = error.config;

    // Check if the error is 401 and it's not a retry request or the refresh endpoint
    if (error.response && error.response.status === 401 && !originalRequest._retry && originalRequest.url !== '/auth/refresh') {
      originalRequest._retry = true; // Mark it as a retry

      try {
        const refreshToken = localStorage.getItem('refreshToken');
        if (!refreshToken) {
          return Promise.reject(error); // No refresh token, reject
        }

        // Request a new access token using the refresh token
        const { data } = await api.post('/auth/refresh', { refresh_token: refreshToken });

        // Store new tokens
        localStorage.setItem('accessToken', data.access_token);
        localStorage.setItem('refreshToken', data.refresh_token);

        // Update the default authorization header
        api.defaults.headers.common['Authorization'] = `Bearer ${data.access_token}`;

        // Update the authorization header of the original request
        originalRequest.headers['Authorization'] = `Bearer ${data.access_token}`;

        // Retry the original request
        return api(originalRequest);
      } catch (refreshError: any) {
        // If refresh fails, clear tokens and reject
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
        delete api.defaults.headers.common['Authorization'];
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export default api;
