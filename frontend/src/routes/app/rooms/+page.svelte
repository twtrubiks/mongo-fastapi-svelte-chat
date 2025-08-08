<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { roomStore } from '$lib/stores/room.svelte';
  import { isAuthenticated } from '$lib/stores/auth.svelte';
  
  // 這個頁面主要作為一個重定向頁面
  // 負責將用戶引導到適當的聊天室
  
  onMount(async () => {
    // 檢查認證狀態
    if (!isAuthenticated) {
      goto('/login');
      return;
    }
    
    try {
      // 載入用戶已加入的房間
      const userRooms = await roomStore.loadMyRooms();
      
      if (userRooms && userRooms.length > 0) {
        // 重定向到第一個可用房間
        goto(`/app/room/${userRooms[0].id}`, { replaceState: true });
      } else {
        // 載入所有可用房間
        await roomStore.loadRooms();
        const allRooms = roomStore.rooms;
        
        if (allRooms && allRooms.length > 0) {
          // 嘗試找到一個可以加入的公開房間
          for (const room of allRooms) {
            try {
              const requirements = await roomStore.checkJoinRequirements(room.id);
              
              if (requirements.isMember || requirements.requirements.canDirectJoin) {
                if (!requirements.isMember && requirements.requirements.canDirectJoin) {
                  await roomStore.joinRoom(room.id);
                }
                goto(`/app/room/${room.id}`, { replaceState: true });
                return;
              }
            } catch (error) {
              continue;
            }
          }
        }
        
        // 如果沒有找到可加入的房間，顯示空狀態
        // 用戶可以從左側列表創建或加入房間
        // 重定向到一個特殊的 URL 表示沒有房間
        goto('/app/room/none', { replaceState: true });
      }
    } catch (error) {
      console.error('載入房間列表失敗:', error);
      // 發生錯誤時，重定向到一個特殊的 URL
      goto('/app/room/none', { replaceState: true });
    }
  });
</script>

<div class="flex items-center justify-center h-screen">
  <div class="loading loading-spinner loading-lg"></div>
  <span class="ml-4 text-lg">正在載入聊天室...</span>
</div>