// src/App.jsx
// DocMind — Router setup
// Upload is now a MODAL inside Chat, not a separate page
// So only 2 routes needed: /login and /chat

import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import Login from "./pages/Login.jsx"
import Chat  from "./pages/Chat.jsx"

// ── ProtectedRoute ──
// Redirects to /login if no JWT token found
function ProtectedRoute({ children }) {
  const token = localStorage.getItem("rag_token")
  return token ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public */}
        <Route path="/login" element={<Login />} />

        {/* Protected */}
        <Route
          path="/chat"
          element={
            <ProtectedRoute>
              <Chat />
            </ProtectedRoute>
          }
        />

        {/* Default redirect */}
        <Route
          path="/"
          element={
            localStorage.getItem("rag_token")
              ? <Navigate to="/chat" />
              : <Navigate to="/login" />
          }
        />

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </BrowserRouter>
  )
}
