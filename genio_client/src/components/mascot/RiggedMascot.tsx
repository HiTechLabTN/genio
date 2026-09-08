import { useEffect, useRef } from "react";
import { useGLTF, useAnimations } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { MascotContext } from "../../lib/mascotAnimator";

const MODEL_URL = "/models/genio-mascot.glb";

/**
 * RiggedMascot — vrai personnage 3D riggé fidèle à la référence (fez rouge,
 * barbe, robe rouge/or, membres blancs articulés, pendentif G).
 * 34 bones + 4 morphs (mouth_open/smile, eye_blink L/R) + 8 clips EXACTS
 * pour mascotAnimator.ts : idle, greeting, listening, thinking, executing,
 * success, error, speaking. Ne pas renommer — le mapping contexte→clip
 * en dépend. CyberAvatar reste le filet de sécurité (ErrorBoundary dans
 * MascotStage) — ne pas supprimer CyberAvatar.tsx.
 */
export function RiggedMascot({
  activeClip,
  audioLevel = 0,
  headYaw = 0,
  headTilt = 0,
}: {
  activeClip: MascotContext | string;
  audioLevel?: number;
  headYaw?: number;
  headTilt?: number;
}) {
  const group = useRef<THREE.Group>(null);
  const headRef = useRef<THREE.Bone | null>(null);
  const { scene, animations } = useGLTF(MODEL_URL) as unknown as {
    scene: THREE.Group;
    animations: THREE.AnimationClip[];
  };
  const { actions } = useAnimations(animations, group);

  // Trouver l'os tête une fois pour le look-at procédural par-dessus l'anim
  useEffect(() => {
    if (!group.current) return;
    let found: THREE.Bone | null = null;
    group.current.traverse((o) => {
      if ((o as THREE.Bone).isBone && o.name.toLowerCase().includes("head") && !found) {
        found = o as THREE.Bone;
      }
    });
    headRef.current = found;
  }, [scene]);

  // Changer de clip avec fondu 0.35s, fallback idle si inconnu
  useEffect(() => {
    const keys = Object.keys(actions ?? {});
    if (keys.length === 0) return;
    const name = (actions as Record<string, THREE.AnimationAction | undefined>)[activeClip]
      ? activeClip
      : "idle";
    const action = (actions as Record<string, THREE.AnimationAction | undefined>)[name];
    if (!action) return;
    // Stop les autres en fondu pour éviter les mélanges parasites
    Object.entries(actions as Record<string, THREE.AnimationAction>).forEach(([k, a]) => {
      if (k !== name) {
        try {
          a.fadeOut(0.35);
        } catch { /* ignore */ }
      }
    });
    try {
      action.reset().fadeIn(0.35).play();
    } catch { /* ignore */ }
    return () => {
      try {
        action.fadeOut(0.35);
      } catch { /* ignore */ }
    };
  }, [activeClip, actions]);

  // Lip-sync morph + look-at tête par-dessus l'animation Mixamo/procédurale
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (!group.current) return;
    // Morph bouche si présent
    group.current.traverse((o) => {
      const mesh = o as THREE.SkinnedMesh;
      if (
        mesh.isSkinnedMesh &&
        mesh.morphTargetDictionary &&
        mesh.morphTargetInfluences
      ) {
        const dict = mesh.morphTargetDictionary as Record<string, number>;
        const infl = mesh.morphTargetInfluences as number[];
        if (dict["mouth_open"] !== undefined) {
          // speaking → suit audioLevel, sinon respiration légère
          const target =
            activeClip === "speaking"
              ? Math.min(1, 0.25 + audioLevel * 1.2 + Math.abs(Math.sin(t * 7.5)) * 0.15)
              : activeClip === "success"
                ? 0.35
                : Math.abs(Math.sin(t * 1.2)) * 0.04;
          infl[dict["mouth_open"]] = THREE.MathUtils.lerp(
            infl[dict["mouth_open"]] ?? 0,
            target,
            0.25,
          );
        }
        // Clignement auto toutes les ~3-5s (140ms)
        const blinkPhase = t % 3.7;
        const blink = blinkPhase < 0.14 ? Math.sin((blinkPhase / 0.14) * Math.PI) : 0;
        if (dict["eye_blink_L"] !== undefined) infl[dict["eye_blink_L"]] = blink;
        if (dict["eye_blink_R"] !== undefined) infl[dict["eye_blink_R"]] = blink;
      }
    });
    // Tête suit légèrement le pose procédural (yaw/tilt de mascotAnimator)
    if (headRef.current) {
      headRef.current.rotation.y = THREE.MathUtils.lerp(
        headRef.current.rotation.y,
        headYaw * 0.5,
        0.08,
      );
      headRef.current.rotation.x = THREE.MathUtils.lerp(
        headRef.current.rotation.x,
        headTilt * 0.5,
        0.08,
      );
    }
  });

  return (
    <group ref={group} position={[0, -0.32, 0]}>
      <primitive object={scene} />
    </group>
  );
}

useGLTF.preload(MODEL_URL);
export default RiggedMascot;
