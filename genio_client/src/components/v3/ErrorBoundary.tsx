import React from "react";

interface Props { children: React.ReactNode; fallback?: React.ReactNode; name?: string }
interface State { hasError: boolean; error?: Error }

export default class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error(`[v3 ErrorBoundary ${this.props.name ?? ""}]`, error, info.componentStack);
  }
  render() {
    if (this.state.hasError) {
      return (this.props.fallback as React.ReactNode) ?? (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-[#020B1E]/60 p-4 text-center font-mono text-[10px] text-amber-300/70">
          {this.props.name ?? "Canvas"} crashed — fallback active.
        </div>
      );
    }
    return this.props.children;
  }
}
