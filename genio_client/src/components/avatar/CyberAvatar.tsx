import { motion } from "framer-motion";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Text } from "@react-three/drei";
import * as THREE from "three";
import React, { useEffect, useRef, useState, Suspense } from "react";
import { useFaceTracking, useFaceTrackingContext } from "./useFaceTracking";

/**
 * v2.2.2 — Simplified WebGL avatar (MeshStandardMaterial, low-poly, gesture-capable)
 */

type AvatarMode = "idle" | "listening" | "speaking" | "greeting";

export interface CyberAvatarProps {
  mode?: AvatarMode;
  size?: number;
  interactive?: boolean;
  faceTrack?: boolean;
  audioLevel?: number;
  className?: string;
  isGreeting?: boolean;
}

function smooth(raw: number): number {
  return Math.max(-0.7, Math.min(0.7, raw));
}

function LoadingUI() {
  return (
    <div className="flex h-full w-full items-center justify-center">
      <div className="h-14 w-14 animate-spin rounded-full border-4 border-neon/20 border-t-neon" />
    </div>
  );
}

function SceneCanvas({
  mode,
  audioLevel,
  interactive,
}: {
  mode: AvatarMode;
  audioLevel: number;
  interactive: boolean;
}) {
  return (
    <Canvas
      dpr={[1, 1.6]}
      camera={{ position: [0, 0.18, 2.95], fov: 52 }}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
    >
      <Suspense fallback={null}>
        <AvatarScene mode={mode} audioLevel={audioLevel} interactive={interactive} />
      </Suspense>
    </Canvas>
  );
}
const MemoizedSceneCanvas = React.memo(SceneCanvas);

const CYBER_MAT = {
  ceramic: new THREE.MeshStandardMaterial({ color: "#F8F9FA", roughness: 0.35, metalness: 0.05 }),
  chrome: new THREE.MeshStandardMaterial({ color: "#e8ecf1", roughness: 0.25, metalness: 0.6 }),
  crimson: new THREE.MeshStandardMaterial({ color: "#DC0A0A", roughness: 0.6, metalness: 0.05 }),
  red: new THREE.MeshStandardMaterial({ color: "#E53935", roughness: 0.7, metalness: 0.0 }),
  gold: new THREE.MeshStandardMaterial({ color: "#FFD700", metalness: 0.85, roughness: 0.25, emissive: "#7A5A00", emissiveIntensity: 0.12 }),
  cyan: new THREE.MeshStandardMaterial({ color: "#00E5FF", emissive: "#00E5FF", emissiveIntensity: 1.0 }),
  black: new THREE.MeshStandardMaterial({ color: "#0A0A0A", roughness: 0.2, metalness: 0.3 }),
  eyeWhite: new THREE.MeshStandardMaterial({ color: "#ffffff", roughness: 0.1 }),
  eyeIris: new THREE.MeshStandardMaterial({ color: "#8B4513", emissive: "#FF1A1A", emissiveIntensity: 0.3 }),
  eyeHighlight: new THREE.MeshStandardMaterial({ color: "#ffffff", emissive: "#ffffff", emissiveIntensity: 0.6 }),
  pupil: new THREE.MeshStandardMaterial({ color: "#000000" }),
  glowRing: new THREE.MeshStandardMaterial({ color: "#FF1A1A", emissive: "#FF1A1A", emissiveIntensity: 0.8, transparent: true, opacity: 0.6 }),
};

interface HeadProps {
  target: React.MutableRefObject<[number, number]>;
  mode: AvatarMode;
  audioLevel: number;
  isGreeting: boolean;
}

