import React, { useEffect, useMemo, useState } from 'react';
import compressImage from '../utils/imageCompressor';
import { saveMarkerToQueue } from '../store/markerQueue';
import { triggerImpact, triggerSelection, triggerNotification } from '../utils/haptics';

const MARKER_SUBMIT_ENDPOINT = process.env.REACT_APP_MARKER_SUBMIT_URL || '/api/markers';

const CATEGORY_OPTIONS = [
  { value: 'camera', label: '📷 Камера' },
  { value: 'incident', label: '⚠️ Инцидент' },
  { value: 'accident', label: '🚗 ДТП' },
  { value: 'suspicious_person', label: '👤 Подозрительное лицо' },
];

const getTelegramWebApp = () => {
  if (typeof window === 'undefined') return null;
  return window.Telegram?.WebApp ?? null;
};

const getCurrentPosition = () => new Promise((resolve, reject) => {
  if (!navigator.geolocation) {
    reject(new Error('geolocation_unavailable'));
    return;
  }

  navigator.geolocation.getCurrentPosition(
    (position) => {
      resolve({
        lat: position.coords.latitude,
        lon: position.coords.longitude,
      });
    },
    () => reject(new Error('geolocation_failed')),
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 },
  );
});

export default function SmartMarkerForm({ onClose }) {
  const [category, setCategory] = useState(CATEGORY_OPTIONS[0].value);
  const [description, setDescription] = useState('');
  const [photoFile, setPhotoFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [toast, setToast] = useState('');

  const isDirty = useMemo(
    () => Boolean(description.trim() || photoFile),
    [description, photoFile],
  );

  useEffect(() => {
    if (!previewUrl) return undefined;
    return () => URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  useEffect(() => {
    const tg = getTelegramWebApp();
    if (!tg) return undefined;

    const handleBack = () => {
      if (onClose) onClose();
    };

    if (isDirty) {
      tg.BackButton?.show?.();
      tg.BackButton?.onClick?.(handleBack);
      tg.enableClosingConfirmation?.();
    } else {
      tg.BackButton?.offClick?.(handleBack);
      tg.BackButton?.hide?.();
      tg.disableClosingConfirmation?.();
    }

    return () => {
      tg.BackButton?.offClick?.(handleBack);
      if (!isDirty) tg.BackButton?.hide?.();
    };
  }, [isDirty, onClose]);

  useEffect(() => {
    if (!toast) return undefined;
    const timeout = setTimeout(() => setToast(''), 2200);
    return () => clearTimeout(timeout);
  }, [toast]);

  const resetForm = () => {
    setCategory(CATEGORY_OPTIONS[0].value);
    setDescription('');
    setPhotoFile(null);
    setPreviewUrl('');
  };

  const handlePhotoChange = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const compressed = await compressImage(file);
      setPhotoFile(compressed);
      setPreviewUrl(URL.createObjectURL(compressed));
      triggerSelection();
    } catch (_error) {
      setToast('Не удалось обработать фото');
      triggerNotification('error');
    }
  };

  const submitOnline = async (payload) => {
    const response = await fetch(MARKER_SUBMIT_ENDPOINT, {
      method: 'POST',
      body: payload,
    });

    if (!response.ok) throw new Error('marker_submit_failed');
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (isSubmitting) return;

    setIsSubmitting(true);
    triggerImpact('heavy');

    try {
      const coords = await getCurrentPosition();
      const payload = {
        category,
        description: description.trim(),
        ...coords,
        photo: photoFile,
      };

      if (navigator.onLine) {
        const formData = new FormData();
        formData.append('category', payload.category);
        formData.append('description', payload.description);
        formData.append('lat', String(payload.lat));
        formData.append('lon', String(payload.lon));
        if (payload.photo) formData.append('photo', payload.photo);

        await submitOnline(formData);
        triggerNotification('success');
        setToast('Метка отправлена');
      } else {
        await saveMarkerToQueue(payload);
        triggerNotification('success');
        setToast('Сохранено в офлайн-очередь');
      }

      resetForm();
      if (onClose) onClose();
    } catch (_error) {
      triggerNotification('warning');
      setToast('Не удалось отправить метку');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="pointer-events-auto w-full max-w-md rounded-2xl border border-white/10 bg-black/80 p-4 backdrop-blur-lg">
      <h3 className="text-sm font-black uppercase tracking-wider text-cyan-200">Новая метка</h3>

      <form className="mt-3 space-y-3" onSubmit={handleSubmit}>
        <div className="overflow-x-auto">
          <div className="flex w-max gap-2 pb-1">
            {CATEGORY_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => {
                  setCategory(option.value);
                  triggerSelection();
                }}
                className={`rounded-full px-4 py-2 text-sm transition ${
                  category === option.value ? 'bg-cyan-600 text-white' : 'bg-gray-800 text-white'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        <textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Кратко опишите ситуацию"
          className="min-h-[96px] w-full rounded-xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm text-white outline-none focus:border-cyan-400"
        />

        <label className="flex cursor-pointer items-center justify-between rounded-xl border border-dashed border-cyan-400/40 bg-cyan-500/10 px-3 py-2 text-sm text-cyan-200">
          <span>{photoFile ? 'Фото выбрано' : 'Добавить фото'}</span>
          <input
            type="file"
            accept="image/*"
            capture="environment"
            onChange={handlePhotoChange}
            className="hidden"
          />
        </label>

        {previewUrl ? (
          <img src={previewUrl} alt="Предпросмотр" className="h-28 w-full rounded-xl object-cover" />
        ) : null}

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full rounded-xl bg-cyan-600 px-4 py-3 text-sm font-black uppercase tracking-wider text-white transition hover:bg-cyan-500 disabled:opacity-50"
        >
          {isSubmitting ? 'Отправка...' : 'Отправить'}
        </button>
      </form>

      {toast ? (
        <div className="mt-3 rounded-lg border border-white/15 bg-black/70 px-3 py-2 text-xs text-cyan-100">
          {toast}
        </div>
      ) : null}
    </div>
  );
}
