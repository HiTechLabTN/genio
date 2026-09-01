import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";

/** Phase 4 v2.1 — Cyber-Tunisian 3D Avatar.
 *
 * Stylized robotic head with a cybernetic Chachia (شاشية) — the classic
 * Tunisian chechia topped with a neon beak/band — luminous facial accents and
 * a holographic neon rim. Idle breathing, listening and speaking lip-sync
 * morphs are driven by `mode` (idle | listening | speaking). The head's
 * look-at vector follows the device pointer (and, when available, an enhanced
 * FaceMesh landmark) without requiring a webcam.
 *
 * Falls back gracefully to a static framed canvas bubble if WebGL is missing.
 */

type AvatarMode = "idle" | "listening" | "speaking";

export interface CyberAvatarProps {
  mode?: AvatarMode;
  size?: number;
  interactive?: boolean;
  /** Phase 4 v2.1: enable FaceMesh webcam look-at (defaults to false so we
   * never silently request a camera; the head still follows the pointer). */
  faceTrack?: boolean;
  className?: string;
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function smooth(raw: number): number {
  // Cheap exponential smoothing so look-at motion isn't jittery.
  return Math.max(-0.6, Math.min(0.6, raw));
}

/* ------------------------------------------------------------------ */
/* Head — static geometry (Chachia + neon accents)                     */
/* ------------------------------------------------------------------ */

interface HeadGeometryProps {
  target: React.MutableRefObject<[number, number]>;
  morph: number; // 0 = idle, 1 = speaking
  breathing: number;
  altitude: number;
  accentMat: THREE.MeshStandardMaterial | THREE.MeshBasicMaterial;
}

function HeadGeometry({ target, morph, breathing, altitude, accentMat }: HeadGeometryProps) {
  const group = useRef<THREE.Group>(null);
  const eyeL = useRef<THREE.Mesh>(null);
  const eyeR = useRef<THREE.Mesh>(null);
  const jaw = useRef<THREE.Mesh>(null);

  useFrame(({ clock }) => {
    const g = group.current;
    if (!g) return;
    const t = clock.getElapsedTime();
    // gentle body bob (breathing) + altitude damping
    g.position.y = Math.sin(t * 1.6) * 0.05 * breathing + altitude;

    // look-at pointer target
    const wantX = target.current[0];
    const wantY = target.current[1];
    g.rotation.y += (wantX - g.rotation.y) * 0.06;
    g.rotation.x += (wantY - g.rotation.x) * 0.06;

    // lip-sync morph: lower jaw opens slightly on speaking
    if (jaw.current) {
      const base = Math.sin(t * 0.8) * 0.4 * morph + 0.25 * morph;
      jaw.current.position.y = -base * 0.35;
      (jaw.current.scale as THREE.Vector3).set(1, 1 - base * 0.2, 1);
    }
    // neon eye glow pulse
    if (eyeL.current && eyeR.current) {
      const pulse = 0.85 + 0.15 * Math.sin(t * 2.4) + morph * 0.3;
      const m = eyeL.current.material as THREE.MeshStandardMaterial;
      if (m) m.emissiveIntensity = pulse;
      eyeL.current.scale.setScalar(0.9 + 0.1 * morph);
      eyeR.current.scale.setScalar(0.9 + 0.1 * morph);
    }
  });

  return (
    <group ref={group} position={[0, 0, 0]}>
      {/* skull */}
      <mesh>
        <sphereGeometry args={[0.62, 48, 48]} />
        <meshStandardMaterial color="#101a2e" metalness={0.75} roughness={0.35} />
      </mesh>
      {/* cybernetic Chachia — the Tunisian chechia reimagined as neon polymer */}
      <group position={[0, 0.66, 0]}>
        <mesh>
          <boxGeometry args={[0.5, 0.12, 0.5]} />
          <meshStandardMaterial color="#7a5c2e" metalness={0.6} roughness={0.4} />
        </mesh>
        <mesh position={[0, 0.1, 0]}>
          <cylinderGeometry args={[0.28, 0.3, 0.1, 24]} />
          <meshStandardMaterial color="#5f451f" metalness={0.55} roughness={0.45} />
        </mesh>
        {/* neon beak / band */}
        <mesh position={[0, 0.03, 0.34]} material={accentMat}>
          <boxGeometry args={[0.16, 0.05, 0.06]} />
        </mesh>
      </group>
      {/* eye visor */}
      <mesh ref={eyeL} position={[-0.18, 0.05, 0.54]} material={accentMat}>
        <sphereGeometry args={[0.06, 16, 16]} />
      </mesh>
      <mesh ref={eyeR} position={[0.18, 0.05, 0.54]} material={accentMat}>
        <sphereGeometry args={[0.06, 16, 16]} />
      </mesh>
      {/* jaw */}
      <mesh ref={jaw} position={[0, -0.4, 0.5]}>
        <boxGeometry args={[0.4, 0.12, 0.1]} />
        <meshStandardMaterial color="#0c1526" metalness={0.7} roughness={0.4} />
      </mesh>
      {/* cheek neon stripes */}
      <mesh position={[-0.52, -0.02, 0.32]} material={accentMat}>
        <boxGeometry args={[0.04, 0.16, 0.04]} />
      </mesh>
      <mesh position={[0.52, -0.02, 0.32]} material={accentMat}>
        <boxGeometry args={[0.04, 0.16, 0.04]} />
      </mesh>
      {/* holo rim */}
      <mesh position={[0, -0.1, 0.55]} material={accentMat}>
        <torusGeometry args={[0.3, 0.015, 12, 48]} />
      </mesh>
    </group>
  );
}

/* ------------------------------------------------------------------ */
/* Scene                                                               */
/* ------------------------------------------------------------------ */

function AvatarScene({ mode, interactive }: { mode: AvatarMode; interactive: boolean }) {
  const target = useRef<[number, number]>([0, 0]);
  const { pointer } = useThree();
  const accentMat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#22d3ee",
        emissive: "#22d3ee",
        emissiveIntensity: 1.1,
        metalness: 0.3,
        roughness: 0.2,
      }),
    [],
  );

  // Phase 4 v2.1: optional FaceMesh look-at shared ref (set by useFaceTracking).
  const { faceLookTarget } = useFaceTrackingContext();

  useFrame(() => {
    if (faceLookTarget.current[0] !== 0 || faceLookTarget.current[1] !== 0) {
      // Prefer FaceMesh-derived direction when a webcam is present.
      target.current = [
        smooth(faceLookTarget.current[0]),
        smooth(faceLookTarget.current[1]),
      ];
    } else if (interactive) {
      // Map pointer (already normalized -1..1) to look-at vector.
      const x = smooth(pointer.x * 0.9);
      const y = smooth(pointer.y * -0.5);
      target.current = [x, y];
    }
  });

  const morph = mode === "speaking" ? 1 : 0;
  const breathing = mode === "idle" ? 1 : mode === "listening" ? 0.6 : 0.5;

  return (
    <>
      <ambientLight intensity={0.55} />
      <directionalLight position={[3, 4, 5]} intensity={1.1} />
      <pointLight position={[-2, 0, 3]} intensity={1.6} color="#22d3ee" />
      <pointLight position={[2, -1, 2]} intensity={0.8} color="#a855f7" />
      <HeadGeometry
        target={target}
        morph={morph}
        breathing={breathing}
        altitude={0}
        accentMat={accentMat}
      />
      {interactive && (
        <OrbitControls enableZoom={false} enablePan={false} autoRotate={false} />
      )}
    </>
  );
}

