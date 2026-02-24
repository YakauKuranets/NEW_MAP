const TWA_COLOR = '#050505';

const getTelegramWebApp = () => {
  if (typeof window === 'undefined') return null;
  return window.Telegram?.WebApp ?? null;
};

/**
 * Initializes Telegram Web App native behavior and visual settings.
 * Safe to call multiple times.
 */
export function setupTelegramWebApp() {
  const tg = getTelegramWebApp();
  if (!tg) return null;

  tg.ready();
  tg.expand();

  if (typeof tg.disableVerticalSwipes === 'function') {
    tg.disableVerticalSwipes();
  }

  if (typeof tg.enableClosingConfirmation === 'function') {
    tg.enableClosingConfirmation();
  }

  tg.setHeaderColor(TWA_COLOR);
  tg.setBackgroundColor(TWA_COLOR);

  return tg;
}

/**
 * Triggers impact haptic feedback for generic button interactions.
 * @param {'light'|'medium'|'heavy'|'rigid'|'soft'} style
 */
export function triggerImpact(style = 'light') {
  const tg = getTelegramWebApp();
  const haptic = tg?.HapticFeedback;
  if (!haptic || typeof haptic.impactOccurred !== 'function') return;

  haptic.impactOccurred(style);
}

/**
 * Triggers notification haptic feedback for status events.
 * @param {'error'|'success'|'warning'} type
 */
export function triggerNotification(type = 'success') {
  const tg = getTelegramWebApp();
  const haptic = tg?.HapticFeedback;
  if (!haptic || typeof haptic.notificationOccurred !== 'function') return;

  haptic.notificationOccurred(type);
}

/**
 * Triggers selection haptic feedback for lightweight state switches.
 */
export function triggerSelection() {
  const tg = getTelegramWebApp();
  const haptic = tg?.HapticFeedback;
  if (!haptic || typeof haptic.selectionChanged !== 'function') return;

  haptic.selectionChanged();
}

export default setupTelegramWebApp;
