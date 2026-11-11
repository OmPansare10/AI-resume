import { useEffect, useRef } from "react";

/**
 * Safely coerces an arbitrary field (array, newline string, or object) into a renderable array.
 */
function toSafeArray(val) {
  if (!val) return [];
  if (Array.isArray(val)) {
    return val
      .map((item) => (typeof item === "string" ? item.replace(/[\r\n]+/g, " ").trim() : item))
      .filter((item) => item !== null && item !== undefined && item !== "");
  }
  if (typeof val === "string") {
    return val.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
  }
  if (typeof val === "object") {
    try {
      return Object.values(val)
        .flat()
        .map((item) => (typeof item === "string" ? item.replace(/[\r\n]+/g, " ").trim() : item))
        .filter((item) => item !== null && item !== undefined && item !== "");
    } catch {
      return [];
    }
  }
  return [];
}

/**
 * Reusable AI Resume Copilot Chat panel supporting text prompts, quick-suggestion chips,
 * drag-and-drop / multi-image screenshot upload, and Ctrl+V clipboard paste.
 */
export function ResumeCopilotChat({
  title = "AI Resume Copilot Chat",
  subtitle = "Type your problem, upload, or paste (Ctrl+V) any screenshot / photo like ChatGPT — the AI extracts the details and updates the resume below in real time!",
  statusLabel = "Live Resume Synced",
  messages = [],
  input = "",
  onInputChange,
  attachedImages = [],
  onClearImages,
  onAttachImages,
  onRemoveImage,
  onPaste,
  isDragging = false,
  onDragStateChange,
  isSubmitting = false,
  suggestions = [],
  onSubmit,
  onZoomImage,
  placeholder = "Type anything to change or paste screenshot (Ctrl+V) like ChatGPT (e.g. 'Add this certificate', 'Change projects to match screenshot', 'Use as photo')...",
  submitLabel = "Update Resume",
  typingText = "Analyzing your problem & screenshot, extracting details, and updating resume in real time..."
}) {
  const streamRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (streamRef.current && messages.length > 1) {
      streamRef.current.scrollTop = streamRef.current.scrollHeight;
    }
  }, [messages, isSubmitting]);

  return (
    <div className="chatbox-card chatbox-above-resume" onPaste={onPaste}>
      <div className="chatbox-header">
        <div className="chatbox-header-left">
          <span className="chatbox-icon">💬</span>
          <div>
            <h3 className="chatbox-title">{title}</h3>
            <p className="chatbox-subtitle">{subtitle}</p>
          </div>
        </div>
        <div className="chatbox-header-right">
          <span className="chat-status-pill live">
            <span className="pill-dot"></span> {statusLabel}
          </span>
        </div>
      </div>

      {/* Chat Messages Stream */}
      <div className="chatbox-stream" ref={streamRef}>
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`chat-message ${
              msg.sender === "user" ? "user-msg" : "ai-msg"
            } ${msg.isNotice ? "notice-msg" : ""} ${
              msg.isError ? "error-msg" : ""
            }`}
          >
            <div className="msg-avatar">
              {msg.sender === "user" ? "👤" : "✨"}
            </div>
            <div className="msg-bubble">
              <div className="msg-header">
                <span className="msg-sender-name">
                  {msg.sender === "user" ? "You" : "Resume Copilot"}
                </span>
                <span className="msg-time">{msg.time}</span>
              </div>

              {/* Display attached image thumbnail(s) in user message */}
              {((msg.images && msg.images.length > 0) || msg.image) && (
                <div className="msg-images-gallery">
                  {(msg.images || [msg.image]).map((imgSrc, imgIdx) => (
                    <div
                      key={imgIdx}
                      className="msg-image-wrap"
                      onClick={() => onZoomImage?.(imgSrc)}
                      title="Click to view full image"
                    >
                      <img
                        src={imgSrc}
                        alt={`Attached photo ${imgIdx + 1}`}
                        className="msg-attached-img"
                      />
                      <div className="msg-image-meta">
                        <span>📷 Photo {imgIdx + 1}</span>
                        <span className="zoom-hint">🔍 Zoom</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <p className="msg-text">{msg.text}</p>

              {/* Extracted OCR Information Note */}
              {msg.extractedText && (
                <div className="msg-extracted-note">
                  <span className="ocr-badge">🔍 Extracted from Image:</span>
                  <p className="ocr-snippet">
                    {msg.extractedText.slice(0, 180)}
                    {msg.extractedText.length > 180 ? "..." : ""}
                  </p>
                </div>
              )}

              {toSafeArray(msg.changes).length > 0 && (
                <div className="msg-changes-list">
                  <strong>Modifications Applied:</strong>
                  <ul>
                    {toSafeArray(msg.changes).map((ch, cIdx) => (
                      <li key={cIdx}>✓ {ch}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        ))}

        {isSubmitting && (
          <div className="chat-message ai-msg typing-msg">
            <div className="msg-avatar">✨</div>
            <div className="msg-bubble">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
              <span className="typing-text">{typingText}</span>
            </div>
          </div>
        )}
      </div>

      {/* Quick Prompt Suggestion Chips */}
      {suggestions.length > 0 && (
        <div className="chatbox-suggestions">
          <span className="suggestions-label">Suggestions:</span>
          {suggestions.map((prompt, idx) => (
            <button
              key={idx}
              type="button"
              className="chat-chip"
              onClick={() => onSubmit(prompt)}
              disabled={isSubmitting}
            >
              + {prompt}
            </button>
          ))}
        </div>
      )}

      {/* Attachment Preview Strip (supports multiple attached photos) */}
      {attachedImages.length > 0 && (
        <div className="chatbox-attachments-strip">
          <div className="attachments-header-row">
            <span className="attachments-count-badge">
              📷 {attachedImages.length} Photo{attachedImages.length > 1 ? "s" : ""} Ready to Send
            </span>
            <button
              type="button"
              className="attachments-clear-all"
              onClick={onClearImages}
            >
              Clear all
            </button>
          </div>
          <div className="attachments-cards-row">
            {attachedImages.map((att) => (
              <div key={att.id} className="chatbox-attachment-card">
                <div
                  className="attachment-thumb-wrap"
                  onClick={() => onZoomImage?.(att.dataUrl)}
                  title="Click to zoom image"
                >
                  <img
                    src={att.dataUrl}
                    alt={att.name}
                    className="attachment-thumb"
                  />
                  <span className="attachment-zoom-hint">🔍</span>
                </div>
                <div className="attachment-info">
                  <span className="attachment-name" title={att.name}>
                    {att.name}
                  </span>
                  <span className="attachment-size">{att.size}</span>
                </div>
                <button
                  type="button"
                  className="attachment-remove-btn"
                  onClick={() => onRemoveImage(att.id)}
                  title="Remove attached image"
                >
                  ✕
                </button>
              </div>
            ))}
            <button
              type="button"
              className="attachment-add-more-btn"
              onClick={() => fileInputRef.current?.click()}
              title="Add another photo / screenshot"
            >
              <span>+ Add Photo</span>
            </button>
          </div>
        </div>
      )}

      {/* Chat Input Bar (ChatGPT style with upload, Ctrl+V, drag & drop) */}
      <form
        className={`chatbox-input-row ${isDragging ? "dragging-over" : ""}`}
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
        onDragOver={(e) => {
          e.preventDefault();
          onDragStateChange?.(true);
        }}
        onDragLeave={() => onDragStateChange?.(false)}
        onDrop={(e) => {
          e.preventDefault();
          onDragStateChange?.(false);
          if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            onAttachImages(e.dataTransfer.files);
          }
        }}
      >
        {/* Hidden file input for uploading images (supports multiple) */}
        <input
          type="file"
          ref={fileInputRef}
          style={{ display: "none" }}
          accept="image/*"
          multiple
          onChange={(e) => {
            if (e.target.files && e.target.files.length > 0) {
              onAttachImages(e.target.files);
              e.target.value = "";
            }
          }}
        />
        {/* Attach File Button */}
        <button
          type="button"
          className={`chat-attach-btn ${attachedImages.length > 0 ? "has-attachment" : ""}`}
          onClick={() => fileInputRef.current?.click()}
          title="Upload images / screenshots (supports multiple, or paste with Ctrl+V)"
          disabled={isSubmitting}
        >
          <span className="attach-icon">📎</span>
          <span className="attach-btn-label">
            {attachedImages.length > 0 ? `Images (${attachedImages.length})` : "Images"}
          </span>
        </button>

        <textarea
          className="chatbox-input chatbox-textarea"
          rows={1}
          placeholder={placeholder}
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSubmit();
            }
          }}
          disabled={isSubmitting}
        />

        <button
          type="submit"
          className="chatbox-send-btn"
          disabled={isSubmitting || (!input.trim() && attachedImages.length === 0)}
        >
          {isSubmitting ? (
            <span className="chat-btn-spinner" />
          ) : (
            <>
              <span>{submitLabel}</span>
              <span className="send-arrow">➤</span>
            </>
          )}
        </button>
      </form>
    </div>
  );
}
