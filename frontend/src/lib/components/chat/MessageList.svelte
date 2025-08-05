<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { messageStore, currentUser } from '$lib/stores';
  import { groupMessagesByDate } from '$lib/utils';
  import { Loading } from '$lib/components/ui';
  import MessageItem from './MessageItem.svelte';
  import type { Message } from '$lib/types';
  
  // 創建本地的響應式用戶變數
  let user = $derived(currentUser());
  
  interface Props {
    messages?: Message[];
    loading?: boolean;
    hasMore?: boolean;
    roomId?: string;
  }
  
  let {
    messages = [],
    loading = false,
    hasMore = true,
    roomId = ''
  }: Props = $props();
  
  
  let messageContainer: HTMLDivElement;
  let isAtBottom = $state(true);
  let showScrollToBottom = $state(false);
  let autoScroll = $state(true);
  let previousMessageCount = $state(0);
  let userScrolling = $state(false);
  
  // 按日期分組訊息 - 過濾掉沒有 created_at 的訊息
  let groupedMessages = $derived.by(() => {
    const validMessages = messages.filter(msg => {
      if (!msg.created_at) {
        console.warn('[MessageList] 訊息缺少 created_at:', msg);
        return false;
      }
      return true;
    });
    return groupMessagesByDate(validMessages);
  });
  
  // 當訊息變化時檢查滾動位置
  $effect(() => {
    if (messages.length > 0 && messageContainer) {
      checkScrollPosition();
    }
  });
  
  // 檢查是否滾動到底部
  function checkScrollPosition() {
    if (!messageContainer) return;
    
    const { scrollTop, scrollHeight, clientHeight } = messageContainer;
    const threshold = 100;
    
    isAtBottom = scrollTop + clientHeight >= scrollHeight - threshold;
    showScrollToBottom = !isAtBottom && messages.length > 0;
  }
  
  // 滾動到底部
  function scrollToBottom(smooth = true) {
    if (!messageContainer) return;
    
    messageContainer.scrollTo({
      top: messageContainer.scrollHeight,
      behavior: smooth ? 'smooth' : 'auto',
    });
  }

  // 滾動到特定訊息
  export function scrollToMessage(messageId: string, highlight = true) {
    if (!messageContainer) return false;
    
    const messageElement = messageContainer.querySelector(`[data-message-id="${messageId}"]`);
    if (messageElement) {
      messageElement.scrollIntoView({ 
        behavior: 'smooth', 
        block: 'center' 
      });
      
      if (highlight) {
        // 添加高亮效果
        messageElement.classList.add('highlight-message');
        setTimeout(() => {
          messageElement.classList.remove('highlight-message');
        }, 3000);
      }
      
      return true;
    }
    
    return false;
  }
  
  // 載入更多訊息
  async function loadMoreMessages() {
    if (loading || !hasMore) return;
    
    const scrollHeight = messageContainer.scrollHeight;
    const scrollTop = messageContainer.scrollTop;
    
    try {
      await messageStore.loadMoreMessages(roomId, 20);
      
      // 載入後保持滾動位置
      await tick();
      const newScrollHeight = messageContainer.scrollHeight;
      messageContainer.scrollTop = scrollTop + (newScrollHeight - scrollHeight);
    } catch (error) {
      console.error('載入更多訊息失敗:', error);
    }
  }
  
  // 處理滾動事件
  function handleScroll() {
    // 標記用戶正在滾動
    userScrolling = true;
    
    checkScrollPosition();
    
    // 如果滾動到頂部且有更多訊息，自動載入
    if (messageContainer.scrollTop === 0 && hasMore && !loading) {
      loadMoreMessages();
    }
    
    // 延遲重置用戶滾動狀態
    clearTimeout(handleScroll.scrollTimeout);
    handleScroll.scrollTimeout = setTimeout(() => {
      userScrolling = false;
    }, 150);
  }
  
  // 新訊息到達時自動滾動
  $effect(() => {
    if (autoScroll && !userScrolling) {
      // 檢查是否有新訊息
      const currentMessageCount = messages.length;
      const hasNewMessage = currentMessageCount > previousMessageCount;
      
      if (hasNewMessage) {
        // 檢查最新訊息是否為當前用戶發送
        const latestMessage = messages[messages.length - 1];
        const isCurrentUserMessage = latestMessage && user?.id === latestMessage.user_id;
        
        // 如果是當前用戶的訊息，總是滾動到底部
        // 如果是其他人的訊息，只有在底部時才滾動
        if (isCurrentUserMessage || isAtBottom) {
          tick().then(() => scrollToBottom(false));
        }
        
        // 更新訊息計數
        previousMessageCount = currentMessageCount;
      }
    }
  });
  
  onMount(() => {
    // 初始化訊息計數
    previousMessageCount = messages.length;
    
    // 初始滾動到底部
    scrollToBottom(false);
    
    // 監聽滾動事件
    if (messageContainer) {
      messageContainer.addEventListener('scroll', handleScroll);
    }
    
    return () => {
      if (messageContainer) {
        messageContainer.removeEventListener('scroll', handleScroll);
        // 清理滾動計時器
        clearTimeout(handleScroll.scrollTimeout);
      }
    };
  });
