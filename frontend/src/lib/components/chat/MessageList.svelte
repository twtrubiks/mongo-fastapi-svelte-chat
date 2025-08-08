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
    skipAutoScroll?: boolean;  // 新增：是否跳過自動滾動
  }
  
  let {
    messages = [],
    loading = false,
    hasMore = true,
    roomId = '',
    skipAutoScroll = false
  }: Props = $props();
  
  
  let messageContainer: HTMLDivElement;
  let isAtBottom = $state(true);
  let showScrollToBottom = $state(false);
  let autoScroll = $state(true);
  let previousMessageCount = $state(0);
  let userScrolling = $state(false);
  let previousRoomId = $state('');  // 追蹤房間切換
  
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
  
  // 監聽房間切換
  $effect(() => {
    if (roomId && roomId !== previousRoomId) {
      // 房間切換時重置狀態
      previousRoomId = roomId;
      previousMessageCount = 0;
      userScrolling = false;
      isAtBottom = true;
      showScrollToBottom = false;  // 立即隱藏按鈕
      
      // 如果沒有特殊定位需求，滾動到底部
      if (messages.length > 0 && !skipAutoScroll) {
        tick().then(() => {
          scrollToBottom(false);
          // 多次檢查確保按鈕狀態正確
          setTimeout(() => {
            isAtBottom = true;
            showScrollToBottom = false;
            checkScrollPosition();
          }, 100);
          setTimeout(() => {
            checkScrollPosition();
            // 強制更新按鈕狀態
            if (isAtBottom) {
              showScrollToBottom = false;
            }
          }, 300);
        });
      } else if (skipAutoScroll) {
        // 如果跳過自動滾動，只檢查當前位置
        setTimeout(() => {
          checkScrollPosition();
        }, 100);
      }
    }
  });
  
  // 當訊息變化時檢查滾動位置
  $effect(() => {
    if (messages.length > 0 && messageContainer) {
      // 如果是新房間的第一批訊息且沒有特殊定位需求，滾動到底部
      if (previousMessageCount === 0 && !skipAutoScroll) {
        tick().then(() => {
          scrollToBottom(false);
          previousMessageCount = messages.length;
          // 確保按鈕隱藏
          isAtBottom = true;
          showScrollToBottom = false;
          
          setTimeout(() => {
            checkScrollPosition();
            // 再次確保按鈕狀態
            if (messageContainer) {
              const { scrollTop, scrollHeight, clientHeight } = messageContainer;
              if (scrollTop + clientHeight >= scrollHeight - 20) {
                showScrollToBottom = false;
              }
            }
          }, 200);
        });
      } else if (previousMessageCount === 0 && skipAutoScroll) {
        // 如果有特殊定位需求，只更新計數，不滾動
        previousMessageCount = messages.length;
        setTimeout(() => {
          checkScrollPosition();
        }, 100);
      } else {
        // 使用 requestAnimationFrame 確保 DOM 已更新
        requestAnimationFrame(() => {
          checkScrollPosition();
        });
      }
    }
  });
  
  // 檢查是否滾動到底部
  function checkScrollPosition() {
    if (!messageContainer) return;
    
    const { scrollTop, scrollHeight, clientHeight } = messageContainer;
    const threshold = 20; // 更低的閾值
    
    // 計算是否在底部
    const atBottom = scrollTop + clientHeight >= scrollHeight - threshold;
    
    // 只在狀態真的改變時更新
    if (atBottom !== isAtBottom) {
      isAtBottom = atBottom;
    }
    
    // 更新按鈕顯示狀態
    showScrollToBottom = !isAtBottom && messages.length > 0;
  }
  
  // 滾動到底部
  function scrollToBottom(smooth = true) {
    if (!messageContainer) return;
    
    messageContainer.scrollTo({
      top: messageContainer.scrollHeight,
      behavior: smooth ? 'smooth' : 'auto',
    });
    
    // 立即設置狀態
    isAtBottom = true;
    showScrollToBottom = false;
    
    // 滾動後再次確認狀態
    setTimeout(() => {
      isAtBottom = true;
      showScrollToBottom = false;
      checkScrollPosition();
    }, smooth ? 300 : 50);
  }

  // 滾動到特定訊息
  export function scrollToMessage(messageId: string, highlight = true) {
    if (!messageContainer) return false;
    
    const messageElement = messageContainer.querySelector(`[data-message-id="${messageId}"]`);
    if (messageElement) {
      // 檢查是否為移動裝置
      const isMobile = window.innerWidth <= 768;
      
      if (isMobile) {
        // 移動端：考慮固定輸入框的高度，將訊息滾動到更上方
        const inputHeight = 80; // 輸入框大約高度 + 安全邊距
        const containerRect = messageContainer.getBoundingClientRect();
        const messageRect = messageElement.getBoundingClientRect();
        
        // 計算目標滾動位置：讓訊息顯示在視窗中上部
        const targetScrollTop = messageContainer.scrollTop + 
          (messageRect.top - containerRect.top) - 
          (containerRect.height / 3); // 顯示在上 1/3 位置
        
        messageContainer.scrollTo({
          top: targetScrollTop,
          behavior: 'smooth'
        });
      } else {
        // 桌面端：保持原有的中央定位
        messageElement.scrollIntoView({ 
          behavior: 'smooth', 
          block: 'center' 
        });
      }
      
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
  let scrollTimeout: any;
  function handleScroll() {
    // 標記用戶正在滾動
    userScrolling = true;
    
    // 立即檢查滾動位置
    checkScrollPosition();
    
    // 如果滾動到頂部且有更多訊息，自動載入
    if (messageContainer.scrollTop === 0 && hasMore && !loading) {
      loadMoreMessages();
    }
    
    // 延遲重置用戶滾動狀態
    clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(() => {
      userScrolling = false;
      // 再次檢查確保狀態正確
      checkScrollPosition();
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
          tick().then(() => {
            scrollToBottom(false);
            // 滾動後立即檢查位置
            setTimeout(checkScrollPosition, 100);
          });
        }
        
        // 更新訊息計數
        previousMessageCount = currentMessageCount;
      }
    }
    
    // 訊息變化後總是檢查按鈕狀態
    if (messageContainer && messages.length > 0) {
      setTimeout(checkScrollPosition, 100);
    }
  });
  
  onMount(() => {
    // 初始化訊息計數和房間ID
    previousMessageCount = messages.length;
    previousRoomId = roomId;
    
    // 初始滾動到底部並檢查狀態（除非有特殊定位需求）
    if (messages.length > 0 && !skipAutoScroll) {
      scrollToBottom(false);
      setTimeout(() => {
        checkScrollPosition();
        // 確保按鈕狀態正確
        if (isAtBottom) {
          showScrollToBottom = false;
        }
      }, 200);
    } else if (skipAutoScroll) {
      // 如果跳過自動滾動，只檢查當前位置
      setTimeout(() => {
        checkScrollPosition();
      }, 100);
    }
    
    // 監聽滾動事件
    if (messageContainer) {
      messageContainer.addEventListener('scroll', handleScroll);
      
      // 使用 ResizeObserver 監聽容器大小變化
      const resizeObserver = new ResizeObserver(() => {
        checkScrollPosition();
      });
      resizeObserver.observe(messageContainer);
      
      return () => {
        messageContainer.removeEventListener('scroll', handleScroll);
        resizeObserver.disconnect();
        // 清理滾動計時器
        clearTimeout(scrollTimeout);
      };
    }
    
    return () => {
      if (messageContainer) {
        messageContainer.removeEventListener('scroll', handleScroll);
        // 清理滾動計時器
        clearTimeout(scrollTimeout);
      }
    };
  });
