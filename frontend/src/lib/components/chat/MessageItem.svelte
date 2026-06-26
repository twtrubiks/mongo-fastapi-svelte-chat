<script lang="ts">
  import { formatDateTime, formatTime, normalizeFileUrl } from '$lib/utils';
  import { Avatar } from '$lib/components/ui';
  import ImageViewer from '$lib/components/ui/ImageViewer.svelte';
  import VideoPlayer from '$lib/components/ui/VideoPlayer.svelte';
  import FileMessage from './FileMessage.svelte';
  import { fade, fly, scale } from 'svelte/transition';
  import { elasticOut, quartOut } from 'svelte/easing';
  import type { Message } from '$lib/types';
  import { messageStatusStore } from '$lib/stores/messageStatus.svelte';
  import { messageStore } from '$lib/stores/message.svelte';
  import { messageRetryManager } from '$lib/utils/messageRetry';
  
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
  // 自己的訊息以 client_id 追蹤發送狀態（sending / sent / failed）
  let statusKey = $derived(message.client_id ?? message.id);
  let sendStatus = $derived(
    isCurrentUser ? messageStatusStore.state[statusKey]?.status : undefined
  );

  async function retrySend() {
    await messageRetryManager.manualRetry(statusKey);
  }
  let isImageMessage = $derived(message.message_type === 'image');
  let isFileMessage = $derived(message.message_type === 'file');
  let messageTime = $derived(formatTime(message.created_at));
  let messageDate = $derived(formatDateTime(message.created_at));
  let normalizedContentUrl = $derived(normalizeFileUrl(message.content));

  // 訊息編輯／刪除（僅作者本人；圖片／檔案只能刪不能編）
  let canEdit = $derived(isCurrentUser && !isSystemMessage && !isImageMessage && !isFileMessage);
  let canDelete = $derived(isCurrentUser && !isSystemMessage);

  let isEditing = $state(false);
  let editContent = $state('');
  let isConfirmingDelete = $state(false);
  let isSaving = $state(false);
  let actionError = $state('');

  // 進入編輯態時自動聚焦並選取內容
  function focusOnMount(node: HTMLTextAreaElement) {
    node.focus();
    node.select();
  }

  function startEdit() {
    editContent = message.content;
    actionError = '';
    isEditing = true;
  }

  function cancelEdit() {
    isEditing = false;
    editContent = '';
    actionError = '';
  }

  async function saveEdit() {
    const trimmed = editContent.trim();
    if (!trimmed) {
      actionError = '訊息內容不能為空';
      return;
    }
    if (trimmed === message.content) {
      cancelEdit(); // 內容未變更，直接關閉
      return;
    }
    isSaving = true;
    actionError = '';
    try {
      await messageStore.editMessage(message.id, trimmed);
      isEditing = false;
      editContent = '';
    } catch {
      actionError = '編輯失敗，請稍後再試';
    } finally {
      isSaving = false;
    }
  }

  function handleEditKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      saveEdit();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      cancelEdit();
    }
  }

  function startDelete() {
    actionError = '';
    isConfirmingDelete = true;
  }

  function cancelDelete() {
    isConfirmingDelete = false;
    actionError = '';
  }

  async function confirmDelete() {
    isSaving = true;
    actionError = '';
    try {
      await messageStore.deleteMessage(message.id);
      // 成功後訊息會從 store 移除，元件隨之卸載
    } catch {
      actionError = '刪除失敗，請稍後再試';
      isSaving = false;
      isConfirmingDelete = false;
    }
  }

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
          <Avatar user={{ username: message.username ?? '', avatar: message.user?.avatar ?? message.avatar ?? '' }} size="sm" />
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
          {#if message.reply_to_message}
            <!-- 引用區塊：此訊息回覆的對象（目前用於 @bot 回覆指回提問者） -->
            <div class="message-reply-quote">
              <span class="reply-quote-author">{message.reply_to_message.username}</span>
              <span class="reply-quote-content">{message.reply_to_message.content}</span>
            </div>
          {/if}
          {#if isImageMessage}
            <!-- 圖片訊息 -->
            <div 
              class="message-image"
              in:scale={{ duration: 400, delay: 250, easing: elasticOut }}
            >
              <button
                class="max-w-xs max-h-64 rounded-lg object-cover cursor-pointer transition-transform duration-200 hover:scale-105 border-none bg-transparent p-0"
                onclick={() => handleImageClick(normalizedContentUrl)}
                aria-label="點擊查看大圖"
              >
                <img
                  src={normalizedContentUrl}
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
                fileUrl={normalizedContentUrl}
                fileName={(message.metadata?.['filename'] as string) || ''}
                fileSize={(message.metadata?.['fileSize'] as number) || 0}
                mimeType={(message.metadata?.['mimeType'] as string) || ''}
                {isCurrentUser}
                {compact}
                onDownload={handleFileDownload}
                onPreview={handleFilePreview}
                onPlay={handleFilePlay}
              />
            </div>
          {:else if isEditing}
            <!-- 編輯態（inline 編輯文字訊息） -->
            <div class="message-edit">
              <textarea
                class="message-edit-input"
                bind:value={editContent}
                onkeydown={handleEditKeydown}
                use:focusOnMount
                rows="2"
                disabled={isSaving}
                aria-label="編輯訊息"
              ></textarea>
              <div class="message-edit-actions">
                <button class="message-edit-cancel" onclick={cancelEdit} disabled={isSaving}>取消</button>
                <button class="message-edit-save" onclick={saveEdit} disabled={isSaving}>儲存</button>
              </div>
              {#if actionError}
                <div class="message-action-error">{actionError}</div>
              {/if}
            </div>
          {:else}
            <!-- 文字訊息 -->
            <div
              class="message-text"
              in:fade={{ duration: 300, delay: 200 }}
            >
              {message.content}{#if message.edited}<span class="message-edited-tag">（已編輯）</span>{/if}
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

        {#if (canEdit || canDelete) && !isEditing && !isConfirmingDelete}
          <!-- 訊息操作（hover 顯示，僅作者本人） -->
          <div class="message-actions">
            {#if canEdit}
              <button class="message-action-btn" onclick={startEdit} aria-label="編輯訊息" title="編輯">
                ✏️ 編輯
              </button>
            {/if}
            {#if canDelete}
              <button class="message-action-btn message-action-delete" onclick={startDelete} aria-label="刪除訊息" title="刪除">
                🗑️ 刪除
              </button>
            {/if}
          </div>
        {/if}

        {#if isConfirmingDelete}
          <!-- 刪除確認 -->
          <div class="message-delete-confirm">
            <span>確定刪除這則訊息？</span>
            <button class="message-confirm-cancel" onclick={cancelDelete} disabled={isSaving}>取消</button>
            <button class="message-confirm-delete" onclick={confirmDelete} disabled={isSaving}>刪除</button>
          </div>
          {#if actionError}
            <div class="message-action-error">{actionError}</div>
          {/if}
        {/if}

        {#if isCurrentUser && sendStatus && sendStatus !== 'idle'}
          <!-- 發送狀態指示（真 ack：等待伺服器確認） -->
          <div class="message-send-status" class:send-status-failed={sendStatus === 'failed'}>
            {#if sendStatus === 'sending'}
              <span class="loading loading-spinner loading-xs"></span>
              <span>傳送中</span>
            {:else if sendStatus === 'sent'}
              <span>✓ 已送達</span>
            {:else if sendStatus === 'failed'}
              <span>⚠ 傳送失敗</span>
              <button class="send-retry-button" onclick={retrySend}>重試</button>
            {/if}
          </div>
        {/if}
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
	@reference "$lib/styles/tailwind.css";
  .message-item {
    @apply mb-4 transition-all duration-200 hover:scale-[1.01] hover:shadow-sm;
    /* 確保訊息項目不會超出容器 */
    width: 100%;
    overflow: hidden;
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
    @apply flex items-start space-x-3;
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
    @apply text-xs text-gray-700 bg-white/90 px-2 py-1 rounded-full font-semibold border border-gray-300;
  }
  
  .message-bubble {
    @apply rounded-2xl px-4 py-3 max-w-xs lg:max-w-md break-words shadow-sm transition-all duration-200 hover:shadow-md;
    position: relative;
    /* 優化文字換行 */
    word-wrap: break-word;
    overflow-wrap: break-word;
    /* 支援長按選擇文字 */
    -webkit-user-select: text;
    user-select: text;
    /* 優化觸控反饋 */
    -webkit-tap-highlight-color: rgba(0, 0, 0, 0.1);
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

  /* 引用區塊：此訊息回覆的對象（@bot 回覆指回提問者） */
  .message-reply-quote {
    @apply flex items-baseline gap-1.5 mb-2 pl-2 py-0.5 text-xs;
    border-left: 2px solid currentColor;
    opacity: 0.7;
    max-width: 100%;
  }

  .reply-quote-author {
    @apply font-semibold flex-shrink-0;
  }

  .reply-quote-content {
    @apply truncate min-w-0;
  }

  .message-time-own {
    @apply text-xs text-white mt-2 text-right bg-black/40 px-2 py-1 rounded-full inline-block font-semibold;
  }

  /* 發送狀態指示 */
  .message-send-status {
    @apply flex items-center gap-1 mt-1 text-xs text-base-content/60;
  }

  .send-status-failed {
    @apply text-error;
  }

  .send-retry-button {
    @apply btn btn-ghost btn-xs text-error underline px-1;
  }

  /* 訊息操作（編輯／刪除）：平時隱藏，hover 訊息時浮現 */
  .message-actions {
    @apply flex items-center gap-1 mt-1 opacity-0 transition-opacity duration-200;
  }

  .message-item:hover .message-actions {
    @apply opacity-100;
  }

  .message-action-btn {
    @apply btn btn-ghost btn-xs px-2 text-xs font-normal;
  }

  .message-action-delete {
    @apply text-error;
  }

  /* 編輯態 */
  .message-edit {
    @apply flex flex-col gap-2;
    min-width: 12rem;
  }

  .message-edit-input {
    @apply w-full text-sm leading-relaxed text-base-content bg-base-100 rounded-lg border border-base-300 px-2 py-1 resize-none;
    @apply focus:outline-none focus:ring-2 focus:ring-primary/40;
  }

  .message-edit-actions {
    @apply flex items-center gap-2 justify-end;
  }

  .message-edit-save {
    @apply btn btn-primary btn-xs;
  }

  .message-edit-cancel {
    @apply btn btn-ghost btn-xs;
  }

  /* 已編輯標記 */
  .message-edited-tag {
    @apply text-xs opacity-60 ml-1;
  }

  /* 刪除確認 */
  .message-delete-confirm {
    @apply flex items-center gap-2 mt-1 text-xs text-base-content/80;
  }

  .message-confirm-delete {
    @apply btn btn-error btn-xs;
  }

  .message-confirm-cancel {
    @apply btn btn-ghost btn-xs;
  }

  /* 操作錯誤訊息 */
  .message-action-error {
    @apply text-xs text-error mt-1;
  }
  
  .message-image {
    @apply p-2 bg-gradient-to-br from-gray-50 to-gray-100 rounded-xl;
  }
  
  .message-image img {
    @apply transition-all duration-300 hover:scale-105 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 rounded-lg shadow-md;
    max-width: 100%;
    height: auto;
  }
  
  /* 手機端圖片優化 */
  @media (max-width: 768px) {
    .message-image {
      @apply p-1;
    }
    
    .message-image img {
      max-width: min(280px, calc(100vw - 5rem));
      /* 禁用手機端的 hover 放大效果 */
      @apply hover:scale-100;
    }
  }
  
  /* 動畫效果 */
  .message-item {
    animation: message-appear 0.2s ease-out;
  }
  
  @keyframes message-appear {
    from {
      opacity: 0;
      transform: translateY(5px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
  
  /* 手機端減少動畫，提升性能 */
  @media (max-width: 768px) and (prefers-reduced-motion: no-preference) {
    .message-item {
      animation-duration: 0.15s;
    }
  }
  
  @media (prefers-reduced-motion: reduce) {
    .message-item {
      animation: none;
    }
  }
  
  /* 響應式設計 */
  @media (max-width: 768px) {
    .message-item {
      @apply mb-2;
    }
    
    .message-bubble {
      /* 調整手機版訊息泡泡的最大寬度，充分利用螢幕空間 */
      max-width: calc(100vw - 3.5rem);
      @apply px-3 py-2 text-sm shadow-sm;
    }
    
    /* 自己的訊息可以更寬 */
    .message-own .message-bubble {
      max-width: calc(100vw - 3rem);
    }
    
    .message-content {
      @apply space-x-1;
    }
    
    .message-own .message-content {
      @apply space-x-reverse;
    }
    
    .message-avatar {
      /* 手機版使用更小的頭像 */
      transform: scale(0.85);
    }
    
    .message-username {
      @apply text-xs px-1.5 py-0.5;
    }
    
    .message-time {
      @apply text-xs px-1.5 py-0.5;
    }
    
    .message-text {
      @apply text-sm leading-snug;
    }
    
    /* 移除手機版訊息泡泡的偽元素箭頭，節省空間 */
    .message-bubble-other::before,
    .message-bubble-own::before {
      display: none;
    }
    
    /* 系統訊息手機端調整 */
    .system-message-content {
      @apply px-3 py-2 text-xs;
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
    @apply ring-2 ring-primary/50 bg-primary/10 rounded-lg;
    animation: highlightPulse 3s ease-in-out;
  }

  @keyframes highlightPulse {
    0% {
      --tw-ring-color: oklch(var(--p) / 0.8);
      background-color: oklch(var(--p) / 0.2);
    }
    50% {
      --tw-ring-color: oklch(var(--p) / 0.3);
      background-color: oklch(var(--p) / 0.05);
    }
    100% {
      --tw-ring-color: oklch(var(--p) / 0);
      background-color: oklch(var(--p) / 0);
    }
  }
</style>