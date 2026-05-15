"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { JobStatus, pipelineApi } from "./api";

interface UseJobPollerReturn {
  status: JobStatus | null;
  isPolling: boolean;
  startPolling: (jobId: string) => void;
  stopPolling: () => void;
}

export function useJobPoller(intervalMs = 5000): UseJobPollerReturn {
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const jobIdRef = useRef<string | null>(null);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setIsPolling(false);
  }, []);

  const poll = useCallback(async () => {
    if (!jobIdRef.current) return;
    try {
      const result = await pipelineApi.jobStatus(jobIdRef.current);
      setStatus(result);
      if (result.status === "success" || result.status === "failed") {
        stopPolling();
      }
    } catch {
      // Keep polling on transient errors
    }
  }, [stopPolling]);

  const startPolling = useCallback(
    (jobId: string) => {
      stopPolling();
      jobIdRef.current = jobId;
      setIsPolling(true);
      setStatus(null);
      poll();
      intervalRef.current = setInterval(poll, intervalMs);
    },
    [poll, stopPolling, intervalMs]
  );

  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  return { status, isPolling, startPolling, stopPolling };
}