function CyborgHead({ target, mode, audioLevel, isGreeting }: HeadProps) {
  const group = useRef<THREE.Group>(null);
  const jaw = useRef<THREE.Group>(null);
  const irisL = useRef<THREE.Mesh>(null);
  const irisR = useRef<THREE.Mesh>(null);
  const lidL = useRef<THREE.Mesh>(null);
  const lidR = useRef<THREE.Mesh>(null);
  const rightArm = useRef<THREE.Group>(null);

  const t = useRef(0);

  useFrame(({ clock }) => {
    const g = group.current;
    if (!g) return;
    const time = clock.getElapsedTime();
    t.current = time;

    const breathe = Math.sin(time * 1.2) * 0.035 + Math.sin(time * 0.6) * 0.012;
    g.position.y = breathe;
    g.position.x = Math.sin(time * 0.85) * 0.018;

    const wantX = target.current[0];
    const wantY = target.current[1];
    g.rotation.y += (wantX - g.rotation.y) * 0.08;
    g.rotation.x += (wantY - g.rotation.x) * 0.08;
    g.rotation.z *= 0.92;

    // Gesture: listening → raise right arm to ear + tilt head forward
    if (mode === "listening") {
      g.rotation.x += (0.15 - g.rotation.x) * 0.08;
      if (rightArm.current) {
        rightArm.current.position.x += (0.35 - rightArm.current.position.x) * 0.1;
        rightArm.current.rotation.z += (0.6 - rightArm.current.rotation.z) * 0.08;
        rightArm.current.position.y = -0.02;
      }
    }
    // Gesture: greeting → wave hand (oscillate right arm left-right 3 times over ~3s)
    else if (mode === "greeting" || isGreeting) {
      if (rightArm.current) {
        const wavePhase = (time % 3) / 3;
        const waveAngle = Math.sin(wavePhase * Math.PI * 6) * 0.5;
        rightArm.current.position.x += (0.35 - rightArm.current.position.x) * 0.1;
        rightArm.current.rotation.z += (waveAngle - rightArm.current.rotation.z) * 0.12;
        rightArm.current.position.y = -0.02;
      }
    }
    // Idle / speaking → arm down
    else {
      if (rightArm.current) {
        rightArm.current.position.x += (0 - rightArm.current.position.x) * 0.08;
        rightArm.current.rotation.z += (0 - rightArm.current.rotation.z) * 0.08;
        rightArm.current.position.y = 0;
      }
    }

    const blinkPhase = time % 3.4;
    const isBlink = blinkPhase > 3.25;
    const lidScale = isBlink ? 0.02 : 1;
    if (lidL.current) lidL.current.scale.y = THREE.MathUtils.lerp(lidL.current.scale.y, lidScale, 0.35);
    if (lidR.current) lidR.current.scale.y = THREE.MathUtils.lerp(lidR.current.scale.y, lidScale, 0.35);

    if (irisL.current && irisR.current) {
      const pulse = 0.95 + 0.12 * Math.sin(time * 2.0) + (mode === "speaking" ? 0.18 : 0);
      (irisL.current.material as THREE.MeshStandardMaterial).emissiveIntensity = pulse * 0.6;
      (irisR.current.material as THREE.MeshStandardMaterial).emissiveIntensity = pulse * 0.6;
    }

    if (jaw.current) {
      const level = mode === "speaking" ? Math.max(audioLevel, 0.28 + 0.38 * Math.abs(Math.sin(time * 7.5))) : audioLevel * 0.55;
      const open = THREE.MathUtils.clamp(level, 0, 1) * 0.32;
      jaw.current.position.y = -open;
      jaw.current.rotation.x = open * 0.55;
    }
  });

  return (
    <group ref={group}>
      {/* Torso — red with golden G */}
      <mesh position={[0, -0.55, 0]}>
        <boxGeometry args={[0.5, 0.35, 0.28]} />
        <primitive object={CYBER_MAT.crimson} attach="material" />
      </mesh>
      {/* Golden G on chest */}
      <mesh position={[0, -0.55, 0.15]}>
        <Text fontSize={0.14} color="#FFD700" anchorX="center" anchorY="middle" outlineWidth={0.008} outlineColor="#7A5A00" font="https://fonts.gstatic.com/s/orbitron/v31/yMJRMgzdpvBhQQL_Qq7dy0e2.ttf">
          G
        </Text>
      </mesh>

      {/* Right arm (for gestures) */}
      <group ref={rightArm} position={[0.32, -0.42, 0]}>
        <mesh>
          <boxGeometry args={[0.1, 0.28, 0.1]} />
          <primitive object={CYBER_MAT.crimson} attach="material" />
        </mesh>
        <mesh position={[0, -0.16, 0]}>
          <sphereGeometry args={[0.06, 12, 12]} />
          <primitive object={CYBER_MAT.crimson} attach="material" />
        </mesh>
      </group>

      {/* Left arm (idle) */}
      <group position={[-0.32, -0.42, 0]}>
        <mesh>
          <boxGeometry args={[0.1, 0.28, 0.1]} />
          <primitive object={CYBER_MAT.crimson} attach="material" />
        </mesh>
        <mesh position={[0, -0.16, 0]}>
          <sphereGeometry args={[0.06, 12, 12]} />
          <primitive object={CYBER_MAT.crimson} attach="material" />
        </mesh>
      </group>

      {/* Chachia — red cylinder */}
      <mesh position={[0, 0.08, -0.02]}>
        <cylinderGeometry args={[0.42, 0.45, 0.22, 16]} />
        <primitive object={CYBER_MAT.crimson} attach="material" />
      </mesh>
      {/* Cape back */}
      <mesh position={[0, 0.18, -0.1]} rotation={[0.2, 0, 0]}>
        <boxGeometry args={[0.5, 0.22, 0.12]} />
        <primitive object={CYBER_MAT.crimson} attach="material" />
      </mesh>
      {/* Gold piping */}
      <mesh position={[0, 0.2, 0.02]}>
        <torusGeometry args={[0.42, 0.012, 8, 24, Math.PI * 1.7]} />
        <primitive object={CYBER_MAT.gold} attach="material" />
      </mesh>

      {/* Head dome — white ceramic sphere */}
      <mesh position={[0, 0.12, 0]}>
        <sphereGeometry args={[0.5, 16, 16]} />
        <primitive object={CYBER_MAT.ceramic} attach="material" />
      </mesh>
      {/* Lower face chrome */}
      <mesh position={[0, -0.2, 0.02]}>
        <capsuleGeometry args={[0.28, 0.2, 4, 12]} />
        <primitive object={CYBER_MAT.chrome} attach="material" />
      </mesh>

      {/* Face plate black screen */}
      <mesh position={[0, 0.02, 0.42]}>
        <sphereGeometry args={[0.34, 16, 16, 0, Math.PI * 2, 0, Math.PI * 0.55]} />
        <primitive object={CYBER_MAT.black} attach="material" />
      </mesh>

      {/* Big anime eyes */}
      <group position={[0, 0.06, 0.48]}>
        <group position={[-0.14, 0, 0]}>
          <mesh>
            <sphereGeometry args={[0.08, 16, 16]} />
            <primitive object={CYBER_MAT.eyeWhite} attach="material" />
          </mesh>
          <mesh ref={irisL} position={[0, 0, 0.06]}>
            <circleGeometry args={[0.05, 16]} />
            <primitive object={CYBER_MAT.eyeIris} attach="material" />
          </mesh>
          <mesh position={[0.015, 0.015, 0.07]}>
            <circleGeometry args={[0.014, 12]} />
            <primitive object={CYBER_MAT.eyeHighlight} attach="material" />
          </mesh>
          <mesh position={[0, 0, 0.065]}>
            <circleGeometry args={[0.02, 12]} />
            <primitive object={CYBER_MAT.pupil} attach="material" />
          </mesh>
          <mesh ref={lidL} position={[0, 0.025, 0.08]}>
            <sphereGeometry args={[0.09, 12, 12, 0, Math.PI * 2, 0, Math.PI * 0.5]} />
            <primitive object={CYBER_MAT.eyeWhite} attach="material" />
          </mesh>
        </group>
        <group position={[0.14, 0, 0]}>
          <mesh>
            <sphereGeometry args={[0.08, 16, 16]} />
            <primitive object={CYBER_MAT.eyeWhite} attach="material" />
          </mesh>
          <mesh ref={irisR} position={[0, 0, 0.06]}>
            <circleGeometry args={[0.05, 16]} />
            <primitive object={CYBER_MAT.eyeIris} attach="material" />
          </mesh>
          <mesh position={[0.015, 0.015, 0.07]}>
            <circleGeometry args={[0.014, 12]} />
            <primitive object={CYBER_MAT.eyeHighlight} attach="material" />
          </mesh>
          <mesh position={[0, 0, 0.065]}>
            <circleGeometry args={[0.02, 12]} />
            <primitive object={CYBER_MAT.pupil} attach="material" />
          </mesh>
          <mesh ref={lidR} position={[0, 0.025, 0.08]}>
            <sphereGeometry args={[0.09, 12, 12, 0, Math.PI * 2, 0, Math.PI * 0.5]} />
            <primitive object={CYBER_MAT.eyeWhite} attach="material" />
          </mesh>
        </group>
        {/* red glow rim */}
        <mesh position={[-0.14, 0, -0.04]}>
          <ringGeometry args={[0.09, 0.105, 16]} />
          <primitive object={CYBER_MAT.glowRing} attach="material" />
        </mesh>
        <mesh position={[0.14, 0, -0.04]}>
          <ringGeometry args={[0.09, 0.105, 16]} />
          <primitive object={CYBER_MAT.glowRing} attach="material" />
        </mesh>
      </group>

      {/* Thick red cartoon beard — simplified */}
      <group position={[0, -0.12, 0.46]}>
        <mesh position={[-0.08, 0.03, 0]} rotation={[0.15, 0, 0.15]}>
          <capsuleGeometry args={[0.035, 0.14, 4, 10]} />
          <primitive object={CYBER_MAT.red} attach="material" />
        </mesh>
        <mesh position={[0.08, 0.03, 0]} rotation={[0.15, 0, -0.15]}>
          <capsuleGeometry args={[0.035, 0.14, 4, 10]} />
          <primitive object={CYBER_MAT.red} attach="material" />
        </mesh>
        <mesh position={[0, -0.1, -0.02]}>
          <sphereGeometry args={[0.18, 12, 8, 0, Math.PI * 2, 0, Math.PI * 0.5]} />
          <primitive object={CYBER_MAT.red} attach="material" />
        </mesh>
      </group>

      {/* Jaw with lip-sync */}
      <group ref={jaw} position={[0, -0.26, 0.34]}>
        <mesh>
          <boxGeometry args={[0.3, 0.06, 0.1]} />
          <primitive object={CYBER_MAT.chrome} attach="material" />
        </mesh>
      </group>

      {/* Holo under-glow */}
      <mesh position={[0, -0.4, 0.4]} rotation={[Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.28, 0.33, 24]} />
        <primitive object={CYBER_MAT.cyan} attach="material" />
      </mesh>
    </group>
  );
}

