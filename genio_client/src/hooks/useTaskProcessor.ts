import { useEffect, useRef, useState } from "react";

/**
 * useTaskProcessor — Custom hook that receives a task (string or null)
 * and returns animated processing state for the Chronos Portal.
 */

export interface TaskMetrics {
  cpu: number;
  gpu: number;
  ram: { used: number; total: number };
  vram: { used: number; total: number };
}

export interface TaskProcessorState {
  isMinimized: boolean;
  setIsMinimized: (v: boolean) => void;
  thinkingSteps: string[];
  metrics: TaskMetrics;
  result: string;
  isProcessing: boolean;
}

const THINKING_STEPS = [
  "Analyse...",
  "Fouille...",
  "Connexion...",
  "Synchronisation...",
  "Generation...",
];

const DONE_MESSAGES = [
  "Tache terminee avec succes. Chronos a genere tous les fichiers necessaires.",
  "Analyses completees. Rapport genere et pret a l'emploi.",
  "Synchronisation terminee. Toutes les donnees sont a jour.",
  "Traitement effectue. Fichiers prats pour le deploiement.",
  "Mission accomplie. Chronos a optimise tous les parametres.",
];

function randomMetric(min: number, max: number): number {
  return Math.round((Math.random() * (max - min) + min) * 10) / 10;
}

export function useTaskProcessor(task: string | null): TaskProcessorState {
  const [isMinimized, setIsMinimized] = useState(false);
  const [thinkingSteps, setThinkingSteps] = useState<string[]>([]);
  const [metrics, setMetrics] = useState<TaskMetrics>({
    cpu: 0, gpu: 0,
    ram: { used: 0, total: 16 },
    vram: { used: 0, total: 8 },
  });
  const [result, setResult] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);

  const stepIdxRef = useRef(0);
  const stepTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const metricsTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Reset when a new task arrives
  useEffect(() => {
    if (!task) return;

    setIsMinimized(false);
    setThinkingSteps([]);
    setResult("");
    setIsProcessing(true);
    stepIdxRef.current = 0;

    // Add thinking steps every 1.2s
    stepTimerRef.current = setInterval(() => {
      if (stepIdxRef.current < THINKING_STEPS.length) {
        setThinkingSteps((prev) => [...prev, THINKING_STEPS[stepIdxRef.current]]);
        stepIdxRef.current++;
      }
    }, 1200);

    // Start metrics simulation after first thinking step (1.2s delay)
    const metricsStart = setTimeout(() => {
      metricsTimerRef.current = setInterval(() => {
        setMetrics({
          cpu: randomMetric(15, 85),
          gpu: randomMetric(10, 90),
          ram: { used: randomMetric(4, 14), total: 16 },
          vram: { used: randomMetric(1, 6), total: 8 },
        });
      }, 2000);
    }, 1200);

    // Complete processing after 8-12s
    const duration = 8000 + Math.random() * 4000;
    const completeTimer = setTimeout(() => {
      setIsProcessing(false);
      setIsMinimized(true);
      setResult(DONE_MESSAGES[Math.floor(Math.random() * DONE_MESSAGES.length)]);
    }, duration);

    return () => {
      if (stepTimerRef.current) clearInterval(stepTimerRef.current);
      if (metricsTimerRef.current) clearInterval(metricsTimerRef.current);
      clearTimeout(metricsStart);
      clearTimeout(completeTimer);
    };
  }, [task]);

  return { isMinimized, setIsMinimized, thinkingSteps, metrics, result, isProcessing };
}
