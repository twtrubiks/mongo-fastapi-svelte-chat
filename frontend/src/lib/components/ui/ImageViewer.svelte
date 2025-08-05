<script lang="ts">
  import { Button } from '$lib/components/ui';
  
  interface Props {
    show?: boolean;
    src?: string;
    alt?: string;
    title?: string;
    onClose?: () => void;
  }
  
  let {
    show = $bindable(false),
    src = '',
    alt = '',
    title = '',
    onClose = undefined
  }: Props = $props();
  
  let imageLoaded = $state(false);
  let imageError = $state(false);
  let scale = $state(1);
  let translateX = $state(0);
  let translateY = $state(0);
  let isDragging = $state(false);
  let dragStartX = $state(0);
  let dragStartY = $state(0);
  let startTranslateX = $state(0);
  let startTranslateY = $state(0);
  
  // 重置狀態
  function reset() {
    scale = 1;
    translateX = 0;
    translateY = 0;
    imageLoaded = false;
    imageError = false;
  }
  
  // 關閉查看器
  function close() {
    show = false;
    reset();
    onClose?.();
  }
  
  // 縮放
  function zoomIn() {
    scale = Math.min(scale * 1.5, 5);
  }
  
  function zoomOut() {
    scale = Math.max(scale / 1.5, 0.5);
  }
  
  function resetZoom() {
    scale = 1;
    translateX = 0;
    translateY = 0;
  }
  
  // 處理滾輪縮放
  function handleWheel(event: WheelEvent) {
    event.preventDefault();
    
    if (event.deltaY > 0) {
      zoomOut();
    } else {
      zoomIn();
    }
  }
  
  // 處理拖拽
  function handleMouseDown(event: MouseEvent) {
    if (scale <= 1) return;
    
    isDragging = true;
    dragStartX = event.clientX;
    dragStartY = event.clientY;
    startTranslateX = translateX;
    startTranslateY = translateY;
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }
  
  function handleMouseMove(event: MouseEvent) {
    if (!isDragging) return;
    
    const deltaX = event.clientX - dragStartX;
    const deltaY = event.clientY - dragStartY;
    
    translateX = startTranslateX + deltaX;
    translateY = startTranslateY + deltaY;
  }
  
  function handleMouseUp() {
    isDragging = false;
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
  }
  
  // 處理鍵盤事件
  function handleKeyDown(event: KeyboardEvent) {
    switch (event.key) {
      case 'Escape':
        close();
        break;
      case '+':
      case '=':
        zoomIn();
        break;
      case '-':
        zoomOut();
        break;
      case '0':
        resetZoom();
        break;
    }
  }
  
  // 處理圖片載入
  function handleImageLoad() {
    imageLoaded = true;
    imageError = false;
  }
  
  function handleImageError() {
    imageLoaded = false;
    imageError = true;
  }
  
  // 監聽 show 變化
  $effect(() => {
    if (show) {
      reset();
    }
  });
</script>

<svelte:window onkeydown={handleKeyDown} />