/* ------------------------------------------------------------------ */
/* FaceMesh look-at context (default no-op, filled by useFaceTracking) */
/* ------------------------------------------------------------------ */

const FaceLookContext = React.createContext<{
  faceLookTarget: React.MutableRefObject<[number, number]>;
}>({
  faceLookTarget: ({ current: [0, 0] } as unknown) as React.MutableRefObject<[number, number]>,
});

function useFaceTrackingContext() {
  return React.useContext(FaceLookContext);
}

/** Phase 4 v2.1 — wire @mediapipe/face_mesh to the 3D look-at vector.
 *
 * Enables "the avatar watches you" on devices that grant a webcam; otherwise
 * the head follows the device pointer. Gated by GENIO_3D_AVATAR (client probe)
 * and only ever runs when the meshing model is available.
 */
export function useFaceTracking(enabled: boolean): {
  provider: ({ children }: { children?: React.ReactNode }) => React.ReactElement;
  active: boolean;
} {
  const target = useRef<[number, number]>([0, 0]);
  const [active, setActive] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let video: HTMLVideoElement | null = null;
    let stream: MediaStream | null = null;
    let faceMesh:
      | { send: (opts: { image: HTMLVideoElement }) => Promise<unknown>; close: () => void }
      | null = null;

    async function setup() {
      try {
        const { FaceMesh } = await import("@mediapipe/face_mesh");
        const landmark = (results: {
          multiFaceLandmarks?: Array<Array<{ x: number; y: number }>>;
        }) => {
          if (cancelled || !results || !results.multiFaceLandmarks?.length) return;
          const face = results.multiFaceLandmarks[0];
          const nose = face[1];
          const left = face[33];
          const right = face[263];
          if (!nose || !left || !right) return;
          // yaw estimate + slight pitch from face center
          const dx = (left.x + right.x) / 2 - nose.x;
          const yaw = Math.max(-0.6, Math.min(0.6, dx * 6));
          const pitch = Math.max(-0.4, Math.min(0.4, (0.5 - nose.y) * 2));
          target.current = [yaw, -pitch];
        };
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const runner = new FaceMesh({
          locateFile: (file: string) =>
            `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`,
        }) as unknown as {
          setOptions: (o: Record<string, unknown>) => void;
          onResults: (cb: (r: unknown) => void) => void;
          send: (opts: { image: HTMLVideoElement }) => Promise<unknown>;
          close: () => void;
        };
        faceMesh = runner;
        try {
          runner.setOptions({ maxNumFaces: 1, refineLandmarks: true });
        } catch { /* older API */ }
        runner.onResults((r) => {
          // normalize results into the shape our landmark cb expects
          void landmark(r as { multiFaceLandmarks?: Array<Array<{ x: number; y: number }>> });
        });
        stream = await navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240 } });
        video = document.createElement("video");
        video.srcObject = stream;
        video.width = 320;
        video.height = 240;
        await video.play();
        const videoEl = video;
        const tick = async () => {
          if (cancelled || !faceMesh) return;
          try {
            await faceMesh.send({ image: videoEl });
          } catch { /* transient */ }
          requestAnimationFrame(tick);
        };
        tick();
        setActive(true);
      } catch {
        // Webcam unavailable / model fetch failed — fall back to pointer.
        setActive(false);
      }
    }

    setup();
    return () => {
      cancelled = true;
      void stream?.getTracks().forEach((t) => t.stop());
      try {
        faceMesh?.close();
      } catch { /* noop */ }
    };
  }, [enabled]);

  const provider = React.useCallback(
    ({ children }: { children?: React.ReactNode }) => (
      <FaceLookContext.Provider value={{ faceLookTarget: target }}>{children}</FaceLookContext.Provider>
    ),
    [],
  );

  return { provider, active };
}

