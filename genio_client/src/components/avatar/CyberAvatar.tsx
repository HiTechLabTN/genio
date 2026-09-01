import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { useFaceTracking, useFaceTrackingContext } from "./useFaceTracking";

/**
 * High-Fidelity 3D Cyber-Cyborg — Phase 3 overhaul.
 *
 * Chassis: polished white-ceramic / chrome skull (NOD32/iRobot) with cyan optics.
 * Heritage: precision-fitted metallic crimson Chachia (شاشية) with micro-texture.
 * Accents: neon-etched mustache & beard geometry.
 * Animation: look-at linked to face tracking, breathing, blinking, lip-sync.
 */

type AvatarMode = "idle" | "listening" | "speaking";

export interface CyberAvatarProps {
  mode?: AvatarMode;
  size?: number;
  interactive?: boolean;
  faceTrack?: boolean;
  audioLevel?: number; // 0..1 for lip-sync
  className?: string;
}

function smooth(raw: number): number {
  return Math.max(-0.7, Math.min(0.7, raw));
}

/* ------------------------------------------------------------------ */
/* Head geometry — high-fidelity cyborg                               */
/* ------------------------------------------------------------------ */

interface HeadProps {
  target: React.MutableRefObject<[number, number]>;
  mode: AvatarMode;
  audioLevel: number;
}

