import React from 'react';
import { DrawPolygonMode, ModifyMode, ViewMode } from '@nebula.gl/edit-modes';

export default function GeofenceToolbar({ mode, onModeChange, onClear }) {
  const isActive = (targetMode) => mode === targetMode;
  const buttonBase = 'rounded border px-3 py-2 text-left text-xs font-semibold transition';

  return (
    <div className="absolute top-4 left-4 bg-gray-900 border border-gray-700 rounded-lg p-2 flex flex-col gap-2 z-50">
      <button
        type="button"
        onClick={() => onModeChange(ViewMode)}
        className={`${buttonBase} ${isActive(ViewMode) ? 'border-cyan-400 bg-cyan-500/20 text-cyan-200' : 'border-gray-600 bg-gray-800 text-gray-200 hover:bg-gray-700'}`}
      >
        ✋ Просмотр
      </button>

      <button
        type="button"
        onClick={() => onModeChange(DrawPolygonMode)}
        className={`${buttonBase} ${isActive(DrawPolygonMode) ? 'border-cyan-400 bg-cyan-500/20 text-cyan-200' : 'border-gray-600 bg-gray-800 text-gray-200 hover:bg-gray-700'}`}
      >
        ✏️ Нарисовать Зону
      </button>

      <button
        type="button"
        onClick={() => onModeChange(ModifyMode)}
        className={`${buttonBase} ${isActive(ModifyMode) ? 'border-cyan-400 bg-cyan-500/20 text-cyan-200' : 'border-gray-600 bg-gray-800 text-gray-200 hover:bg-gray-700'}`}
      >
        🔄 Редактировать
      </button>

      <button
        type="button"
        onClick={onClear}
        className="rounded border border-red-500/60 bg-red-500/20 px-3 py-2 text-left text-xs font-semibold text-red-200 transition hover:bg-red-500/35"
      >
        🗑 Очистить Все
      </button>
    </div>
  );
}
