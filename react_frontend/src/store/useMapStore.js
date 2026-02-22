import { create } from '../vendor/zustand';

const useMapStore = create((set) => ({
  // --- СОСТОЯНИЕ (STATE) ---

  // Основной массив сохраненных объектов (метки с описанием, фото и ссылками)
  markers: [],

  // ID метки, которая выбрана в данный момент (для Popup и центрирования)
  activeMarkerId: null,

  // Временная точка (прицел), возникающая при правом клике, но еще не сохраненная
  draftMarker: null,

  // --- ДЕЙСТВИЯ (ACTIONS) ---

  // Создать временный черновик метки (вызывается при клике/правом клике на карту)
  setDraftMarker: (data) => set({
    draftMarker: data,
    activeMarkerId: null
  }),

  // Убрать черновик (если отменили создание)
  clearDraftMarker: () => set({ draftMarker: null }),

  // Добавить готовую метку в основную базу
  addMarker: (markerData) => set((state) => ({
    markers: [
      ...state.markers,
      {
        id: Date.now().toString(), // Генерация уникального ID
        ...markerData
      }
    ],
    draftMarker: null // Очищаем черновик после сохранения
  })),

  // Обновить существующую метку (редактирование описания, фото и т.д.)
  updateMarker: (id, updatedData) => set((state) => ({
    markers: state.markers.map((m) =>
      m.id === id ? { ...m, ...updatedData } : m
    )
  })),

  // Удалить метку из базы
  deleteMarker: (id) => set((state) => ({
    markers: state.markers.filter((m) => m.id !== id),
    activeMarkerId: state.activeMarkerId === id ? null : state.activeMarkerId
  })),

  // Сделать метку активной (для FlyTo перелета и открытия окна описания)
  setActiveMarker: (id) => set({
    activeMarkerId: id,
    draftMarker: null
  }),

  // Полный сброс всех данных
  reset: () => set({
    markers: [],
    activeMarkerId: null,
    draftMarker: null
  }),
}));

export default useMapStore;