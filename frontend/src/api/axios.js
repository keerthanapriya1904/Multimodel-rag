// src/api/axios.js
// Configured Axios instance for DocMind
// Auto-attaches JWT token to every request
// Auto-redirects to /login on 401

import axios from "axios"

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
  headers: { "Content-Type": "application/json" }
})

// Attach token before every request
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("rag_token")
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
  },
  (error) => Promise.reject(error)
)

// Redirect to login on expired token
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem("rag_token")
      localStorage.removeItem("rag_user")
      window.location.href = "/login"
    }
    return Promise.reject(error)
  }
)

export default api
