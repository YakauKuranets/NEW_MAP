import React, { useMemo, useState, useCallback, useEffect, useRef } from 'react';
import DeckGL from '@deck.gl/react';
import { ColumnLayer } from '@deck.gl/layers';
import { FlyToInterpolator } from '@deck.gl/core';
import Map, { NavigationControl, Popup, Marker } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';

import useMapStore from '../store/useMapStore';
import {
  Layers, Flame, Target, Sun, Moon, MapPin,
  Loader2, Save, X, Upload, Monitor, Cctv, Search, CheckCircle2
} from 'lucide-react';

export default function CommandCenterMap({ theme, onToggleTheme }) {
  const { markers = [], activeMarkerId, draftMarker, setDraftMarker, addMarker, deleteMarker, setActiveMarker } = useMapStore();
  const [loadingAddress, setLoadingAddress] = useState(false);
  const [addressVerified, setAddressVerified] = useState(false);
  const fileInputRef = useRef(null);

  const [layersVisible, setLayersVisible] = useState({ markers: true, heatmap: false });
  const [formValues, setFormValues] = useState({ title: '', description: '', address: '', url: '', image: null, cameraType: 'remote' });
  const [viewState, setViewState] = useState({ longitude: 27.56, latitude: 53.9, zoom: 12, pitch: 45, bearing: 0 });

  const isDark = theme === 'dark';
  const activeMarker = useMemo(() => markers.find(m => m.id === activeMarkerId), [markers, activeMarkerId]);

  // ЦЕНТРИРОВАНИЕ ПРИ КЛИКЕ НА МЕТКУ В БОКОВОЙ ПАНЕЛИ
  useEffect(() => {
    if (activeMarkerId) {
      const targetMarker = markers.find(m => m.id === activeMarkerId);
      if (targetMarker && !isNaN(Number(targetMarker.lon)) && !isNaN(Number(targetMarker.lat))) {
        setViewState(prev => ({
          ...prev,
          longitude: Number(targetMarker.lon),
          latitude: Number(targetMarker.lat),
          zoom: 16,
          transitionDuration: 1500,
          transitionInterpolator: new FlyToInterpolator()
        }));
      }
    }
  }, [activeMarkerId, markers]);

  // Заполняем форму ТОЛЬКО при открытии нового draftMarker,
  // чтобы не стирать текст при геокодировании
  const prevDraftId = useRef(null);
  useEffect(() => {
    const isNewDraft = draftMarker && (!prevDraftId.current || prevDraftId.current !== draftMarker.id);
    const isOpeningFromNull = draftMarker && prevDraftId.current === null;

    if (isNewDraft || isOpeningFromNull) {
      setFormValues({
        title: draftMarker.title || '',
        description: draftMarker.description || '',
        address: draftMarker.address || '',
        url: draftMarker.url || '',
        image: draftMarker.image || null,
        cameraType: draftMarker.cameraType || 'remote'
      });
      setAddressVerified(!!draftMarker.address);
    }

    prevDraftId.current = draftMarker ? (draftMarker.id || 'new') : null;
  }, [draftMarker]);

  // ОБРАТНОЕ геокодирование (Клик -> Текст)
  const fetchAddress = async (lon, lat) => {
    setLoadingAddress(true);
    try {
      const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lon=${lon}&lat=${lat}`);
      const data = await res.json();
      const addr = data.display_name || "Координаты зафиксированы";
      setFormValues(prev => ({ ...prev, address: addr }));
      setAddressVerified(true);
    } catch (e) {
      setAddressVerified(false);
    } finally {
      setLoadingAddress(false);
    }
  };

  // ПРЯМОЕ геокодирование (Текст -> Координаты + Перелет)
  const forwardGeocode = async () => {
    if (!formValues.address) return;
    setLoadingAddress(true);
    try {
      const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(formValues.address)}`);
      const data = await res.json();

      if (data && data.length > 0) {
        const newLon = parseFloat(data[0].lon);
        const newLat = parseFloat(data[0].lat);
        const newAddr = data[0].display_name;

        // Обновляем координаты луча, но сохраняем форму
        setDraftMarker(prev => ({ ...prev, lon: newLon, lat: newLat }));
        setFormValues(prev => ({ ...prev, address: newAddr }));

        // Плавный перелет к найденному адресу
        setViewState(prev => ({
          ...prev,
          longitude: newLon,
          latitude: newLat,
          zoom: 16,
          transitionDuration: 1500,
          transitionInterpolator: new FlyToInterpolator()
        }));
        setAddressVerified(true);
      } else {
        alert("Локация не найдена. Уточните запрос.");
        setAddressVerified(false);
      }
    } catch (e) {
      console.error(e);
      setAddressVerified(false);
    } finally {
      setLoadingAddress(false);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => setFormValues(prev => ({ ...prev, image: reader.result }));
      reader.readAsDataURL(file);
    }
  };

  const handleContextMenu = useCallback((info) => {
    if (info.nativeEvent) info.nativeEvent.preventDefault();
    const [lon, lat] = info.coordinate;
    setDraftMarker({ lon, lat, id: undefined });
    fetchAddress(lon, lat);
  }, [setDraftMarker]);

  // Гарантируем, что координаты сохраняются вместе с формой
  const handleSave = () => {
    if (draftMarker.id) deleteMarker(draftMarker.id);
    addMarker({
      ...formValues, // Берем все из формы
      lon: Number(draftMarker.lon), // Обязательно берем координаты из черновика
      lat: Number(draftMarker.lat),
      id: draftMarker.id || Date.now().toString()
    });
    setDraftMarker(null);
  };

  const layers = [
    // Лазерный луч создания (остался в DeckGL)
    draftMarker && new ColumnLayer({
      id: 'laser-beam',
      data: [draftMarker],
      getPosition: d => [Number(d.lon), Number(d.lat)],
      getFillColor: [244, 63, 94, 255],
      radius: 2,
      getElevation: 500,
      extruded: true,
    })
  ].filter(Boolean);

  const panelBg = isDark ? 'bg-slate-900/80 border-slate-700/50' : 'bg-white/80 border-slate-300/50';

  return (
    <div className="w-full h-full relative overflow-hidden">

      {/* АБСОЛЮТНЫЙ УБИЙЦА БЕЛОГО ФОНА */}
      <style>{`
        div.maplibregl-popup-content {
          background: transparent !important;
          box-shadow: none !important;
          padding: 0 !important;
          border: none !important;
          border-radius: 0 !important;
        }
        div.maplibregl-popup-tip {
          display: none !important;
        }
        .maplibregl-marker {
          z-index: 10 !important;
        }
      `}</style>

      {/* ПАНЕЛЬ УПРАВЛЕНИЯ СЛОЯМИ */}
      <div className="absolute top-6 left-6 z-20 flex flex-col gap-2 w-48 pointer-events-auto">
        <button onClick={onToggleTheme} className={`flex items-center justify-between px-4 py-3 rounded-2xl backdrop-blur-xl border transition-all ${panelBg}`}>
          <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">{isDark ? 'Киберпанк' : 'Дневная'}</span>
          {isDark ? <Moon className="w-4 h-4 text-blue-400" /> : <Sun className="w-4 h-4 text-amber-500" />}
        </button>
        <div className={`backdrop-blur-xl border p-2 rounded-2xl transition-colors ${panelBg}`}>
          <div className="flex items-center gap-2 px-3 py-2 border-b border-slate-700 mb-1">
            <Layers className="w-4 h-4 text-blue-400" />
            <span className="text-[10px] font-black uppercase tracking-widest opacity-60 text-slate-400">Слои</span>
          </div>
          <LayerToggle active={layersVisible.markers} theme={theme} onClick={() => setLayersVisible(v => ({...v, markers: !v.markers}))} icon={<Target className="w-4 h-4" />} label="Объекты" />
          <LayerToggle active={layersVisible.heatmap} theme={theme} onClick={() => setLayersVisible(v => ({...v, heatmap: !v.heatmap}))} icon={<Flame className="w-4 h-4" />} label="Анализ" />
        </div>
      </div>

      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState: next }) => setViewState(next)}
        layers={layers}
        controller={true}
        onContextMenu={handleContextMenu}
      >
        <Map mapStyle={isDark ? 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json' : 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'}>
          <NavigationControl position="top-right" />

          {/* ПАРЯЩИЕ МЕТКИ (РОМБЫ) */}
          {layersVisible.markers && markers.map(marker => (
            !isNaN(Number(marker.lon)) && !isNaN(Number(marker.lat)) && (
              <Marker
                key={`marker-${marker.id}`}
                longitude={Number(marker.lon)}
                latitude={Number(marker.lat)}
                anchor="bottom"
                onClick={(e) => {
                  e.originalEvent.stopPropagation();
                  setActiveMarker(marker.id);
                }}
              >
                <div className="group relative flex flex-col items-center cursor-pointer transition-transform hover:scale-110">

                  {/* Tooltip при наведении */}
                  <div className="absolute bottom-full mb-2 opacity-0 group-hover:opacity-100 transition-all duration-300 translate-y-2 group-hover:translate-y-0 pointer-events-none whitespace-nowrap bg-slate-900/95 border border-slate-700 text-white text-[10px] font-bold uppercase px-3 py-1.5 rounded-xl shadow-xl backdrop-blur-md">
                    {marker.title || "БЕЗ НАЗВАНИЯ"}
                  </div>

                  {/* Ромб с анимацией */}
                  <div className="relative animate-bounce" style={{ animationDuration: '2s' }}>
                    <div className={`w-3 h-3 transform rotate-45 transition-all duration-300 shadow-[0_0_15px_currentColor] ${marker.cameraType === 'local' ? 'bg-blue-400 text-blue-400' : 'bg-rose-400 text-rose-400'}`} />
                    <div className="absolute inset-0 transform rotate-45 bg-white/40 scale-50" />
                  </div>

                  {/* Лазерная нить к земле */}
                  <div className={`w-[1px] h-4 opacity-60 transition-colors duration-300 ${marker.cameraType === 'local' ? 'bg-gradient-to-t from-transparent to-blue-400' : 'bg-gradient-to-t from-transparent to-rose-400'}`} />
                  <div className={`w-1.5 h-1.5 rounded-full mt-0.5 ${marker.cameraType === 'local' ? 'bg-blue-400' : 'bg-rose-400'} shadow-[0_0_10px_currentColor]`} />
                </div>
              </Marker>
            )
          ))}

          {/* ПОПАП ПРОСМОТРА СОХРАНЕННОЙ МЕТКИ */}
          {activeMarker && !isNaN(Number(activeMarker.lon)) && !isNaN(Number(activeMarker.lat)) && (
            <Popup
              longitude={Number(activeMarker.lon)}
              latitude={Number(activeMarker.lat)}
              anchor="bottom"
              offset={40} // Подняли выше, чтобы не перекрывать маркер
              onClose={() => setActiveMarker(null)}
              closeButton={false}
              closeOnClick={false}
              className="z-50"
            >
              <div
                className="w-64 p-4 rounded-[24px] backdrop-blur-xl bg-slate-900/95 border border-slate-700 shadow-[0_20px_50px_rgba(0,0,0,0.5)] text-white relative pointer-events-auto"
                onClick={(e) => e.stopPropagation()} // Изоляция
              >
                {/* Кнопка закрытия работает безупречно */}
                <button
                  onClick={(e) => { e.preventDefault(); e.stopPropagation(); setActiveMarker(null); }}
                  className="absolute top-4 right-4 text-slate-500 hover:text-white z-50 bg-slate-800 hover:bg-rose-500/20 rounded-full p-1 transition-colors cursor-pointer"
                >
                  <X size={14} />
                </button>

                {activeMarker.image && <img src={activeMarker.image} alt="" className="w-full h-32 object-cover rounded-[16px] mb-3 border border-slate-700" />}

                <div className="flex items-center gap-2 mb-1 pr-6">
                  {activeMarker.cameraType === 'local' ? <Monitor size={12} className="text-blue-400" /> : <Cctv size={12} className="text-rose-400" />}
                  <h3 className="font-bold text-sm uppercase tracking-wider truncate">{activeMarker.title || "БЕЗ НАЗВАНИЯ"}</h3>
                </div>

                <p className="text-[10px] opacity-60 mb-3 text-slate-300 line-clamp-2">{activeMarker.address}</p>
                <p className="text-xs leading-relaxed opacity-80 custom-scrollbar max-h-24 overflow-y-auto">{activeMarker.description}</p>
              </div>
            </Popup>
          )}
        </Map>
      </DeckGL>

      {/* МОДАЛЬНАЯ ФОРМА ФИКСАЦИИ/РЕДАКТИРОВАНИЯ */}
      {draftMarker && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm pointer-events-auto">
          <div
            className="w-[360px] p-6 rounded-[28px] backdrop-blur-2xl bg-slate-900/95 border border-rose-500/50 shadow-[0_0_50px_rgba(244,63,94,0.2)] text-white relative animate-in fade-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            <button onClick={() => setDraftMarker(null)} className="absolute top-5 right-5 text-slate-400 hover:text-white bg-white/5 hover:bg-rose-500/20 rounded-full p-1.5 transition-all cursor-pointer">
              <X size={18} />
            </button>

            <div className="flex items-center gap-2 mb-5">
              <div className="w-2 h-2 rounded-full bg-rose-500 animate-pulse shadow-[0_0_10px_rgba(244,63,94,0.8)]" />
              <p className="text-[10px] font-black text-rose-500 uppercase tracking-[0.2em]">
                {draftMarker.id ? "Редактирование объекта" : "Регистрация объекта"}
              </p>
            </div>

            <div className="space-y-4">
              <div>
                <input
                  value={formValues.title}
                  onChange={(e) => setFormValues({...formValues, title: e.target.value})}
                  placeholder="ID или Название..."
                  className="w-full bg-black/40 border border-slate-700 rounded-xl p-3 text-xs outline-none focus:border-rose-500 transition-colors text-white placeholder:text-slate-600"
                />
              </div>

              <div>
                <label className="text-[9px] font-bold text-slate-500 uppercase tracking-widest mb-2 block">Тип подключения</label>
                <div className="flex gap-2">
                  <button
                    onClick={() => setFormValues({...formValues, cameraType: 'local'})}
                    className={`flex-1 py-2.5 px-3 rounded-xl border flex items-center justify-center gap-2 text-[10px] font-bold uppercase transition-all ${
                      formValues.cameraType === 'local' ? 'bg-blue-500/20 border-blue-500/50 text-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.2)]' : 'bg-black/40 border-slate-700 text-slate-500 hover:border-slate-500'
                    }`}
                  >
                    <Monitor size={14} /> Локальная
                  </button>
                  <button
                    onClick={() => setFormValues({...formValues, cameraType: 'remote'})}
                    className={`flex-1 py-2.5 px-3 rounded-xl border flex items-center justify-center gap-2 text-[10px] font-bold uppercase transition-all ${
                      formValues.cameraType === 'remote' ? 'bg-rose-500/20 border-rose-500/50 text-rose-400 shadow-[0_0_15px_rgba(244,63,94,0.2)]' : 'bg-black/40 border-slate-700 text-slate-500 hover:border-slate-500'
                    }`}
                  >
                    <Cctv size={14} /> Удаленная
                  </button>
                </div>
              </div>

              {/* УМНОЕ ПОЛЕ АДРЕСА С ПРЯМЫМ ПОИСКОМ */}
              <div>
                <label className="text-[9px] font-bold text-slate-500 uppercase tracking-widest mb-1 flex items-center gap-2">
                  <span>Локация</span>
                  {addressVerified && <CheckCircle2 size={12} className="text-emerald-500" />}
                </label>
                <div className="relative flex items-center bg-black/30 border border-slate-700 rounded-xl p-1 focus-within:border-rose-500 transition-colors">
                  <MapPin size={14} className="text-rose-500 shrink-0 ml-3" />
                  <input
                    value={formValues.address}
                    onChange={(e) => {
                      setFormValues({...formValues, address: e.target.value});
                      setAddressVerified(false);
                    }}
                    onKeyDown={(e) => e.key === 'Enter' && forwardGeocode()}
                    placeholder="Введите адрес и нажмите поиск..."
                    className="bg-transparent border-none outline-none text-[10px] w-full text-slate-300 placeholder:text-slate-600 px-3 py-2"
                  />
                  <button
                    onClick={forwardGeocode}
                    disabled={loadingAddress}
                    title="Найти на карте"
                    className="p-2 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 transition-colors mr-1 cursor-pointer"
                  >
                    {loadingAddress ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
                  </button>
                </div>
              </div>

              <div>
                <textarea
                  value={formValues.description}
                  onChange={(e) => setFormValues({...formValues, description: e.target.value})}
                  placeholder="Дополнительные детали..."
                  className="w-full bg-black/40 border border-slate-700 rounded-xl p-3 text-xs h-16 outline-none focus:border-rose-500 transition-colors resize-none custom-scrollbar text-white placeholder:text-slate-600"
                />
              </div>

              <div>
                <input
                  value={formValues.url}
                  onChange={(e) => setFormValues({...formValues, url: e.target.value})}
                  placeholder="URL потока..."
                  className="w-full bg-black/40 border border-slate-700 rounded-xl p-3 text-xs outline-none focus:border-blue-500 transition-colors text-white placeholder:text-slate-600"
                />
              </div>

              <div
                onClick={() => fileInputRef.current.click()}
                className={`flex items-center justify-center gap-2 py-3 rounded-xl border border-dashed cursor-pointer transition-all ${
                  formValues.image ? 'border-emerald-500 bg-emerald-500/10 text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.15)]' : 'border-slate-600 text-slate-400 hover:border-slate-400 hover:bg-white/5'
                }`}
              >
                <Upload size={14} />
                <span className="text-[10px] font-bold uppercase tracking-widest">{formValues.image ? 'Снимок прикреплен' : 'Прикрепить кадр'}</span>
                <input type="file" ref={fileInputRef} className="hidden" accept="image/*" onChange={handleFileChange} />
              </div>

              <button
                onClick={handleSave}
                disabled={loadingAddress}
                className="w-full py-4 mt-2 bg-rose-600 hover:bg-rose-500 disabled:opacity-50 disabled:grayscale rounded-xl text-[11px] font-black uppercase tracking-widest shadow-[0_0_20px_rgba(244,63,94,0.3)] hover:shadow-[0_0_30px_rgba(244,63,94,0.5)] flex items-center justify-center gap-2 transition-all text-white cursor-pointer"
              >
                <Save size={16} /> Сохранить изменения
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function LayerToggle({ active, onClick, icon, label, theme }) {
  const isDark = theme === 'dark';
  return (
    <button onClick={onClick} className={`flex items-center gap-3 w-full p-2.5 rounded-xl transition-all duration-300 ${active ? (isDark ? 'bg-blue-500/20 text-blue-400' : 'bg-blue-100 text-blue-700') : (isDark ? 'text-slate-500 hover:bg-slate-800/50' : 'text-slate-500 hover:bg-slate-100')}`}>
      {icon}
      <span className="text-xs font-medium">{label}</span>
    </button>
  );
}