<script lang="ts">
  import { Button } from '$lib/components/ui';
  import FileUpload from '$lib/components/ui/FileUpload.svelte';
  import { debounce, isSupportedFileType, isFileSizeValid, getMaxFileSize, getAcceptString } from '$lib/utils';
  import { messageStatusStore } from '$lib/stores/messageStatus.svelte';
  import { messageRetryManager } from '$lib/utils/messageRetry';
  import type { MessageStatus } from '$lib/stores/messageStatus.svelte';
  
  // Svelte 5 callback props - 使用正確的語法
  let { 
    onSend = undefined,
    onFileUploaded = undefined,
    onFileSelected = undefined,
    onError = undefined,
    disabled = false,
    placeholder = '輸入訊息...',
    maxLength = 2000,
    allowFiles = true,
    allowedFileTypes = undefined
  } = $props();
  
  let message = $state('');
  let textArea: HTMLTextAreaElement;
  let fileInput: HTMLInputElement;
  let fileUploadComponent: any; // FileUpload 組件引用
  let isComposing = $state(false);
  let isDragging = $state(false);
  let dragCounter = $state(0);
  let showFileUpload = $state(false);
  let currentMessageId = $state<string | null>(null);
  
  // 監聽當前訊息的發送狀態 - 使用 Svelte 5 $derived.by
  let sendingStatus = $derived.by(() => {
    // 確保 store 已初始化
    const storeValue = messageStatusStore.state;
    if (currentMessageId && storeValue) {
      const status = storeValue[currentMessageId];
      return status?.status || 'idle';
    }
    return 'idle';
  });
  
  
  // 調整文字區域高度
  function adjustTextAreaHeight() {
    if (!textArea) return;
    
    textArea.style.height = 'auto';
    textArea.style.height = Math.min(textArea.scrollHeight, 120) + 'px';
  }
  
  // 防抖調整高度
  const debouncedAdjustHeight = debounce(adjustTextAreaHeight, 100);
  
  // 發送訊息
  function sendMessage() {
    // console.log('[MessageInput] sendMessage 被調用');
    const content = message.trim();
    // console.log('[MessageInput] content:', content, 'disabled:', disabled, 'sendingStatus:', sendingStatus);
    
    if (!content || disabled || sendingStatus === 'sending') {
      // console.log('[MessageInput] 條件不滿足，取消發送');
      return;
    }
    
    // 生成訊息 ID
    const messageId = `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    currentMessageId = messageId;
    
    // 添加到重試佇列
    messageRetryManager.addToRetryQueue({
      id: messageId,
      content,
      type: 'text'
    });
    
    // 使用 callback props 發送
    // console.log('[MessageInput] onSend 是否存在:', !!onSend);
    if (onSend) {
      // console.log('[MessageInput] 調用 onSend');
      onSend({
        content,
        type: 'text',
        messageId
      });
    }
    
    message = '';
    adjustTextAreaHeight();
    
    // 清除狀態延遲
    setTimeout(() => {
      if (sendingStatus === 'sent') {
        currentMessageId = null;
      }
    }, 2000);
  }
  
  // 重試發送
  async function retryMessage() {
    if (!currentMessageId) return;
    
    const success = await messageRetryManager.manualRetry(currentMessageId);
    if (success) {
      setTimeout(() => {
        currentMessageId = null;
      }, 1000);
    }
  }
  
  // 處理按鍵事件
  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey && !isComposing) {
      event.preventDefault();
      sendMessage();
    }
  }
  
  // 處理輸入事件
  function handleInput() {
    debouncedAdjustHeight();
  }
  
  // 處理檔案選擇
  function handleFileSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    const files = input.files;
    
    if (files && files.length > 0) {
      const file = files[0];
      
      // 檢查檔案類型
      if (!isSupportedFileType(file, allowedFileTypes)) {
        const typeDesc = allowedFileTypes ? allowedFileTypes.join('、') : '所有支援的類型';
        const errorData = { message: `不支援的檔案類型，支援：${typeDesc}` };
        if (onError) {
          onError(errorData);
        } else {
          }
        return;
      }
      
      // 檢查檔案大小
      if (!isFileSizeValid(file)) {
        const maxSize = getMaxFileSize(file);
        const errorData = { message: `檔案大小不能超過 ${maxSize}MB` };
        if (onError) {
          onError(errorData);
        } else {
          }
        return;
      }
      
      // 使用 callback props 通知檔案選擇
      if (onFileSelected) {
        onFileSelected({ file });
      }
    }
    
    // 清空檔案輸入
    input.value = '';
  }
  
  // 檔案上傳相關
  function handleFileUpload(data: { files: File[] }) {
    // FileUpload 組件會自動上傳，我們不需要在這裡做任何事
    // 只需等待 uploaded 事件
  }
  
  function handleFileUploaded(data: { files: File[]; results: any[] }) {
    const { files, results } = data;
    
    if (results && results.length > 0) {
      const result = results[0];
      
      if (result.result && result.result.success) {
        // BFF API 回應結構: { success: true, data: { file: { url: ... } } }
        const fileData = result.result.data?.file;
        
        if (fileData?.url) {
          
          // 先關閉面板
          showFileUpload = false;
          
          // 準備事件資料
          const eventData = { 
            file: result.file, 
            url: fileData.url, 
            filename: fileData.filename || result.file.name
          };
          
          // 使用 Svelte 5 callback props
          if (onFileUploaded) {
            onFileUploaded(eventData);
          } else {
          }
          
        } else {
          
          const errorData = { message: '上傳回應中沒有檔案URL' };
          if (onError) {
            onError(errorData);
          } else {
              }
          showFileUpload = false;
        }
      } else if (result.error) {
        const errorData = { message: result.error.message || '上傳失敗' };
        if (onError) {
          onError(errorData);
        } else {
          }
        showFileUpload = false;
      }
    } else {
      showFileUpload = false;
    }
  }
  
  function handleFileUploadError(errorData: { message: string }) {
    if (onError) {
      onError(errorData);
    } else {
      console.error('檔案上傳錯誤:', errorData.message);
    }
  }
  
  function toggleFileUpload() {
    showFileUpload = !showFileUpload;
  }
  
  // 處理拖拽事件
  function handleDragEnter(event: DragEvent) {
    // 如果 FileUpload 面板已經打開，不處理拖拽
    if (showFileUpload) return;
    
    event.preventDefault();
    dragCounter++;
    isDragging = true;
  }
  
  function handleDragOver(event: DragEvent) {
    // 如果 FileUpload 面板已經打開，不處理拖拽
    if (showFileUpload) return;
    
    event.preventDefault();
  }
  
  function handleDragLeave(event: DragEvent) {
    // 如果 FileUpload 面板已經打開，不處理拖拽
    if (showFileUpload) return;
    
    event.preventDefault();
    dragCounter--;
    if (dragCounter === 0) {
      isDragging = false;
    }
  }
  
  function handleDrop(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    isDragging = false;
    dragCounter = 0;
    
    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      const file = files[0];
      
      // 基本驗證
      if (!isSupportedFileType(file, allowedFileTypes)) {
        const typeDesc = allowedFileTypes ? allowedFileTypes.join('、') : '所有支援的類型';
        const errorData = { message: `不支援的檔案類型，支援：${typeDesc}` };
        if (onError) {
          onError(errorData);
        } else {
          }
        return;
      }
      
      if (!isFileSizeValid(file)) {
        const maxSize = getMaxFileSize(file);
        const errorData = { message: `檔案大小不能超過 ${maxSize}MB` };
        if (onError) {
          onError(errorData);
        } else {
          }
        return;
      }
      
      // 如果 FileUpload 面板已經打開，直接使用組件處理
      if (showFileUpload && fileUploadComponent) {
        fileUploadComponent.processFiles([file]);
      } else {
        // 打開 FileUpload 面板
        showFileUpload = true;
        
        // 延遲一下讓 FileUpload 組件渲染完成
        setTimeout(() => {
          if (fileUploadComponent) {
            fileUploadComponent.processFiles([file]);
          }
        }, 100);
      }
    }
  }
  
  // 公開聚焦方法
  export function focus() {
    textArea?.focus();
  }
  
</script>

<div class="message-input-container">
  <div
    class="message-input-area"
    class:dragging={isDragging}
    class:disabled
    ondragenter={handleDragEnter}
    ondragover={handleDragOver}
    ondragleave={handleDragLeave}
    ondrop={handleDrop}
    role="textbox"
    aria-label="訊息輸入區域"
    tabindex="0"
  >
    <div class="input-content">
      <div class="textarea-container">
        <textarea
          bind:this={textArea}
          bind:value={message}
          {placeholder}
          {disabled}
          maxlength={maxLength}
          class="message-textarea"
          rows="1"
          oninput={handleInput}
          onkeydown={handleKeyDown}
          oncompositionstart={() => isComposing = true}
          oncompositionend={() => isComposing = false}
        ></textarea>
        
        {#if isDragging}
          <div class="drag-overlay">
            <div class="drag-indicator">
              <svg class="w-8 h-8 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              <span class="drag-text">拖拽檔案到此處上傳</span>
            </div>
          </div>
        {/if}
      </div>
      
      <div class="input-actions">
        {#if allowFiles}
          <button
            type="button"
            class="action-button"
            class:active={showFileUpload}
            {disabled}
            onclick={toggleFileUpload}
            aria-label="上傳檔案"
            title="上傳檔案"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </button>
          
          <input
            bind:this={fileInput}
            type="file"
            accept={getAcceptString(allowedFileTypes)}
            class="hidden"
            onchange={handleFileSelect}
          />
        {/if}
        
        <!-- 發送按鈕 -->
        {#if sendingStatus === 'failed' && currentMessageId}
          <Button
            type="button"
            variant="error"
            size="sm"
            onclick={retryMessage}
            title="發送失敗，點擊重試"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            重試
          </Button>
        {:else}
          <Button
            type="button"
            variant="primary"
            size="sm"
            disabled={!message.trim() || disabled || sendingStatus === 'sending'}
            onclick={sendMessage}
          >
            {#if sendingStatus === 'sending'}
              <svg class="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              發送中
            {:else if sendingStatus === 'sent'}
              <svg class="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
              </svg>
              已發送
            {:else}
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
              發送
            {/if}
          </Button>
        {/if}
      </div>
    </div>
    
    <!-- 字符計數 -->
    {#if message.length > 0}
      <div class="character-count">
        <span class="count-text" class:warning={message.length > maxLength * 0.8}>
          {message.length}/{maxLength}
        </span>
      </div>
    {/if}
    
    <!-- 重試提示 -->
    {#if messageStatusStore.state}
      {@const failedMessages = Object.entries(messageStatusStore.state).filter(([_, status]) => status.status === 'failed')}
      {#if failedMessages.length > 0}
        <div class="retry-panel">
          <div class="retry-info">
            <svg class="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span class="retry-text">
              {failedMessages.length} 則訊息發送失敗
              {#if failedMessages.length === 1}
                {@const [id, status] = failedMessages[0]}
                {#if status.error}
                  <span class="retry-error">({status.error})</span>
                {/if}
              {/if}
            </span>
          </div>
          <div class="retry-actions">
            <button
              type="button"
              class="retry-all-button"
              onclick={() => messageRetryManager.retryAllFailed()}
            >
              全部重試
            </button>
            <button
              type="button"
              class="clear-failed-button"
              onclick={() => {
                failedMessages.forEach(([id]) => {
                  messageRetryManager.removeFromQueue(id);
                });
              }}
            >
              清除
            </button>
          </div>
        </div>
      {/if}
    {/if}
  </div>
  
  <!-- 檔案上傳面板 -->
  {#if showFileUpload}
    <div class="file-upload-panel">
      <FileUpload
        bind:this={fileUploadComponent}
        allowedTypes={allowedFileTypes}
        compact
        autoUpload
        onFilesSelected={handleFileUpload}
        onUploaded={handleFileUploaded}
        onError={handleFileUploadError}
        onAllFilesRemoved={() => showFileUpload = false}
      />
    </div>
  {/if}
</div>

<style>
  .message-input-container {
    @apply border-t border-base-200 bg-base-100 p-2 md:p-4;
    /* 確保輸入框容器有足夠的最小高度 */
    min-height: 60px;
  }
  
  @media (max-width: 768px) {
    .message-input-container {
      @apply p-2;
      min-height: 56px;
    }
  }
  
  .message-input-area {
    @apply relative bg-base-200 rounded-lg transition-all duration-200;
  }
  
  .message-input-area.dragging {
    @apply bg-primary opacity-10 border-2 border-primary border-dashed;
  }
  
  .message-input-area.disabled {
    @apply opacity-50 cursor-not-allowed;
  }
  
  .input-content {
    @apply flex items-end gap-2 p-2 md:p-3;
  }
  
  .textarea-container {
    @apply flex-1 relative;
  }
  
  .message-textarea {
    @apply w-full bg-transparent resize-none outline-none text-base-content placeholder-base-content opacity-60 leading-relaxed;
    min-height: 20px;
    max-height: 120px;
    /* 優化手機端輸入 */
    font-size: 16px; /* 避免 iOS Safari 自動放大 */
    -webkit-appearance: none;
  }
  
  .drag-overlay {
    @apply absolute inset-0 bg-base-100 opacity-90 backdrop-blur-sm rounded flex items-center justify-center;
  }
  
  .drag-indicator {
    @apply flex flex-col items-center space-y-2;
  }
  
  .drag-text {
    @apply text-sm font-medium text-primary;
  }
  
  .input-actions {
    @apply flex items-center gap-1 md:gap-2;
  }
  
  .action-button {
    @apply btn btn-ghost btn-sm btn-circle text-base-content hover:text-primary hover:bg-base-300 transition-all duration-200;
    /* 手機端增大觸控區域 */
    min-width: 2.5rem;
    min-height: 2.5rem;
  }
  
  @media (max-width: 768px) {
    .action-button {
      @apply w-11 h-11; /* 增大觸控區域到 44x44px */
    }
    
    .message-textarea {
      /* 確保字體大小不會觸發 iOS 縮放 */
      font-size: 16px !important;
    }
  }
  
  .action-button:disabled {
    @apply opacity-50 cursor-not-allowed;
  }
  
  .action-button.active {
    @apply bg-primary text-primary-content;
  }
  
  .character-count {
    @apply px-3 pb-2 text-right;
  }
  
  .count-text {
    @apply text-xs text-base-content opacity-60;
  }
  
  .count-text.warning {
    @apply text-warning;
  }
  
  .retry-panel {
    @apply border-t border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-3 py-2;
    @apply flex items-center justify-between;
  }
  
  .retry-info {
    @apply flex items-center space-x-2;
  }
  
  .retry-text {
    @apply text-sm text-red-700 dark:text-red-300 font-medium;
  }
  
  .retry-error {
    @apply text-xs opacity-80;
  }
  
  .retry-actions {
    @apply flex items-center space-x-2;
  }
  
  .retry-all-button {
    @apply px-3 py-1 text-xs font-medium rounded;
    @apply bg-red-600 text-white hover:bg-red-700;
    @apply transition-colors duration-200;
    @apply focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2;
  }
  
  .clear-failed-button {
    @apply px-3 py-1 text-xs font-medium rounded;
    @apply bg-gray-200 text-gray-700 hover:bg-gray-300;
    @apply dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600;
    @apply transition-colors duration-200;
    @apply focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2;
  }
  
  .hidden {
    @apply sr-only;
  }
  
  .file-upload-panel {
    @apply border-t border-base-200 p-4 bg-base-100;
    /* 確保檔案上傳面板有足夠的空間顯示 */
    min-height: 200px;
  }
</style>