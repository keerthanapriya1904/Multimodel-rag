// src/pages/Login.jsx
// DocMind — Clean centered card login (Claude-style)
// Black & white theme

import { useState } from "react"
import { useNavigate } from "react-router-dom"
import api from "../api/axios"

// ── DocMind Logo SVG ──────────────────────────────────────────
function DocMindLogo({ size = 36 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none">
      <rect width="40" height="40" rx="10" fill="#171717"/>
      {/* Document shape */}
      <rect x="10" y="8" width="14" height="18" rx="2" fill="white" opacity="0.9"/>
      <path d="M19 8l5 5h-5V8z" fill="#171717" opacity="0.4"/>
      {/* Spark/AI lines */}
      <line x1="12" y1="16" x2="21" y2="16" stroke="#171717" strokeWidth="1.5" opacity="0.5"/>
      <line x1="12" y1="19" x2="21" y2="19" stroke="#171717" strokeWidth="1.5" opacity="0.5"/>
      <line x1="12" y1="22" x2="18" y2="22" stroke="#171717" strokeWidth="1.5" opacity="0.5"/>
      {/* Chat bubble */}
      <rect x="20" y="22" width="12" height="10" rx="3" fill="white" opacity="0.95"/>
      <circle cx="24" cy="27" r="1.2" fill="#171717"/>
      <circle cx="27" cy="27" r="1.2" fill="#171717"/>
      <circle cx="30" cy="27" r="1.2" fill="#171717"/>
    </svg>
  )
}

export default function Login() {
  const [mode,     setMode]     = useState("login")
  const [username, setUsername] = useState("")
  const [email,    setEmail]    = useState("")
  const [password, setPassword] = useState("")
  const [error,    setError]    = useState("")
  const [loading,  setLoading]  = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async () => {
    if (!username.trim() || !password.trim()) {
      setError("Please fill in all fields")
      return
    }
    if (mode === "register" && !email.trim()) {
      setError("Please enter your email")
      return
    }
    setLoading(true)
    setError("")
    try {
      const endpoint = mode === "login" ? "/auth/login" : "/auth/register"
      const payload  = mode === "login"
        ? { username, password }
        : { username, email, password }
      const res = await api.post(endpoint, payload)
      localStorage.setItem("rag_token", res.data.token)
      localStorage.setItem("rag_user", JSON.stringify({
        user_id: res.data.user_id, username: res.data.username
      }))
      navigate("/chat")
    } catch (err) {
      setError(err.response?.data?.detail || "Something went wrong. Try again.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-white flex flex-col items-center justify-center px-4">

      {/* Logo + name */}
      <div className="flex flex-col items-center mb-8">
        <DocMindLogo size={48} />
        <h1 className="mt-3 text-2xl font-bold text-gray-900 tracking-tight">DocMind</h1>
        <p className="mt-1 text-sm text-gray-500">
          {mode === "login" ? "Welcome back" : "Create your account"}
        </p>
      </div>

      {/* Card */}
      <div className="w-full max-w-[360px] bg-white border border-gray-200
                      rounded-2xl shadow-sm px-7 py-7">

        {/* Mode tabs */}
        <div className="flex bg-gray-100 rounded-xl p-1 mb-6">
          {["login", "register"].map(m => (
            <button key={m}
              onClick={() => { setMode(m); setError("") }}
              className={`flex-1 py-2 text-sm font-medium rounded-lg transition-all duration-150
                ${mode === m
                  ? "bg-white shadow-sm text-gray-900"
                  : "text-gray-500 hover:text-gray-700"}`}
            >
              {m === "login" ? "Sign In" : "Register"}
            </button>
          ))}
        </div>

        {/* Fields */}
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleSubmit()}
              placeholder="keerthana"
              className="w-full px-3.5 py-2.5 text-sm border border-gray-200 rounded-xl
                         bg-white text-gray-900 placeholder-gray-400
                         focus:outline-none focus:ring-2 focus:ring-gray-900
                         focus:border-transparent transition-all"
            />
          </div>

          {mode === "register" && (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full px-3.5 py-2.5 text-sm border border-gray-200 rounded-xl
                           bg-white text-gray-900 placeholder-gray-400
                           focus:outline-none focus:ring-2 focus:ring-gray-900
                           focus:border-transparent transition-all"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1.5">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleSubmit()}
              placeholder="••••••••"
              className="w-full px-3.5 py-2.5 text-sm border border-gray-200 rounded-xl
                         bg-white text-gray-900 placeholder-gray-400
                         focus:outline-none focus:ring-2 focus:ring-gray-900
                         focus:border-transparent transition-all"
            />
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="mt-4 flex items-start gap-2 px-3.5 py-2.5 rounded-xl
                          bg-red-50 border border-red-200 text-red-600 text-sm">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2" className="flex-shrink-0 mt-0.5">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            {error}
          </div>
        )}

        {/* Submit */}
        <button
          onClick={handleSubmit}
          disabled={loading}
          className="mt-5 w-full bg-gray-900 text-white py-2.5 rounded-xl text-sm
                     font-medium hover:bg-gray-700 active:bg-gray-800
                     disabled:opacity-50 transition-all duration-150"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <div className="w-4 h-4 border-2 border-white border-t-transparent
                              rounded-full animate-spin"/>
              Please wait...
            </span>
          ) : mode === "login" ? "Sign In" : "Create Account"}
        </button>
      </div>

      {/* Footer */}
      <p className="mt-6 text-xs text-gray-400 text-center max-w-xs">
        Your documents are processed privately on your own server.
        Nothing is shared externally.
      </p>
    </div>
  )
}
