// src/pages/Chat.jsx
// DocMind — ChatGPT/Claude hybrid design
// Dark sidebar (#171717) + clean white chat area
// Features: conversation history, documents, voice input,
//           copy button, thumbs up/down, upload modal

import { useState, useRef, useEffect, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import api from "../api/axios"
import UploadModal from "../components/UploadModal"

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000"
const CONV_KEY = "docmind_conversations"   // localStorage key

// ── DocMind Logo (small, for sidebar) ────────────────────────
function Logo({ size = 28 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none">
      <rect width="40" height="40" rx="10" fill="white" opacity="0.15"/>
      <rect x="10" y="8" width="14" height="18" rx="2" fill="white" opacity="0.9"/>
      <path d="M19 8l5 5h-5V8z" fill="#171717" opacity="0.5"/>
      <line x1="12" y1="16" x2="21" y2="16" stroke="#171717" strokeWidth="1.5" opacity="0.4"/>
      <line x1="12" y1="19" x2="21" y2="19" stroke="#171717" strokeWidth="1.5" opacity="0.4"/>
      <line x1="12" y1="22" x2="18" y2="22" stroke="#171717" strokeWidth="1.5" opacity="0.4"/>
      <rect x="20" y="22" width="12" height="10" rx="3" fill="white" opacity="0.95"/>
      <circle cx="24" cy="27" r="1.2" fill="#171717"/>
      <circle cx="27" cy="27" r="1.2" fill="#171717"/>
      <circle cx="30" cy="27" r="1.2" fill="#171717"/>
    </svg>
  )
}

// ── Markdown renderer ─────────────────────────────────────────
// Handles: **bold**, bullet lists, numbered lists, headers,
// `inline code`, [Source: ...] citation badges
function renderMarkdown(text) {
  if (!text) return null
  const lines = text.split("\n")
  const out   = []
  let   i     = 0

  while (i < lines.length) {
    const line = lines[i]

    // Empty line → spacer
    if (line.trim() === "") {
      out.push(<div key={i} className="h-2" />)
      i++
      continue
    }

    // ## or ### heading
    if (line.startsWith("## ") || line.startsWith("### ")) {
      out.push(
        <p key={i} className="font-semibold text-sm mt-3 mb-1 text-gray-900">
          {renderInline(line.replace(/^#{2,3}\s/, ""))}
        </p>
      )
      i++
      continue
    }

    // Bullet list — collect consecutive lines
    if (/^[\s]*[-*•]\s/.test(line)) {
      const bullets = []
      while (i < lines.length && /^[\s]*[-*•]\s/.test(lines[i])) {
        bullets.push(lines[i].replace(/^[\s]*[-*•]\s/, ""))
        i++
      }
      out.push(
        <ul key={"ul" + i} className="my-2 space-y-1.5 pl-1">
          {bullets.map((b, j) => (
            <li key={j} className="flex gap-2.5 text-sm leading-relaxed text-gray-800">
              <span className="mt-2 w-1.5 h-1.5 rounded-full bg-gray-400 flex-shrink-0"/>
              <span>{renderInline(b)}</span>
            </li>
          ))}
        </ul>
      )
      continue
    }

    // Numbered list — collect consecutive lines
    if (/^[\s]*\d+\.\s/.test(line)) {
      const items = []
      while (i < lines.length && /^[\s]*\d+\.\s/.test(lines[i])) {
        items.push(lines[i].replace(/^[\s]*\d+\.\s/, ""))
        i++
      }
      out.push(
        <ol key={"ol" + i} className="my-2 space-y-2 pl-1">
          {items.map((item, j) => (
            <li key={j} className="flex gap-2.5 text-sm leading-relaxed text-gray-800">
              <span className="flex-shrink-0 w-5 h-5 mt-0.5 rounded-full bg-gray-100
                               text-xs font-semibold flex items-center justify-center
                               text-gray-500">
                {j + 1}
              </span>
              <span>{renderInline(item)}</span>
            </li>
          ))}
        </ol>
      )
      continue
    }

    // Normal paragraph
    out.push(
      <p key={i} className="text-sm leading-relaxed text-gray-800 my-1">
        {renderInline(line)}
      </p>
    )
    i++
  }
  return out
}

// Renders **bold**, `code`, [Source: ...] citation badges
function renderInline(text) {
  const parts  = []
  const regex  = /(\*\*[^*]+\*\*|`[^`]+`|\[Source[^\]]+\])/g
  let   last   = 0
  let   match

  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index))
    const tok = match[0]

    if (tok.startsWith("**")) {
      parts.push(
        <strong key={match.index} className="font-semibold text-gray-900">
          {tok.slice(2, -2)}
        </strong>
      )
    } else if (tok.startsWith("`")) {
      parts.push(
        <code key={match.index}
          className="px-1.5 py-0.5 rounded bg-gray-100 text-xs font-mono text-pink-700">
          {tok.slice(1, -1)}
        </code>
      )
    } else if (tok.startsWith("[Source")) {
      parts.push(
        <span key={match.index}
          className="inline-flex items-center gap-1 mx-0.5 px-2 py-0.5 rounded-md
                     bg-blue-50 text-blue-600 text-xs font-medium border border-blue-200">
          <svg width="9" height="9" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2.5">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12
                     a2 2 0 0 0 2-2V8z"/>
            <polyline points="14,2 14,8 20,8"/>
          </svg>
          {tok.slice(1, -1)}
        </span>
      )
    }
    last = match.index + tok.length
  }

  if (last < text.length) parts.push(text.slice(last))
  return parts.length === 1 && typeof parts[0] === "string" ? parts[0] : parts
}

// ── Group conversations by date ───────────────────────────────
function groupByDate(conversations) {
  const today     = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)

  const groups = { Today: [], Yesterday: [], "Previous 7 Days": [], Older: [] }

  conversations.forEach(conv => {
    const d = new Date(conv.createdAt)
    const diffDays = Math.floor((today - d) / (1000 * 60 * 60 * 24))
    if (diffDays === 0)       groups["Today"].push(conv)
    else if (diffDays === 1)  groups["Yesterday"].push(conv)
    else if (diffDays <= 7)   groups["Previous 7 Days"].push(conv)
    else                      groups["Older"].push(conv)
  })

  return Object.entries(groups).filter(([, v]) => v.length > 0)
}

// ── Main Chat Component ───────────────────────────────────────
export default function Chat() {
  // ── Messages & input ────────────────────────────────────────
  const [messages,      setMessages]      = useState([])
  const [question,      setQuestion]      = useState("")
  const [loading,       setLoading]       = useState(false)

  // ── Sidebar & UI ─────────────────────────────────────────────
  const [sidebarOpen,   setSidebarOpen]   = useState(true)
  const [showUpload,    setShowUpload]    = useState(false)
  const [documents,     setDocuments]     = useState([])

  // ── Conversation history (localStorage) ─────────────────────
  const [conversations, setConversations] = useState([])
  const [currentConvId, setCurrentConvId] = useState(null)

  // ── Voice recording ──────────────────────────────────────────
  const [recording,     setRecording]     = useState(false)
  const [mediaRecorder, setMediaRecorder] = useState(null)

  // ── Per-message feedback (copy / thumbs) ─────────────────────
  const [feedback,      setFeedback]      = useState({})  // {msgIndex: "up"|"down"|"copied"}

  const bottomRef  = useRef(null)
  const inputRef   = useRef(null)
  const navigate   = useNavigate()
  const token      = localStorage.getItem("rag_token")
  const user       = JSON.parse(localStorage.getItem("rag_user") || "{}")

  // ── Load on mount ────────────────────────────────────────────
  useEffect(() => {
    loadDocuments()
    loadConversations()
  }, [])

  // ── Auto scroll ──────────────────────────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  // ── Save current conversation when messages change ───────────
  useEffect(() => {
    if (currentConvId && messages.length > 0) {
      saveCurrentConversation(messages)
    }
  }, [messages])

  const loadDocuments = async () => {
    try {
      const res = await api.get("/upload/list")
      setDocuments(res.data.documents || [])
    } catch { setDocuments([]) }
  }

  // ── Conversation history ─────────────────────────────────────
  // ZERO PERSISTENCE POLICY:
  // Only the conversation TITLE is stored in localStorage.
  // Message content (answers, document excerpts) is NEVER
  // written to localStorage or any persistent storage.
  // Messages live only in React state (RAM) and are lost
  // when the page is refreshed — intentional for privacy.

  const loadConversations = () => {
    try {
      // Load only titles from localStorage — no message content
      const saved = JSON.parse(localStorage.getItem(CONV_KEY) || "[]")
      // Strip any messages that may have been stored by old version
      const safe = saved.map(c => ({
        id:        c.id,
        title:     c.title,
        createdAt: c.createdAt
        // messages field deliberately excluded
      }))
      setConversations(safe)
    } catch { setConversations([]) }
  }

  const createNewConversation = () => {
    const id = Date.now().toString()
    setCurrentConvId(id)
    setMessages([])
    setFeedback({})
    return id
  }

  const saveCurrentConversation = useCallback((msgs) => {
    if (!currentConvId || msgs.length === 0) return
    const title = msgs.find(m => m.role === "user")
                    ?.content?.slice(0, 45) || "New conversation"

    setConversations(prev => {
      const exists  = prev.find(c => c.id === currentConvId)
      let   updated
      if (exists) {
        updated = prev.map(c =>
          c.id === currentConvId ? { ...c, title } : c
        )
      } else {
        updated = [{
          id:        currentConvId,
          title,
          createdAt: new Date().toISOString()
          // NO messages field — zero persistence policy
        }, ...prev]
      }
      // Save ONLY titles to localStorage — never message content
      localStorage.setItem(CONV_KEY, JSON.stringify(updated))
      return updated
    })
  }, [currentConvId])

  const loadConversation = (conv) => {
    // When clicking a past conversation, we can only restore
    // the title — messages are not persisted by design.
    // Start a new empty chat with that conversation ID.
    setCurrentConvId(conv.id)
    setMessages([])   // messages not persisted — privacy policy
    setFeedback({})
  }

  const deleteConversation = (e, convId) => {
    e.stopPropagation()
    const updated = conversations.filter(c => c.id !== convId)
    setConversations(updated)
    localStorage.setItem(CONV_KEY, JSON.stringify(updated))
    if (currentConvId === convId) {
      setMessages([])
      setCurrentConvId(null)
    }
  }

  const handleNewChat = () => {
    createNewConversation()
    inputRef.current?.focus()
  }

  // ── Voice recording ──────────────────────────────────────────
  const startRecording = async () => {
    try {
      const stream   = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      const chunks   = []

      recorder.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data) }
      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(chunks, { type: "audio/webm" })
        const fd   = new FormData()
        fd.append("audio", blob, "recording.webm")
        try {
          const res = await api.post("/voice/transcribe", fd, {
            headers: { "Content-Type": "multipart/form-data" }
          })
          setQuestion(res.data.text || "")
          inputRef.current?.focus()
        } catch {
          // Whisper might not be installed — just clear
          console.warn("Voice transcription unavailable")
        }
      }

      recorder.start()
      setMediaRecorder(recorder)
      setRecording(true)
    } catch {
      alert("Microphone access denied or not available.")
    }
  }

  const stopRecording = () => {
    if (recording) {
      mediaRecorder?.stop()
      setRecording(false)
      console.log("recording stopped");
    }
    
  };

  // ── Copy message text ─────────────────────────────────────────
  const copyMessage = async (index, text) => {
    // Strip markdown and source badges for plain text copy
    const plain = text
      .replace(/\*\*([^*]+)\*\*/g, "$1")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/\[Source[^\]]+\]/g, "")
      .trim()
    try {
      await navigator.clipboard.writeText(plain)
      setFeedback(prev => ({ ...prev, [index]: "copied" }))
      setTimeout(() => setFeedback(prev => {
        const n = { ...prev }; delete n[index]; return n
      }), 2000)
    } catch { /* ignore */ }
  }

  // ── Thumbs feedback ───────────────────────────────────────────
  const setThumb = (index, value) => {
    setFeedback(prev => ({
      ...prev,
      [index]: prev[index] === value ? null : value
    }))
  }

  // ── Send question ─────────────────────────────────────────────
  const sendQuestion = async () => {
    const q = question.trim()
    if (!q || loading) return

    // Create new conversation if none active
    let convId = currentConvId
    if (!convId) {
      convId = Date.now().toString()
      setCurrentConvId(convId)
    }

    setQuestion("")
    setLoading(true)
    inputRef.current?.focus()

    // Reset textarea height
    if (inputRef.current) inputRef.current.style.height = "auto"

    // Add user message
    setMessages(prev => [...prev, {
      role: "user", content: q, streaming: false
    }])
    // Add empty assistant placeholder
    setMessages(prev => [...prev, {
      role: "assistant", content: "", streaming: true
    }])

    try {
      const enriched = q +
        "\n\n[FORMAT: Cite every fact inline as [Source: filename, Page N] right after " +
        "the sentence. If asked for points/steps/list use bullet format with - prefix. " +
        "If numbered, use 1. 2. 3. format. Use **bold** for key terms.]"

      const response = await fetch(`${API_URL}/query/`, {
        method: "POST",
        headers: {
          "Content-Type":  "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ question: enriched, stream: true })
      })

      if (!response.ok) throw new Error(`Server error ${response.status}`)

      const reader  = response.body.getReader()
      const decoder = new TextDecoder()
      let   buffer  = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop() || ""

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue
          const data = line.slice(6)

          if (data === "[DONE]") {
            setMessages(prev => {
              const c = [...prev]
              c[c.length - 1] = { ...c[c.length - 1], streaming: false }
              return c
            })
            break
          }
          if (data.startsWith("[SOURCES]") || data.startsWith("[ERROR]")) continue

          setMessages(prev => {
            const c = [...prev]
            c[c.length - 1] = {
              ...c[c.length - 1],
              content: c[c.length - 1].content + data
            }
            return c
          })
        }
      }
    } catch (err) {
      setMessages(prev => {
        const c = [...prev]
        c[c.length - 1] = {
          role: "assistant",
          content: "Something went wrong. Please check the backend is running on port 8000.",
          streaming: false
        }
        return c
      })
    } finally {
      setLoading(false)
    }
  }

  const clearCurrentChat = async () => {
    try {
      await fetch(`${API_URL}/query/history`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${token}` }
      })
    } catch { /* ignore */ }
    setMessages([])
    setCurrentConvId(null)
    setFeedback({})
  }

  const logout = () => {
    localStorage.removeItem("rag_token")
    localStorage.removeItem("rag_user")
    navigate("/login")
  }

  // ── Render ────────────────────────────────────────────────────
  return (
    <div className="flex h-screen overflow-hidden bg-white">

      {/* ══ DARK SIDEBAR ══════════════════════════════════════ */}
      <aside
        className={`${sidebarOpen ? "w-64" : "w-0"} flex-shrink-0
                    transition-all duration-200 overflow-hidden
                    bg-[#171717] flex flex-col select-none`}
      >
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-4 py-4">
          <Logo size={28} />
          <span className="text-white font-semibold text-[15px] tracking-tight">
            DocMind
          </span>
        </div>

        {/* New Chat button */}
        <div className="px-3 pb-2">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl
                       text-[#ececec] text-sm font-medium
                       hover:bg-white/10 transition-colors border border-white/10"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2.5">
              <path d="M12 5v14M5 12h14"/>
            </svg>
            New conversation
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto px-3 pt-2 space-y-4
                        scrollbar-thin scrollbar-track-transparent
                        scrollbar-thumb-white/10">

          {/* ── Conversation history ── */}
          {conversations.length > 0 && (
            <div>
              {groupByDate(conversations).map(([label, convs]) => (
                <div key={label} className="mb-3">
                  <p className="text-[10px] font-semibold text-white/30
                                uppercase tracking-widest px-2 mb-1">
                    {label}
                  </p>
                  {convs.map(conv => (
                    <button
                      key={conv.id}
                      onClick={() => loadConversation(conv)}
                      className={`w-full text-left flex items-center justify-between
                                  px-2 py-2 rounded-lg text-sm transition-colors group
                                  ${currentConvId === conv.id
                                    ? "bg-white/15 text-white"
                                    : "text-white/60 hover:bg-white/8 hover:text-white/90"
                                  }`}
                    >
                      <span className="truncate text-[13px]">{conv.title}</span>
                      <span
                        onClick={e => deleteConversation(e, conv.id)}
                        className="ml-1 flex-shrink-0 opacity-0 group-hover:opacity-100
                                   text-white/30 hover:text-white/70 transition-all text-[10px]"
                      >
                        ✕
                      </span>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          )}

          {/* ── Documents section ── */}
          <div>
            <p className="text-[10px] font-semibold text-white/30
                          uppercase tracking-widest px-2 mb-1.5">
              Documents
            </p>
            {documents.length === 0 ? (
              <p className="text-[12px] text-white/25 px-2">No documents uploaded</p>
            ) : (
              <div className="space-y-0.5">
                {documents.map(doc => (
                  <div key={doc}
                    className="flex items-center gap-2 px-2 py-1.5 rounded-lg
                               hover:bg-white/8 cursor-default">
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
                      stroke="white" strokeWidth="1.5" opacity="0.4"
                      className="flex-shrink-0">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12
                               a2 2 0 0 0 2-2V8z"/>
                      <polyline points="14,2 14,8 20,8"/>
                    </svg>
                    <span className="text-[12px] text-white/55 truncate">{doc}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Upload button */}
            <button
              onClick={() => setShowUpload(true)}
              className="mt-2 w-full flex items-center gap-2 px-2 py-2 rounded-lg
                         text-[12px] text-white/50 hover:text-white/80
                         hover:bg-white/8 transition-colors"
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="2.5">
                <path d="M12 5v14M5 12h14"/>
              </svg>
              Upload document
            </button>
          </div>
        </div>

        {/* ── User section at bottom ── */}
        <div className="px-3 py-3 border-t border-white/10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-full bg-white/15 flex items-center justify-center">
                <span className="text-[11px] font-bold text-white">
                  {user.username?.[0]?.toUpperCase() || "U"}
                </span>
              </div>
              <span className="text-[13px] text-white/70 truncate max-w-[100px]">
                {user.username || "User"}
              </span>
            </div>
            <button
              onClick={logout}
              title="Sign out"
              className="w-7 h-7 flex items-center justify-center rounded-lg
                         hover:bg-white/10 transition-colors"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                stroke="white" strokeWidth="1.5" opacity="0.5">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                <polyline points="16 17 21 12 16 7"/>
                <line x1="21" y1="12" x2="9" y2="12"/>
              </svg>
            </button>
          </div>
        </div>
      </aside>

      {/* ══ MAIN CHAT AREA ════════════════════════════════════ */}
      <div className="flex-1 flex flex-col min-w-0 bg-white">

        {/* ── Top bar ── */}
        <div className="flex items-center gap-3 px-4 py-3
                        border-b border-gray-100 flex-shrink-0">
          {/* Toggle sidebar */}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
              stroke="#666" strokeWidth="2">
              <line x1="3" y1="6"  x2="21" y2="6"/>
              <line x1="3" y1="12" x2="21" y2="12"/>
              <line x1="3" y1="18" x2="21" y2="18"/>
            </svg>
          </button>

          <span className="text-sm font-semibold text-gray-900">DocMind</span>

          {documents.length > 0 && (
            <span className="text-xs text-gray-400 hidden sm:block">
              {documents.length} document{documents.length !== 1 ? "s" : ""} loaded
            </span>
          )}

          {/* Right side actions */}
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={() => setShowUpload(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium
                         text-gray-600 border border-gray-200 rounded-lg
                         hover:bg-gray-50 hover:border-gray-300 transition-all"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="2.5">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
              Upload
            </button>

            {messages.length > 0 && (
              <button
                onClick={clearCurrentChat}
                className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
                title="Clear chat"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                  stroke="#999" strokeWidth="2">
                  <polyline points="3 6 5 6 21 6"/>
                  <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                  <path d="M10 11v6M14 11v6"/>
                  <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
                </svg>
              </button>
            )}
          </div>
        </div>

        {/* ── Messages area ── */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (

            // ── Empty state ──────────────────────────────────
            <div className="h-full flex flex-col items-center justify-center
                            px-6 text-center">
              <div className="w-14 h-14 rounded-2xl bg-gray-900 flex items-center
                              justify-center mb-5 shadow-lg">
                <svg width="24" height="24" viewBox="0 0 40 40" fill="none">
                  <rect x="8" y="6" width="14" height="18" rx="2" fill="white" opacity="0.9"/>
                  <path d="M17 6l5 5h-5V6z" fill="#111" opacity="0.4"/>
                  <rect x="18" y="20" width="14" height="12" rx="3" fill="white" opacity="0.95"/>
                  <circle cx="23" cy="26" r="1.4" fill="#111"/>
                  <circle cx="27" cy="26" r="1.4" fill="#111"/>
                  <circle cx="31" cy="26" r="1.4" fill="#111"/>
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-gray-900 mb-2">
                How can I help you?
              </h2>
              <p className="text-sm text-gray-500 max-w-xs mb-8">
                Upload a document and ask me anything.
                I'll answer with inline citations showing exactly
                where each fact came from.
              </p>

              {/* Suggestion chips */}
              {documents.length > 0 ? (
                <div className="flex flex-wrap gap-2 justify-center max-w-sm">
                  {[
                    "Summarise this document",
                    "List the key points",
                    "Explain the methodology",
                    "What are the main findings?",
                    "Give me a quick overview"
                  ].map(s => (
                    <button key={s}
                      onClick={() => { setQuestion(s); inputRef.current?.focus() }}
                      className="px-3.5 py-2 bg-gray-50 text-sm text-gray-600
                                 rounded-xl hover:bg-gray-100 border border-gray-200
                                 hover:border-gray-300 transition-all">
                      {s}
                    </button>
                  ))}
                </div>
              ) : (
                <button
                  onClick={() => setShowUpload(true)}
                  className="px-5 py-2.5 bg-gray-900 text-white text-sm font-medium
                             rounded-xl hover:bg-gray-700 transition-colors shadow-sm">
                  Upload a document →
                </button>
              )}
            </div>

          ) : (

            // ── Message list ─────────────────────────────────
            <div className="max-w-3xl mx-auto w-full px-4 py-8 space-y-7">
              {messages.map((msg, i) => (
                <div key={i}
                  className={`flex gap-3 ${msg.role === "user" ? "justify-end" : ""}`}
                >
                  {/* Assistant avatar */}
                  {msg.role === "assistant" && (
                    <div className="w-8 h-8 rounded-full bg-gray-900 flex-shrink-0
                                    mt-0.5 flex items-center justify-center shadow-sm">
                      <svg width="14" height="14" viewBox="0 0 40 40" fill="none">
                        <rect x="8" y="6" width="11" height="14" rx="2"
                          fill="white" opacity="0.9"/>
                        <rect x="14" y="16" width="11" height="9" rx="2.5"
                          fill="white" opacity="0.9"/>
                        <circle cx="17" cy="20.5" r="1" fill="#111"/>
                        <circle cx="20" cy="20.5" r="1" fill="#111"/>
                        <circle cx="23" cy="20.5" r="1" fill="#111"/>
                      </svg>
                    </div>
                  )}

                  <div className={`max-w-[84%] flex flex-col
                                   ${msg.role === "user" ? "items-end" : "items-start"}`}>

                    {/* Message bubble / text */}
                    {msg.role === "user" ? (
                      <div className="bg-gray-100 rounded-2xl rounded-tr-sm
                                      px-4 py-3">
                        <p className="text-sm text-gray-900 leading-relaxed">
                          {msg.content}
                        </p>
                      </div>
                    ) : (
                      <div className="pt-0.5 select-text w-full">
                        {msg.streaming && msg.content === "" ? (
                          // Thinking dots
                          <div className="flex gap-1 py-3 pl-1">
                            {[0, 1, 2].map(j => (
                              <div key={j}
                                className="w-2 h-2 rounded-full bg-gray-300 animate-bounce"
                                style={{ animationDelay: `${j * 120}ms` }}
                              />
                            ))}
                          </div>
                        ) : (
                          <div>
                            {renderMarkdown(msg.content)}
                            {/* Blinking cursor while streaming */}
                            {msg.streaming && (
                              <span className="inline-block w-0.5 h-4 bg-gray-400
                                               ml-0.5 animate-pulse"/>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {/* ── Action buttons (assistant only, after streaming) ── */}
                    {msg.role === "assistant" && !msg.streaming && msg.content && (
                      <div className="flex items-center gap-1 mt-2 ml-1">

                        {/* Copy */}
                        <button
                          onClick={() => copyMessage(i, msg.content)}
                          title="Copy"
                          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg
                                      text-xs transition-all
                                      ${feedback[i] === "copied"
                                        ? "bg-green-50 text-green-600 border border-green-200"
                                        : "text-gray-400 hover:text-gray-600 hover:bg-gray-100"
                                      }`}
                        >
                          {feedback[i] === "copied" ? (
                            <>
                              <svg width="11" height="11" viewBox="0 0 24 24"
                                fill="none" stroke="currentColor" strokeWidth="2.5">
                                <path d="M20 6L9 17l-5-5"/>
                              </svg>
                              Copied
                            </>
                          ) : (
                            <>
                              <svg width="11" height="11" viewBox="0 0 24 24"
                                fill="none" stroke="currentColor" strokeWidth="2">
                                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9
                                         a2 2 0 0 1 2 2v1"/>
                              </svg>
                              Copy
                            </>
                          )}
                        </button>

                        {/* Separator */}
                        <div className="w-px h-3 bg-gray-200"/>

                        {/* Thumbs Up */}
                        <button
                          onClick={() => setThumb(i, "up")}
                          title="Good response"
                          className={`p-1.5 rounded-lg transition-all
                                      ${feedback[i] === "up"
                                        ? "text-green-600 bg-green-50"
                                        : "text-gray-400 hover:text-gray-600 hover:bg-gray-100"
                                      }`}
                        >
                          <svg width="13" height="13" viewBox="0 0 24 24"
                            fill={feedback[i] === "up" ? "currentColor" : "none"}
                            stroke="currentColor" strokeWidth="2">
                            <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0
                                     2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z"/>
                            <path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/>
                          </svg>
                        </button>

                        {/* Thumbs Down */}
                        <button
                          onClick={() => setThumb(i, "down")}
                          title="Bad response"
                          className={`p-1.5 rounded-lg transition-all
                                      ${feedback[i] === "down"
                                        ? "text-red-500 bg-red-50"
                                        : "text-gray-400 hover:text-gray-600 hover:bg-gray-100"
                                      }`}
                        >
                          <svg width="13" height="13" viewBox="0 0 24 24"
                            fill={feedback[i] === "down" ? "currentColor" : "none"}
                            stroke="currentColor" strokeWidth="2">
                            <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0
                                     -2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z"/>
                            <path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31
                                     0 0 1-2.33 2H17"/>
                          </svg>
                        </button>
                      </div>
                    )}
                  </div>

                  {/* User avatar */}
                  {msg.role === "user" && (
                    <div className="w-8 h-8 rounded-full bg-gray-200 flex-shrink-0
                                    mt-0.5 flex items-center justify-center">
                      <span className="text-xs font-bold text-gray-600">
                        {user.username?.[0]?.toUpperCase() || "U"}
                      </span>
                    </div>
                  )}
                </div>
              ))}
              <div ref={bottomRef}/>
            </div>
          )}
        </div>

        {/* ── Input area ── */}
        <div className="flex-shrink-0 px-4 pb-5 pt-3 border-t border-gray-100">
          <div className="max-w-3xl mx-auto">
            <div className={`flex items-end gap-2 bg-white border rounded-2xl
                             px-3 py-2.5 shadow-sm transition-all duration-150
                             ${loading
                               ? "border-gray-200"
                               : "border-gray-300 focus-within:border-gray-400 focus-within:shadow-md"
                             }`}>

              {/* Voice button */}
              <button
                onMouseDown={startRecording}
                onMouseUp={stopRecording}
                onTouchStart={startRecording}
                onTouchEnd={stopRecording}
                title={recording ? "Release to stop" : "Hold to record"}
                className={`flex-shrink-0 w-8 h-8 rounded-xl flex items-center
                             justify-center transition-all duration-150 mb-0.5
                             ${recording
                               ? "bg-red-500 text-white scale-110 shadow-md"
                               : "text-gray-400 hover:text-gray-600 hover:bg-gray-100"
                             }`}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" strokeWidth="2">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                  <line x1="12" y1="19" x2="12" y2="23"/>
                  <line x1="8" y1="23" x2="16" y2="23"/>
                </svg>
              </button>

              {/* Text input */}
              <textarea
                ref={inputRef}
                value={question}
                onChange={e => {
                  setQuestion(e.target.value)
                  e.target.style.height = "auto"
                  e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px"
                }}
                onKeyDown={e => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault()
                    sendQuestion()
                  }
                }}
                placeholder={recording ? "🔴 Recording... release to stop" : "Ask anything about your documents..."}
                disabled={loading}
                rows={1}
                className="flex-1 resize-none text-sm text-gray-900
                           placeholder-gray-400 outline-none bg-transparent
                           leading-relaxed max-h-40 disabled:opacity-50 py-1"
                style={{ minHeight: "24px" }}
              />

              {/* Send button */}
              <button
                onClick={sendQuestion}
                disabled={loading || !question.trim()}
                className={`flex-shrink-0 w-8 h-8 rounded-xl flex items-center
                             justify-center transition-all duration-150 mb-0.5
                             ${question.trim() && !loading
                               ? "bg-gray-900 hover:bg-gray-700 cursor-pointer shadow-sm"
                               : "bg-gray-200 cursor-not-allowed"
                             }`}
              >
                {loading ? (
                  <div className="w-3.5 h-3.5 border-2 border-white
                                  border-t-transparent rounded-full animate-spin"/>
                ) : (
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
                    stroke={question.trim() ? "white" : "#aaa"} strokeWidth="2.5">
                    <line x1="22" y1="2" x2="11" y2="13"/>
                    <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                  </svg>
                )}
              </button>
            </div>

            <p className="text-center text-[11px] text-gray-400 mt-2">
              Enter to send · Shift+Enter for new line ·
              Hold mic to record · Citations appear inline
            </p>
          </div>
        </div>
      </div>

      {/* ══ UPLOAD MODAL ══════════════════════════════════════ */}
      {showUpload && (
        <UploadModal
          onClose={() => setShowUpload(false)}
          onUploaded={() => {
            loadDocuments()
            setShowUpload(false)
          }}
        />
      )}
    </div>
  )
}
