import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

const toTimelineNumber = (value, fallback = 0) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
};

export default function useTimelineAnimation({
  minTime,
  maxTime,
  initialTime,
  initialSpeed = 1,
  loop = false,
}) {
  const normalizedMin = useMemo(() => toTimelineNumber(minTime, 0), [minTime]);
  const normalizedMax = useMemo(() => toTimelineNumber(maxTime, normalizedMin), [maxTime, normalizedMin]);

  const initialPoint = useMemo(() => {
    const fromProp = toTimelineNumber(initialTime, normalizedMin);
    return Math.min(normalizedMax, Math.max(normalizedMin, fromProp));
  }, [initialTime, normalizedMax, normalizedMin]);

  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(initialPoint);
  const [speedMultiplier, setSpeedMultiplier] = useState(initialSpeed);

  const rafRef = useRef(0);
  const lastFrameAtRef = useRef(0);
  const currentTimeRef = useRef(initialPoint);

  useEffect(() => {
    currentTimeRef.current = currentTime;
  }, [currentTime]);

  useEffect(() => {
    setCurrentTime(initialPoint);
    currentTimeRef.current = initialPoint;
  }, [initialPoint]);

  const cancelLoop = useCallback(() => {
    if (rafRef.current) {
      window.cancelAnimationFrame(rafRef.current);
      rafRef.current = 0;
    }
    lastFrameAtRef.current = 0;
  }, []);

  const seekTime = useCallback((nextTime) => {
    const numeric = toTimelineNumber(nextTime, normalizedMin);
    const clamped = Math.min(normalizedMax, Math.max(normalizedMin, numeric));
    currentTimeRef.current = clamped;
    setCurrentTime(clamped);
  }, [normalizedMax, normalizedMin]);

  const togglePlay = useCallback(() => {
    setIsPlaying((prev) => {
      if (!prev && currentTimeRef.current >= normalizedMax) {
        const restartAt = loop ? normalizedMin : normalizedMax;
        currentTimeRef.current = restartAt;
        setCurrentTime(restartAt);
      }
      return !prev;
    });
  }, [loop, normalizedMax, normalizedMin]);

  const setSpeed = useCallback((nextSpeed) => {
    const numeric = Number(nextSpeed);
    if (!Number.isFinite(numeric) || numeric <= 0) return;
    setSpeedMultiplier(numeric);
  }, []);

  useEffect(() => {
    if (!isPlaying) {
      cancelLoop();
      return undefined;
    }

    const tick = (now) => {
      if (!lastFrameAtRef.current) lastFrameAtRef.current = now;
      const dtMs = now - lastFrameAtRef.current;
      lastFrameAtRef.current = now;

      const nextTime = currentTimeRef.current + (dtMs / 1000) * speedMultiplier;
      if (nextTime >= normalizedMax) {
        if (loop) {
          const range = normalizedMax - normalizedMin || 1;
          const looped = normalizedMin + ((nextTime - normalizedMin) % range);
          currentTimeRef.current = looped;
          setCurrentTime(looped);
          rafRef.current = window.requestAnimationFrame(tick);
          return;
        }

        currentTimeRef.current = normalizedMax;
        setCurrentTime(normalizedMax);
        setIsPlaying(false);
        cancelLoop();
        return;
      }

      const clamped = Math.max(normalizedMin, nextTime);
      currentTimeRef.current = clamped;
      setCurrentTime(clamped);
      rafRef.current = window.requestAnimationFrame(tick);
    };

    rafRef.current = window.requestAnimationFrame(tick);
    return cancelLoop;
  }, [cancelLoop, isPlaying, loop, normalizedMax, normalizedMin, speedMultiplier]);

  return {
    isPlaying,
    currentTime,
    timeRange: { min: normalizedMin, max: normalizedMax },
    speedMultiplier,
    togglePlay,
    setSpeed,
    seekTime,
    setIsPlaying,
  };
}
