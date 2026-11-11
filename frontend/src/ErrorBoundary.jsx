import React from "react";

export class ResumeSectionErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ResumeSectionErrorBoundary caught an error:", error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: "36px 24px",
          textAlign: "center",
          backgroundColor: "#fef2f2",
          border: "1px dashed #f87171",
          borderRadius: "12px",
          margin: "16px auto",
          maxWidth: "600px",
          color: "#991b1b",
          fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif"
        }}>
          <div style={{ fontSize: "32px", marginBottom: "8px" }}>⚠️</div>
          <h3 style={{ fontSize: "17px", fontWeight: "700", marginBottom: "6px", color: "#991b1b" }}>
            Resume Preview Refreshed
          </h3>
          <p style={{ fontSize: "13px", color: "#b91c1c", marginBottom: "16px", lineHeight: "1.5" }}>
            A layout calculation or formatting update encountered a minor issue. Your data is safe.
          </p>
          <div style={{ display: "flex", gap: "10px", justifyContent: "center" }}>
            <button
              type="button"
              onClick={this.handleRetry}
              style={{
                backgroundColor: "#dc2626",
                color: "#ffffff",
                border: "none",
                padding: "8px 18px",
                borderRadius: "6px",
                fontSize: "13px",
                fontWeight: "600",
                cursor: "pointer"
              }}
            >
              🔄 Refresh Preview
            </button>
          </div>
          {this.state.error && (
            <details style={{ marginTop: "12px", textAlign: "left", fontSize: "11px", color: "#7f1d1d" }}>
              <summary style={{ cursor: "pointer", fontWeight: "600" }}>Error details</summary>
              <pre style={{ marginTop: "4px", whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
                {this.state.error.toString()}
              </pre>
            </details>
          )}
        </div>
      );
    }
    return this.props.children;
  }
}

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
    this.setState({ errorInfo });
  }

  handleReload = () => {
    try {
      // Clear potentially corrupt in-memory or session states that trigger repeated crashes
      sessionStorage.removeItem("ai_resume_preview_cache");
    } catch {
      // ignore
    }
    window.location.reload();
  };

  handleReset = () => {
    try {
      sessionStorage.clear();
      localStorage.clear();
    } catch {
      // Ignore storage errors
    }
    window.location.href = window.location.pathname;
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#f8fafc",
          fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
          padding: "24px",
          color: "#0f172a"
        }}>
          <div style={{
            maxWidth: "560px",
            width: "100%",
            backgroundColor: "#ffffff",
            borderRadius: "16px",
            boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)",
            border: "1px solid #e2e8f0",
            padding: "32px",
            textAlign: "center"
          }}>
            <div style={{
              width: "64px",
              height: "64px",
              borderRadius: "50%",
              backgroundColor: "#fee2e2",
              color: "#dc2626",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "32px",
              margin: "0 auto 20px auto"
            }}>
              ⚠️
            </div>

            <h2 style={{ fontSize: "22px", fontWeight: "700", marginBottom: "8px", color: "#0f172a" }}>
              Something went wrong in the preview
            </h2>

            <p style={{ fontSize: "14px", color: "#64748b", lineHeight: "1.6", marginBottom: "24px" }}>
              The application encountered a render issue, but your session can be easily restored. Click below to reload or reset back to the home screen.
            </p>

            <div style={{ display: "flex", gap: "12px", justifyContent: "center", flexWrap: "wrap", marginBottom: "24px" }}>
              <button
                type="button"
                onClick={this.handleReload}
                style={{
                  backgroundColor: "#2563eb",
                  color: "#ffffff",
                  border: "none",
                  padding: "10px 20px",
                  borderRadius: "8px",
                  fontSize: "14px",
                  fontWeight: "600",
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px"
                }}
              >
                <span>🔄</span> Reload Page
              </button>

              <button
                type="button"
                onClick={this.handleReset}
                style={{
                  backgroundColor: "#f1f5f9",
                  color: "#334155",
                  border: "1px solid #cbd5e1",
                  padding: "10px 20px",
                  borderRadius: "8px",
                  fontSize: "14px",
                  fontWeight: "600",
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px"
                }}
              >
                <span>🏠</span> Reset to Home
              </button>
            </div>

            {this.state.error && (
              <details style={{ textAlign: "left", backgroundColor: "#f8fafc", borderRadius: "8px", padding: "12px", border: "1px solid #e2e8f0" }}>
                <summary style={{ cursor: "pointer", fontSize: "12px", fontWeight: "600", color: "#64748b" }}>
                  View technical details
                </summary>
                <pre style={{
                  fontSize: "11px",
                  color: "#dc2626",
                  marginTop: "8px",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-all",
                  fontFamily: "monospace"
                }}>
                  {this.state.error.toString()}
                </pre>
              </details>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
