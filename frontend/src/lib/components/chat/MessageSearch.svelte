<script lang="ts">
  import { onMount } from 'svelte';
  import { apiClient } from '$lib/api/client';
  import type { Message } from '$lib/types';
  import { formatDateTime } from '$lib/utils/datetime';
  import { Avatar } from '$lib/components/ui';
  
  interface Props {
    roomId: string;
    isOpen?: boolean;
    onClose?: () => void;
    onSelectMessage?: (message: Message) => void;
  }
  
  let {
    roomId,
    isOpen = $bindable(),
    onClose = undefined,
    onSelectMessage = undefined
  }: Props = $props();
  
  // 搜尋狀態
  let searchKeyword = $state('');
  let searchType: 'all' | 'text' | 'image' | 'file' = $state('all');
  let searchUserId = $state('');
  let searchStartDate = $state('');
  let searchEndDate = $state('');
  let currentPage = $state(1);
  let pageSize = $state(20);
  
  // 搜尋結果
  let searchResults: Message[] = $state([]);
  let isSearching = $state(false);
  let hasSearched = $state(false);
  let searchError = $state('');
  
  // 搜尋歷史
  let searchHistory: string[] = $state([]);
  const SEARCH_HISTORY_KEY = 'chat_search_history';
  const MAX_HISTORY_ITEMS = 10;
  
  onMount(() => {
    // 載入搜尋歷史
    const savedHistory = localStorage.getItem(SEARCH_HISTORY_KEY);
    if (savedHistory) {
      searchHistory = JSON.parse(savedHistory);
    }
  });
  
  // 執行搜尋
  async function performSearch() {
    if (!searchKeyword.trim() && !searchUserId && !searchStartDate && !searchEndDate && searchType === 'all') {
      searchError = '請輸入搜尋條件';
      return;
    }
    
    isSearching = true;
    searchError = '';
    hasSearched = true;
    
    try {
      const query: any = {
        page: currentPage,
        page_size: pageSize,
      };
      
      if (searchKeyword.trim()) {
        query.keyword = searchKeyword.trim();
        
        // 儲存到搜尋歷史
        if (!searchHistory.includes(searchKeyword.trim())) {
          searchHistory = [searchKeyword.trim(), ...searchHistory].slice(0, MAX_HISTORY_ITEMS);
          localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(searchHistory));
        }
      }
      
      if (searchType !== 'all') {
        query.message_type = searchType;
      }
      
      if (searchUserId) {
        query.user_id = searchUserId;
      }
      
      if (searchStartDate) {
        query.start_date = new Date(searchStartDate).toISOString();
      }
      
      if (searchEndDate) {
        query.end_date = new Date(searchEndDate).toISOString();
      }
      
      searchResults = await apiClient.messages.search(roomId, query);
    } catch (error) {
      searchError = '搜尋失敗，請稍後再試';
      searchResults = [];
    } finally {
      isSearching = false;
    }
  }
  
  // 選擇搜尋歷史
  function selectHistory(keyword: string) {
    searchKeyword = keyword;
    performSearch();
  }
  
  // 清除搜尋歷史
  function clearHistory() {
    searchHistory = [];
    localStorage.removeItem(SEARCH_HISTORY_KEY);
  }
  
  // 重設搜尋
  function resetSearch() {
    searchKeyword = '';
    searchType = 'all';
    searchUserId = '';
    searchStartDate = '';
    searchEndDate = '';
    currentPage = 1;
    searchResults = [];
    hasSearched = false;
    searchError = '';
  }
  
  // 選擇訊息
  function selectMessage(message: Message) {
    onSelectMessage?.(message);
    onClose?.();
  }
  
  // 格式化訊息時間
  function formatMessageTime(createdAt: string) {
    return formatDateTime(createdAt);
  }
  
  // 按下 Enter 鍵搜尋
  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !isSearching) {
      performSearch();
    }
  }
</script>