function AvatarScene({ mode, audioLevel, interactive }: { mode: AvatarMode; audioLevel: number; interactive: boolean }) {
  const target = useRef<[number, number]>([0, 0]);
  const { pointer } = useThree();
  const { faceLookTarget } = useFaceTrackingContext();

  useFrame(() => {
    if (faceLookTarget.current[0] !== 0 || faceLookTarget.current[1] !== 0) {
      target.current = [smooth(faceLookTarget.current[0]), smooth(faceLookTarget.current[1])];
    } else if (interactive) {
      target.current = [smooth(pointer.x * 0.85), smooth(pointer.y * -0.45)];
    }
  });

  return (
    <>
      {/* v3.0.1 hotfix removed drei's <Environment preset="city" /> — it fetched an
          HDRI file from an external CDN (raw.githack.com) at runtime. When that
          fetch fails (offline first boot, restrictive network, CORS depending on
          the app's origin scheme, CDN downtime), the rejection is thrown outside
          Suspense's reach — only an ErrorBoundary catches a *rejected* loader, and
          none wrapped this Canvas, so the failure took down the entire React root
          (empirically reproduced: black screen, #root left completely empty).
          The existing manual lights below already give the cyberpunk look without
          any network dependency. */}
      <ambientLight intensity={0.7} />
      <directionalLight position={[3, 5, 4]} intensity={1.2} />
      <pointLight position={[-2.2, 1.2, 3]} intensity={1.8} color="#00E5FF" />
      <pointLight position={[2.0, -0.8, 2.2]} intensity={1.0} color="#FF1A1A" />
      <spotLight position={[0, 3, 2]} angle={0.4} penumbra={0.6} intensity={0.9} color="#fff7ed" />
      <CyborgHead target={target} mode={mode} audioLevel={audioLevel} isGreeting={mode === "greeting"} />
      {interactive && <OrbitControls enableZoom={false} enablePan={false} enableRotate={true} rotateSpeed={0.3} />}
    </>
  );
}

