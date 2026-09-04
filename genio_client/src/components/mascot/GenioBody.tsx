import { memo, useRef, useState, useEffect, Suspense } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useGLTF, Bounds, ContactShadows } from "@react-three/drei";
import { Physics, RigidBody, CuboidCollider } from "@react-three/rapier";
import * as THREE from "three";
import { useFaceTrackingContext } from "../avatar/useFaceTracking";

type Status = string;

interface Props {
  status: Status;
  audioLevel?: number;
  gestureHint?: string;
}

// Charter-driven physics + creativity (S4)
const WALK_SPEED = 1.4; // m/s
const GRAVITY = -9.81;

// S7: query composer with Gemini gesture_hint forwarded
async function fetchGesturePlan(context: string, emotion: string, hint?: string) {
  const charterFallback = { head: { tilt: 0, nod: 0, blink: false }, hands: [], mouth: 0, body: "idle" };
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 1500);
    const res = await fetch("http://localhost:8001/compose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ context: hint ? `${context} hint:${hint}` : context, emotion, user_id: localStorage.getItem("genio:user:id") || "anon", user_prefs: {} }),
      signal: ctrl.signal,
    });
    clearTimeout(t);
    if (res.ok) {
      const data = await res.json();
      return data.gesture_plan || charterFallback;
    }
  } catch {}
  // charter fallback
  try {
    const r = await fetch("/assets/movement_charter.json");
    if (r.ok) return charterFallback;
  } catch {}
  return charterFallback;
}

function useTier() {
  const [tier, setTier] = useState<"high" | "low">("high");
  useEffect(() => {
    try {
      const canvas = document.createElement("canvas");
      const gl = (canvas.getContext("webgl") || canvas.getContext("experimental-webgl")) as WebGLRenderingContext | null;
      if (!gl) setTier("low");
      const texSize = gl?.getParameter(gl?.MAX_TEXTURE_SIZE) as number | undefined;
      if (texSize && texSize < 2048) setTier("low");
      // @ts-ignore
      const mem = navigator.deviceMemory;
      if (typeof mem === "number" && mem <= 2) setTier("low");
      // desktop flag genio:body:3d
      const isCoarse = window.matchMedia?.("(pointer: coarse)")?.matches;
      const flag = localStorage.getItem("genio:body:3d");
      if (flag === "off") setTier("low");
      else if (isCoarse && mem && mem <= 4) setTier("low");
      else if (!isCoarse) {
        // desktop on by default per spec
        if (flag !== "off") setTier("high");
      }
    } catch {
      setTier("low");
    }
  }, []);
  return tier;
}

