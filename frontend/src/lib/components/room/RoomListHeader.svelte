<script lang="ts">
  interface Props {
    compact: boolean;
    mobileMode: boolean;
    onCreateRoom: () => void;
    onJoinByInvite: () => void;
  }

  let {
    compact = false,
    mobileMode = false,
    onCreateRoom,
    onJoinByInvite
  }: Props = $props();
</script>

{#if mobileMode}
  <!-- 移動端：使用 navbar 組件，增大按鈕尺寸提升觸控體驗 -->
  <div class="navbar bg-base-100 border-b border-base-200 sticky top-0 z-50 min-h-[3.5rem]">
    <div class="navbar-start flex-1">
      <span class="text-lg font-bold px-2">聊天室</span>
    </div>
    <div class="navbar-end flex-none">
      <div class="flex gap-1">
        <button
          class="btn btn-ghost btn-square"
          onclick={onCreateRoom}
          aria-label="創建聊天室"
          title="創建聊天室"
        >
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
        </button>
        <button
          class="btn btn-ghost btn-square"
          onclick={onJoinByInvite}
          aria-label="加入房間"
          title="加入房間"
        >
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
          </svg>
        </button>
      </div>
    </div>
  </div>
{:else if !compact}
  <!-- 桌面端：原有的標題欄 -->
  <div class="room-list-header">
    <h2 class="room-list-title">聊天室</h2>
    <div class="btn-group">
      <button
        class="btn btn-sm btn-ghost btn-square"
        onclick={onCreateRoom}
        aria-label="創建聊天室"
        title="創建聊天室"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
        </svg>
      </button>

      <button
        class="btn btn-sm btn-ghost btn-square"
        onclick={onJoinByInvite}
        aria-label="通過邀請碼加入"
        title="通過邀請碼加入"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
        </svg>
      </button>
    </div>
  </div>
{/if}

<style>
  @reference "$lib/styles/tailwind.css";
  .room-list-header {
    @apply flex items-center justify-between bg-base-100 border-b border-base-200 shadow-sm flex-shrink-0;
    padding: 0.5rem 0.75rem;
    width: 100%;
    box-sizing: border-box;
    min-height: 56px;
  }

  .room-list-title {
    @apply text-base font-bold text-base-content tracking-tight;
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .room-list-header .btn-group {
    @apply flex gap-1 flex-shrink-0;
  }

  .room-list-header .btn-square {
    @apply w-8 h-8 min-h-8;
  }

  .room-list-header button {
    @apply rounded-full p-2 hover:bg-base-200 transition-colors duration-200 text-base-content;
  }

  .room-list-header button svg {
    @apply text-base-content;
  }
</style>
