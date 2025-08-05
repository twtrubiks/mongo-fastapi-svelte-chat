<script lang="ts">
  import { fade, scale } from 'svelte/transition';
  import { elasticOut } from 'svelte/easing';
  import { Button } from '$lib/components/ui';
  
  interface Props {
    show?: boolean;
    src?: string;
    title?: string;
    filename?: string;
    onClose?: () => void;
  }
  
  let {
    show = $bindable(false),
    src = '',
    title = '',
    filename = '',
    onClose = undefined
  }: Props = $props();
  
  // 狀態
  let videoElement: HTMLVideoElement | undefined = $state();
  let isLoading = $state(true);
  let hasError = $state(false);
  let isPlaying = $state(false);
  
  // 響應式檢查是否為移動裝置
  let isMobile = $derived(typeof window !== 'undefined' && window.innerWidth < 768);
  
  // 關閉播放器
  function close() {
    if (videoElement) {
      videoElement.pause();
    }
    show = false;
    onClose?.();
  }
  
  // 鍵盤事件處理
  function handleKeydown(event: KeyboardEvent) {
    if (!show) return;
    
    switch (event.key) {
      case 'Escape':
        close();
        break;
      case ' ':
        event.preventDefault();
        togglePlay();
        break;
    }
  }
  
  // 切換播放/暫停
  function togglePlay() {
    if (!videoElement) return;
    
    if (isPlaying) {
      videoElement.pause();
    } else {
      videoElement.play();
    }
  }
  
  // 影片載入完成
  function handleLoadedData() {
    isLoading = false;
    hasError = false;
  }
  
  // 影片載入錯誤
  function handleError(event: Event) {
    isLoading = false;
    hasError = true;
  }
  
  // 影片開始載入
  function handleLoadStart() {
    // 不在這裡設置 isLoading = true，因為在 effect 中已經設置了
  }
  
  // 影片可以開始播放（有足夠數據）
  function handleCanPlay() {
    isLoading = false;
    hasError = false;
  }
  
  // 影片可以連續播放（不需要緩衝）
  function handleCanPlayThrough() {
    isLoading = false;
    hasError = false;
  }
  
  // 影片載入元數據
  function handleLoadedMetadata() {
    // 元數據載入完成通常表示影片可以顯示，但還沒有足夠數據播放
    // 先不在這裡設置 isLoading = false，等待 canplay 事件
  }
  
  // 影片播放狀態改變
  function handlePlay() {
    isPlaying = true;
  }
  
  function handlePause() {
    isPlaying = false;
  }
  
  // 重置狀態
  $effect(() => {
    if (show && src) {
      isLoading = true;
      hasError = false;
      isPlaying = false;
    } else if (!show) {
      // 關閉時重置狀態
      isLoading = true;
      hasError = false;
      isPlaying = false;
    }
  });
</script>

<svelte:window onkeydown={handleKeydown} />

{#if show}
  <!-- 背景遮罩 -->
  <div 
    class="video-player-overlay"
    in:fade={{ duration: 200 }}
    out:fade={{ duration: 200 }}
    onclick={(e) => { if (e.target === e.currentTarget) close(); }}
    onkeydown={(e) => { if (e.key === 'Escape') close(); }}
    role="dialog"
    aria-modal="true"
    aria-label="影片播放器"
    tabindex="0"
  >
    <!-- 播放器容器 -->
    <div 
      class="video-player-container"
      in:scale={{ duration: 300, easing: elasticOut }}
      out:scale={{ duration: 200 }}
    >
      <!-- 標題列 -->
      <div class="video-header">
        <h3 class="video-title">{title || filename || '影片播放'}</h3>
        <Button
          variant="ghost"
          size="sm"
          onclick={close}
          class="close-button"
          aria-label="關閉播放器"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </Button>
      </div>
      
      <!-- 影片區域 -->
      <div class="video-content">
        <!-- 影片元素（始終渲染，讓瀏覽器處理載入） -->
        <video
          bind:this={videoElement}
          {src}
          controls
          class="video-element"
          onloadstart={handleLoadStart}
          onloadeddata={handleLoadedData}
          onloadedmetadata={handleLoadedMetadata}
          aria-label={filename || '影片播放器'}
          oncanplay={handleCanPlay}
          oncanplaythrough={handleCanPlayThrough}
          onerror={handleError}
          onplay={handlePlay}
          onpause={handlePause}
          preload="metadata"
        >
          <!-- 添加空的字幕軌道以滿足無障礙性要求 -->
          <track kind="captions" src="" label="No captions available" default />
          您的瀏覽器不支援影片播放。
        </video>
        
        <!-- 載入狀態覆蓋層 -->
        {#if isLoading && !hasError}
          <div class="loading-overlay">
            <div class="loading-spinner"></div>
            <p>載入中...</p>
          </div>
        {/if}
        
        <!-- 錯誤狀態覆蓋層 -->
        {#if hasError}
          <div class="error-overlay">
            <div class="error-icon">⚠️</div>
            <p>影片載入失敗</p>
            <Button
              variant="primary"
              size="sm"
              onclick={() => window.open(src, '_blank')}
            >
              在新視窗開啟
            </Button>
          </div>
        {/if}
      </div>
      
      <!-- 控制按鈕 -->
      <div class="video-actions">
        <Button
          variant="ghost"
          size="sm"
          onclick={() => window.open(src, '_blank')}
          class="action-button"
        >
          在新視窗開啟
        </Button>
        <Button
          variant="ghost" 
          size="sm"
          onclick={() => {
            const link = document.createElement('a');
            link.href = src;
            link.download = filename || 'video';
            link.click();
          }}
          class="action-button"
        >
          下載影片
        </Button>
      </div>
    </div>
  </div>
{/if}

<style>
  .video-player-overlay {
    @apply fixed inset-0 z-50 flex items-center justify-center;
    @apply bg-black bg-opacity-75 backdrop-blur-sm;
  }
  
  .video-player-container {
    @apply relative w-full max-w-4xl mx-4 bg-white rounded-lg shadow-2xl;
    @apply overflow-hidden max-h-[90vh] flex flex-col;
  }
  
  .video-header {
    @apply flex items-center justify-between p-4 border-b border-gray-200;
    @apply bg-gray-50;
  }
  
  .video-title {
    @apply text-lg font-semibold text-gray-900 truncate flex-1 mr-4;
  }
  
  
  .video-content {
    @apply flex-1 flex items-center justify-center min-h-96;
    @apply bg-black relative;
  }
  
  .video-element {
    @apply w-full h-full max-h-[70vh];
  }
  
  .loading-overlay,
  .error-overlay {
    @apply absolute inset-0 flex flex-col items-center justify-center space-y-4;
    @apply bg-black bg-opacity-75 text-white p-8 z-10;
  }
  
  .loading-spinner {
    @apply w-12 h-12 border-4 border-white border-t-transparent rounded-full;
    animation: spin 1s linear infinite;
  }
  
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
  
  .error-icon {
    @apply text-4xl;
  }
  
  .video-actions {
    @apply flex items-center justify-center gap-2 p-4;
    @apply bg-gray-50 border-t border-gray-200;
  }
  
  /* 響應式設計 */
  @media (max-width: 768px) {
    .video-player-container {
      @apply mx-2 max-h-[95vh];
    }
    
    .video-header {
      @apply p-3;
    }
    
    .video-title {
      @apply text-base;
    }
    
    .video-actions {
      @apply flex-col gap-2 p-3;
    }
  }
</style>