import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Canvas } from "@react-three/fiber";
import { Physics, RigidBody, CuboidCollider, type RapierRigidBody } from "@react-three/rapier";
import { Mic, MicOff, Settings2 } from "lucide-react";
import CyberAvatar from "../avatar/CyberAvatar";
import RiggedMascot from "./RiggedMascot";
import ErrorBoundary from "../v3/ErrorBoundary";
import { AndalusianBackground } from "../v3";
import { useVoiceOutput } from "../v3/useVoiceOutput";
import { nextPose, type PoseTarget } from "../../lib/mascotAnimator";
import { markPositive, getStats } from "../../lib/mascotMemory";
import { startVoiceRecording, stopVoiceRecording, setIntermediateTranscript, speechRecognitionSupported } from "../../lib/audio";
import type { AgentStatus, ChatEvent, Attachment } from "../../lib/types";

interface MascotStageProps {
  chat: ChatEvent[];
  agentStatus: AgentStatus;
  sendPrompt: (text: string, attachments?: Attachment[]) => void;
  onSwitchToTechnicalMode: () => void;
}

// Free-roam bounds (meters) the physics body is allowed to drift within.
const BOUNDS = { x: 1.6, y: 0.7, z: 0.6 };

/**
 * Invisible physics body: a real Rapier rigid body drifting under actual
 * simulated forces (impulses + damping + wall collisions) within BOUNDS.
 * We don't render the character inside this Canvas — nesting the existing,
 * already-hardened CyberAvatar Canvas inside another Canvas is asking for
 * trouble (two WebGL contexts, two render loops). Instead this canvas only
 * *computes* where the character should be; MascotStage reads that position
 * out every frame and applies it as a CSS transform to the real CyberAvatar
 * overlay sitting in the DOM above it. Physics stays real, rendering stays
 * on the proven, crash-hardened component.
 */
