import React from "react";
import { getLang, t } from "../../lib/lang";

interface Props {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  name?: string;
  /**
   * bare: render null on error. REQUIRED when this boundary is placed
   * inside an R3F <Canvas>: a DOM fallback <div> inside the Canvas
   * reconciler throws "Div is not part of the THREE namespace" and
   * escalates a contained visual failure into a full-screen crash.
   */
  bare?: boolean;
  /** Called once when an error is caught (e.g. persist a safe fallback mode). */
  onCrash?: (error: Error) => void;
}
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
    try {
      this.props.onCrash?.(error);
    } catch {
      /* observer must never break rendering */
    }
  }
  render() {
    if (this.state.hasError) {
      if (this.props.fallback !== undefined) return this.props.fallback;
      if (this.props.bare) return null;
      return (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-[#020B1E]/60 p-4 text-center font-mono text-[10px] text-amber-300/70">
          {t(getLang(), "boundary.crash")}
        </div>
      );
    }
    return this.props.children;
  }
}