</script>

<div class="message-list-container">
  {#if loading && messages.length === 0}
    <div class="flex items-center justify-center h-full">
      <div class="text-center">
        <span class="loading loading-spinner loading-lg text-primary"></span>
        <p class="mt-4 text-base-content/60">載入訊息中...</p>
      </div>
    </div>
  {:else}
    <div
      bind:this={messageContainer}
      class="message-list"
      class:has-messages={messages.length > 0}
    >
      {#if loading && hasMore}
        <div class="flex justify-center py-4">
          <span class="loading loading-dots loading-sm"></span>
          <span class="ml-2 text-sm text-base-content/60">載入更多訊息...</span>
        </div>
      {/if}
      
      {#if messages.length === 0}
        <div class="hero min-h-full">
          <div class="hero-content text-center">
            <div class="max-w-md">
              <div class="mb-4">
                <svg class="w-16 h-16 mx-auto text-base-content opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <h3 class="text-lg font-bold mb-2">還沒有訊息</h3>
              <p class="text-base-content/60">開始聊天吧！</p>
            </div>
          </div>
        </div>
      {:else}
        {#each groupedMessages as group (group.date)}
          <div class="message-group">
            <div class="divider text-sm text-base-content/50">
              {group.date}
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
      class="btn btn-circle btn-primary btn-sm absolute bottom-6 right-6 shadow-lg z-20"
      onclick={() => scrollToBottom(true)}
      aria-label="滾動到底部"
    >
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
      </svg>
    </button>
  {/if}
</div>

<style>
  .message-list-container {
    @apply relative h-full overflow-hidden bg-gradient-to-b from-base-200 to-base-100;
    /* 確保容器不會超出螢幕寬度 */
    width: 100%;
    overflow-x: hidden;
    /* 防止容器過度擴展 */
    max-height: 100%;
    display: flex;
    flex-direction: column;
  }
  
  .message-list {
    @apply overflow-y-auto py-2;
    /* 使用 flex-1 而不是 h-full，讓它在 flex 容器中正確伸縮 */
    flex: 1 1 auto;
    min-height: 0; /* 重要：允許 flex 項目收縮到比內容小 */
    /* 調整左右內邊距，手機版使用更小的值以充分利用空間 */
    padding-left: 0.375rem;
    padding-right: 0.375rem;
    scroll-behavior: smooth;
    /* 增加底部內邊距，確保最後一個訊息不被遮擋 */
    padding-bottom: 1rem;
    /* 確保內容不會橫向溢出 */
    overflow-x: hidden;
    /* 優化 iOS 觸控滾動 */
    -webkit-overflow-scrolling: touch;
    /* 防止彈性滾動超出邊界 */
    overscroll-behavior: contain;
  }
  
  /* 桌面版使用較大的內邊距 */
  @media (min-width: 768px) {
    .message-list {
      padding-left: 1.5rem;
      padding-right: 1.5rem;
      padding-top: 1rem;
      padding-bottom: 2rem;
    }
  }
  
  .message-list.has-messages {
    /* 有訊息時增加更多底部空間 */
    @apply pb-16;
  }
  
  .message-group {
    @apply mb-8;
  }
  
  /* 使用 DaisyUI 的滾動條樣式 */
  .message-list {
    scrollbar-width: thin;
    scrollbar-color: oklch(var(--bc) / 0.2) transparent;
  }
  
  .message-list::-webkit-scrollbar {
    @apply w-2;
  }
  
  .message-list::-webkit-scrollbar-track {
    @apply bg-transparent;
  }
  
  .message-list::-webkit-scrollbar-thumb {
    @apply bg-base-content bg-opacity-20 rounded-full;
  }
  
  .message-list::-webkit-scrollbar-thumb:hover {
    @apply bg-base-content bg-opacity-30;
  }
  
  /* 上下淡出效果 */
  .message-list-container::before {
    content: '';
    @apply absolute top-0 left-0 right-0 h-4 bg-gradient-to-b from-base-100 to-transparent pointer-events-none z-10;
  }
  
  .message-list-container::after {
    content: '';
    @apply absolute bottom-0 left-0 right-0 h-4 bg-gradient-to-t from-base-100 to-transparent pointer-events-none z-10;
  }
</style>