function CyborgHead({ target, mode, audioLevel }: HeadProps) {
  const group = useRef<THREE.Group>(null);
  const jaw = useRef<THREE.Group>(null);
  const eyeL = useRef<THREE.Mesh>(null);
  const eyeR = useRef<THREE.Mesh>(null);
  const lidL = useRef<THREE.Mesh>(null);
  const lidR = useRef<THREE.Mesh>(null);

  // Materials — physical ceramic/chrome
  const ceramicMat = useMemo(
    () =>
      new THREE.MeshPhysicalMaterial({
        color: "#fafafa",
        metalness: 0.15,
        roughness: 0.08,
        clearcoat: 1.0,
        clearcoatRoughness: 0.12,
        envMapIntensity: 1.2,
      }),
    []
  );
  const chromeMat = useMemo(
    () =>
      new THREE.MeshPhysicalMaterial({
        color: "#e8e8e8",
        metalness: 0.95,
        roughness: 0.18,
        clearcoat: 0.6,
      }),
    []
  );
  const crimsonMat = useMemo(() => {
    const m = new THREE.MeshStandardMaterial({
      color: "#a11a2f",
      metalness: 0.45,
      roughness: 0.35,
      emissive: "#3a0a12",
      emissiveIntensity: 0.08,
    });
    return m;
  }, []);
  const neonCyanMat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#22d3ee",
        emissive: "#22d3ee",
        emissiveIntensity: 1.4,
        metalness: 0.2,
        roughness: 0.2,
      }),
    []
  );
  const neonAmberMat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#f59e0b",
        emissive: "#f59e0b",
        emissiveIntensity: 1.0,
      }),
    []
  );

  useFrame(({ clock }) => {
    const g = group.current;
    if (!g) return;
    const t = clock.getElapsedTime();

    // Organic idle breathing — subtle vertical bob + micro-sway
    const breathe = Math.sin(t * 1.35) * 0.04 + Math.sin(t * 0.7) * 0.015;
    const sway = Math.sin(t * 0.9) * 0.02;
    g.position.y = breathe;
    g.position.x = sway * 0.5;

    // Look-at lerp damping
    const wantX = target.current[0];
    const wantY = target.current[1];
    g.rotation.y += (wantX - g.rotation.y) * 0.08;
    g.rotation.x += (wantY - g.rotation.x) * 0.08;
    // Slight head tilt stabilisation
    g.rotation.z *= 0.92;

    // Eye blinking — every ~3.5s close for 120ms
    const blinkPhase = t % 3.7;
    const isBlink = blinkPhase > 3.55;
    const lidScale = isBlink ? 0.05 : 1;
    if (lidL.current) lidL.current.scale.y = THREE.MathUtils.lerp(lidL.current.scale.y, lidScale, 0.3);
    if (lidR.current) lidR.current.scale.y = THREE.MathUtils.lerp(lidR.current.scale.y, lidScale, 0.3);

    // Eye glow pulse
    if (eyeL.current && eyeR.current) {
      const pulse = 0.9 + 0.15 * Math.sin(t * 2.2) + (mode === "speaking" ? 0.25 : 0);
      (eyeL.current.material as THREE.MeshStandardMaterial).emissiveIntensity = pulse;
      (eyeR.current.material as THREE.MeshStandardMaterial).emissiveIntensity = pulse;
    }

    // Lip-sync: jaw aperture driven by audioLevel or speaking mode fallback
    if (jaw.current) {
      const level = mode === "speaking" ? Math.max(audioLevel, 0.25 + 0.35 * Math.abs(Math.sin(t * 8))) : audioLevel * 0.6;
      const open = THREE.MathUtils.clamp(level, 0, 1) * 0.35;
      jaw.current.position.y = -open;
      jaw.current.rotation.x = open * 0.6;
    }
  });

  return (
    <group ref={group}>
      {/* Main cranium — polished ceramic dome split into upper/lower */}
      <mesh position={[0, 0.12, 0]}>
        <sphereGeometry args={[0.66, 64, 64, 0, Math.PI * 2, 0, Math.PI * 0.62]} />
        <primitive object={ceramicMat} attach="material" />
      </mesh>
      {/* Lower jaw chassis chrome */}
      <mesh position={[0, -0.22, 0.02]}>
        <capsuleGeometry args={[0.38, 0.32, 8, 32]} />
        <primitive object={chromeMat} attach="material" />
      </mesh>
      {/* Face plate — cheek panels */}
      <mesh position={[-0.52, -0.02, 0.18]} rotation={[0, 0.4, 0]}>
        <boxGeometry args={[0.08, 0.42, 0.32]} />
        <primitive object={chromeMat} attach="material" />
      </mesh>
      <mesh position={[0.52, -0.02, 0.18]} rotation={[0, -0.4, 0]}>
        <boxGeometry args={[0.08, 0.42, 0.32]} />
        <primitive object={chromeMat} attach="material" />
      </mesh>

      {/* Chachia — metallic crimson, precision-fitted */}
      <group position={[0, 0.68, -0.02]}>
        {/* base band micro-texture via torus */}
        <mesh>
          <cylinderGeometry args={[0.48, 0.50, 0.14, 48]} />
          <primitive object={crimsonMat} attach="material" />
        </mesh>
        {/* dome top */}
        <mesh position={[0, 0.10, 0]}>
          <sphereGeometry args={[0.50, 48, 32, 0, Math.PI * 2, 0, Math.PI * 0.52]} />
          <primitive object={crimsonMat} attach="material" />
        </mesh>
        {/* subtle brim etching band */}
        <mesh position={[0, 0.02, 0.02]}>
          <torusGeometry args={[0.49, 0.012, 12, 64]} />
          <primitive object={neonCyanMat} attach="material" />
        </mesh>
        {/* tiny tassel anchor */}
        <mesh position={[0.18, 0.08, 0.38]}>
          <sphereGeometry args={[0.03, 12, 12]} />
          <primitive object={neonAmberMat} attach="material" />
        </mesh>
      </group>

      {/* Optic eyes — illuminated cyan */}
      <group position={[0, 0.06, 0.52]}>
        <mesh ref={eyeL} position={[-0.19, 0, 0]}>
          <sphereGeometry args={[0.075, 24, 24]} />
          <primitive object={neonCyanMat} attach="material" />
        </mesh>
        <mesh ref={eyeR} position={[0.19, 0, 0]}>
          <sphereGeometry args={[0.075, 24, 24]} />
          <primitive object={neonCyanMat} attach="material" />
        </mesh>
        {/* eyelids for blink */}
        <mesh ref={lidL} position={[-0.19, 0.02, 0.06]}>
          <sphereGeometry args={[0.08, 16, 16, 0, Math.PI * 2, 0, Math.PI * 0.5]} />
          <meshStandardMaterial color="#fafafa" metalness={0.1} roughness={0.2} />
        </mesh>
        <mesh ref={lidR} position={[0.19, 0.02, 0.06]}>
          <sphereGeometry args={[0.08, 16, 16, 0, Math.PI * 2, 0, Math.PI * 0.5]} />
          <meshStandardMaterial color="#fafafa" metalness={0.1} roughness={0.2} />
        </mesh>
        {/* eye rim glow */}
        <mesh position={[-0.19, 0, -0.02]}>
          <ringGeometry args={[0.085, 0.095, 32]} />
          <primitive object={neonCyanMat} attach="material" />
        </mesh>
        <mesh position={[0.19, 0, -0.02]}>
          <ringGeometry args={[0.085, 0.095, 32]} />
          <primitive object={neonCyanMat} attach="material" />
        </mesh>
      </group>

      {/* Nose bridge chrome accent */}
      <mesh position={[0, -0.04, 0.58]}>
        <boxGeometry args={[0.06, 0.14, 0.04]} />
        <primitive object={chromeMat} attach="material" />
      </mesh>

      {/* Neon-etched mustache & beard geometry */}
      <group position={[0, -0.18, 0.52]}>
        {/* mustache — two curved bars */}
        <mesh position={[-0.11, 0.02, 0]} rotation={[0, 0, 0.25]}>
          <capsuleGeometry args={[0.018, 0.14, 4, 16]} />
          <primitive object={neonCyanMat} attach="material" />
        </mesh>
        <mesh position={[0.11, 0.02, 0]} rotation={[0, 0, -0.25]}>
          <capsuleGeometry args={[0.018, 0.14, 4, 16]} />
          <primitive object={neonCyanMat} attach="material" />
        </mesh>
        {/* beard — jawline etched frame */}
        <mesh position={[0, -0.10, -0.02]}>
          <torusGeometry args={[0.22, 0.016, 8, 32, Math.PI]} />
          <primitive object={neonCyanMat} attach="material" />
        </mesh>
        <mesh position={[-0.16, -0.06, 0]} rotation={[0.4, 0.6, 0]}>
          <boxGeometry args={[0.02, 0.12, 0.02]} />
          <primitive object={neonCyanMat} attach="material" />
        </mesh>
        <mesh position={[0.16, -0.06, 0]} rotation={[0.4, -0.6, 0]}>
          <boxGeometry args={[0.02, 0.12, 0.02]} />
          <primitive object={neonCyanMat} attach="material" />
        </mesh>
      </group>

      {/* Articulated jaw group for lip-sync */}
      <group ref={jaw} position={[0, -0.28, 0.38]}>
        <mesh>
          <boxGeometry args={[0.38, 0.08, 0.14]} />
          <primitive object={chromeMat} attach="material" />
        </mesh>
        {/* teeth row */}
        <mesh position={[0, 0.025, 0.02]}>
          <boxGeometry args={[0.30, 0.015, 0.02]} />
          <meshStandardMaterial color="#eef2ff" emissive="#22d3ee" emissiveIntensity={0.15} />
        </mesh>
        {/* chin neon edge */}
        <mesh position={[0, -0.03, 0.06]}>
          <boxGeometry args={[0.28, 0.015, 0.02]} />
          <primitive object={neonCyanMat} attach="material" />
        </mesh>
      </group>

      {/* Holo under-glow rim */}
      <mesh position={[0, -0.38, 0.48]} rotation={[Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.32, 0.36, 48]} />
        <primitive object={neonCyanMat} attach="material" />
      </mesh>
      {/* Neck collar */}
      <mesh position={[0, -0.62, -0.05]}>
        <cylinderGeometry args={[0.28, 0.32, 0.18, 32]} />
        <primitive object={chromeMat} attach="material" />
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
      <ambientLight intensity={0.65} />
      <directionalLight position={[3, 5, 4]} intensity={1.15} castShadow />
      <pointLight position={[-2.2, 1.2, 3]} intensity={1.6} color="#22d3ee" />
      <pointLight position={[2.0, -0.8, 2.2]} intensity={0.9} color="#a855f7" />
      <spotLight position={[0, 3, 2]} angle={0.4} penumbra={0.6} intensity={0.8} color="#fff7ed" />
      <CyborgHead target={target} mode={mode} audioLevel={audioLevel} />
      {interactive && <OrbitControls enableZoom={false} enablePan={false} enableRotate={true} rotateSpeed={0.3} />}
    </>
  );
}

