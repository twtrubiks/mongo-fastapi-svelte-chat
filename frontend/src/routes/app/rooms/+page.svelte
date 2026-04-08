<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { roomStore } from '$lib/stores/room.svelte';
  import { isAuthenticated, currentUser } from '$lib/stores/auth.svelte';
  import { extractUserId } from '$lib/utils/userIdNormalizer';
  import { apiClient } from '$lib/api/client';
  import { RoomType, JoinPolicy } from '$lib/types';
  import Loading from '$lib/components/ui/Loading.svelte';

  // 這個頁面負責將用戶引導到適當的聊天室
  // 若無可用房間，則停留在此頁顯示空狀態

  let loading = $state(true);
  let roomsExist = $state(false);

  onMount(async () => {
    if (!isAuthenticated()) {
      goto('/login');
      return;
    }

    try {
      const userRooms = await roomStore.loadMyRooms(true);

      if (userRooms && userRooms.length > 0) {
        goto(`/app/room/${userRooms[0]!.id}`, { replaceState: true });
        return;
      }

      // 沒有已加入的房間，直接呼叫 API 查詢可加入的房間（不汙染 store 的探索快取）
      const allRooms = await apiClient.rooms.list({ limit: 50, offset: 0 });

      if (allRooms && allRooms.length > 0) {
        const userId = extractUserId(currentUser());

        if (userId) {
          const target = allRooms.find((room) => {
            return room.is_member
              || (room.join_policy === JoinPolicy.DIRECT && room.room_type === RoomType.PUBLIC);
          });

          if (target) {
            if (!target.is_member) {
              await roomStore.joinRoom(target.id);
            }
            goto(`/app/room/${target.id}`, { replaceState: true });
            return;
          }
        }
        roomsExist = true;
      }
    } catch (error) {
      console.error('載入房間列表失敗:', error);
    } finally {
      loading = false;
    }
  });
</script>

{#if loading}
  <Loading size="lg" text="正在載入聊天室..." fullscreen />
{:else}
  <div class="flex flex-col items-center justify-center h-screen text-center px-4">
    <svg class="w-20 h-20 text-base-content opacity-30 mb-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
    </svg>
    <h2 class="text-2xl font-bold text-base-content mb-2">
      {roomsExist ? '尚未加入任何聊天室' : '目前沒有聊天室'}
    </h2>
    <p class="text-base-content opacity-60 max-w-md mb-6">
      {roomsExist ? '瀏覽可用的聊天室並加入，開始與其他人聊天' : '創建第一個聊天室，邀請朋友一起聊天吧！'}
    </p>
    <a href="/app/dashboard" class="btn btn-primary">
      前往儀表板
    </a>
  </div>
{/if}
