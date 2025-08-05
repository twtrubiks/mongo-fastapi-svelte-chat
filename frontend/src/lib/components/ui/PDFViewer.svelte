<script lang="ts">
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
  
  let showFallback = $state(false);
  
  // 關閉 PDF 檢視器
  function close() {
    show = false;
    onClose?.();
  }
  
  // 下載 PDF
  function downloadPDF() {
    const link = document.createElement('a');
    link.href = src;
    link.download = filename || 'document.pdf';
    link.target = '_blank';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
  
  // 在新視窗開啟
  function openInNewTab() {
    window.open(src, '_blank');
  }
  
  // 檢測 PDF 是否載入失敗
  function handlePDFError() {
    showFallback = true;
  }
  
  // 重置狀態
  $effect(() => {
    if (show && src) {
      showFallback = false;
    }
  });
</script>

{#if show}
  <div class="pdf-overlay" onclick={(e) => { if (e.target === e.currentTarget) close(); }} onkeydown={(e) => { if (e.key === 'Escape') close(); }} role="dialog" aria-modal="true" tabindex="0">
    <div class="pdf-container" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()} role="main">
      <div class="pdf-header">
        <h3>{title || filename || 'PDF 文檔'}</h3>
        <div class="pdf-actions">
          <button
            type="button"
            class="action-btn download-btn"
            onclick={downloadPDF}
            aria-label="下載 PDF"
            title="下載 PDF"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </button>
          
          <button
            type="button"
            class="action-btn open-btn"
            onclick={openInNewTab}
            aria-label="在新視窗開啟"
            title="在新視窗開啟"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </button>
          
          <button
            type="button"
            class="action-btn close-btn"
            onclick={close}
            aria-label="關閉"
            title="關閉"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
      
      <div class="pdf-content">
        {#if showFallback}
          <!-- 備選方案 -->
          <div class="pdf-fallback">
            <div class="fallback-content">
              <div class="fallback-icon">📄</div>
              <h4>無法載入 PDF 預覽</h4>
              <p>您的瀏覽器可能不支援內嵌 PDF 顯示</p>
              <div class="fallback-actions">
                <button
                  type="button"
                  class="fallback-btn primary"
                  onclick={openInNewTab}
                >
                  在新視窗開啟
                </button>
                <button
                  type="button"
                  class="fallback-btn secondary"
                  onclick={downloadPDF}
                >
                  下載檔案
                </button>
              </div>
            </div>
          </div>
        {:else}
          <!-- PDF 嵌入 -->
          <iframe
            {src}
            class="pdf-iframe"
            title="PDF 文檔預覽"
            loading="lazy"
            onerror={handlePDFError}
          ></iframe>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .pdf-overlay {
    @apply fixed inset-0 z-50 bg-black bg-opacity-75 flex items-center justify-center;
    @apply backdrop-blur-sm;
  }
  
  .pdf-container {
    @apply bg-white rounded-lg shadow-2xl w-full max-w-6xl h-full max-h-[90vh];
    @apply m-4 flex flex-col overflow-hidden;
  }
  
  .pdf-header {
    @apply flex items-center justify-between p-4 border-b border-gray-200;
    @apply bg-gray-50;
  }
  
  .pdf-header h3 {
    @apply text-lg font-semibold text-gray-900 truncate flex-1 mr-4;
  }
  
  .pdf-actions {
    @apply flex items-center space-x-2;
  }
  
  .action-btn {
    @apply p-2 rounded-md transition-colors duration-200;
    @apply border-none bg-transparent cursor-pointer;
    @apply flex items-center justify-center;
  }
  
  .download-btn {
    @apply text-blue-600 hover:bg-blue-100;
  }
  
  .open-btn {
    @apply text-green-600 hover:bg-green-100;
  }
  
  .close-btn {
    @apply text-gray-600 hover:bg-gray-100;
  }
  
  .pdf-content {
    @apply flex-1 relative overflow-hidden;
  }
  
  .pdf-iframe {
    @apply w-full h-full border-none;
  }
  
  .pdf-fallback {
    @apply w-full h-full flex items-center justify-center;
    @apply bg-gray-100;
  }
  
  .fallback-content {
    @apply text-center p-8 max-w-md;
  }
  
  .fallback-icon {
    @apply text-6xl mb-4;
  }
  
  .fallback-content h4 {
    @apply text-xl font-semibold text-gray-900 mb-2;
  }
  
  .fallback-content p {
    @apply text-gray-600 mb-6;
  }
  
  .fallback-actions {
    @apply flex flex-col sm:flex-row gap-3 justify-center;
  }
  
  .fallback-btn {
    @apply px-4 py-2 rounded-md font-medium transition-colors duration-200;
    @apply border-none cursor-pointer;
  }
  
  .fallback-btn.primary {
    @apply bg-blue-600 text-white hover:bg-blue-700;
  }
  
  .fallback-btn.secondary {
    @apply bg-gray-200 text-gray-900 hover:bg-gray-300;
  }
  
  /* 響應式設計 */
  @media (max-width: 768px) {
    .pdf-container {
      @apply m-2 max-h-[95vh];
    }
    
    .pdf-header {
      @apply p-3;
    }
    
    .pdf-header h3 {
      @apply text-base;
    }
    
    .pdf-actions {
      @apply space-x-1;
    }
    
    .action-btn {
      @apply p-1.5;
    }
    
    .action-btn svg {
      @apply w-4 h-4;
    }
  }
</style>