export default function CyberAvatar({
  mode = "idle",
  size = 320,
  interactive = true,
  faceTrack = false,
  audioLevel = 0,
  className = "",
  isGreeting = false,
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

  const face = useFaceTracking(faceTrack);
  const Provider = face.provider;

  const finalMode: AvatarMode = isGreeting ? "greeting" : mode;

  if (!webgl) {
    return (
      <motion.div
        initial={{ scale: 0.85, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className={`relative flex h-full w-full items-center justify-center ${className}`}
      >
        <div className="flex h-44 w-44 items-center justify-center rounded-full bg-gradient-to-br from-cyan-500/30 via-white/10 to-fuchsia-500/20 ring-1 ring-neon/40 shadow-neon-lg animate-float-y">
          <div className="flex h-24 w-24 items-center justify-center rounded-full bg-gradient-to-br from-white to-slate-200 ring-2 ring-neon/50 shadow-lg">
            <span className="text-4xl">G</span>
          </div>
        </div>
      </motion.div>
    );
  }

  return (
    <div className={`relative overflow-hidden rounded-[2rem] ${className}`} style={{ width: size, height: size }}>
      <div className="pointer-events-none absolute inset-0 -z-10 rounded-[2rem] bg-gradient-to-br from-cyan-500/12 via-transparent to-violet-500/10 blur-2xl" />
      <Provider>
        <Suspense fallback={<LoadingUI />}>
          <MemoizedSceneCanvas mode={finalMode} audioLevel={audioLevel} interactive={interactive} />
        </Suspense>
      </Provider>
      <div className="pointer-events-none absolute inset-0 rounded-[2rem] ring-1 ring-white/5" />
    </div>
  );
}