function PhysicsDriver({ onPosition, target }: { onPosition: (x: number, y: number) => void; target: { current: { x: number; y: number; z: number } } }) {
  const bodyRef = useRef<RapierRigidBody>(null);
  const lastImpulseAt = useRef(0);

  useEffect(() => {
    let raf: number;
    const tick = (t: number) => {
      const body = bodyRef.current;
      if (body) {
        // Gently steer toward the animator's current target, real impulses (not teleporting).
        if (t - lastImpulseAt.current > 400) {
          lastImpulseAt.current = t;
          const pos = body.translation();
          const dx = target.current.x - pos.x;
          const dy = target.current.y - pos.y;
          const dz = target.current.z - pos.z;
          body.applyImpulse({ x: dx * 0.02, y: dy * 0.02, z: dz * 0.015 }, true);
        }
        const p = body.translation();
        onPosition(p.x, p.y);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Physics gravity={[0, 0, 0]}>
      <RigidBody
        ref={bodyRef}
        type="dynamic"
        colliders="ball"
        linearDamping={2.2}
        angularDamping={4}
        position={[0, 0, 0]}
      >
        <mesh visible={false}>
          <sphereGeometry args={[0.18, 8, 8]} />
        </mesh>
      </RigidBody>
      {/* Invisible walls keeping the free movement bounded — real collisions, not clamping. */}
      <CuboidCollider position={[BOUNDS.x + 0.1, 0, 0]} args={[0.1, 2, 2]} />
      <CuboidCollider position={[-BOUNDS.x - 0.1, 0, 0]} args={[0.1, 2, 2]} />
      <CuboidCollider position={[0, BOUNDS.y + 0.1, 0]} args={[2, 0.1, 2]} />
      <CuboidCollider position={[0, -BOUNDS.y - 0.1, 0]} args={[2, 0.1, 2]} />
      <CuboidCollider position={[0, 0, BOUNDS.z + 0.1]} args={[2, 2, 0.1]} />
      <CuboidCollider position={[0, 0, -BOUNDS.z - 0.1]} args={[2, 2, 0.1]} />
    </Physics>
  );
}

export default function MascotStage({ chat, agentStatus, sendPrompt, onSwitchToTechnicalMode }: MascotStageProps) {
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const [pose, setPose] = useState<PoseTarget | null>(null);
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [caption, setCaption] = useState("");
  const [micError, setMicError] = useState<string | null>(null);
  const targetRef = useRef({ x: 0, y: 0, z: 0 });
  const { speak, stop: stopSpeak } = useVoiceOutput();
  const lastAssistantIdxRef = useRef(0);

  // Re-roll the animator's target pose whenever the agent status / listening / speaking state changes,
  // and periodically during idle so the mascot keeps fidgeting naturally instead of freezing.
  useEffect(() => {
    const roll = () => {
      const p = nextPose(agentStatus, { listening, speaking });
      setPose(p);
      if (p.moveTo) targetRef.current = { x: p.moveTo.x, y: 0, z: p.moveTo.z };
    };
    roll();
    const isIdle = agentStatus.kind === "idle" && !listening && !speaking;
    const interval = isIdle ? window.setInterval(roll, 3500) : undefined;
    return () => { if (interval) window.clearInterval(interval); };
  }, [agentStatus, listening, speaking]);

  // Speak new assistant messages aloud + drive the "speaking" pose/mouth while doing so.
  useEffect(() => {
    if (chat.length <= lastAssistantIdxRef.current) return;
    const newOnes = chat.slice(lastAssistantIdxRef.current);
    lastAssistantIdxRef.current = chat.length;
    const lastText = [...newOnes].reverse().find((e) => (e as { type?: string }).type === "answer") as { text?: string } | undefined;
    if (lastText?.text) {
      setSpeaking(true);
      (speak as (t: string, _lang?: string) => void)(lastText.text, "fr-FR");
      const estMs = Math.min(9000, Math.max(1200, lastText.text.length * 55));
      window.setTimeout(() => setSpeaking(false), estMs);
    }
  }, [chat, speak]);

  const avatarMode: "idle" | "listening" | "speaking" | "greeting" =
    speaking ? "speaking" : listening ? "listening" : "idle";
  // Clip riggé = contexte mascotAnimator (noms EXACTS: idle/greeting/listening/thinking/executing/success/error/speaking)
  const activeClip = pose?.contextKey ?? avatarMode;

  const toggleMic = useCallback(async () => {
    setMicError(null);
    if (listening) {
      const audio = await stopVoiceRecording();
      setListening(false);
      if (audio?.transcript?.trim()) {
        sendPrompt(audio.transcript.trim());
        if (pose) markPositive(pose.contextKey, pose.variantId);
      }
      setCaption("");
    } else {
      setIntermediateTranscript("");
      try {
        stopSpeak();
        await startVoiceRecording((text) => setCaption(text));
        setListening(true);
      } catch (err: unknown) {
        setMicError(err instanceof Error ? err.message : "Micro indisponible");
      }
    }
  }, [listening, sendPrompt, pose, stopSpeak]);

  const stats = getStats();

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-[#020B1E]">
      <AndalusianBackground />

      {/* Real physics simulation — invisible, only computes position */}
      <div className="pointer-events-none absolute inset-0 opacity-0">
        <Canvas>
          <ErrorBoundary name="MascotPhysics">
            <PhysicsDriver onPosition={(x, y) => setPos({ x, y })} target={targetRef} />
          </ErrorBoundary>
        </Canvas>
      </div>

      {/* The actual character, positioned by the real physics output above.
          RiggedMascot (v3 riggé fidèle) en premier, CyberAvatar en filet de sécurité. */}
      <motion.div
        className="absolute left-1/2 top-[38%] -translate-x-1/2 -translate-y-1/2"
        animate={{ x: pos.x * 140, y: -pos.y * 140 }}
        transition={{ type: "spring", stiffness: 60, damping: 18 }}
      >
        <ErrorBoundary name="RiggedMascot-stage">
          <Suspense
            fallback={
              <ErrorBoundary name="CyberAvatar-mascotStage-fallback">
                <CyberAvatar mode={avatarMode} size={420} interactive={false} faceTrack={false} audioLevel={speaking ? 0.5 : 0} />
              </ErrorBoundary>
            }
          >
            <div style={{ width: 520, height: 520 }}>
              <Canvas camera={{ position: [0, 0.85, 3.9], fov: 36 }} dpr={[1, 1.5]} gl={{ antialias: true, toneMappingExposure: 1.25 }}>
                <ambientLight intensity={1.15} />
                <directionalLight position={[2.5, 4, 3]} intensity={2.0} />
                <directionalLight position={[-2.5, 2, 2.5]} intensity={0.9} color="#67e8f9" />
                <hemisphereLight args={["#a5f3fc", "#020B1E", 0.85]} />
                <Suspense fallback={null}>
                  <RiggedMascot
                    activeClip={activeClip}
                    audioLevel={speaking ? 0.5 : 0}
                    headYaw={pose?.headYaw ?? 0}
                    headTilt={pose?.headTilt ?? 0}
                  />
                </Suspense>
              </Canvas>
            </div>
          </Suspense>
        </ErrorBoundary>
      </motion.div>

      {/* Live caption while listening */}
      <AnimatePresence>
        {listening && caption && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="absolute bottom-32 left-1/2 -translate-x-1/2 rounded-full bg-black/50 px-5 py-2 text-sm text-cyan-100 backdrop-blur"
          >
            {caption}
          </motion.div>
        )}
      </AnimatePresence>

      {micError && (
        <div className="absolute bottom-44 left-1/2 -translate-x-1/2 rounded-lg bg-red-950/80 px-4 py-2 text-xs text-red-200">
          {micError}
        </div>
      )}

      {/* Voice control — the primary interaction for public users */}
      <div className="absolute bottom-12 left-1/2 flex -translate-x-1/2 flex-col items-center gap-3">
        <button
          onClick={toggleMic}
          disabled={!speechRecognitionSupported() && !navigator.mediaDevices}
          className={`flex h-16 w-16 items-center justify-center rounded-full border transition-all ${
            listening
              ? "border-red-400/60 bg-red-500/20 shadow-[0_0_30px_rgba(248,113,113,0.5)]"
              : "border-cyan-400/40 bg-cyan-500/10 shadow-[0_0_24px_rgba(0,229,255,0.3)] hover:bg-cyan-500/20"
          }`}
          aria-label={listening ? "Arrêter le micro" : "Parler à Genio"}
        >
          {listening ? <MicOff className="h-6 w-6 text-red-200" /> : <Mic className="h-6 w-6 text-cyan-200" />}
        </button>
        <span className="text-[11px] uppercase tracking-widest text-cyan-200/50">
          {listening ? "écoute…" : speaking ? "parle…" : "touchez pour parler"}
        </span>
      </div>

      {/* Escape hatch to the full technical/dev interface */}
      <button
        onClick={onSwitchToTechnicalMode}
        className="absolute right-4 top-4 flex items-center gap-1.5 rounded-full border border-white/10 bg-black/30 px-3 py-1.5 text-[11px] text-white/60 backdrop-blur hover:bg-black/50 hover:text-white/90"
        title={`${stats.totalGestures} gestes appris pour cet utilisateur`}
      >
        <Settings2 className="h-3.5 w-3.5" /> Mode technique
      </button>
    </div>
  );
}