{#if show}
  <div class="image-viewer" onclick={(e) => { if (e.target === e.currentTarget) close(); }} onkeydown={handleKeyDown} role="dialog" aria-modal="true" aria-labelledby="image-viewer-title" tabindex="-1">
    <!-- 背景遮罩 -->
    <div class="viewer-backdrop" onclick={close} onkeydown={(e) => e.key === 'Enter' && close()} role="button" tabindex="0" aria-label="關閉圖片檢視器"></div>
    
    <!-- 工具欄 -->
    <div class="viewer-toolbar">
      <div class="toolbar-left">
        {#if title}
          <h3 class="viewer-title">{title}</h3>
        {/if}
      </div>
      
      <div class="toolbar-right">
        <Button
          variant="ghost"
          size="sm"
          onclick={zoomOut}
          disabled={scale <= 0.5}
          aria-label="縮小"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6" />
          </svg>
        </Button>
        
        <span class="zoom-level">{Math.round(scale * 100)}%</span>
        
        <Button
          variant="ghost"
          size="sm"
          onclick={zoomIn}
          disabled={scale >= 5}
          aria-label="放大"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v6m-3-3h6" />
          </svg>
        </Button>
        
        <Button
          variant="ghost"
          size="sm"
          onclick={resetZoom}
          aria-label="重置縮放"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </Button>
        
        <Button
          variant="ghost"
          size="sm"
          onclick={close}
          aria-label="關閉"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </Button>
      </div>
    </div>
    
    <!-- 圖片容器 -->
    <div
      class="image-container"
      class:dragging={isDragging}
      onwheel={handleWheel}
      onmousedown={handleMouseDown}
      role="img"
      aria-label={alt || '圖片檢視器'}
    >
      {#if imageError}
        <div class="image-error">
          <svg class="w-16 h-16 text-base-content opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          <p class="error-text">圖片載入失敗</p>
        </div>
      {:else}
        <img
          {src}
          {alt}
          class="viewer-image"
          class:loaded={imageLoaded}
          style="transform: scale({scale}) translate({translateX}px, {translateY}px)"
          onload={handleImageLoad}
          onerror={handleImageError}
          ondragstart={(e) => e.preventDefault()}
        />
        
        {#if !imageLoaded}
          <div class="image-loading">
            <div class="loading-spinner"></div>
            <p class="loading-text">載入中...</p>
          </div>
        {/if}
      {/if}
    </div>
    
    <!-- 操作提示 -->
    <div class="viewer-hints">
      <p class="hint-text">
        滾輪縮放 · 拖拽移動 · ESC 關閉
      </p>
    </div>
  </div>
{/if}

<style>
  .image-viewer {
    @apply fixed inset-0 z-50 flex flex-col bg-black opacity-90 backdrop-blur-sm;
  }
  
  .viewer-backdrop {
    @apply absolute inset-0 cursor-pointer;
  }
  
  .viewer-toolbar {
    @apply relative z-10 flex items-center justify-between p-4 bg-black opacity-50;
  }
  
  .toolbar-left {
    @apply flex items-center;
  }
  
  .viewer-title {
    @apply text-white font-medium truncate max-w-md;
  }
  
  .toolbar-right {
    @apply flex items-center space-x-2;
  }
  
  .zoom-level {
    @apply text-white text-sm font-medium px-2;
  }
  
  .image-container {
    @apply relative flex-1 flex items-center justify-center overflow-hidden;
  }
  
  .image-container.dragging {
    @apply cursor-grabbing;
  }
  
  .viewer-image {
    @apply max-w-full max-h-full object-contain cursor-grab transition-opacity duration-200 opacity-0 select-none;
  }
  
  .viewer-image.loaded {
    @apply opacity-100;
  }
  
  .image-container.dragging .viewer-image {
    @apply cursor-grabbing;
  }
  
  .image-error {
    @apply flex flex-col items-center justify-center text-white;
  }
  
  .error-text {
    @apply mt-4 text-lg;
  }
  
  .image-loading {
    @apply absolute inset-0 flex flex-col items-center justify-center text-white;
  }
  
  .loading-spinner {
    @apply w-8 h-8 border-2 border-white opacity-30 border-t-white rounded-full animate-spin;
  }
  
  .loading-text {
    @apply mt-4 text-sm;
  }
  
  .viewer-hints {
    @apply relative z-10 p-4 text-center;
  }
  
  .hint-text {
    @apply text-white opacity-70 text-sm;
  }
  
  /* 工具欄按鈕樣式 */
  .viewer-toolbar :global(.btn) {
    @apply text-white hover:bg-white hover:opacity-20;
  }
  
  .viewer-toolbar :global(.btn:disabled) {
    @apply opacity-50 cursor-not-allowed;
  }
</style>