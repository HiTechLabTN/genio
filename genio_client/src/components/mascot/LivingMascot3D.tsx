import { memo, useEffect, useRef, useState, Suspense } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { useFaceTrackingContext } from "../avatar/useFaceTracking";
import HologramMascot from "./HologramMascot";

type Status = "idle" | "listening" | "thinking" | "executing" | "answering" | "completed" | string;

interface Props {
  status: Status;
  audioLevel?: number;
  className?: string;
}

function LivingSceneInner({ status, audioLevel = 0 }: { status: Status; audioLevel: number }) {
  const group = useRef<THREE.Group>(null);
  const head = useRef<THREE.Group>(null);
  const leftEye = useRef<THREE.Mesh>(null);
  const rightEye = useRef<THREE.Mesh>(null);
  const jaw = useRef<THREE.Group>(null);
  const beard = useRef<THREE.Group>(null);
  const tassel = useRef<THREE.Group>(null);
  const leftArm = useRef<THREE.Group>(null);
  const rightArm = useRef<THREE.Group>(null);
  const { faceLookTarget } = useFaceTrackingContext();
  const { camera, raycaster, pointer } = useThree();
  const [blink, setBlink] = useState(false);
  const [surprised, setSurprised] = useState(false);
  const [proud, setProud] = useState(false);
  const [waveBack, setWaveBack] = useState(false);
  const [jump, setJump] = useState(false);
  const lastTap = useRef(0);
  const sparkRef = useRef<THREE.Group>(null);

  // Blink 3-6s random (120ms)
  useEffect(() => {
    let tm: number;
    function schedule() {
      const delay = 3000 + Math.random() * 3000;
      tm = window.setTimeout(() => {
        setBlink(true);
        window.setTimeout(() => setBlink(false), 120);
        schedule();
      }, delay) as unknown as number;
    }
    schedule();
    return () => { clearTimeout(tm); };
  }, []);

  // Idle look-around 4-7s when no face tracking
  const idleLook = useRef({ x: 0, y: 0, t: 0 });
  useEffect(() => {
    const id = window.setInterval(() => {
      if (status === "idle" && !faceLookTarget.current[0] && !faceLookTarget.current[1]) {
        idleLook.current = { x: (Math.random() - 0.5) * 0.5, y: (Math.random() - 0.5) * 0.3, t: performance.now() };
      }
    }, 4500);
    return () => clearInterval(id);
  }, [status]);

  // Touch reactions via raycast
  const onPointerDown = (_e: PointerEvent) => {
    // double-tap → jump + sparks
    const now = Date.now();
    if (now - lastTap.current < 300) {
      setJump(true);
      window.setTimeout(() => setJump(false), 600);
      if (sparkRef.current) {
        sparkRef.current.visible = true;
        window.setTimeout(() => { if (sparkRef.current) sparkRef.current.visible = false; }, 600);
      }
      return;
    }
    lastTap.current = now;

    // raycast
    raycaster.setFromCamera(pointer, camera);
    const intersects = raycaster.intersectObjects(group.current?.children || [], true);
    if (!intersects.length) return;
    const obj = intersects[0].object;
    let name = (obj as unknown as { name?: string }).name || obj.parent?.name || "";
    // fallback to position-based: head is upper, belly is middle, hand is outer
    const pt = intersects[0].point;
    if (!name) {
      if (pt.y > 0.2) name = "head";
      else if (pt.y > -0.3 && Math.abs(pt.x) < 0.25) name = "belly";
      else if (Math.abs(pt.x) > 0.3) name = "hand";
    }
    if (name.includes("head") || pt.y > 0.2) {
      setSurprised(true);
      window.setTimeout(() => setSurprised(false), 600);
    } else if (name.includes("belly") || (pt.y > -0.3 && pt.y < 0.1)) {
      setProud(true);
      window.setTimeout(() => setProud(false), 700);
    } else if (name.includes("hand") || name.includes("arm")) {
      setWaveBack(true);
      window.setTimeout(() => setWaveBack(false), 800);
    }
  };

  useEffect(() => {
    const canvas = document.querySelector("canvas");
    if (!canvas) return;
    canvas.addEventListener("pointerdown", onPointerDown as unknown as EventListener);
    return () => canvas.removeEventListener("pointerdown", onPointerDown as unknown as EventListener);
  });

  // Pose targets per status (lerp/spring in useFrame)
  const pose = (() => {
    switch (status) {
      case "listening": return { headY: 0.12, lean: 0.18, leftArm: { x: -0.45, z: 0.9 }, rightArm: { x: 0.38, z: -0.6 }, eyesUp: false };
      case "thinking": return { headY: 0.08, lean: -0.1, leftArm: { x: -0.2, z: 0.4 }, rightArm: { x: 0.22, z: 0.45 }, eyesUp: true };
      case "executing": return { headY: 0, lean: 0.05, leftArm: { x: -0.6, z: 0 }, rightArm: { x: 0.55, z: 0.15 }, eyesUp: false };
      case "answering": return { headY: 0, lean: 0, leftArm: { x: -0.35, z: -0.2 }, rightArm: { x: 0.35, z: 0.2 }, eyesUp: false };
      case "completed": return { headY: 0, lean: 0, leftArm: { x: -0.5, z: -0.8 }, rightArm: { x: 0.5, z: 0.8 }, eyesUp: false };
      default: return { headY: 0, lean: 0, leftArm: { x: -0.1, z: 0 }, rightArm: { x: 0.1, z: 0 }, eyesUp: false };
    }
  })();

  useFrame(({ clock }) => {
    if (document.hidden) return;
    const g = group.current;
    if (!g) return;
    const t = clock.getElapsedTime();

    // Breathing body scaleY ±.015 @4.5s
    const breath = Math.sin(t * (Math.PI * 2 / 4.5)) * 0.015;
    g.scale.y = 1 + breath;
    g.position.y = Math.sin(t * 1.396) * 0.045 + (jump ? Math.sin(t * 12) * 0.18 : 0);

    // Eyes track user: reuse useFaceTracking → lerp eyes + head ±10°
    const tx = faceLookTarget.current[0] || idleLook.current.x;
    const ty = faceLookTarget.current[1] || idleLook.current.y;
    const hx = THREE.MathUtils.lerp(head.current?.rotation.x ?? 0, ty * 0.18 + (pose.eyesUp ? -0.18 : 0) + pose.lean, 0.08);
    const hy = THREE.MathUtils.lerp(head.current?.rotation.y ?? 0, tx * 0.18, 0.08);
    if (head.current) { head.current.rotation.x = hx; head.current.rotation.y = hy; }
    if (leftEye.current) { leftEye.current.position.x = THREE.MathUtils.lerp(leftEye.current.position.x, tx * 0.07, 0.12); leftEye.current.position.y = THREE.MathUtils.lerp(leftEye.current.position.y, -ty * 0.05, 0.12); }
    if (rightEye.current) { rightEye.current.position.x = THREE.MathUtils.lerp(rightEye.current.position.x, tx * 0.07, 0.12); rightEye.current.position.y = THREE.MathUtils.lerp(rightEye.current.position.y, -ty * 0.05, 0.12); }

    // Blink
    const eyeScaleY = blink || surprised ? 0.08 : 1;
    if (leftEye.current) leftEye.current.scale.y = THREE.MathUtils.lerp(leftEye.current.scale.y, eyeScaleY, 0.35);
    if (rightEye.current) rightEye.current.scale.y = THREE.MathUtils.lerp(rightEye.current.scale.y, eyeScaleY, 0.35);

    // Surprised eyes wide
    if (surprised && leftEye.current && rightEye.current) {
      leftEye.current.scale.x = THREE.MathUtils.lerp(leftEye.current.scale.x, 1.18, 0.2);
      rightEye.current.scale.x = THREE.MathUtils.lerp(rightEye.current.scale.x, 1.18, 0.2);
    } else if (leftEye.current && rightEye.current) {
      leftEye.current.scale.x = THREE.MathUtils.lerp(leftEye.current.scale.x, 1, 0.15);
      rightEye.current.scale.x = THREE.MathUtils.lerp(rightEye.current.scale.x, 1, 0.15);
    }

    // Tassel spring sway
    if (tassel.current) {
      tassel.current.rotation.z = Math.sin(t * 2.1) * 0.22 + Math.sin(t * 0.9) * 0.12;
      tassel.current.position.x = Math.sin(t * 1.7) * 0.04;
    }

    // Beard/mustache wiggle when proud
    if (beard.current && proud) {
      beard.current.position.x = Math.sin(t * 18) * 0.012;
    }

    // Arms lerp to pose targets
    if (leftArm.current) {
      const target = waveBack && status !== "completed" ? { x: -0.52, z: -0.9 } : pose.leftArm;
      leftArm.current.rotation.z = THREE.MathUtils.lerp(leftArm.current.rotation.z, target.z, 0.12);
      leftArm.current.rotation.x = THREE.MathUtils.lerp(leftArm.current.rotation.x, target.x, 0.12);
    }
    if (rightArm.current) {
      const target = waveBack ? { x: 0.52, z: 0.9 } : pose.rightArm;
      rightArm.current.rotation.z = THREE.MathUtils.lerp(rightArm.current.rotation.z, target.z, 0.12);
      rightArm.current.rotation.x = THREE.MathUtils.lerp(rightArm.current.rotation.x, target.x, 0.12);
    }

    // Jaw lip-sync by audioLevel
    if (jaw.current) {
      const open = Math.min(1, audioLevel) * 0.22 + (status === "answering" ? Math.abs(Math.sin(t * 7.5)) * 0.06 : 0);
      jaw.current.position.y = THREE.MathUtils.lerp(jaw.current.position.y, -open, 0.22);
    }
  });

  return (
    <group ref={group} position={[0, -0.1, 0]}>
      {/* Body — crimson jebba capsule + gold sfifa strips + G emblem */}
      <mesh position={[0, -0.35, 0]}>
        <capsuleGeometry args={[0.32, 0.55, 8, 16]} />
        <meshStandardMaterial color="#8B0F1A" roughness={0.7} metalness={0.05} />
      </mesh>
      {/* gold sfifa strips */}
      <mesh position={[-0.08, -0.35, 0.16]}>
        <planeGeometry args={[0.04, 0.55]} />
        <meshStandardMaterial color="#FFD700" roughness={0.35} metalness={0.5} side={THREE.DoubleSide} />
      </mesh>
      <mesh position={[0.08, -0.35, 0.16]}>
        <planeGeometry args={[0.04, 0.55]} />
        <meshStandardMaterial color="#FFD700" roughness={0.35} metalness={0.5} side={THREE.DoubleSide} />
      </mesh>
      {/* G emblem */}
      <mesh position={[0, -0.18, 0.32]}>
        <cylinderGeometry args={[0.09, 0.09, 0.02, 24]} />
        <meshStandardMaterial color="#FFD700" roughness={0.3} metalness={0.85} />
      </mesh>

      {/* Head — white ceramic sphere */}
      <group ref={head} position={[0, 0.42, 0]}>
        <mesh>
          <sphereGeometry args={[0.34, 32, 32]} />
          <meshStandardMaterial color="#F8F9FA" roughness={0.35} metalness={0.04} />
        </mesh>
        {/* visor maroon glossy */}
        <mesh position={[0, 0.02, 0.22]}>
          <sphereGeometry args={[0.26, 24, 16, 0, Math.PI * 2, 0, Math.PI * 0.55]} />
          <meshStandardMaterial color="#4A0A0A" roughness={0.18} metalness={0.3} transparent opacity={0.96} />
        </mesh>
        {/* AMBER eyes — movable + blinkable */}
        <mesh ref={leftEye} position={[-0.11, 0.04, 0.28]} name="eyeL">
          <sphereGeometry args={[0.052, 16, 16]} />
          <meshStandardMaterial color="#FF8C00" roughness={0.2} metalness={0.1} emissive="#FF8C00" emissiveIntensity={0.45} />
        </mesh>
        <mesh ref={rightEye} position={[0.11, 0.04, 0.28]} name="eyeR">
          <sphereGeometry args={[0.052, 16, 16]} />
          <meshStandardMaterial color="#FF8C00" roughness={0.2} metalness={0.1} emissive="#FF8C00" emissiveIntensity={0.45} />
        </mesh>
        {/* pupils */}
        <mesh position={[-0.11, 0.04, 0.305]}>
          <sphereGeometry args={[0.022, 12, 12]} />
          <meshStandardMaterial color="#000000" />
        </mesh>
        <mesh position={[0.11, 0.04, 0.305]}>
          <sphereGeometry args={[0.022, 12, 12]} />
          <meshStandardMaterial color="#000000" />
        </mesh>
        {/* jaw for lip-sync */}
        <group ref={jaw} position={[0, -0.14, 0.18]}>
          <mesh>
            <boxGeometry args={[0.18, 0.06, 0.08]} />
            <meshStandardMaterial color="#E8E8E8" />
          </mesh>
        </group>
        {/* Chachia cone red */}
        <mesh position={[0, 0.38, 0]} rotation={[0, 0, 0]}>
          <coneGeometry args={[0.22, 0.26, 24]} />
          <meshStandardMaterial color="#B91C1C" roughness={0.6} />
        </mesh>
        {/* tassel chain black spheres with spring sway */}
        <group ref={tassel} position={[0.14, 0.42, 0]}>
          <mesh position={[0, -0.04, 0]}>
            <sphereGeometry args={[0.03, 8, 8]} />
            <meshStandardMaterial color="#0A0A0A" />
          </mesh>
          <mesh position={[0, -0.10, 0]}>
            <sphereGeometry args={[0.028, 8, 8]} />
            <meshStandardMaterial color="#0A0A0A" />
          </mesh>
          <mesh position={[0, -0.16, 0]}>
            <sphereGeometry args={[0.025, 8, 8]} />
            <meshStandardMaterial color="#0A0A0A" />
          </mesh>
        </group>
        {/* Beard/mustache fluffy red — scaled spheres */}
        <group ref={beard} position={[0, -0.12, 0.26]}>
          <mesh position={[0, -0.04, 0]}>
            <sphereGeometry args={[0.14, 12, 8]} />
            <meshStandardMaterial color="#DC2626" roughness={0.9} flatShading />
          </mesh>
          <mesh position={[0, 0.02, 0.02]}>
            <sphereGeometry args={[0.09, 10, 8]} />
            <meshStandardMaterial color="#DC2626" roughness={0.9} flatShading />
          </mesh>
        </group>
      </group>

      {/* Arms — capsule with pose targets */}
      <group ref={leftArm} position={[-0.42, -0.28, 0]}>
        <mesh>
          <capsuleGeometry args={[0.07, 0.38, 6, 12]} />
          <meshStandardMaterial color="#8B0F1A" />
        </mesh>
        <mesh position={[0, -0.26, 0]}>
          <sphereGeometry args={[0.07, 10, 10]} />
          <meshStandardMaterial color="#E8E8E8" />
        </mesh>
      </group>
      <group ref={rightArm} position={[0.42, -0.28, 0]}>
        <mesh>
          <capsuleGeometry args={[0.07, 0.38, 6, 12]} />
          <meshStandardMaterial color="#8B0F1A" />
        </mesh>
        <mesh position={[0, -0.26, 0]}>
          <sphereGeometry args={[0.07, 10, 10]} />
          <meshStandardMaterial color="#E8E8E8" />
        </mesh>
      </group>

      {/* spark particles for double-tap jump */}
      <group ref={sparkRef} visible={false}>
        {Array.from({ length: 8 }, (_, i) => (
          <mesh key={i} position={[(Math.random() - 0.5) * 0.9, -0.6 + Math.random() * 0.4, 0.2]}>
            <sphereGeometry args={[0.02, 6, 6]} />
            <meshStandardMaterial color="#FFD700" emissive="#FFD700" emissiveIntensity={1} />
          </mesh>
        ))}
      </group>
    </group>
  );
}

