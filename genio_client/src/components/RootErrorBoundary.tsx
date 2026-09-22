import React from "react";

interface Props { children: React.ReactNode }
interface State { hasError: boolean; error?: Error }

/**
 * Root-level safety net. A local ErrorBoundary (see components/v3/ErrorBoundary.tsx)
 * only protects the component subtree it wraps — an error escaping every local
 * boundary (or one thrown outside React's render cycle, e.g. a rejected async
 * texture loader) unmounts the whole app in React 18+, leaving a silent black
 * screen (reproduced empirically: WebGL Environment HDR fetch failure → #root
 * left completely empty). This boundary is the last line of defense: whatever
 * escapes everything else still lands on a real, visible, actionable screen
 * instead of nothing.
 */
export default class RootErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("[Genio RootErrorBoundary] uncaught error", error, info.componentStack);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            width: "100vw",
            height: "100vh",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "16px",
            background: "#020B1E",
            color: "#e2f6ff",
            fontFamily: "monospace",
            padding: "24px",
            textAlign: "center",
          }}
        >
          <div style={{ fontSize: "40px" }}>⚠️</div>
          <div style={{ fontSize: "16px", fontWeight: 700 }}>Genio a rencontré une erreur inattendue</div>
          <div style={{ fontSize: "12px", opacity: 0.6, maxWidth: "480px" }}>
            {this.state.error?.message ?? "Erreur inconnue"}
          </div>
          <button
            onClick={() => window.location.reload()}
            style={{
              marginTop: "8px",
              padding: "10px 20px",
              borderRadius: "10px",
              border: "1px solid rgba(0,229,255,0.4)",
              background: "rgba(0,229,255,0.12)",
              color: "#00E5FF",
              cursor: "pointer",
              fontFamily: "monospace",
              fontSize: "13px",
            }}
          >
            Recharger
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
