import React from 'react';

const SPEED_OPTIONS = [1, 5, 10, 60];

const formatTimelineTime = (value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return '--:--:--';
  const date = new Date((numeric < 1e12 ? numeric * 1000 : numeric));
  if (Number.isNaN(date.getTime())) return '--:--:--';
  return new Intl.DateTimeFormat('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date);
};

export default function TimelineSlider({
  currentTime,
  minTime,
  maxTime,
  isPlaying,
  speedMultiplier,
  onTogglePlay,
  onSeek,
  onSpeedChange,
  className = '',
}) {
  return (
    <div className={`absolute bottom-10 left-1/2 z-50 w-2/3 -translate-x-1/2 rounded-xl border border-gray-700 bg-gray-900/90 p-4 backdrop-blur-md ${className}`}>
      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <button
          type="button"
          onClick={onTogglePlay}
          className="inline-flex min-w-[120px] items-center justify-center rounded-lg border border-cyan-500/50 bg-cyan-500/15 px-4 py-2 text-sm font-semibold text-cyan-200 transition hover:bg-cyan-500/25"
        >
          {isPlaying ? 'Pause' : 'Play'}
        </button>

        <input
          type="range"
          min={minTime}
          max={maxTime}
          step={1}
          value={currentTime}
          onChange={(event) => onSeek(Number(event.target.value))}
          className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-gray-700 accent-cyan-400"
        />

        <div className="flex items-center gap-3 md:min-w-[230px] md:justify-end">
          <span className="font-mono text-sm text-gray-100">{formatTimelineTime(currentTime)}</span>
          <select
            value={speedMultiplier}
            onChange={(event) => onSpeedChange(Number(event.target.value))}
            className="rounded-lg border border-gray-600 bg-gray-800 px-2 py-1 text-sm text-gray-100"
          >
            {SPEED_OPTIONS.map((option) => (
              <option key={option} value={option}>{option}x</option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
