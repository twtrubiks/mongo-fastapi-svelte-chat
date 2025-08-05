<script lang="ts">
  import { formatDateTime, formatTime } from '$lib/utils';
  import { Avatar } from '$lib/components/ui';
  import ImageViewer from '$lib/components/ui/ImageViewer.svelte';
  import VideoPlayer from '$lib/components/ui/VideoPlayer.svelte';
  import FileMessage from './FileMessage.svelte';
  import { fade, fly, scale } from 'svelte/transition';
  import { elasticOut, quartOut } from 'svelte/easing';
  import type { Message } from '$lib/types';
  
  interface Props {
    message: Message;
    isCurrentUser?: boolean;
    showAvatar?: boolean;
    showTime?: boolean;
    compact?: boolean;
  }
  
  let {
    message,
    isCurrentUser = false,
    showAvatar = true,
    showTime = true,
    compact = false
  }: Props = $props();
  
  let isSystemMessage = $derived(message.message_type === 'system');
  let isImageMessage = $derived(message.message_type === 'image');
  let isFileMessage = $derived(message.message_type === 'file');
  let messageTime = $derived(formatTime(message.created_at));
  let messageDate = $derived(formatDateTime(message.created_at));
  
  
  let showImageViewer = $state(false);
  let imageViewerSrc = $state('');
  let showVideoPlayer = $state(false);
  let videoPlayerSrc = $state('');
  let videoPlayerTitle = $state('');
  
  function handleImageClick(imageSrc: string) {
    imageViewerSrc = imageSrc;
    showImageViewer = true;
  }
  
  function handleFileDownload(data: { url: string; fileName: string }) {
    const { url, fileName } = data;
  }
  
  function handleFilePreview(data: { url: string; fileName: string; type: string }) {
    const { url, fileName, type } = data;
    
    // 直接在新視窗開啟檔案預覽
    window.open(url, '_blank');
  }
  
  function handleFilePlay(data: { url: string; fileName: string; type: string }) {
    const { url, fileName, type } = data;
    
    // 設置影片播放器資料
    videoPlayerSrc = url;
    videoPlayerTitle = fileName;
    showVideoPlayer = true;
  }
</script>

<div 
  class="message-item {isCurrentUser ? 'message-own' : 'message-other'} {compact ? 'compact' : ''}"
  data-message-id={message.id}
  in:fly={{
    y: 20,
    duration: 400,
    delay: isCurrentUser ? 0 : 100,
    easing: elasticOut
  }}
  out:scale={{
    duration: 200,
    easing: quartOut
  }}
