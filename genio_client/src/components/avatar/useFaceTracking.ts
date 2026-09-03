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

    // F3: gate face_mesh import until genio:ready + idle + camera permission granted
    function waitForReady(): Promise<void> {
      return new Promise((resolve) => {
        let done = false;
        const finish = () => { if (!done) { done = true; resolve(); } };
        // if already ready (SplashScreen hidden), check flag on window
        if ((window as unknown as { __GENIO_READY__?: boolean }).__GENIO_READY__) return finish();
        const onReady = () => { window.removeEventListener("genio:ready" as unknown as string, onReady); finish(); };
        window.addEventListener("genio:ready" as unknown as string, onReady);
        // idle + visible check
        const checkIdle = () => {
          if (document.visibilityState === "visible" && !document.hidden) return true;
          return false;
        };
        // if not visible, wait for visible
        if (!checkIdle()) {
          const onVis = () => { if (checkIdle()) { document.removeEventListener("visibilitychange", onVis); finish(); } };
          document.addEventListener("visibilitychange", onVis);
          // timeout fallback 2s
          window.setTimeout(finish, 2000);
        } else {
          // also wait a tiny idle via requestIdleCallback
          const ric = (window as unknown as { requestIdleCallback?: (cb: () => void) => number }).requestIdleCallback;
          if (ric) ric(() => finish());
          else window.setTimeout(finish, 600);
        }
        // hard timeout 3s
        window.setTimeout(finish, 3000);
      });
    }

    async function hasCameraPermission(): Promise<boolean> {
      try {
        // @ts-ignore
        const perm = await navigator.permissions?.query?.({ name: "camera" as PermissionName });
        if (perm && perm.state === "granted") return true;
        if (perm && perm.state === "denied") return false;
      } catch { /* ignore */ }
      // fallback: try to query via getUserMedia with ideal, but don't actually open yet
      return true; // assume granted, getUserMedia will handle denial gracefully
    }

    async function setup() {
      try {
        await waitForReady();
        if (cancelled) return;
        if (document.hidden) {
          // wait for visible
          await new Promise<void>((res) => {
            const onVis = () => { if (!document.hidden) { document.removeEventListener("visibilitychange", onVis); res(); } };
            document.addEventListener("visibilitychange", onVis);
            window.setTimeout(() => { document.removeEventListener("visibilitychange", onVis); res(); }, 2000);
          });
        }
        if (cancelled) return;
        const hasPerm = await hasCameraPermission();
        if (!hasPerm) {
          // F4: graceful degradation, mascot centered (no face tracking)
          setActive(false);
          return;
        }
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