const LivingMascot3D = memo(function LivingMascot3D({ status, audioLevel = 0 }: Props) {
  const [tier, setTier] = useState<"high" | "low">("high");
  const [webglFailed, setWebglFailed] = useState(false);
  const isCoarse = typeof window !== "undefined" && window.matchMedia?.("(pointer: coarse)")?.matches;

  useEffect(() => {
    try {
      const canvas = document.createElement("canvas");
      const gl = (canvas.getContext("webgl") || canvas.getContext("experimental-webgl")) as WebGLRenderingContext | null;
      if (!gl) setWebglFailed(true);
      const texSize = gl?.getParameter(gl?.MAX_TEXTURE_SIZE) as number | undefined;
      if (texSize && texSize < 2048) setTier("low");
      // also check device memory
      // @ts-ignore
      const mem = navigator.deviceMemory;
      if (typeof mem === "number" && mem <= 2) setTier("low");
    } catch {
      setWebglFailed(true);
    }
  }, []);

  if (tier === "low" || webglFailed) {
    // auto-fallback to 2D HologramMascot — same h-[35vh] zone, never crash
    return (
      <div className="absolute z-10 flex h-[35vh] w-full items-center justify-center left-1/2 top-[72px] -translate-x-1/2 md:top-[80px]">
        <HologramMascot status={status} audioLevel={audioLevel} isMinimized={status === "answering"} />
      </div>
    );
  }

  return (
    <Canvas
      dpr={[1, isCoarse ? 1.2 : 1.5] as unknown as [number, number]}
      camera={{ position: [0, 0.9, 3.2], fov: 38 }}
      gl={{ antialias: !isCoarse, alpha: true, powerPreference: "high-performance" }}
      onCreated={({ gl }) => {
        // pause frameloop on hidden
        const onVis = () => {
          if (document.hidden) gl.setAnimationLoop(null);
          else gl.setAnimationLoop(null); // R3F handles loop internally, we just avoid rendering
        };
        document.addEventListener("visibilitychange", onVis);
      }}
      style={{ position: "absolute", inset: 0, zIndex: 1 }}
      onError={() => setWebglFailed(true)}
    >
      <Suspense fallback={null}>
        <ambientLight intensity={0.85} />
        <directionalLight position={[2, 3, 2]} intensity={0.9} />
        <pointLight position={[-2, 1, 2]} color="#00E5FF" intensity={0.6} />
        <pointLight position={[2, -0.5, -1]} color="#FFD700" intensity={0.45} />
        {/* Andalusian lattice light glow pulse */}
        <color attach="background" args={["#0a0e1a"]} />
        <LivingSceneInner status={status} audioLevel={audioLevel} />
        {/* radial light beam sprite behind mascot */}
        <mesh position={[0, -0.2, -0.6]}>
          <planeGeometry args={[3.2, 3.2]} />
          <meshBasicMaterial color="#22d3ee" transparent opacity={0.25} blending={THREE.AdditiveBlending} depthWrite={false} />
        </mesh>
      </Suspense>
    </Canvas>
  );
});

export default LivingMascot3D;