</script>

<div class="message-list-container">
  {#if loading && messages.length === 0}
    <Loading text="載入訊息中..." />
  {:else}
    <div
      bind:this={messageContainer}
      class="message-list"
      class:has-messages={messages.length > 0}
    >
      {#if loading && hasMore}
        <div class="load-more-indicator">
          <Loading size="sm" text="載入更多訊息..." />
        </div>
      {/if}
      
      {#if messages.length === 0}
        <div class="empty-state">
          <div class="empty-state-icon">
            <svg class="w-12 h-12 text-base-content opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <p class="empty-state-text">還沒有訊息，開始聊天吧！</p>
        </div>
      {:else}
        {#each groupedMessages as group (group.date)}
          <div class="message-group">
            <div class="date-separator">
              <span class="date-text">{group.date}</span>
            </div>
            
            {#each group.messages as message, index (message.id)}
              {@const isCurrentUser = user?.id === message.user_id}
              {@const previousMessage = index > 0 ? group.messages[index - 1] : null}
              {@const isSameUser = previousMessage?.user_id === message.user_id}
              {@const showAvatar = !isCurrentUser && (!isSameUser || index === 0)}
              
              <MessageItem
                {message}
                {isCurrentUser}
                {showAvatar}
                compact={isSameUser && index > 0}
              />
            {/each}
          </div>
        {/each}
      {/if}
    </div>
  {/if}
  
  {#if showScrollToBottom}
    <button
      class="scroll-to-bottom"
      onclick={() => scrollToBottom(true)}
      aria-label="滾動到底部"
    >
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
      </svg>
    </button>
  {/if}
</div>

<style>
  .message-list-container {
    @apply relative flex-1 overflow-hidden bg-gradient-to-b from-base-200 to-base-100;
    height: calc(100vh - 200px);
    max-height: calc(100vh - 200px);
  }
  
  .message-list {
    @apply h-full overflow-y-auto px-6 py-4;
    scroll-behavior: smooth;
  }
  
  .message-list.has-messages {
    @apply pb-6;
  }
  
  .load-more-indicator {
    @apply py-6 text-center;
  }
  
  .empty-state {
    @apply flex flex-col items-center justify-center h-full text-center p-8;
  }
  
  .empty-state-icon {
    @apply mb-6 p-4 bg-base-200 rounded-full;
  }
  
  .empty-state-text {
    @apply text-base-content opacity-60 text-lg font-medium;
  }
  
  .message-group {
    @apply mb-8;
  }
  
  .date-separator {
    @apply flex justify-center py-4 mb-6 relative;
  }
  
  .date-separator::before {
    content: '';
    @apply absolute top-1/2 left-0 right-0 h-px bg-base-300 -translate-y-1/2;
  }
  
  .date-text {
    @apply bg-base-100 text-base-content opacity-70 px-4 py-2 rounded-full text-sm font-semibold shadow-sm border border-base-200 relative z-10;
  }
  
  .scroll-to-bottom {
    @apply absolute bottom-6 right-6 bg-primary text-primary-content p-3 rounded-full shadow-xl transition-all duration-300 hover:scale-110 hover:shadow-2xl focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 backdrop-blur-sm;
    animation: bounce-gentle 2s infinite;
  }
  
  @keyframes bounce-gentle {
    0%, 20%, 50%, 80%, 100% {
      transform: translateY(0);
    }
    40% {
      transform: translateY(-4px);
    }
    60% {
      transform: translateY(-2px);
    }
  }
  
  /* 隱藏滾動條但保持滾動功能 */
  .message-list {
    scrollbar-width: none; /* Firefox */
    -ms-overflow-style: none; /* IE and Edge */
  }
  
  .message-list::-webkit-scrollbar {
    display: none; /* Chrome, Safari and Opera */
  }
  
  /* 提升視覺層次 */
  .message-list-container::before {
    content: '';
    @apply absolute top-0 left-0 right-0 h-4 bg-gradient-to-b from-base-200 to-transparent pointer-events-none z-10;
  }
  
  .message-list-container::after {
    content: '';
    @apply absolute bottom-0 left-0 right-0 h-4 bg-gradient-to-t from-base-200 to-transparent pointer-events-none z-10;
  }
</style>