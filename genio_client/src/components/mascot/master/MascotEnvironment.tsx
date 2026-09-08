/**
 * MascotEnvironment — procedural Genio stage (§3, §22).
 * Dark void #020B1E, cyan rim + gold accent + red fill lights, holographic
 * rings under feet, lightweight particle field, fog. No baked textures.
 * Reacts subtly to mascot state (thinking/speaking/success/error/idle).
 */
import { memo, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

export type EnvMood = "idle" | "thinking" | "speaking" | "success" | "error" | "warm";

function Rings({ mood, reduced }: { mood: EnvMood; reduced: boolean }) {
  const g1 = useRef<THREE.Group>(null);
  const g2 = useRef<THREE.Group>(null);
  const color = mood === "success" || mood === "warm" ? "#FFD700" : mood === "error" ? "#f87171" : "#00E5FF";
  useFrame((_, dt) => {
    if (reduced) return;
    const s = Math.min(dt, 0.05);
    if (g1.current) g1.current.rotation.z += s * (mood === "thinking" ? 0.25 : 0.6);
    if (g2.current) g2.current.rotation.z -= s * (mood === "thinking" ? 0.35 : 0.9);
  });
  const pulse = mood === "success" ? 1.25 : 1;
  return (
    <group position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <group ref={g1}>
        <mesh>
          <ringGeometry args={[0.55 * pulse, 0.62 * pulse, 64]} />
          <meshBasicMaterial color={color} transparent opacity={0.75} side={THREE.DoubleSide} />
        </mesh>
      </group>
      <group ref={g2}>
        <mesh>
          <ringGeometry args={[0.34, 0.38, 48]} />
          <meshBasicMaterial color="#ffffff" transparent opacity={0.5} side={THREE.DoubleSide} />
        </mesh>
      </group>
      <mesh>
        <circleGeometry args={[0.2, 32]} />
        <meshBasicMaterial color={color} transparent opacity={0.28} />
      </mesh>
    </group>
  );
}

function Particles({ reduced, count = 260 }: { reduced: boolean; count?: number }) {
  const ref = useRef<THREE.Points>(null);
  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      arr[i * 3] = (Math.random() - 0.5) * 8;
      arr[i * 3 + 1] = Math.random() * 3.2;
      arr[i * 3 + 2] = (Math.random() - 0.5) * 8;
    }
    return arr;
  }, [count]);
  useFrame(({ clock }) => {
    if (reduced || !ref.current) return;
    ref.current.rotation.y = clock.getElapsedTime() * 0.015;
  });
  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial color="#67e8f9" size={0.02} transparent opacity={0.55} sizeAttenuation depthWrite={false} />
    </points>
  );
}

const MascotEnvironment = memo(function MascotEnvironment({
  mood = "idle",
  reducedMotion = false,
  audioLevel = 0,
}: {
  mood?: EnvMood;
  reducedMotion?: boolean;
  audioLevel?: number;
}) {
  const warm = mood === "success" || mood === "warm";
  return (
    <group>
      <fog attach="fog" args={["#020B1E", 4.5, 11]} />
      {/* studio key + gold accent + cyan rim + red jebba fill */}
      <ambientLight intensity={0.55} />
      <directionalLight position={[2.2, 3.6, 2.4]} intensity={1.6} color="#fff4e0" />
      <directionalLight position={[-2.6, 1.6, -1.8]} intensity={1.1} color="#00E5FF" />
      <directionalLight position={[0, 2.2, -2.5]} intensity={warm ? 1.4 : 0.7} color="#FFD700" />
      <directionalLight position={[1.5, 0.6, 2.2]} intensity={0.5} color="#ef4444" />
      <pointLight position={[0, 1.9, 0.6]} intensity={0.5 + audioLevel * 1.4} color="#67e8f9" />
      <Rings mood={mood} reduced={reducedMotion} />
      <Particles reduced={reducedMotion} />
      {/* ground glow disc */}
      <mesh position={[0, 0.005, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.85, 48]} />
        <meshBasicMaterial color={warm ? "#FFD700" : "#00E5FF"} transparent opacity={warm ? 0.14 : 0.1} depthWrite={false} />
      </mesh>
    </group>
  );
});

export default MascotEnvironment;