/* ------------------------------------------------------------------ */
/* Public component                                                    */
/* ------------------------------------------------------------------ */

export default function CyberAvatar({
  mode = "idle",
  size = 220,
  interactive = true,
  faceTrack = false,
  className = "",
}: CyberAvatarProps) {
  const [webgl, setWebgl] = useState(true);

  useEffect(() => {
    try {
      const canvas = document.createElement("canvas");
      const gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
      if (!gl) setWebgl(false);
    } catch {
      setWebgl(false);
    }
  }, []);

  // Phase 4 v2.1: face-mesh look-at (webcam) when opted in and granted;
  // otherwise the head follows the device pointer.
  const face = useFaceTracking(faceTrack);
  const Provider = face.provider;

  if (!webgl) {
    // Graceful fallback: framed neon orb.
    return (
      <motion.div
        initial={{ scale: 0.85, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className={`relative flex h-full w-full items-center justify-center ${className}`}
      >
        <div className="flex h-40 w-40 items-center justify-center rounded-full bg-gradient-to-br from-cyan-500/30 to-fuchsia-500/20 ring-1 ring-neon/40 shadow-neon-lg animate-float-y">
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-carbon ring-2 ring-neon/50">
            <span className="text-4xl text-neon">◉</span>
          </div>
        </div>
      </motion.div>
    );
  }

  return (
    <div className={`relative ${className}`} style={{ width: size, height: size }}>
      <div className="pointer-events-none absolute inset-0 -z-10 rounded-full bg-neon/10 blur-2xl" />
      <Provider>
        <Canvas
          dpr={[1, 1.5]}
          camera={{ position: [0, 0, 3.1], fov: 55 }}
          gl={{ antialias: true, alpha: true }}
        >
          <AvatarScene mode={mode} interactive={interactive} />
        </Canvas>
      </Provider>
    </div>
  );
}