>
  {#if isSystemMessage}
    <!-- 系統訊息 -->
    <div 
      class="system-message"
      in:fade={{ duration: 300, delay: 200 }}
    >
      <div class="system-message-content">
        <span class="system-message-text">{message.content}</span>
        {#if showTime}
          <span class="system-message-time">{messageTime}</span>
        {/if}
      </div>
    </div>
  {:else}
    <!-- 一般訊息 -->
    <div class="message-content">
      {#if showAvatar && !isCurrentUser}
        <div 
          class="message-avatar"
          in:scale={{ duration: 300, delay: 150, easing: elasticOut }}
        >
          <Avatar user={{ username: message.username }} size="sm" />
        </div>
      {/if}
      
      <div class="message-body">
        {#if !isCurrentUser && !compact}
          <div 
            class="message-header"
            in:fade={{ duration: 200, delay: 100 }}
          >
            <span class="message-username">{message.username}</span>
            {#if showTime}
              <span class="message-time" title={messageDate}>{messageTime}</span>
            {/if}
          </div>
        {/if}
        
        <div 
          class="message-bubble {isCurrentUser ? 'message-bubble-own' : 'message-bubble-other'}"
          in:fly={{
            x: isCurrentUser ? 30 : -30,
            duration: 350,
            delay: 150,
            easing: quartOut
          }}
        >
          {#if isImageMessage}
            <!-- 圖片訊息 -->
            <div 
              class="message-image"
              in:scale={{ duration: 400, delay: 250, easing: elasticOut }}
            >
              <button
                class="max-w-xs max-h-64 rounded-lg object-cover cursor-pointer transition-transform duration-200 hover:scale-105 border-none bg-transparent p-0"
                onclick={() => handleImageClick(message.content)}
                aria-label="點擊查看大圖"
              >
                <img 
                  src={message.content} 
                  alt="圖片訊息" 
                  class="max-w-xs max-h-64 rounded-lg object-cover w-full h-full"
                />
              </button>
            </div>
          {:else if isFileMessage}
            <!-- 檔案訊息 -->
            <div 
              class="message-file"
              in:scale={{ duration: 400, delay: 250, easing: elasticOut }}
            >
              <FileMessage
                fileUrl={message.content}
                fileName={message.metadata?.filename || ''}
                fileSize={message.metadata?.fileSize || 0}
                mimeType={message.metadata?.mimeType || ''}
                {isCurrentUser}
                {compact}
                onDownload={handleFileDownload}
                onPreview={handleFilePreview}
                onPlay={handleFilePlay}
              />
            </div>
          {:else}
            <!-- 文字訊息 -->
            <div 
              class="message-text"
              in:fade={{ duration: 300, delay: 200 }}
            >
              {message.content}
            </div>
          {/if}
          
          {#if isCurrentUser && showTime}
            <div 
              class="message-time-own" 
              title={messageDate}
              in:fade={{ duration: 200, delay: 300 }}
            >
              {messageTime}
            </div>
          {/if}
        </div>
      </div>
    </div>
  {/if}
</div>

<!-- 圖片查看器 -->
<ImageViewer
  bind:show={showImageViewer}
  src={imageViewerSrc}
  alt="圖片訊息"
  title="圖片訊息"
  onClose={() => showImageViewer = false}
/>

<!-- 影片播放器 -->
<VideoPlayer
  bind:show={showVideoPlayer}
  src={videoPlayerSrc}
  title={videoPlayerTitle}
  filename={videoPlayerTitle}
  onClose={() => showVideoPlayer = false}
/>

<style>
  .message-item {
    @apply mb-4 transition-all duration-200 hover:scale-[1.01] hover:shadow-sm;
  }
  
  .message-item.compact {
    @apply mb-2;
  }
  
  /* 系統訊息樣式 */
  .system-message {
    @apply flex justify-center py-3;
  }
  
  .system-message-content {
    @apply bg-gradient-to-r from-base-200 to-base-300 rounded-full px-5 py-3 text-sm text-base-content opacity-80 flex items-center space-x-3 shadow-sm border border-base-300;
  }
  
  .system-message-text {
    @apply font-semibold;
  }
  
  .system-message-time {
    @apply text-xs opacity-90 bg-base-100 px-2 py-1 rounded-full font-medium;
  }
  
  /* 一般訊息樣式 */
  .message-content {
    @apply flex items-start space-x-4;
  }
  
  .message-own .message-content {
    @apply flex-row-reverse space-x-reverse;
  }
  
  .message-avatar {
    @apply flex-shrink-0 mt-1;
  }
  
  .message-body {
    @apply flex-1 min-w-0;
  }
  
  .message-own .message-body {
    @apply flex flex-col items-end;
  }
  
  .message-header {
    @apply flex items-center space-x-3 mb-2;
  }
  
  .message-username {
    @apply text-sm font-bold text-base-content opacity-90 px-2 py-1 bg-base-200 rounded-full;
  }
  
  .message-time {
    @apply text-xs text-gray-700 bg-white bg-opacity-90 px-2 py-1 rounded-full font-semibold border border-gray-300;
  }
  
  .message-bubble {
    @apply rounded-2xl px-4 py-3 max-w-xs lg:max-w-md break-words shadow-md transition-all duration-200 hover:shadow-lg;
    position: relative;
  }
  
  .message-bubble-other {
    @apply bg-gradient-to-br from-base-100 to-base-200 text-base-content border border-base-300;
  }
  
  .message-bubble-other::before {
    content: '';
    position: absolute;
    left: -8px;
    top: 12px;
    width: 0;
    height: 0;
    border-style: solid;
    border-width: 8px 8px 8px 0;
    border-color: transparent hsl(var(--b1)) transparent transparent;
  }
  
  .message-bubble-own {
    @apply bg-gradient-to-br from-primary to-primary text-primary-content shadow-md;
    filter: brightness(0.95);
    box-shadow: 0 4px 6px -1px rgba(var(--p) / 0.2), 0 2px 4px -1px rgba(var(--p) / 0.1);
  }
  
  .message-bubble-own::before {
    content: '';
    position: absolute;
    right: -8px;
    top: 12px;
    width: 0;
    height: 0;
    border-style: solid;
    border-width: 8px 0 8px 8px;
    border-color: transparent transparent transparent hsl(var(--p));
  }
  
  .message-text {
    @apply text-sm leading-relaxed font-medium;
  }
  
  .message-time-own {
    @apply text-xs text-white mt-2 text-right bg-black bg-opacity-40 px-2 py-1 rounded-full inline-block font-semibold;
  }
  
  .message-image {
    @apply p-2 bg-gradient-to-br from-gray-50 to-gray-100 rounded-xl;
  }
  
  .message-image img {
    @apply transition-all duration-300 hover:scale-105 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 rounded-lg shadow-md;
  }
  
  /* 動畫效果 */
  .message-item {
    animation: message-appear 0.3s ease-out;
  }
  
  @keyframes message-appear {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
  
  /* 響應式設計 */
  @media (max-width: 768px) {
    .message-bubble {
      @apply max-w-xs px-3 py-2;
    }
    
    .message-content {
      @apply space-x-2;
    }
    
    .message-header {
      @apply space-x-2;
    }
  }
  
  /* 深色模式優化 */
  @media (prefers-color-scheme: dark) {
    .message-bubble-other {
      @apply shadow-black/20;
    }
  }

  /* 訊息高亮效果 */
  :global(.highlight-message) {
    @apply ring-2 ring-primary ring-opacity-50 bg-primary bg-opacity-10 rounded-lg;
    animation: highlightPulse 3s ease-in-out;
  }

  @keyframes highlightPulse {
    0% {
      @apply ring-opacity-80 bg-opacity-20;
    }
    50% {
      @apply ring-opacity-30 bg-opacity-5;
    }
    100% {
      @apply ring-opacity-0 bg-opacity-0;
    }
  }
</style>