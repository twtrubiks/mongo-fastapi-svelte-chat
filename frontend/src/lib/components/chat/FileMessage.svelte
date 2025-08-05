<script lang="ts">
  import { getFileType, getFileIcon, formatFileSize, extractFileNameFromUrl, inferMimeTypeFromUrl } from '$lib/utils';
  import { Button } from '$lib/components/ui';
  import { fade, scale } from 'svelte/transition';
  import { elasticOut } from 'svelte/easing';
  
  interface Props {
    fileUrl: string;
    fileName?: string;
    fileSize?: number;
    mimeType?: string;
    isCurrentUser?: boolean;
    compact?: boolean;
    onDownload?: (data: { url: string; fileName: string }) => void;
    onPreview?: (data: { url: string; fileName: string; type: string }) => void;
    onPlay?: (data: { url: string; fileName: string; type: string }) => void;
  }
  
  let {
    fileUrl,
    fileName = '',
    fileSize = 0,
    mimeType = '',
    isCurrentUser = false,
    compact = false,
    onDownload = undefined,
    onPreview = undefined,
    onPlay = undefined
  }: Props = $props();
  
  // 從 URL 提取檔案名稱（如果沒有提供）
  let actualFileName = $derived(
    fileName || 
    (fileUrl ? extractFileNameFromUrl(fileUrl) : '')
  );
  
  // 推斷 MIME 類型（如果沒有提供）
  let actualMimeType = $derived(
    mimeType || 
    (fileUrl ? inferMimeTypeFromUrl(fileUrl) : '')
  );
  
  // 創建臨時 File 物件用於工具函數
  let dummyFile = $derived(new File([''], actualFileName, { type: actualMimeType }));
  let fileType = $derived(getFileType(dummyFile));
  let fileIcon = $derived(getFileIcon(dummyFile));
  let fileSizeText = $derived(fileSize > 0 ? formatFileSize(fileSize) : '');
  
  // 檔案預覽支援
  let fileExtension = $derived(getFileExtension(actualFileName));
  let canPreview = $derived(['pdf'].includes(fileExtension));
  let canPlayInline = $derived(['mp4', 'webm', 'ogg'].includes(fileExtension));
  let canPlayAudio = $derived(['mp3', 'wav', 'ogg'].includes(fileExtension));
  
  function getFileExtension(filename: string): string {
    return filename.split('.').pop()?.toLowerCase() || '';
  }
  
  function handleDownload() {
    onDownload?.({ url: fileUrl, fileName: actualFileName });
    
    // 創建下載連結
    const link = document.createElement('a');
    link.href = fileUrl;
    link.download = actualFileName;
    link.target = '_blank';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
  
  function handlePreview() {
    onPreview?.({ url: fileUrl, fileName: actualFileName, type: fileType });
  }
  
  function handlePlay() {
    onPlay?.({ url: fileUrl, fileName: actualFileName, type: fileType });
  }
</script>

<div 
  class="file-message"
  class:compact
  class:current-user={isCurrentUser}
  in:scale={{ duration: 300, easing: elasticOut }}
>
  <!-- 檔案資訊 -->
  <div class="file-info">
    <!-- 檔案圖標 -->
    <div 
      class="file-icon"
      in:scale={{ duration: 400, delay: 100, easing: elasticOut }}
    >
      <span class="icon-emoji">{fileIcon}</span>
    </div>
    
    <!-- 檔案詳情 -->
    <div class="file-details">
      <div 
        class="file-name" 
        title={actualFileName}
        in:fade={{ duration: 300, delay: 150 }}
      >
        {actualFileName}
      </div>
      {#if fileSizeText}
        <div 
          class="file-size"
          in:fade={{ duration: 300, delay: 200 }}
        >
          {fileSizeText}
        </div>
      {/if}
    </div>
  </div>
  
  <!-- 操作按鈕 -->
  <div 
    class="file-actions"
    in:fade={{ duration: 300, delay: 250 }}
  >
    {#if canPlayInline}
      <!-- 影片播放 -->
      <Button
        variant="ghost"
        size="xs"
        class="text-blue-700 hover:text-blue-900 hover:bg-blue-100 bg-blue-50 border border-blue-200"
        onclick={handlePlay}
        aria-label="播放影片"
        title="播放影片"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </Button>
    {:else if canPlayAudio}
      <!-- 音檔播放 -->
      <Button
        variant="ghost"
        size="xs"
        class="text-green-700 hover:text-green-900 hover:bg-green-100 bg-green-50 border border-green-200"
        onclick={handlePlay}
        aria-label="播放音檔"
        title="播放音檔"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
        </svg>
      </Button>
    {:else if canPreview}
      <!-- 檔案預覽 -->
      <Button
        variant="ghost"
        size="xs"
        class="text-purple-700 hover:text-purple-900 hover:bg-purple-100 bg-purple-50 border border-purple-200"
        onclick={handlePreview}
        aria-label="在新視窗預覽檔案"
        title="在新視窗預覽檔案"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
        </svg>
      </Button>
    {/if}
    
    <!-- 下載按鈕 -->
    <Button
      variant="ghost"
      size="xs"
      class="text-gray-700 hover:text-gray-900 hover:bg-gray-200 bg-gray-100 border border-gray-300"
      onclick={handleDownload}
      aria-label="下載檔案"
      title="下載檔案"
    >
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    </Button>
  </div>
</div>

<style>
  .file-message {
    @apply flex items-center space-x-3 p-4 bg-white rounded-xl border-2 border-gray-200 max-w-sm transition-all duration-200 hover:bg-gray-50 hover:shadow-xl shadow-lg;
  }
  
  .file-message.current-user {
    @apply bg-white border-gray-300 shadow-xl hover:shadow-2xl ring-2 ring-white ring-opacity-60;
  }
  
  .file-message.compact {
    @apply p-2 max-w-xs;
  }
  
  .file-info {
    @apply flex items-center space-x-3 flex-1 min-w-0;
  }
  
  .file-icon {
    @apply flex-shrink-0 w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center border border-blue-100;
  }
  
  .file-message.current-user .file-icon {
    @apply bg-blue-100 border-blue-200;
  }
  
  .icon-emoji {
    @apply text-2xl;
  }
  
  .file-details {
    @apply flex-1 min-w-0;
  }
  
  .file-name {
    @apply font-bold text-gray-900 truncate text-base;
  }
  
  .file-size {
    @apply text-xs text-gray-700 mt-1 font-medium;
  }
  
  .file-actions {
    @apply flex items-center space-x-2 flex-shrink-0;
  }
  
  .file-message.compact .file-actions {
    @apply space-x-0.5;
  }
  
  /* 響應式設計 */
  @media (max-width: 640px) {
    .file-message {
      @apply max-w-full;
    }
    
    .file-actions {
      @apply flex-col space-x-0 space-y-1;
    }
    
    .file-message.compact .file-actions {
      @apply flex-row space-y-0 space-x-0.5;
    }
  }
</style>