import { memo, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import IslamicPatterns from "../background/IslamicPatterns";
import HologramMascot from "../mascot/HologramMascot";
import SystemMetrics from "../hud/SystemMetrics";
import BrainActivity from "../hud/BrainActivity";
import MatrixTaskScreen from "../hud/MatrixTaskScreen";
import type { AgentStatus, ChatEvent, TelemetrySnapshot } from "../../lib/types";

interface Props {
  status: AgentStatus["kind"] | string;
  audioLevel?: number;
  chat: ChatEvent[];
  telemetry?: TelemetrySnapshot | null;
  tasks: string[];
  expanded?: boolean;
  onToggleExpand?: () => void;
  children?: React.ReactNode; // ChatBubble list + VoiceInput
}

/**
 * GenioShell — Islamic Cyberpunk Anime HUD
 * z-order: patterns(0) → matrix(8) → mascot(10) → chat(15) → metrics/brain(20)
 * isMascotSmall = answering || expanded
 * Keeps ChatBubble + VoiceInput (Darija STT/TTS) via children
 */
const GenioShell = memo(function GenioShell({
  status,
  audioLevel = 0,
  chat,
  telemetry,
  tasks,
  expanded = false,
  onToggleExpand,
  children,
}: Props) {
  const isMascotSmall = useMemo(() => status === "answering" || expanded, [status, expanded]);

  return (
    <div className="relative flex h-screen w-full flex-col overflow-hidden bg-[#020B1E]">
      {/* z-0 IslamicPatterns */}
      <div className="absolute inset-0 z-0">
        <IslamicPatterns />
      </div>

      {/* z-8 MatrixTaskScreen */}
      <div className="absolute inset-x-3 top-3 z-[8] md:inset-x-6 md:top-4">
        <MatrixTaskScreen tasks={tasks} expanded={expanded} onToggle={onToggleExpand} />
      </div>

      {/* z-10 HologramMascot */}
      <div
        className={`absolute z-10 flex transition-all duration-500 ${isMascotSmall ? "right-3 top-3 md:right-6 md:top-4" : "left-1/2 top-[22%] -translate-x-1/2 md:top-[28%]"}`}
        style={{ pointerEvents: isMascotSmall ? "auto" : "none" }}
      >
        <HologramMascot status={status} audioLevel={audioLevel} isMinimized={isMascotSmall} />
      </div>

      {/* z-15 Chat (ChatBubble + VoiceInput) */}
      <div className="relative z-[15] flex min-h-0 flex-1 flex-col pt-[36vh] md:pt-[38vh]">
        <div className="flex min-h-0 flex-1 flex-col">
          {/* Answer screen — expanded when answering */}
          <AnimatePresence>
            {status === "answering" && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 12 }}
                className="mx-3 mb-3 rounded-2xl border border-emerald-400/20 bg-emerald-500/5 p-4 backdrop-blur md:mx-6"
              >
                <div className="mb-2 font-mono text-xs tracking-widest text-emerald-300">GENIO ANSWER</div>
                <div className="max-h-[28vh] overflow-auto custom-scrollbar text-sm leading-relaxed text-white/90" dir="auto">
                  {(() => {
                    const last = [...chat].reverse().find((c) => c.type === "answer");
                    return last && "text" in last ? (last as { text: string }).text : "…";
                  })()}
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <div className="flex flex-1 items-center gap-1">
                    {Array.from({ length: 20 }, (_, i) => (
                      <motion.div
                        key={i}
                        className="h-3 w-[3px] rounded-full bg-emerald-400"
                        animate={{ scaleY: [0.3, 1.2 + audioLevel, 0.3] }}
                        transition={{ duration: 0.5 + Math.random() * 0.5, delay: i * 0.04, repeat: Infinity }}
                      />
                    ))}
                  </div>
                  <button className="rounded-full bg-emerald-500 p-2 text-black hover:bg-emerald-400">
                    <span className="text-xs">▶</span>
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="flex min-h-0 flex-1 flex-col">{children}</div>
        </div>
      </div>

      {/* z-20 metrics/brain */}
      <div className="pointer-events-none absolute bottom-3 right-3 z-20 flex flex-col items-end gap-3 md:bottom-4 md:right-6">
        <div className="pointer-events-auto">
          <SystemMetrics telemetry={telemetry ?? undefined} />
        </div>
        <BrainActivity active={status === "thinking" || status === "executing"} />
      </div>
    </div>
  );
});

export default GenioShell;
