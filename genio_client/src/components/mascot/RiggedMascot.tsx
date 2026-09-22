import { useEffect, useRef } from "react";
import { useGLTF, useAnimations } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { MascotContext } from "../../lib/mascotAnimator";
import { TRANSITION_MS } from "../../lib/mascotAnimator";

/**
 * Modèle v2 approuvé (AZMI, arbitrage Partie A) : v2_fallback_baked.glb + squelette
 * minimal (root_joint + head_joint) ajouté SANS toucher la géométrie (POSITION et
 * COLOR_0 byte-identiques). Le mesh n'a pas de clips d'animation : le mouvement est
 * 100% procédural (respiration, balancement, eye saccades via l'os tête).
 *
 * Accessoires modulaires (directive Partie A) attachés par bone socket anchors :
 *   - gland_submesh.glb      → os head_joint (sommet du fez, suit la tête)
 *   - headphones_submesh.glb → racine du modèle (autour du cou, style DJ)
 *   - g_pendant_submesh.glb  → racine du modèle (chaîne poitrine, lettre G)
 * Chaque submesh est centré sur son origine ; l'ancre (position monde) est posée ici.
 */
const MODEL_URL = "/models/genio-mascot-v2.glb";
const GLAND_URL = "/models/gland_submesh.glb";
const HEADPHONES_URL = "/models/headphones_submesh.glb";
const G_PENDANT_URL = "/models/g_pendant_submesh.glb";

// Ancres (espace mesh, mesurées sur v2_fallback_baked.glb) :
// head_joint à (0, 1.30, -0.02) → gland au sommet du fez (0, 1.70, -0.03).
const GLAND_HEAD_LOCAL: [number, number, number] = [0, 0.4, -0.01];
const HEADPHONES_POS: [number, number, number] = [0, 1.02, 0];
const G_PENDANT_POS: [number, number, number] = [0, 0.87, -0.17];

/** Retrouve le premier os dont le nom contient "head" (head_joint du squelette v2). */
function findHeadBone(root: THREE.Object3D): THREE.Bone | null {
  let found: THREE.Bone | null = null;
  root.traverse((o) => {
    if (!found && (o as THREE.Bone).isBone && o.name.toLowerCase().includes("head")) {
      found = o as THREE.Bone;
    }
  });
  return found;
}

/**
 * RiggedMascot — vrai personnage 3D riggé fidèle à la référence (fez rouge,
 * barbe, robe rouge/or, membres blancs articulés, pendentif G).
 * v2 approuvé : mesh chibi + vertex colors + squelette minimal (root/head).
 * Le mapping contexte→clip de mascotAnimator reste supporté (si un modèle avec
 * clips est chargé) ; sans clips, le mouvement procédural prend le relais.
 * CyberAvatar reste le filet de sécurité (ErrorBoundary dans MascotStage) —
 * ne pas supprimer CyberAvatar.tsx.
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
  // Accessoires modulaires (bone socket anchors) — chargés une fois, attachés
  // quand l'os tête est disponible.
  const gland = useGLTF(GLAND_URL) as unknown as { scene: THREE.Group };
  const headphones = useGLTF(HEADPHONES_URL) as unknown as { scene: THREE.Group };
  const gPendant = useGLTF(G_PENDANT_URL) as unknown as { scene: THREE.Group };

  // Trouver l'os tête une fois pour le look-at procédural par-dessus l'anim
  // + y attacher le gland (suit la tête).
  useEffect(() => {
    if (!group.current) return;
    const found = findHeadBone(group.current);
    headRef.current = found;
    // Bone socket anchors : gland → os tête ; casque + G → racine du modèle
    // (scene est à l'identité dans le groupe scalé → positions espace-mesh).
    if (found) {
      const glandHolder = new THREE.Group();
      glandHolder.position.set(...GLAND_HEAD_LOCAL);
      glandHolder.add(gland.scene.clone());
      found.add(glandHolder);
    }
    const hpHolder = new THREE.Group();
    hpHolder.position.set(...HEADPHONES_POS);
    hpHolder.add(headphones.scene.clone());
    scene.add(hpHolder);
    const gHolder = new THREE.Group();
    gHolder.position.set(...G_PENDANT_POS);
    gHolder.add(gPendant.scene.clone());
    scene.add(gHolder);
  }, [scene, gland.scene, headphones.scene, gPendant.scene]);

  // Changer de clip avec fondu variable selon le contexte (rapide pour
  // `error`, lent/posé pour `thinking`), fallback idle si inconnu
  useEffect(() => {
    const keys = Object.keys(actions ?? {});
    if (keys.length === 0) return;
    const name = (actions as Record<string, THREE.AnimationAction | undefined>)[activeClip]
      ? activeClip
      : "idle";
    const fadeSec =
      (TRANSITION_MS[activeClip as MascotContext] ?? 350) / 1000;
    const action = (actions as Record<string, THREE.AnimationAction | undefined>)[name];
    if (!action) return;
    // Stop les autres en fondu pour éviter les mélanges parasites
    Object.entries(actions as Record<string, THREE.AnimationAction>).forEach(([k, a]) => {
      if (k !== name) {
        try {
          a.fadeOut(fadeSec);
        } catch { /* ignore */ }
      }
    });
    try {
      action.reset().fadeIn(fadeSec).play();
    } catch { /* ignore */ }
    return () => {
      try {
        action.fadeOut(fadeSec);
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
    // + dérive du regard en idle/thinking (jamais figé) par-dessus l'anim
    if (headRef.current) {
      const idleLike = activeClip === "idle" || activeClip === "thinking" || activeClip === "listening";
      const wanderYaw = idleLike ? Math.sin(t * 0.3) * 0.15 : 0;
      const wanderTilt = idleLike ? Math.sin(t * 0.23 + 1.7) * 0.05 : 0;
      headRef.current.rotation.y = THREE.MathUtils.lerp(
        headRef.current.rotation.y,
        headYaw * 0.5 + wanderYaw,
        0.08,
      );
      headRef.current.rotation.x = THREE.MathUtils.lerp(
        headRef.current.rotation.x,
        headTilt * 0.5 + wanderTilt,
        0.08,
      );
    }
    // Respiration permanente + transfert de poids en idle : le corps vit
    // même entre deux gestes explicites (pas de pose figée).
    if (group.current) {
      const breathing = activeClip === "error" ? 0.004 : 0.009;
      group.current.position.y = -0.35 + Math.sin(t * 1.4) * breathing;
      if (activeClip === "idle" || activeClip === "listening" || activeClip === "thinking") {
        group.current.rotation.z = Math.sin(t * 0.5) * 0.012;
      } else {
        group.current.rotation.z = THREE.MathUtils.lerp(group.current.rotation.z, 0, 0.1);
      }
    }
  });

  return (
    <group ref={group} position={[0, -0.35, 0]} scale={0.9}>
      <primitive object={scene} />
    </group>
  );
}

useGLTF.preload(MODEL_URL);
export default RiggedMascot;
