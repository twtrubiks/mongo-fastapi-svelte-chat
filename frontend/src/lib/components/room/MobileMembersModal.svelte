<script lang="ts">
  import { UserList } from '$lib/components/room';
  import type { User } from '$lib/types';

  interface Props {
    show: boolean;
    users: User[];
    loading: boolean;
    currentUserId: string | null;
    hasMore: boolean;
    loadingMore: boolean;
    onClose: () => void;
    onUserClick: (event: { user: User }) => void;
    onLoadMore: () => void;
  }

  let {
    show,
    users,
    loading,
    currentUserId,
    hasMore,
    loadingMore,
    onClose,
    onUserClick,
    onLoadMore,
  }: Props = $props();
</script>

{#if show}
  <div class="modal modal-open">
    <div class="modal-box max-w-md max-h-[80vh] p-0">
      <div class="flex items-center justify-between px-4 py-3 border-b border-base-200">
        <h3 class="font-bold text-lg">成員列表</h3>
        <button
          class="btn btn-sm btn-circle btn-ghost"
          onclick={onClose}
        >
          ✕
        </button>
      </div>
      <div class="overflow-y-auto max-h-[calc(80vh-60px)]">
        <UserList
          {users}
          {loading}
          {currentUserId}
          {hasMore}
          {loadingMore}
          {onUserClick}
          {onLoadMore}
        />
      </div>
    </div>
    <div class="modal-backdrop" role="presentation" onclick={onClose}></div>
  </div>
{/if}
