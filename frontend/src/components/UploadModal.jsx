// src/components/UploadModal.jsx
// Claude-style upload — simple + button to pick file
// No drag and drop zone

import { useState, useEffect, useRef } from "react"
import api from "../api/axios"

export default function UploadModal({ onClose, onUploaded }) {
  const [documents, setDocuments] = useState([])
  const [uploading, setUploading] = useState(false)
  const [progress,  setProgress]  = useState(0)
  const [message,   setMessage]   = useState("")
  const [error,     setError]     = useState("")

  const inputRef   = useRef(null)
  const overlayRef = useRef(null)

  useEffect(() => {
    loadDocuments()
    document.body.style.overflow = "hidden"
    return () => { document.body.style.overflow = "" }
  }, [])

  // Close on Escape
  useEffect(() => {
    const handler = e => { if (e.key === "Escape") onClose() }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [onClose])

  const loadDocuments = async () => {
    try {
      const res = await api.get("/upload/list")
      setDocuments(res.data.documents || [])
    } catch { setDocuments([]) }
  }

  const uploadFile = async (file) => {
    const allowed = [
      "application/pdf",
      "text/plain",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "image/jpg",
      "image/jpeg",
      "image/png"
    ]
    if (!allowed.includes(file.type)) {
      setError("Only PDF, DOCX , JPG ,JPEG ,PNG and TXT files are supported")
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("Maximum file size is 10 MB")
      return
    }

    setUploading(true)
    setError("")
    setMessage("")
    setProgress(0)

    const fd = new FormData()
    fd.append("file", file)

    try {
      const res = await api.post("/upload/", fd, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: e => setProgress(Math.round((e.loaded / e.total) * 100))
      })
      setMessage(`${res.data.pages} pages · ${res.data.chunks} chunks indexed`)
      await loadDocuments()
      if (onUploaded) onUploaded()
    } catch (err) {
      setError(err.response?.data?.detail || "Upload failed. Please try again.")
    } finally {
      setUploading(false)
      setProgress(0)
    }
  }

  const handleFileChange = e => {
    const file = e.target.files[0]
    if (file) uploadFile(file)
    // Reset input so same file can be re-selected
    e.target.value = ""
  }


  const deleteDoc = async (filename) => {
    try {
        // This calls the backend route we just wrote
        await api.delete(`/upload/${encodeURIComponent(filename)}`);
        
        // Refresh the list after deleting
        loadDocuments(); 
        alert("vectors cleared from cloud!");
    } catch (err) {
        console.error("Delete failed", err);
    }
};

  // Click outside overlay to close
  const handleOverlayClick = e => {
    if (e.target === overlayRef.current) onClose()
  }

  // File icon based on extension
  const fileIcon = (name) => {
    const ext = name.split(".").pop().toLowerCase()
    const colors = { pdf: "#ef4444", docx: "#3b82f6", txt: "#6b7280" }
    const color  = colors[ext] || "#6b7280"
    return (
      <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
        style={{ background: color + "18", border: `1px solid ${color}30` }}>
        <span className="text-[9px] font-bold uppercase" style={{ color }}>
          {ext}
        </span>
      </div>
    )
  }

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-50 flex items-center justify-center
                 bg-black/50 backdrop-blur-sm"
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4
                      overflow-hidden animate-in fade-in duration-150">

        {/* ── Header ── */}
        <div className="flex items-center justify-between px-6 py-4
                        border-b border-gray-100">
          <div>
            <h2 className="text-base font-semibold text-gray-900">Documents</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              PDF, DOCX or TXT · max 10 MB
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg
                       hover:bg-gray-100 transition-colors text-gray-400
                       hover:text-gray-700"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2.5">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        {/* ── Body ── */}
        <div className="px-6 py-5">

          {/* ── Claude-style + upload button ── */}
          <button
            onClick={() => inputRef.current?.click()}
            disabled={uploading}
            className="w-full flex items-center gap-3 px-4 py-3.5
                       border border-dashed border-gray-300 rounded-xl
                       hover:border-gray-400 hover:bg-gray-50
                       disabled:opacity-50 disabled:cursor-not-allowed
                       transition-all duration-150 group"
          >
            {/* Plus circle icon */}
            <div className="w-9 h-9 rounded-full bg-gray-100 group-hover:bg-gray-200
                            flex items-center justify-center flex-shrink-0
                            transition-colors">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
                stroke="#555" strokeWidth="2.5">
                <line x1="12" y1="5" x2="12" y2="19"/>
                <line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
            </div>

            <div className="text-left">
              <p className="text-sm font-medium text-gray-700">
                Add document
              </p>
              <p className="text-xs text-gray-400 mt-0.5">
                Click to select a file from your computer
              </p>
            </div>
          </button>

          {/* Hidden file input */}
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.docx,.txt,.jpg,.jpeg,.png"
            className="hidden"
            onChange={handleFileChange}
          />

          {/* ── Upload progress ── */}
          {uploading && (
            <div className="mt-4 px-4 py-3 bg-gray-50 rounded-xl border
                            border-gray-200">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-gray-400
                                  border-t-transparent rounded-full animate-spin"/>
                  <span className="text-xs text-gray-600 font-medium">
                    Processing document...
                  </span>
                </div>
                <span className="text-xs text-gray-500 font-medium">
                  {progress}%
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-1">
                <div
                  className="bg-gray-900 h-1 rounded-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}

          {/* ── Success message ── */}
          {message && (
            <div className="mt-3 flex items-center gap-2.5 px-4 py-2.5
                            rounded-xl bg-green-50 border border-green-200">
              <div className="w-5 h-5 rounded-full bg-green-500 flex items-center
                              justify-center flex-shrink-0">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none"
                  stroke="white" strokeWidth="3">
                  <path d="M20 6L9 17l-5-5"/>
                </svg>
              </div>
              <p className="text-sm text-green-700 font-medium">
                Uploaded — {message}
              </p>
            </div>
          )}

          {/* ── Error message ── */}
          {error && (
            <div className="mt-3 flex items-center gap-2.5 px-4 py-2.5
                            rounded-xl bg-red-50 border border-red-200">
              <div className="w-5 h-5 rounded-full bg-red-500 flex items-center
                              justify-center flex-shrink-0">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none"
                  stroke="white" strokeWidth="3">
                  <line x1="18" y1="6" x2="6" y2="18"/>
                  <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </div>
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          {/* ── Document list ── */}
          <div className="mt-5">
            {documents.length > 0 ? (
              <>
                <p className="text-xs font-semibold text-gray-400 uppercase
                               tracking-wider mb-2.5">
                  {documents.length} document{documents.length !== 1 ? "s" : ""}
                </p>
                <div className="space-y-1.5 max-h-52 overflow-y-auto pr-0.5
                                scrollbar-thin scrollbar-track-transparent
                                scrollbar-thumb-gray-200">
                  {documents.map(filename => (
                    <div key={filename}
                      className="flex items-center justify-between px-3 py-2.5
                                 rounded-xl hover:bg-gray-50 border border-transparent
                                 hover:border-gray-200 transition-all group">
                      <div className="flex items-center gap-3 min-w-0">
                        {fileIcon(filename)}
                        <span className="text-sm text-gray-700 truncate">
                          {filename}
                        </span>
                      </div>
                      <button
                        onClick={() => deleteDoc(filename)}
                        className="ml-3 flex-shrink-0 w-7 h-7 rounded-lg
                                   flex items-center justify-center
                                   text-gray-300 hover:text-red-500
                                   hover:bg-red-50 transition-all
                                   opacity-0 group-hover:opacity-100"
                      >
                        <svg width="13" height="13" viewBox="0 0 24 24"
                          fill="none" stroke="currentColor" strokeWidth="2.5">
                          <polyline points="3 6 5 6 21 6"/>
                          <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0
                                   1-2-2L5 6"/>
                          <path d="M10 11v6M14 11v6"/>
                          <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              !uploading && (
                <div className="text-center py-6">
                  <div className="w-10 h-10 rounded-full bg-gray-100
                                  flex items-center justify-center mx-auto mb-2">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
                      stroke="#bbb" strokeWidth="1.5">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12
                               a2 2 0 0 0 2-2V8z"/>
                      <polyline points="14,2 14,8 20,8"/>
                    </svg>
                  </div>
                  <p className="text-sm text-gray-400">No documents yet</p>
                  <p className="text-xs text-gray-300 mt-0.5">
                    Click "Add document" above to get started
                  </p>
                </div>
              )
            )}
          </div>
        </div>

        {/* ── Footer ── */}
        <div className="px-6 py-4 border-t border-gray-100 flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 bg-gray-900 text-white text-sm font-medium
                       rounded-xl hover:bg-gray-700 transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  )
}
