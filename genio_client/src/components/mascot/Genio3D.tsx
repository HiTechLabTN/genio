import { Suspense, useEffect, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { useGLTF, useAnimations, OrbitControls, Environment, ContactShadows } from "@react-three/drei";
import * as THREE from "three";
import { Physics, RigidBody, CuboidCollider } from "@react-three/rapier";

// PreloadDraco
useGLTF.preload("/media/genio_rigged_advanced_draco.glb");

function GenioModel({ audioLevel = 0, status = "idle", onLoaded }: { audioLevel?: number; status?: string; onLoaded?: () => void }) {
  const group = useRef<THREE.Group>(null);
  const { scene, animations } = useGLTF("/media/genio_rigged_advanced_draco.glb");
  const { actions } = useAnimations(animations, group);

  // Clone scene to avoid mutating original
  const clonedScene = scene.clone(true);

  // Find morph targets for mouth and eyes
  const morphMeshes: THREE.Mesh[] = [];
  clonedScene.traverse((obj) => {
    if ((obj as THREE.Mesh).isMesh && (obj as THREE.Mesh).morphTargetDictionary) {
      morphMeshes.push(obj as THREE.Mesh);
    }
  });

  useEffect(() => {
    if (onLoaded) onLoaded();
    console.log("Animations:", animations.map(a => a.name));
    if (morphMeshes[0]?.morphTargetDictionary) {
      console.log("Genio morph meshes:", morphMeshes.map(m => m.name), morphMeshes[0]?.morphTargetDictionary);
    }
  }, [animations, onLoaded]);

  // Animation switching by status
  useEffect(() => {
    const idle = actions["Idle"];
    const wave = actions["Wave"];
    if (!idle && !wave) {
      if (animations.length > 0 && actions[animations[0].name]) actions[animations[0].name]!.reset().fadeIn(0.3).play();
      return;
    }
    // default idle
    if (status === "wave" && wave) {
      idle?.fadeOut(0.25);
      wave.reset().setLoop(THREE.LoopOnce, 1).clampWhenFinished = true;
      wave.fadeIn(0.25).play();
      const t = setTimeout(() => {
        wave.fadeOut(0.35);
        idle?.reset().fadeIn(0.35).play();
      }, 2200);
      return () => clearTimeout(t);
    }
    // thinking/listening/speaking keep Idle looping
    if (idle && !idle.isRunning()) {
      wave?.fadeOut(0.25);
      idle.reset().fadeIn(0.35).play();
      idle.setLoop(THREE.LoopRepeat, Infinity);
    }
  }, [actions, animations, status]);

  // Blend morph for mouth based on audioLevel
  useEffect(() => {
    const lvl = Math.min(1, Math.max(0, audioLevel * 3));
    morphMeshes.forEach((mesh) => {
      const dict = mesh.morphTargetDictionary;
      const infl = mesh.morphTargetInfluences;
      if (!dict || !infl) return;
      if (dict["mouth_open"] !== undefined) {
        infl[dict["mouth_open"]] = lvl * 0.85;
      }
      if (dict["mouth_smile"] !== undefined) {
        infl[dict["mouth_smile"]] = lvl * 0.3;
      }
    });
  }, [audioLevel]);

  // Blink random
  useEffect(() => {
    let alive = true;
    const schedule = () => {
      setTimeout(() => {
        if (!alive) return;
        // Blink both eyes
        const doBlink = () => {
          let t = 0;
          const blink = () => {
            t += 0.016;
            const v = Math.sin(t * Math.PI * 8) > 0 ? Math.abs(Math.sin(t * Math.PI * 8)) : 0;
            morphMeshes.forEach((mesh) => {
              const dict = mesh.morphTargetDictionary;
              const infl = mesh.morphTargetInfluences;
              if (!dict || !infl) return;
              if (dict["eye_blink_L"] !== undefined) infl[dict["eye_blink_L"]] = v;
              if (dict["eye_blink_R"] !== undefined) infl[dict["eye_blink_R"]] = v;
            });
            if (t < 0.18) requestAnimationFrame(blink);
            else {
              morphMeshes.forEach((mesh) => {
                const dict = mesh.morphTargetDictionary;
                const infl = mesh.morphTargetInfluences;
                if (!dict || !infl) return;
                if (dict["eye_blink_L"] !== undefined) infl[dict["eye_blink_L"]] = 0;
                if (dict["eye_blink_R"] !== undefined) infl[dict["eye_blink_R"]] = 0;
              });
            }
          };
          blink();
        };
        doBlink();
        schedule();
      }, 2800 + Math.random() * 2200);
    };
    schedule();
    return () => { alive = false; };
  }, []);

  // Mouse follow + status-driven micro-animations
  useFrame((state) => {
    if (!group.current) return;
    const { mouse } = state;
    const t = state.clock.elapsedTime;
    // Head follow mouse (dampened when thinking)
    const headBone = group.current.getObjectByName("head") as THREE.Bone;
    const damp = status === "thinking" ? 0.04 : 0.08;
    const tiltFactor = status === "listening" ? 0.12 : 0;
    if (headBone) {
      headBone.rotation.y = THREE.MathUtils.lerp(headBone.rotation.y, mouse.x * 0.35 + Math.sin(t * 0.2) * 0.06, damp);
      headBone.rotation.x = THREE.MathUtils.lerp(headBone.rotation.x, -mouse.y * 0.22 - tiltFactor, damp);
      if (status === "thinking") headBone.rotation.z = Math.sin(t * 0.6) * 0.06;
      else headBone.rotation.z = THREE.MathUtils.lerp(headBone.rotation.z, 0, 0.08);
    }
    // Breathing + idle sway
    group.current.position.y = Math.sin(t * (status === "thinking" ? 0.6 : 0.9)) * 0.015;
    group.current.rotation.y = Math.sin(t * 0.3) * 0.04;
  });

  // Handle status changes (wave, listen, think, speak) via prop? For now idle only, but can switch actions
  // This will be extended to switch animations based on status prop

  return (
    <group ref={group} dispose={null} position={[0, -0.85, 0]} scale={1}>
      <primitive object={clonedScene} />
    </group>
  );
}

export default function Genio3D({ audioLevel = 0, status = "idle", className = "" }: { audioLevel?: number; status?: string; className?: string }) {
  const [loaded, setLoaded] = useState(false);
  const [micLevel, setMicLevel] = useState(0);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);

  // Web Audio API for lip-sync
  useEffect(() => {
    if (audioLevel > 0) {
      setMicLevel(audioLevel);
      return;
    }
    // If no audioLevel prop, use mic
    let stream: MediaStream | null = null;
    let raf = 0;
    const initMic = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
        audioContextRef.current = ctx;
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        analyserRef.current = analyser;
        const source = ctx.createMediaStreamSource(stream);
        source.connect(analyser);
        const data = new Uint8Array(analyser.frequencyBinCount);
        const tick = () => {
          if (!analyserRef.current) return;
          analyserRef.current.getByteFrequencyData(data);
          const avg = data.reduce((a, b) => a + b, 0) / data.length / 255;
          setMicLevel(avg * 1.5);
          raf = requestAnimationFrame(tick);
        };
        tick();
      } catch (e) {
        console.warn("Mic not available", e);
      }
    };
    // Only init mic if no external audioLevel
    if (audioLevel === 0) {
      // Random blink and idle for demo
      const id = setInterval(() => setMicLevel(Math.random() * 0.1), 3000);
      return () => {
        clearInterval(id);
        if (raf) cancelAnimationFrame(raf);
        if (stream) stream.getTracks().forEach(t => t.stop());
        if (audioContextRef.current) audioContextRef.current.close();
      };
    }
    initMic();
    return () => {
      if (raf) cancelAnimationFrame(raf);
      if (stream) stream.getTracks().forEach(t => t.stop());
      if (audioContextRef.current) audioContextRef.current.close();
    };
  }, [audioLevel]);

  const finalLevel = audioLevel > 0 ? audioLevel : micLevel;

  return (
    <div className={`relative w-full h-[85vh] max-h-[850px] ${className}`} style={{ background: "transparent" }}>
      <Canvas
        shadows
        dpr={[1, 1.5]}
        camera={{ position: [0, 1.1, 2.8], fov: 38, near: 0.1, far: 100 }}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
        onCreated={({ gl }) => {
          gl.setClearColor(0x020B1E, 0);
          gl.shadowMap.enabled = true;
          gl.shadowMap.type = THREE.PCFSoftShadowMap;
        }}
        style={{ background: "transparent" }}
      >
        <Suspense fallback={null}>
          <Physics gravity={[0, -9.81, 0]}>
            {/* Ground collider for physics */}
            <RigidBody type="fixed" position={[0, -0.9, 0]}>
              <CuboidCollider args={[5, 0.1, 5]} />
            </RigidBody>
            <GenioModel audioLevel={finalLevel} status={status} onLoaded={() => setLoaded(true)} />
          </Physics>

          {/* Lighting - cyberpunk */}
          <ambientLight intensity={0.55} color="#a0c4ff" />
          <directionalLight
            position={[3, 5, 4]}
            intensity={1.2}
            castShadow
            shadow-mapSize={[2048, 2048]}
            shadow-bias={-0.0001}
          />
          <pointLight position={[-2, 2, 2]} intensity={0.9} color="#00E5FF" distance={4} decay={2} />
          <pointLight position={[2, 2, -1]} intensity={0.6} color="#FFD700" distance={3} decay={2} />
          <spotLight position={[0, 4, 0]} intensity={0.7} angle={0.5} penumbra={0.8} color="#ffffff" castShadow />

          {/* Environment and shadows */}
          <ContactShadows position={[0, -0.88, 0]} opacity={0.42} scale={10} blur={2.2} far={4} color="#020B1E" />
          <Environment preset="city" background={false} />

          {/* Controls for orbit (subtle) */}
          <OrbitControls
            enablePan={false}
            enableZoom={false}
            minPolarAngle={Math.PI / 2.8}
            maxPolarAngle={Math.PI / 1.9}
            minAzimuthAngle={-0.35}
            maxAzimuthAngle={0.35}
            target={[0, 0.85, 0]}
          />
        </Suspense>
      </Canvas>

      {/* Loading overlay */}
      {!loaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-[#020B1E]/80 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-3">
            <div className="h-10 w-10 animate-spin rounded-full border-2 border-cyan-400/30 border-t-cyan-400" />
            <p className="font-mono text-xs tracking-widest text-white/60">Chargement Genio 3D...</p>
          </div>
        </div>
      )}

      {/* UI overlay for mic */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-2 rounded-full bg-black/30 backdrop-blur-md px-3 py-1.5 border border-white/10">
        <div className={`h-2 w-2 rounded-full ${finalLevel > 0.1 ? "bg-emerald-400 animate-pulse shadow-[0_0_8px_#10b981]" : "bg-white/30"}`} />
        <span className="font-mono text-[10px] tracking-widest text-white/70">
          {finalLevel > 0.1 ? "PARLE..." : "IDLE • 60FPS • RTX 3060"}
        </span>
      </div>
    </div>
  );
}
