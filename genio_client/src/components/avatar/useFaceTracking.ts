import React, { useEffect, useRef, useState, useCallback } from "react";

/**
 * MediaPipe Front-Camera Gaze Tracking — Phase 3.
 *
 * Access front-facing video stream, extract yaw/pitch via @mediapipe/face_mesh,
 * and smoothly interpolate look-at vectors toward the user's position using
 * lerp damping. Falls back to device pointer when camera unavailable.
 */

export interface FaceAngles {
  yaw: number;
  pitch: number;
}

export interface FaceTrackingState {
  yaw: number;
  pitch: number;
  isTracking: boolean;
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

const FaceLookContext = React.createContext<{
  faceLookTarget: React.MutableRefObject<[number, number]>;
}>({
  faceLookTarget: ({ current: [0, 0] } as unknown) as React.MutableRefObject<[number, number]>,
});

export function useFaceTrackingContext() {
  return React.useContext(FaceLookContext);
}

export function useFaceTracking(enabled: boolean): {
  provider: ({ children }: { children?: React.ReactNode }) => React.ReactElement;
  active: boolean;
  angles: FaceAngles;
} {
  const target = useRef<[number, number]>([0, 0]);
  const smoothTarget = useRef<[number, number]>([0, 0]);
  const [active, setActive] = useState(false);
  const [angles, setAngles] = useState<FaceAngles>({ yaw: 0, pitch: 0 });
  const lastUpdate = useRef(0);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let video: HTMLVideoElement | null = null;
    let stream: MediaStream | null = null;
    let faceMesh: { send: (opts: { image: HTMLVideoElement }) => Promise<unknown>; close: () => void } | null = null;
    let animId = 0;

    async function setup() {
      try {
        const { FaceMesh } = await import("@mediapipe/face_mesh");
        const onResults = (results: { multiFaceLandmarks?: Array<Array<{ x: number; y: number }>> }) => {
          if (cancelled || !results?.multiFaceLandmarks?.length) return;
          const face = results.multiFaceLandmarks[0];
          const nose = face[1];
          const left = face[33];
          const right = face[263];
          const chin = face[199];
          if (!nose || !left || !right) return;
          const dx = (left.x + right.x) / 2 - nose.x;
          const rawYaw = Math.max(-0.6, Math.min(0.6, dx * 6));
          const dy = chin ? (0.5 - nose.y) * 2 : 0;
          const rawPitch = Math.max(-0.45, Math.min(0.45, dy));
          // lerp damping toward target (smooth 0.15 factor)
          const nextYaw = lerp(smoothTarget.current[0], rawYaw, 0.18);
          const nextPitch = lerp(smoothTarget.current[1], rawPitch, 0.18);
          smoothTarget.current = [nextYaw, nextPitch];
          target.current = [nextYaw, nextPitch];
          // Throttle state updates to 15 FPS (66 ms) to unblock UI thread
          const now = performance.now();
          if (now - lastUpdate.current < 66) return;
          lastUpdate.current = now;
          setAngles({ yaw: nextYaw, pitch: nextPitch });
        };

        const runner = new FaceMesh({
          locateFile: (file: string) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`,
        }) as unknown as {
          setOptions: (o: Record<string, unknown>) => void;
          onResults: (cb: (r: unknown) => void) => void;
          send: (opts: { image: HTMLVideoElement }) => Promise<unknown>;
          close: () => void;
        };
        faceMesh = runner;
        try {
          runner.setOptions({ maxNumFaces: 1, refineLandmarks: true, minDetectionConfidence: 0.5, minTrackingConfidence: 0.5 });
        } catch { /* older api */ }
        runner.onResults((r) => onResults(r as { multiFaceLandmarks?: Array<Array<{ x: number; y: number }>> }));

        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
          audio: false,
        });
        video = document.createElement("video");
        video.srcObject = stream;
        video.muted = true;
        video.playsInline = true;
        video.width = 640;
        video.height = 480;
        await video.play();

        const videoEl = video;
        const tick = async () => {
          if (cancelled || !faceMesh) return;
          try {
            await faceMesh.send({ image: videoEl });
          } catch { /* transient */ }
          animId = requestAnimationFrame(tick) as unknown as number;
        };
        tick();
        setActive(true);
      } catch {
        setActive(false);
      }
    }

    setup();
    return () => {
      cancelled = true;
      if (animId) cancelAnimationFrame(animId);
      try {
        stream?.getTracks().forEach((t) => t.stop());
      } catch {}
      try {
        faceMesh?.close();
      } catch {}
    };
  }, [enabled]);

  const provider = useCallback(
    ({ children }: { children?: React.ReactNode }) => (
      React.createElement(FaceLookContext.Provider, { value: { faceLookTarget: target } }, children)
    ),
    []
  );

  return { provider, active, angles };
}

export { FaceLookContext };