function GenioModel({ status, audioLevel = 0, position, rotation, gestureHint }: { status: Status; audioLevel: number; position: THREE.Vector3; rotation: number; gestureHint?: string }) {
  const { scene } = useGLTF("/media/rig/mascot_rigged.glb") as unknown as { scene: THREE.Group };
  const group = useRef<THREE.Group>(null);
  const headRef = useRef<THREE.Bone | null>(null);
  const jawRef = useRef<THREE.Bone | null>(null);
  const { faceLookTarget } = useFaceTrackingContext();
  const [blink, setBlink] = useState(false);
  const walkRef = useRef(0);
  const breathRef = useRef(0);
  const [gesturePlan, setGesturePlan] = useState<{ head: { tilt: number; nod: number; blink: boolean }; hands: { joint: string; angle: number }[]; mouth: number; body: string } | null>(null);
  // S7: query composer with Gemini hint
  useEffect(() => {
    let alive = true;
    fetchGesturePlan(status, status, gestureHint).then((plan) => {
      if (alive) setGesturePlan(plan);
    });
    return () => {
      alive = false;
    };
  }, [status, gestureHint]);

  // Find head/jaw bones if rigged
  useEffect(() => {
    scene.traverse((obj) => {
      if ((obj as THREE.Bone).isBone) {
        const name = obj.name.toLowerCase();
        if (name.includes("head") && !headRef.current) headRef.current = obj as THREE.Bone;
        if (name.includes("jaw") && !jawRef.current) jawRef.current = obj as THREE.Bone;
      }
    });
    // Clone scene for instance
  }, [scene]);

  // blink 3-6s
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
    return () => clearTimeout(tm);
  }, []);

  useFrame(({ clock }, delta) => {
    if (!group.current) return;
    if (document.hidden) return;
    const t = clock.getElapsedTime();
    // breath (charter creativity hipBob)
    const breath = Math.sin(t * (Math.PI * 2 / 4.5)) * 0.015;
    group.current.scale.y = 1 + breath;
    // head tilt via face tracking + composer plan (S7)
    const tx = faceLookTarget.current[0];
    const ty = faceLookTarget.current[1];
    const tilt = gesturePlan?.head.tilt ?? 0;
    const nod = gesturePlan?.head.nod ?? 0;
    if (headRef.current) {
      const targetY = tx * 0.3 + (tilt * Math.PI) / 180;
      const targetX = ty * 0.2 + (nod * Math.PI) / 180;
      headRef.current.rotation.y = THREE.MathUtils.lerp(headRef.current.rotation.y, targetY, 0.08);
      headRef.current.rotation.x = THREE.MathUtils.lerp(headRef.current.rotation.x, targetX, 0.08);
    }
    // jaw by audioLevel + composer mouth
    if (jawRef.current) {
      const mouth = gesturePlan?.mouth ?? 0;
      const open = Math.min(1, audioLevel) * 0.25 + mouth * 0.1;
      if (status === "answering" || mouth > 0) {
        jawRef.current.rotation.x = THREE.MathUtils.lerp(jawRef.current.rotation.x, open, 0.22);
      }
    }
    // blink via composer + procedural 3-6s
    const shouldBlink = blink || gesturePlan?.head.blink;
    if (shouldBlink && group.current) {
      group.current.scale.y = 0.92;
    }
    // wave via arm IK procedural (shoulder/elbow per charter)
    const hands = gesturePlan?.hands || [];
    if (hands.length > 0) {
      // apply first hand angle to group rotation as simple IK
      const angle = hands[0].angle || 0;
      group.current.rotation.z = THREE.MathUtils.lerp(group.current.rotation.z, (angle * Math.PI) / 180, 0.12);
    } else if (status === "waving" || status === "completed") {
      group.current.rotation.z = Math.sin(t * 3) * 0.08;
    }
    // walk bob + leg swing (charter legSwing)
    if (status === "walking" || gesturePlan?.body === "walking") {
      group.current.position.y = Math.sin(t * 8) * 0.04;
      walkRef.current += delta * WALK_SPEED;
    }
    breathRef.current = t;
  });

  // Tap waypoint handling is done by parent; this model just renders at position
  return (
    <group ref={group} position={position} rotation={[0, rotation, 0]}>
      <primitive object={scene.clone()} scale={0.9} />
    </group>
  );
}

