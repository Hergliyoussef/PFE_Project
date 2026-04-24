import axios from "axios"
import Cookies from "js-cookie"

const API_BASE_URL = "http://localhost:8000/api/v1"

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
})

// Intercepteur pour ajouter le token à chaque requête
api.interceptors.request.use((config) => {
  const token = Cookies.get("pm_chatbot_access_token")
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export default api
