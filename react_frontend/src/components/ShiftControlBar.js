import React from 'react';
import useShiftStore from '../store/useShiftStore';
import { triggerImpact } from '../utils/haptics';

const baseButtonClass = 'w-full rounded-xl px-4 py-4 text-sm font-black uppercase tracking-wider text-white transition active:scale-[0.99]';

const confirmFinishShift = () => {
  const tg = window?.Telegram?.WebApp;

  if (tg && typeof tg.showConfirm === 'function') {
    return new Promise((resolve) => {
      tg.showConfirm('Точно завершить смену?', (confirmed) => resolve(Boolean(confirmed)));
    });
  }

  return Promise.resolve(window.confirm('Точно завершить смену?'));
};

export default function ShiftControlBar() {
  const status = useShiftStore((s) => s.status);
  const changeStatus = useShiftStore((s) => s.changeStatus);

  const handleStartShift = () => {
    triggerImpact('heavy');
    changeStatus('on_duty');
  };

  const handleBreak = () => {
    triggerImpact('medium');
    changeStatus('on_break');
  };

  const handleFinishShift = async () => {
    triggerImpact('heavy');
    const confirmed = await confirmFinishShift();
    if (confirmed) {
      changeStatus('offline');
    }
  };

  const handleReturnToPatrol = () => {
    triggerImpact('medium');
    changeStatus('on_duty');
  };

  return (
    <div className="fixed bottom-0 left-0 w-full bg-black/80 backdrop-blur-lg border-t border-gray-800 p-4 pb-safe z-50">
      {status === 'offline' ? (
        <button
          type="button"
          onClick={handleStartShift}
          className={`${baseButtonClass} bg-green-600 hover:bg-green-500`}
        >
          🟢 НАЧАТЬ СМЕНУ
        </button>
      ) : null}

      {status === 'on_duty' ? (
        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={handleBreak}
            className={`${baseButtonClass} bg-yellow-600 hover:bg-yellow-500`}
          >
            🟡 ОБЕД
          </button>
          <button
            type="button"
            onClick={handleFinishShift}
            className={`${baseButtonClass} bg-red-600 hover:bg-red-500`}
          >
            🔴 ЗАВЕРШИТЬ
          </button>
        </div>
      ) : null}

      {status === 'on_break' ? (
        <button
          type="button"
          onClick={handleReturnToPatrol}
          className={`${baseButtonClass} bg-green-600 hover:bg-green-500`}
        >
          🟢 ВЕРНУТЬСЯ В ПАТРУЛЬ
        </button>
      ) : null}
    </div>
  );
}