function Stage({ status, audioLevel, gestureHint }: { status: Status; audioLevel: number; gestureHint?: string }) {
  const [waypoint, setWaypoint] = useState<THREE.Vector3 | null>(null);
  const [pos, setPos] = useState(new THREE.Vector3(0, 0, 0));
  const [rot, setRot] = useState(0);
  const targetRef = useRef<THREE.Vector3 | null>(null);
  const { camera, raycaster, pointer } = useThree();

  const onPointerDown = () => {
    // Raycast to floor y=0
    raycaster.setFromCamera(pointer, camera);
    const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
    const intersect = new THREE.Vector3();
    raycaster.ray.intersectPlane(plane, intersect);
    if (intersect) {
      // Clamp to 2m walk and stage bounds
      intersect.y = 0;
      const dist = pos.distanceTo(intersect);
      if (dist > 0.3 && dist < 6) {
        targetRef.current = intersect.clone();
        setWaypoint(intersect.clone());
      }
    }
  };

  useEffect(() => {
    const canvas = document.querySelector("canvas");
    if (!canvas) return;
    canvas.addEventListener("pointerdown", onPointerDown as unknown as EventListener);
    return () => canvas.removeEventListener("pointerdown", onPointerDown as unknown as EventListener);
  });

  useFrame((_, delta) => {
    if (!targetRef.current) return;
    const target = targetRef.current;
    const dir = new THREE.Vector3().subVectors(target, pos);
    const dist = dir.length();
    if (dist < 0.05) {
      targetRef.current = null;
      setWaypoint(null);
      return;
    }
    dir.normalize();
    const step = Math.min(dist, WALK_SPEED * delta);
    const next = pos.clone().add(dir.multiplyScalar(step));
    setPos(next);
    // face user (rotate Y)
    const angle = Math.atan2(dir.x, dir.z);
    setRot(angle);
    // stop and face user when reaching
    if (dist < 0.2) {
      // face camera
      const camDir = new THREE.Vector3().subVectors(camera.position, next);
      const camAngle = Math.atan2(camDir.x, camDir.z);
      setRot(THREE.MathUtils.lerp(rot, camAngle, 0.05));
    }
  });

  const walking = !!waypoint;
  const activeStatus = walking ? "walking" : status;

  return (
    <>
      {/* Zellij floor */}
      <RigidBody type="fixed" colliders={false} position={[0, -1.1, 0]}>
        <CuboidCollider args={[5, 0.1, 5]} />
        <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
          <planeGeometry args={[10, 10]} />
          <meshStandardMaterial color="#0a0e1a" roughness={0.8} />
        </mesh>
        {/* zellij pattern overlay */}
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]}>
          <planeGeometry args={[10, 10]} />
          <meshBasicMaterial color="#22d3ee" transparent opacity={0.07} wireframe />
        </mesh>
      </RigidBody>

      {/* Neon ring */}
      <mesh position={[0, -1.0, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.9, 1.0, 32]} />
        <meshBasicMaterial color="#22d3ee" transparent opacity={0.9} side={THREE.DoubleSide} />
      </mesh>

      {/* Arches */}
      {[ -2, 2].map((x) => (
        <mesh key={x} position={[x, -0.2, -1]}>
          <torusGeometry args={[0.6, 0.05, 8, 24, Math.PI]} />
          <meshStandardMaterial color="#FFD700" emissive="#FFD700" emissiveIntensity={0.3} />
        </mesh>
      ))}

      {/* Waypoint marker */}
      {waypoint && (
        <mesh position={[waypoint.x, -0.95, waypoint.z]}>
          <cylinderGeometry args={[0.12, 0.12, 0.02, 16]} />
          <meshBasicMaterial color="#22d3ee" transparent opacity={0.6} />
        </mesh>
      )}

      <GenioModel status={activeStatus} audioLevel={audioLevel} position={pos} rotation={rot} gestureHint={gestureHint} />

      <ContactShadows position={[0, -1.1, 0]} opacity={0.42} scale={3} blur={2.2} far={4} color="#000000" />
    </>
  );
}

const GenioBody = memo(function GenioBody({ status, audioLevel = 0, gestureHint }: Props) {
  const tier = useTier();
  const isCoarse = typeof window !== "undefined" && window.matchMedia?.("(pointer: coarse)")?.matches;

  if (tier === "low") {
    return (
      <div className="absolute inset-0 flex items-center justify-center">
        <p className="font-mono text-[11px] text-white/40">Tier-B fallback — puppet</p>
      </div>
    );
  }

  return (
    <Canvas
      dpr={[1, isCoarse ? 1.2 : 1.5] as unknown as [number, number]}
      camera={{ position: [0, 1.6, 4.2], fov: 38 }}
      gl={{ antialias: !isCoarse, alpha: true, powerPreference: "high-performance" }}
      shadows={false}
      style={{ position: "absolute", inset: 0, zIndex: 1 }}
    >
      <Suspense fallback={null}>
        <ambientLight intensity={0.9} />
        <directionalLight position={[2, 3, 2]} intensity={1.0} />
        <pointLight position={[-2, 1, 2]} color="#00E5FF" intensity={0.6} />
        <pointLight position={[2, -0.5, -1]} color="#FFD700" intensity={0.45} />
        <Physics gravity={[0, GRAVITY, 0]}>
          <Bounds fit clip observe margin={1.2}>
            <Stage status={status} audioLevel={audioLevel} gestureHint={gestureHint} />
          </Bounds>
        </Physics>
      </Suspense>
    </Canvas>
  );
});

export default GenioBody;
