import { get } from 'svelte/store';
import { 
  notificationSettings, 
  browserNotificationManager, 
  soundNotificationManager 
} from '$lib/stores/notification.svelte';

export interface NotificationActionOptions {
  title?: string;
  message?: string;
  type?: 'info' | 'success' | 'warning' | 'error';
  sound?: boolean;
  browser?: boolean;
  vibrate?: boolean;
  duration?: number;
}

/**
 * Svelte Action：智能通知處理
 * 根據設置自動處理聲音、瀏覽器通知和震動
 */
export function notify(node: HTMLElement, options: NotificationActionOptions = {}) {
  const settings = get(notificationSettings);
  
  const defaultOptions: NotificationActionOptions = {
    type: 'info',
    sound: true,
    browser: true,
    vibrate: false,
    duration: 4000,
    ...options
  };

  function triggerNotification() {
    // 聲音通知
    if (defaultOptions.sound && settings.sound) {
      soundNotificationManager.playNotificationSound();
    }

    // 瀏覽器通知
    if (defaultOptions.browser && settings.browserNotifications && defaultOptions.title) {
      browserNotificationManager.showNotification(defaultOptions.title, {
        body: defaultOptions.message,
        tag: 'chat-notification',
        requireInteraction: false,
        silent: !settings.sound,
      });
    }

    // 震動通知（移動設備）
    if (defaultOptions.vibrate && 'navigator' in window && 'vibrate' in navigator) {
      navigator.vibrate([100, 50, 100]);
    }
  }

  function handleClick() {
    triggerNotification();
  }

  // 自動觸發通知（當元素出現時）
  if (defaultOptions.type !== 'info') {
    triggerNotification();
  }

  node.addEventListener('click', handleClick);

  return {
    update(newOptions: NotificationActionOptions) {
      Object.assign(defaultOptions, newOptions);
    },
    destroy() {
      node.removeEventListener('click', handleClick);
    }
  };
}

/**
 * Svelte Action：點擊外部關閉
 */
export function clickOutside(node: HTMLElement, callback: () => void) {
  function handleClick(event: MouseEvent) {
    if (!node.contains(event.target as Node)) {
      callback();
    }
  }

  document.addEventListener('click', handleClick, true);

  return {
    destroy() {
      document.removeEventListener('click', handleClick, true);
    }
  };
}

/**
 * Svelte Action：長按檢測
 */
export function longpress(node: HTMLElement, options: { duration?: number; callback?: () => void } = {}) {
  const { duration = 500, callback } = options;
  let timer: number;

  function handleMouseDown() {
    timer = window.setTimeout(() => {
      callback?.();
    }, duration);
  }

  function handleMouseUp() {
    clearTimeout(timer);
  }

  function handleMouseLeave() {
    clearTimeout(timer);
  }

  node.addEventListener('mousedown', handleMouseDown);
  node.addEventListener('mouseup', handleMouseUp);
  node.addEventListener('mouseleave', handleMouseLeave);

  // 觸摸事件支持
  node.addEventListener('touchstart', handleMouseDown);
  node.addEventListener('touchend', handleMouseUp);
  node.addEventListener('touchcancel', handleMouseLeave);

  return {
    update(newOptions: { duration?: number; callback?: () => void }) {
      Object.assign(options, newOptions);
    },
    destroy() {
      clearTimeout(timer);
      node.removeEventListener('mousedown', handleMouseDown);
      node.removeEventListener('mouseup', handleMouseUp);
      node.removeEventListener('mouseleave', handleMouseLeave);
      node.removeEventListener('touchstart', handleMouseDown);
      node.removeEventListener('touchend', handleMouseUp);
      node.removeEventListener('touchcancel', handleMouseLeave);
    }
  };
}

/**
 * Svelte Action：鍵盤快捷鍵
 */
export function hotkey(node: HTMLElement, options: { key: string; callback: () => void; ctrl?: boolean; alt?: boolean; shift?: boolean }) {
  function handleKeydown(event: KeyboardEvent) {
    const { key, callback, ctrl = false, alt = false, shift = false } = options;
    
    if (
      event.key === key &&
      event.ctrlKey === ctrl &&
      event.altKey === alt &&
      event.shiftKey === shift
    ) {
      event.preventDefault();
      callback();
    }
  }

  window.addEventListener('keydown', handleKeydown);

  return {
    update(newOptions: typeof options) {
      Object.assign(options, newOptions);
    },
    destroy() {
      window.removeEventListener('keydown', handleKeydown);
    }
  };
}

/**
 * Svelte Action：自動焦點
 */
export function autofocus(node: HTMLElement, enabled = true) {
  if (enabled) {
    // 延遲焦點以確保元素已完全渲染
    setTimeout(() => {
      node.focus();
    }, 10);
  }

  return {
    update(newEnabled: boolean) {
      if (newEnabled && !enabled) {
        setTimeout(() => {
          node.focus();
        }, 10);
      }
      enabled = newEnabled;
    }
  };
}

/**
 * Svelte Action：滾動到視圖
 */
export function scrollIntoView(node: HTMLElement, options: ScrollIntoViewOptions = { behavior: 'smooth' }) {
  node.scrollIntoView(options);

  return {
    update(newOptions: ScrollIntoViewOptions) {
      Object.assign(options, newOptions);
      node.scrollIntoView(options);
    }
  };
}

/**
 * Svelte Action：拖拽檢測
 */
export function draggable(node: HTMLElement, options: { onDrag?: (event: DragEvent) => void; onDrop?: (event: DragEvent) => void } = {}) {
  let isDragging = false;

  function handleDragStart(event: DragEvent) {
    isDragging = true;
    node.style.opacity = '0.5';
  }

  function handleDragEnd() {
    isDragging = false;
    node.style.opacity = '1';
  }

  function handleDrag(event: DragEvent) {
    if (isDragging) {
      options.onDrag?.(event);
    }
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault();
    options.onDrop?.(event);
  }

  function handleDragOver(event: DragEvent) {
    event.preventDefault();
  }

  node.draggable = true;
  node.addEventListener('dragstart', handleDragStart);
  node.addEventListener('dragend', handleDragEnd);
  node.addEventListener('drag', handleDrag);
  node.addEventListener('drop', handleDrop);
  node.addEventListener('dragover', handleDragOver);

  return {
    update(newOptions: typeof options) {
      Object.assign(options, newOptions);
    },
    destroy() {
      node.removeEventListener('dragstart', handleDragStart);
      node.removeEventListener('dragend', handleDragEnd);
      node.removeEventListener('drag', handleDrag);
      node.removeEventListener('drop', handleDrop);
      node.removeEventListener('dragover', handleDragOver);
    }
  };
}