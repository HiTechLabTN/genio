import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Environment, OrbitControls, Text } from "@react-three/drei";
import * as THREE from "three";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { useFaceTracking, useFaceTrackingContext } from "./useFaceTracking";

/**
 * Pixar-Style Midjourney Cyborg — v2.2 Hotfix
 * White-ceramic / chrome + crimson Chachia (felt) + thick red cartoon beard + cape with golden G
 * Big anime eyes, PBR + Environment city for Pixar gloss
 */

type AvatarMode = "idle" | "listening" | "speaking";

export interface CyberAvatarProps {
  mode?: AvatarMode;
  size?: number;
  interactive?: boolean;
  faceTrack?: boolean;
  audioLevel?: number;
  className?: string;
}

function smooth(raw: number): number {
  return Math.max(-0.7, Math.min(0.7, raw));
}

interface HeadProps {
  target: React.MutableRefObject<[number, number]>;
  mode: AvatarMode;
  audioLevel: number;
}

function CyborgHead({ target, mode, audioLevel }: HeadProps) {
  const group = useRef<THREE.Group>(null);
  const jaw = useRef<THREE.Group>(null);
  const irisL = useRef<THREE.Mesh>(null);
  const irisR = useRef<THREE.Mesh>(null);
  const lidL = useRef<THREE.Mesh>(null);
  const lidR = useRef<THREE.Mesh>(null);

  const ceramicMat = useMemo(
    () =>
      new THREE.MeshPhysicalMaterial({
        color: "#ffffff",
        metalness: 0.08,
        roughness: 0.12,
        clearcoat: 1.0,
        clearcoatRoughness: 0.08,
        envMapIntensity: 1.4,
      }),
    []
  );
  const chromeMat = useMemo(
    () =>
      new THREE.MeshPhysicalMaterial({
        color: "#e8ecf1",
        metalness: 0.96,
        roughness: 0.15,
        clearcoat: 0.7,
        envMapIntensity: 1.2,
      }),
    []
  );
  const crimsonFeltMat = useMemo(
    () =>
      new THREE.MeshPhysicalMaterial({
        color: "#DC0A0A",
        roughness: 0.85,
        metalness: 0.05,
        clearcoat: 0.15,
        envMapIntensity: 0.6,
      }),
    []
  );
  const beardMat = useMemo(
    () =>
      new THREE.MeshPhysicalMaterial({
        color: "#E53935",
        roughness: 0.9,
        metalness: 0.0,
        clearcoat: 0.0,
      }),
    []
  );
  const capeMat = useMemo(
    () =>
      new THREE.MeshPhysicalMaterial({
        color: "#B91C1C",
        roughness: 0.45,
        metalness: 0.12,
        side: THREE.DoubleSide,
      }),
    []
  );
  const goldMat = useMemo(
    () =>
      new THREE.MeshPhysicalMaterial({
        color: "#FFD700",
        metalness: 0.85,
        roughness: 0.25,
        emissive: "#7A5A00",
        emissiveIntensity: 0.12,
        envMapIntensity: 1.0,
      }),
    []
  );
  const neonCyanMat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#00E5FF",
        emissive: "#00E5FF",
        emissiveIntensity: 1.3,
      }),
    []
  );

  useFrame(({ clock }) => {
    const g = group.current;
    if (!g) return;
    const t = clock.getElapsedTime();

    const breathe = Math.sin(t * 1.2) * 0.035 + Math.sin(t * 0.6) * 0.012;
    g.position.y = breathe;
    g.position.x = Math.sin(t * 0.85) * 0.018;

    const wantX = target.current[0];
    const wantY = target.current[1];
    g.rotation.y += (wantX - g.rotation.y) * 0.08;
    g.rotation.x += (wantY - g.rotation.x) * 0.08;
    g.rotation.z *= 0.92;

    const blinkPhase = t % 3.4;
    const isBlink = blinkPhase > 3.25;
    const lidScale = isBlink ? 0.02 : 1;
    if (lidL.current) lidL.current.scale.y = THREE.MathUtils.lerp(lidL.current.scale.y, lidScale, 0.35);
    if (lidR.current) lidR.current.scale.y = THREE.MathUtils.lerp(lidR.current.scale.y, lidScale, 0.35);

    // Iris micro-movement + glow pulse
    if (irisL.current && irisR.current) {
      const pulse = 0.95 + 0.12 * Math.sin(t * 2.0) + (mode === "speaking" ? 0.18 : 0);
      (irisL.current.material as THREE.MeshStandardMaterial).emissiveIntensity = pulse * 0.6;
      (irisR.current.material as THREE.MeshStandardMaterial).emissiveIntensity = pulse * 0.6;
    }

    if (jaw.current) {
      const level = mode === "speaking" ? Math.max(audioLevel, 0.28 + 0.38 * Math.abs(Math.sin(t * 7.5))) : audioLevel * 0.55;
      const open = THREE.MathUtils.clamp(level, 0, 1) * 0.32;
      jaw.current.position.y = -open;
      jaw.current.rotation.x = open * 0.55;
    }
  });

  return (
    <group ref={group}>
      {/* Crimson cape / hoodie with golden G */}
      <group position={[0, -0.38, -0.18]}>
        <mesh rotation={[0, 0, 0]}>
          <cylinderGeometry args={[0.52, 0.58, 0.72, 32, 1, true, Math.PI * 0.15, Math.PI * 1.7]} />
          <primitive object={capeMat} attach="material" />
        </mesh>
        {/* gold piping */}
        <mesh position={[0, 0.34, 0.02]}>
          <torusGeometry args={[0.51, 0.012, 10, 48, Math.PI * 1.7]} />
          <primitive object={goldMat} attach="material" />
        </mesh>
        {/* Golden G logo */}
        <Text
          position={[0, 0.05, 0.31]}
          fontSize={0.32}
          color="#FFD700"
          anchorX="center"
          anchorY="middle"
          outlineWidth={0.015}
          outlineColor="#7A5A00"
          font="https://fonts.gstatic.com/s/orbitron/v31/yMJRMgzdpvBhQQL_Qq7dy0e2.ttf"
        >
          G
        </Text>
        {/* Cape hood back */}
        <mesh position={[0, 0.28, -0.08]} rotation={[0.2, 0, 0]}>
          <sphereGeometry args={[0.55, 32, 16, 0, Math.PI * 2, 0, Math.PI * 0.45]} />
          <primitive object={capeMat} attach="material" />
        </mesh>
      </group>

      {/* Head dome ceramic */}
      <mesh position={[0, 0.12, 0]}>
        <sphereGeometry args={[0.66, 64, 64, 0, Math.PI * 2, 0, Math.PI * 0.62]} />
        <primitive object={ceramicMat} attach="material" />
      </mesh>
      {/* Lower face chrome */}
      <mesh position={[0, -0.22, 0.02]}>
        <capsuleGeometry args={[0.36, 0.30, 8, 32]} />
        <primitive object={chromeMat} attach="material" />
      </mesh>

      {/* Face plate black screen */}
      <mesh position={[0, 0.02, 0.52]}>
        <sphereGeometry args={[0.42, 32, 32, 0, Math.PI * 2, 0, Math.PI * 0.55]} />
        <meshStandardMaterial color="#0A0A0A" roughness={0.15} metalness={0.1} />
      </mesh>

      {/* Big anime eyes — white sclera + amber iris + highlight */}
      <group position={[0, 0.08, 0.56]}>
        {/* Left eye */}
        <group position={[-0.17, 0, 0]}>
          <mesh>
            <sphereGeometry args={[0.11, 32, 32]} />
            <meshStandardMaterial color="#ffffff" roughness={0.1} />
          </mesh>
          <mesh ref={irisL as unknown as React.RefObject<THREE.Mesh>} position={[0, 0, 0.07]}>
            <circleGeometry args={[0.065, 32]} />
            <meshStandardMaterial color="#8B4513" emissive="#FF1A1A" emissiveIntensity={0.25} />
          </mesh>
          <mesh position={[0.02, 0.02, 0.08]}>
            <circleGeometry args={[0.018, 16]} />
            <meshStandardMaterial color="#ffffff" emissive="#ffffff" emissiveIntensity={0.5} />
          </mesh>
          <mesh position={[0, 0, 0.075]}>
            <circleGeometry args={[0.025, 16]} />
            <meshStandardMaterial color="#000000" />
          </mesh>
          <mesh ref={lidL} position={[0, 0.03, 0.09]}>
            <sphereGeometry args={[0.115, 16, 16, 0, Math.PI * 2, 0, Math.PI * 0.5]} />
            <meshStandardMaterial color="#f5f5f5" />
          </mesh>
        </group>
        {/* Right eye */}
        <group position={[0.17, 0, 0]}>
          <mesh>
            <sphereGeometry args={[0.11, 32, 32]} />
            <meshStandardMaterial color="#ffffff" roughness={0.1} />
          </mesh>
          <mesh ref={irisR as unknown as React.RefObject<THREE.Mesh>} position={[0, 0, 0.07]}>
            <circleGeometry args={[0.065, 32]} />
            <meshStandardMaterial color="#8B4513" emissive="#FF1A1A" emissiveIntensity={0.25} />
          </mesh>
          <mesh position={[0.02, 0.02, 0.08]}>
            <circleGeometry args={[0.018, 16]} />
            <meshStandardMaterial color="#ffffff" emissive="#ffffff" emissiveIntensity={0.5} />
          </mesh>
          <mesh position={[0, 0, 0.075]}>
            <circleGeometry args={[0.025, 16]} />
            <meshStandardMaterial color="#000000" />
          </mesh>
          <mesh ref={lidR} position={[0, 0.03, 0.09]}>
            <sphereGeometry args={[0.115, 16, 16, 0, Math.PI * 2, 0, Math.PI * 0.5]} />
            <meshStandardMaterial color="#f5f5f5" />
          </mesh>
        </group>
        {/* eye red glow rim */}
        <mesh position={[-0.17, 0, -0.05]}>
          <ringGeometry args={[0.12, 0.135, 32]} />
          <meshStandardMaterial color="#FF1A1A" emissive="#FF1A1A" emissiveIntensity={0.8} transparent opacity={0.6} />
        </mesh>
        <mesh position={[0.17, 0, -0.05]}>
          <ringGeometry args={[0.12, 0.135, 32]} />
          <meshStandardMaterial color="#FF1A1A" emissive="#FF1A1A" emissiveIntensity={0.8} transparent opacity={0.6} />
        </mesh>
      </group>

      {/* Chachia felt — crimson with black tassel */}
      <group position={[0, 0.68, -0.02]}>
        <mesh>
          <cylinderGeometry args={[0.47, 0.49, 0.16, 48]} />
          <primitive object={crimsonFeltMat} attach="material" />
        </mesh>
        <mesh position={[0, 0.11, 0]}>
          <sphereGeometry args={[0.49, 48, 32, 0, Math.PI * 2, 0, Math.PI * 0.52]} />
          <primitive object={crimsonFeltMat} attach="material" />
        </mesh>
        {/* black tassel */}
        <group position={[0.28, 0.04, -0.05]} rotation={[0, 0, -0.3]}>
          <mesh position={[0, -0.06, 0]}>
            <cylinderGeometry args={[0.012, 0.012, 0.14, 12]} />
            <meshStandardMaterial color="#0A0A0A" />
          </mesh>
          <mesh position={[0, -0.14, 0]}>
            <coneGeometry args={[0.03, 0.08, 12]} />
            <meshStandardMaterial color="#0A0A0A" />
          </mesh>
        </group>
        {/* red top light bar (as in Midjourney image 2) */}
        <mesh position={[0, 0.06, 0.38]}>
          <boxGeometry args={[0.22, 0.04, 0.02]} />
          <meshStandardMaterial color="#FF1A1A" emissive="#FF1A1A" emissiveIntensity={1.2} />
        </mesh>
      </group>

      {/* Thick red cartoon beard & mustache */}
      <group position={[0, -0.14, 0.54]}>
        {/* Mustache — two thick fluffy lobes */}
        <mesh position={[-0.10, 0.04, 0]} rotation={[0.2, 0, 0.18]}>
          <capsuleGeometry args={[0.045, 0.18, 6, 16]} />
          <primitive object={beardMat} attach="material" />
        </mesh>
        <mesh position={[0.10, 0.04, 0]} rotation={[0.2, 0, -0.18]}>
          <capsuleGeometry args={[0.045, 0.18, 6, 16]} />
          <primitive object={beardMat} attach="material" />
        </mesh>
        {/* Beard — full fluffy volume */}
        <mesh position={[0, -0.14, -0.04]}>
          <sphereGeometry args={[0.24, 24, 16, 0, Math.PI * 2, 0, Math.PI * 0.6]} />
          <primitive object={beardMat} attach="material" />
        </mesh>
        <mesh position={[0, -0.20, 0.04]} rotation={[0.5, 0, 0]}>
          <capsuleGeometry args={[0.08, 0.22, 6, 16]} />
          <primitive object={beardMat} attach="material" />
        </mesh>
      </group>

      {/* Jaw with lip-sync */}
      <group ref={jaw} position={[0, -0.28, 0.38]}>
        <mesh>
          <boxGeometry args={[0.34, 0.07, 0.12]} />
          <primitive object={chromeMat} attach="material" />
        </mesh>
        <mesh position={[0, 0.025, 0.02]}>
          <boxGeometry args={[0.28, 0.014, 0.02]} />
          <meshStandardMaterial color="#eef2ff" />
        </mesh>
      </group>

      {/* Holo under-glow */}
      <mesh position={[0, -0.42, 0.48]} rotation={[Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.32, 0.36, 48]} />
        <primitive object={neonCyanMat} attach="material" />
      </mesh>
      <mesh position={[0, -0.62, -0.05]}>
        <cylinderGeometry args={[0.26, 0.30, 0.14, 32]} />
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
      <Environment preset="city" background={false} />
      <ambientLight intensity={0.7} />
      <directionalLight position={[3, 5, 4]} intensity={1.2} castShadow />
      <pointLight position={[-2.2, 1.2, 3]} intensity={1.8} color="#00E5FF" />
      <pointLight position={[2.0, -0.8, 2.2]} intensity={1.0} color="#FF1A1A" />
      <spotLight position={[0, 3, 2]} angle={0.4} penumbra={0.6} intensity={0.9} color="#fff7ed" />
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
        <Canvas dpr={[1, 1.6]} camera={{ position: [0, 0.18, 2.95], fov: 52 }} gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}>
          <AvatarScene mode={mode} audioLevel={audioLevel} interactive={interactive} />
        </Canvas>
      </Provider>
      <div className="pointer-events-none absolute inset-0 rounded-[2rem] ring-1 ring-white/5" />
    </div>
  );
}