export default function CyberAvatar({ mode = "idle", size = 320, interactive = true, faceTrack = false, audioLevel = 0, className = "" }: CyberAvatarProps) {
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

  if (!webgl) {
    return (
      <motion.div
        initial={{ scale: 0.85, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className={`relative flex h-full w-full items-center justify-center ${className}`}
      >
        <div className="flex h-44 w-44 items-center justify-center rounded-full bg-gradient-to-br from-cyan-500/30 via-white/10 to-fuchsia-500/20 ring-1 ring-neon/40 shadow-neon-lg animate-float-y">
          <div className="flex h-24 w-24 items-center justify-center rounded-full bg-gradient-to-br from-white to-slate-200 ring-2 ring-neon/50 shadow-lg">
            <span className="text-4xl text-neon">◉</span>
          </div>
        </div>
      </motion.div>
    );
  }

  return (
    <div className={`relative overflow-hidden rounded-[2rem] ${className}`} style={{ width: size, height: size }}>
      <div className="pointer-events-none absolute inset-0 -z-10 rounded-[2rem] bg-gradient-to-br from-neon/12 via-transparent to-violet-500/10 blur-2xl" />
      <div className="pointer-events-none absolute inset-0 -z-10 bg-grid-neon opacity-[0.04]" />
      <Provider>
        <Canvas dpr={[1, 1.6]} camera={{ position: [0, 0.18, 2.95], fov: 52 }} gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}>
          <AvatarScene mode={mode} audioLevel={audioLevel} interactive={interactive} />
        </Canvas>
      </Provider>
      {/* subtle vignette */}
      <div className="pointer-events-none absolute inset-0 rounded-[2rem] ring-1 ring-white/5" />
    </div>
  );
}