{#if isOpen}
  <div class="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4" onclick={() => {
    onClose?.();
  }}>
    <div class="bg-base-100 border-2 border-base-300 rounded-lg shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden" onclick={(e) => e.stopPropagation()}>
      <!-- 標題列 -->
      <div class="flex items-center justify-between p-4 border-b border-base-300 bg-base-200">
        <h2 class="text-xl font-bold text-base-content">搜尋訊息</h2>
        <button class="btn btn-circle btn-ghost btn-sm" onclick={() => {
          onClose?.();
        }}>
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      
      <!-- 搜尋表單 -->
      <div class="p-4 border-b border-base-300 bg-base-50">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- 關鍵字搜尋 -->
          <div class="form-control">
            <label class="label">
              <span class="label-text font-medium text-base-content">關鍵字</span>
            </label>
            <input 
              type="text" 
              class="input input-bordered" 
              placeholder="輸入搜尋關鍵字..."
              bind:value={searchKeyword}
              onkeydown={handleKeydown}
            />
            
            {#if searchHistory.length > 0 && !searchKeyword}
              <div class="mt-2">
                <div class="flex items-center justify-between mb-1">
                  <span class="text-sm text-base-content/70">搜尋歷史</span>
                  <button class="btn btn-ghost btn-xs" onclick={clearHistory}>清除</button>
                </div>
                <div class="flex flex-wrap gap-1">
                  {#each searchHistory as keyword}
                    <button 
                      class="btn btn-ghost btn-xs"
                      onclick={() => selectHistory(keyword)}
                    >
                      {keyword}
                    </button>
                  {/each}
                </div>
              </div>
            {/if}
          </div>
          
          <!-- 訊息類型 -->
          <div class="form-control">
            <label class="label">
              <span class="label-text font-medium text-base-content">訊息類型</span>
            </label>
            <select class="select select-bordered" bind:value={searchType}>
              <option value="all">全部</option>
              <option value="text">文字</option>
              <option value="image">圖片</option>
              <option value="file">檔案</option>
            </select>
          </div>
          
          <!-- 日期範圍 -->
          <div class="form-control">
            <label class="label">
              <span class="label-text font-medium text-base-content">開始日期</span>
            </label>
            <input 
              type="date" 
              class="input input-bordered" 
              bind:value={searchStartDate}
            />
          </div>
          
          <div class="form-control">
            <label class="label">
              <span class="label-text font-medium text-base-content">結束日期</span>
            </label>
            <input 
              type="date" 
              class="input input-bordered" 
              bind:value={searchEndDate}
            />
          </div>
        </div>
        
        <!-- 錯誤訊息 -->
        {#if searchError}
          <div class="alert alert-error mt-4">
            <span>{searchError}</span>
          </div>
        {/if}
        
        <!-- 搜尋按鈕 -->
        <div class="flex gap-2 mt-4">
          <button 
            class="btn btn-primary" 
            onclick={performSearch}
            disabled={isSearching}
          >
            {#if isSearching}
              <span class="loading loading-spinner loading-sm"></span>
              搜尋中...
            {:else}
              搜尋
            {/if}
          </button>
          <button class="btn btn-ghost" onclick={resetSearch}>重設</button>
        </div>
      </div>
      
      <!-- 搜尋結果 -->
      <div class="overflow-y-auto" style="max-height: calc(90vh - 300px);">
        {#if isSearching}
          <div class="flex items-center justify-center p-8">
            <span class="loading loading-spinner loading-lg"></span>
          </div>
        {:else if hasSearched && searchResults.length === 0}
          <div class="text-center p-8 text-base-content/70">
            沒有找到符合條件的訊息
          </div>
        {:else if searchResults.length > 0}
          <div class="divide-y divide-base-300">
            {#each searchResults as message}
              <button 
                class="w-full p-4 hover:bg-base-200 transition-colors text-left"
                onclick={() => selectMessage(message)}
              >
                <div class="flex items-start gap-3">
                  <!-- 使用者頭像 -->
                  <Avatar 
                    user={{ username: message.username, avatar: message.user?.avatar }}
                    size="md"
                  />
                  
                  <!-- 訊息內容 -->
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-1">
                      <span 
                        class="font-semibold cursor-help" 
                        title="用戶 ID: {message.user_id}"
                      >
                        {message.username}
                      </span>
                      <span class="text-sm text-base-content/70">
                        {formatMessageTime(message.created_at)}
                      </span>
                    </div>
                    
                    {#if message.message_type === 'text'}
                      <p class="text-sm break-words">
                        {#if searchKeyword}
                          {@html message.content.replace(
                            new RegExp(searchKeyword, 'gi'),
                            (match) => `<mark class="bg-yellow-200 dark:bg-yellow-700">${match}</mark>`
                          )}
                        {:else}
                          {message.content}
                        {/if}
                      </p>
                    {:else if message.message_type === 'image'}
                      <div class="flex items-center gap-2">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5 text-base-content/70">
                          <path stroke-linecap="round" stroke-linejoin="round" d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 0 0 1.5-1.5V6a1.5 1.5 0 0 0-1.5-1.5H3.75A1.5 1.5 0 0 0 2.25 6v12a1.5 1.5 0 0 0 1.5 1.5Zm10.5-11.25h.008v.008h-.008V8.25Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z" />
                        </svg>
                        <span class="text-sm text-base-content/70">[圖片]</span>
                      </div>
                    {:else if message.message_type === 'file'}
                      <div class="flex items-center gap-2">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5 text-base-content/70">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
                        </svg>
                        <span class="text-sm text-base-content/70">[檔案]</span>
                      </div>
                    {/if}
                  </div>
                </div>
              </button>
            {/each}
          </div>
          
          <!-- 分頁控制 -->
          {#if searchResults.length === pageSize}
            <div class="p-4 border-t border-base-300">
              <div class="flex justify-center gap-2">
                <button 
                  class="btn btn-sm"
                  onclick={() => { currentPage--; performSearch(); }}
                  disabled={currentPage === 1}
                >
                  上一頁
                </button>
                <span class="flex items-center px-4">第 {currentPage} 頁</span>
                <button 
                  class="btn btn-sm"
                  onclick={() => { currentPage++; performSearch(); }}
                >
                  下一頁
                </button>
              </div>
            </div>
          {/if}
        {:else}
          <div class="text-center p-8 text-base-content/50">
            輸入搜尋條件開始搜尋訊息
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}