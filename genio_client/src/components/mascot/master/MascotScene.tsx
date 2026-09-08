/**
 * MascotScene — master runtime composition (§15).
 * Loads genio_mascot_master.glb (draco → full fallback chain), wires
 * LayeredMixer + ExpressionController + LipSyncDriver + IdleLife +
 * SecondaryMotion + MascotEnvironment. Never crashes the host: any load
 * failure propagates to the outer ErrorBoundary (2.5D fallback).
 */
import { Component, Suspense, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { useGLTF } from "@react-three/drei";
import * as THREE from "three";
import { LayeredMixer } from "./MascotMixer";
import { ExpressionController, LipSyncDriver } from "./MascotFace";
import { IdleLife, SecondaryMotion } from "./MascotLife";
import MascotEnvironment, { type EnvMood } from "./MascotEnvironment";
import type { BehaviorDirective } from "./MascotController";

export const MASTER_DRACO_URL = "/models/genio_mascot_master_draco.glb";
export const MASTER_FULL_URL = "/models/genio_mascot_master.glb";

export type MascotDebugInfo = {
  state: string;
  clip: string | null;
  weights: Record<string, number>;
  emotionLabel: string;
  viseme: string;
  gaze: string;
  motionSource: string;
  fps: number;
  drawCalls: number;
  triangles: number;
  glbSize: string;
};

class Catch extends Component<{ onCatch: () => void; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }
  componentDidCatch(): void {
    this.props.onCatch();
  }
  render(): ReactNode {
    if (this.state.failed) return null;
    return this.props.children;
  }
}

function MasterRig({
  directive,
  audioLevel,
  voiceEnabled,
  reducedMotion,
  onDebug,
  onReady,
  src,
}: {
  directive: BehaviorDirective;
  audioLevel: number;
  voiceEnabled: boolean;
  reducedMotion: boolean;
  onDebug: (d: MascotDebugInfo) => void;
  onReady: (info: { clips: number; morphs: number }) => void;
  src: string;
}) {
  const group = useRef<THREE.Group>(null);
  const { scene, animations } = useGLTF(src) as unknown as { scene: THREE.Group; animations: THREE.AnimationClip[] };

  const mixer = useMemo(() => new LayeredMixer(scene, animations), [scene, animations]);
  const expr = useMemo(() => new ExpressionController(scene), [scene]);
  const lips = useMemo(() => new LipSyncDriver(scene, expr), [scene, expr]);
  const life = useMemo(() => new IdleLife(scene, { reducedMotion }), [scene]);
  const secondary = useMemo(() => new SecondaryMotion(scene), [scene]);
  const reported = useRef(false);
  const frames = useRef(0);
  const lastFpsAt = useRef(performance.now());
  const fps = useRef(0);

  useEffect(() => {
    life.setReducedMotion(reducedMotion);
    secondary.setReducedMotion(reducedMotion);
    if (reducedMotion) mixer.stopLayer("SPECIAL", 0.2);
  }, [reducedMotion, life, secondary, mixer]);

  useEffect(() => {
    if (!reported.current) {
      reported.current = true;
      let morphs = 0;
      scene.traverse((o) => {
        const m = o as THREE.SkinnedMesh;
        if (m.isSkinnedMesh && m.morphTargetDictionary) morphs = Math.max(morphs, Object.keys(m.morphTargetDictionary).length);
      });
      onReady({ clips: animations.length, morphs });
    }
  }, [scene, animations, onReady]);

  useEffect(() => {
    mixer.play(directive.body);
    expr.setExpression(directive.face);
    secondary.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [directive.body]);

  useEffect(() => {
    expr.setExpression(directive.face);
  }, [directive.face, expr]);

  useFrame(({ gl }, dtRaw) => {
    const dt = Math.min(dtRaw, 0.05);
    const speaking = directive.body === "speak" || directive.body === "speak_emphasis";
    if (!reducedMotion) mixer.update(dt * directive.speed);
    lips.update(dt, voiceEnabled ? audioLevel : 0, speaking && voiceEnabled);
    const { blinkL, blinkR } = life.update(dt);
    expr.setExpression({ Blink_L: blinkL, Blink_R: blinkR });
    expr.update(0.2);
    secondary.update(dt, directive.intensity);
    frames.current += 1;
    const now = performance.now();
    if (now - lastFpsAt.current >= 1000) {
      fps.current = Math.round((frames.current * 1000) / (now - lastFpsAt.current));
      frames.current = 0;
      lastFpsAt.current = now;
      onDebug({
        state: directive.intent,
        clip: mixer.currentClip(),
        weights: { ...(mixer.weights as Record<string, number>) },
        emotionLabel: directive.emotionLabel,
        viseme: speaking ? "audio" : "REST",
        gaze: directive.gaze,
        motionSource: "master-glb",
        fps: fps.current,
        drawCalls: gl.info.render.calls,
        triangles: gl.info.render.triangles,
        glbSize: src.includes("draco") ? "5.1M draco" : "37M full",
      });
    }
  });

  return (
    <group ref={group} position={[0, -0.02, 0]}>
      <primitive object={scene} />
    </group>
  );
}

export default function MascotScene({
  directive,
  audioLevel = 0,
  voiceEnabled = true,
  reducedMotion: reducedProp,
  performanceMode = false,
  overlay = true,
  mood,
  onDebug = () => {},
  onReady = () => {},
}: {
  directive: BehaviorDirective;
  audioLevel?: number;
  voiceEnabled?: boolean;
  reducedMotion?: boolean;
  performanceMode?: boolean;
  overlay?: boolean;
  mood?: EnvMood;
  onDebug?: (d: MascotDebugInfo) => void;
  onReady?: (info: { clips: number; morphs: number }) => void;
}) {
  const [sysReduced] = useState(() =>
    typeof window !== "undefined" && typeof window.matchMedia !== "undefined"
      ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
      : false,
  );
  const reducedMotion = reducedProp ?? sysReduced;
  return (
    <Canvas
      camera={{ position: [0, 0.95, 3.4], fov: 36 }}
      dpr={performanceMode ? [1, 1] : [1, 1.5]}
      gl={{ antialias: !performanceMode, alpha: overlay }}
      style={{ background: overlay ? "transparent" : "#020B1E" }}
    >
      <MascotEnvironment mood={mood ?? (directive.body === "success" || directive.body === "celebrate" ? "success" : "idle")} reducedMotion={reducedMotion} audioLevel={audioLevel} />
      <Suspense fallback={null}>
        <ModelWithFallback directive={directive} audioLevel={audioLevel} voiceEnabled={voiceEnabled} reducedMotion={reducedMotion} onDebug={onDebug} onReady={onReady} />
      </Suspense>
    </Canvas>
  );
}

/** draco → full → rethrow (outer boundary falls back to 2.5D). */
function ModelWithFallback(props: {
  directive: BehaviorDirective;
  audioLevel: number;
  voiceEnabled: boolean;
  reducedMotion: boolean;
  onDebug: (d: MascotDebugInfo) => void;
  onReady: (info: { clips: number; morphs: number }) => void;
}) {
  const [attempt, setAttempt] = useState(0);
  if (attempt > 1) throw new Error("genio-master-glb failed to load (draco + full)");
  return (
    <Catch key={attempt} onCatch={() => setAttempt((a) => a + 1)}>
      <MasterRig {...props} src={attempt === 0 ? MASTER_DRACO_URL : MASTER_FULL_URL} />
    </Catch>
  );
}

useGLTF.preload(MASTER_DRACO_URL);
