import React, { Suspense, lazy, useEffect } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import RootErrorBoundary from "./components/RootErrorBoundary";
import { ThemeProvider } from "./lib/theme";
import { trackPageView } from "./lib/analytics";
import "./index.css";

function Analytics() {
  const loc = useLocation();
  useEffect(() => { trackPageView(loc.pathname + loc.search); }, [loc.pathname, loc.search]);
  return null;
}

const App = lazy(() => import("./App"));
const Landing = lazy(() => import("./pages/Landing"));
const About = lazy(() => import("./pages/About"));
const Admin = lazy(() => import("./pages/Admin"));

function LoadingFallback() {
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-[#020B1E]">
      <div className="flex flex-col items-center gap-3">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-cyan-400/30 border-t-cyan-400" />
        <p className="font-mono text-xs tracking-widest text-white/60">جينيو يحضّر روحه...</p>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <RootErrorBoundary>
      <ThemeProvider>
        <BrowserRouter>
          <Analytics />
          <Suspense fallback={<LoadingFallback />}>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/app" element={<App />} />
              <Route path="/about" element={<About />} />
              <Route path="/genio/admin" element={<Admin />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </ThemeProvider>
    </RootErrorBoundary>
  </React.StrictMode>,
);
