import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";

function resolveApiBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL;

  if (raw) {
    // Strip trailing slash; keep whatever path the user provided (e.g. /api/v1)
    return raw.replace(/\/+$/, "");
  }

  if (process.env.NODE_ENV !== "production") {
    return "http://localhost:8000/api/v1";
  }

  console.error(
    "[Nalam] NEXT_PUBLIC_API_URL is not set. " +
      "Add it to your Vercel environment variables: " +
      "NEXT_PUBLIC_API_URL=https://nalam-backend-ql9u.onrender.com/api/v1"
  );
  return ""; // will surface as a clear network error rather than a silent localhost hit
}

const baseURL = resolveApiBaseUrl();

export const api: AxiosInstance = axios.create({
  baseURL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 15000,
});

// Request interceptor
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    return config;
  },
  (error: AxiosError) => {
    console.error("API Request Error:", error);
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response) {
      console.error(
        `API Error [${error.response.status}]:`,
        error.response.data || error.message
      );
    } else if (error.request) {
      console.error("API Network Error - No response received:", error.message);
    } else {
      console.error("API Setup Error:", error.message);
    }
    return Promise.reject(error);
  }
);

export default api;
