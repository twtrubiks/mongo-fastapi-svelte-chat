// 元件測試（jsdom）共用設定
//
// jsdom 沒有 Web Animations API，Svelte 的轉場會呼叫 element.animate。
// 回傳立即結束的動畫：離場轉場結束後元素才會移除，不結束的話元素會一直留在畫面上
Element.prototype.animate = function () {
  const animation = {
    onfinish: null as (() => void) | null,
    playState: 'finished',
    effect: null,
    cancel() {},
  };
  queueMicrotask(() => animation.onfinish?.());
  return animation as unknown as Animation;
};
