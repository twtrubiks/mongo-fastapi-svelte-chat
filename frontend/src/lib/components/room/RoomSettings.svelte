<script lang="ts">
  import { Button, Loading } from '$lib/components/ui';
  import { roomStore, currentUserRole, userPermissions } from '$lib/stores/room.svelte';
  import { currentUser } from '$lib/stores/auth.svelte';
  import type { Room, RoomType, JoinPolicy, MemberRole } from '$lib/types';
  import { formatDateTime } from '$lib/utils';

  interface Props {
    room: Room;
    show: boolean;
    onClose: () => void;
    onUpdate?: (room: Room) => void;
  }

  let {
    room,
    show = false,
    onClose,
    onUpdate = undefined
  }: Props = $props();

  // 狀態管理
  let activeTab = $state<'general'>('general');
  let isLoading = $state(false);
  let error = $state<string | null>(null);

  // 一般設定
  let roomName = $state(room?.name || '');
  let roomDescription = $state(room?.description || '');
  let roomType = $state<RoomType>(room?.room_type || 'public');
  let roomPassword = $state('');
  let showRoomPassword = $state(false);

  // TODO: 邀請相關狀態等后端 API 實作後再添加

  // 創建本地的響應式變數
  let user = $derived(currentUser());
  let userRole = $derived(currentUserRole());
  let permissions = $derived(userPermissions());

  // 權限檢查 - 檢查當前用戶是否為房間擁有者
  let canManageRoom = $derived.by(() => {
    if (!user || !room) return false;
    return room.owner_id === user.id;
  });


  // 載入房間權限和邀請資料
  async function loadRoomData() {
    if (!room?.id) return;

    isLoading = true;
    error = null;

    try {
      // TODO: 權限 API 有問題，暫時略過
      // await roomStore.loadPermissions(room.id);
      // console.log('[RoomSettings] 略過權限載入，直接允許編輯');

    } catch (err: any) {
      error = err.message || '載入資料失敗';
    } finally {
      isLoading = false;
    }
  }

  // 更新房間設定
  async function updateRoomSettings() {
    if (!room?.id || !canManageRoom) {
      error = '您沒有權限修改這個房間的設定。只有房間擁有者才能修改房間設定。';
      return;
    }

    isLoading = true;
    error = null;

    try {
      // 簡化更新資料，只包含基本資料
      const settings: any = {
        name: roomName.trim(),
        description: roomDescription.trim()
      };

      // 密碼和房間類型功能暫時移除，等後端支援
      // if (roomPassword.trim()) {
      //   settings.password = roomPassword.trim();
      // }

      // console.log('[RoomSettings] 更新資料:', settings);
      // console.log('[RoomSettings] 房間 ID:', room.id);

      const updatedRoom = await roomStore.updateRoomSettings(room.id, settings);
      onUpdate?.(updatedRoom);

    } catch (err: any) {
      console.error('[RoomSettings] 更新失敗:', err);

      // 更好的錯誤訊息處理
      if (err.message && err.message.includes('只有房間擁有者可以修改')) {
        error = '您沒有權限修改這個房間的設定。只有房間擁有者才能修改房間設定。';
      } else {
        error = err.message || '更新失敗';
      }
    } finally {
      isLoading = false;
    }
  }

  // TODO: 邀請和申請管理功能等后端 API 實作完成後再添加

  // 關閉模態框
  function handleClose() {
    // 重置狀態
    activeTab = 'general';
    error = null;
    onClose();
  }

  // 獲取房間類型標籤
  function getRoomTypeLabel(type: RoomType): string {
    switch (type) {
      case 'public': return '🌍 公開房間';
      case 'private': return '🔒 私人房間';
      case 'protected': return '🛡️ 受保護房間';
      case 'organization': return '🏢 組織房間';
      default: return '🌍 公開房間';
    }
  }


  // 監聽 show 變化，自動載入資料
  $effect(() => {
    if (show && room?.id) {
      // 重置表單為當前房間資料
      roomName = room.name || '';
      roomDescription = room.description || '';
      roomType = room.room_type || 'public';
      roomPassword = '';

      loadRoomData();
    }
  });
</script>

{#if show && room}
  <div class="modal modal-open">
    <div class="modal-box max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
      <!-- 標題 -->
      <div class="flex items-center justify-between mb-6">
        <h3 class="font-bold text-xl">房間設定</h3>
        <button
          class="btn btn-sm btn-circle btn-ghost"
          onclick={handleClose}
          disabled={isLoading}
        >
          ✕
        </button>
      </div>

      <!-- 分頁標籤 -->
      <div class="tabs tabs-bordered mb-6">
        <button
          class="tab"
          class:tab-active={activeTab === 'general'}
          onclick={() => activeTab = 'general'}
        >
          一般設定
        </button>

        <!-- 邀請管理和申請審核功能暫時隱藏，等后端 API 實作完成 -->
        <!--
        {#if canInviteUsers}
          <button
            class="tab"
            class:tab-active={activeTab === 'invitations'}
            onclick={() => activeTab = 'invitations'}
          >
            邀請管理
          </button>
        {/if}

        {#if canManageRequests}
          <button
            class="tab"
            class:tab-active={activeTab === 'requests'}
            onclick={() => activeTab = 'requests'}
          >
            申請審核
          </button>
        {/if}
        -->
      </div>

      <!-- 權限提示 -->
      {#if !canManageRoom}
        <div class="alert alert-warning mb-4">
          <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          <span>您沒有權限修改這個房間的設定。只有房間擁有者才能修改房間設定。</span>
        </div>
      {/if}

      <!-- 錯誤提示 -->
      {#if error}
        <div class="alert alert-error mb-4">
          <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>{error}</span>
        </div>
      {/if}

      <!-- 內容區域 -->
      <div class="flex-1 overflow-y-auto">
        {#if activeTab === 'general'}
          <!-- 一般設定 -->
          <div class="space-y-6">
            <!-- 基本資訊 -->
            <div class="form-control">
              <label class="label" for="room-name-settings">
                <span class="label-text font-semibold">房間名稱</span>
              </label>
              <input
                id="room-name-settings"
                type="text"
                placeholder="請輸入房間名稱"
                class="input input-bordered"
                bind:value={roomName}
                disabled={!canManageRoom || isLoading}
                maxlength="50"
              />
            </div>

            <div class="form-control">
              <label class="label" for="room-description-settings">
                <span class="label-text font-semibold">房間描述</span>
              </label>
              <textarea
                id="room-description-settings"
                placeholder="請輸入房間描述"
                class="textarea textarea-bordered"
                rows="3"
                bind:value={roomDescription}
                disabled={!canManageRoom || isLoading}
                maxlength="200"
              ></textarea>
            </div>

            <!-- 房間類型（暫時隱藏） -->
            <!--
            <div class="form-control">
              <label class="label">
                <span class="label-text font-semibold">房間類型</span>
              </label>
              <div class="space-y-3">
                {#each [
                  { value: 'public', label: '🌍 公開房間', desc: '任何人都可以看到並加入，可選密碼保護' },
                  { value: 'private', label: '🔒 私人房間', desc: '僅通過邀請碼加入，可選密碼保護' }
                ] as option}
                  <label class="flex items-start space-x-3 p-3 border rounded-lg cursor-pointer hover:bg-base-200 transition-colors" class:bg-primary={roomType === option.value} class:text-primary-content={roomType === option.value}>
                    <input
                      type="radio"
                      name="room-type-settings"
                      value={option.value}
                      bind:group={roomType}
                      disabled={!canManageRoom || isLoading}
                      class="radio radio-primary mt-1"
                    />
                    <div class="flex-1">
                      <div class="font-medium">{option.label}</div>
                      <div class="text-sm opacity-70">{option.desc}</div>
                    </div>
                  </label>
                {/each}
              </div>
            </div>
            -->

            <!-- 密碼設定（暫時隱藏） -->
            <!--
            <div class="form-control">
              <label class="label">
                <span class="label-text font-semibold">房間密碼（可選）</span>
                <span class="label-text-alt">設置密碼以增加安全性，留空表示不修改</span>
              </label>
              <div class="text-sm text-base-content opacity-70 mb-3">
                {#if roomType === 'public'}
                  • 公開房間：有密碼時需要密碼才能加入，無密碼時可直接加入
                {:else}
                  • 私人房間：始終需要邀請碼，密碼可作為額外保護
                {/if}
              </div>
              <div class="relative">
                  <input
                    id="room-password-settings"
                    type={showRoomPassword ? 'text' : 'password'}
                    placeholder="輸入新密碼（可選）"
                    class="input input-bordered w-full pr-12"
                    bind:value={roomPassword}
                    disabled={!canManageRoom || isLoading}
                    maxlength="50"
                  />
                  <button
                    type="button"
                    class="absolute inset-y-0 right-0 flex items-center pr-3"
                    onclick={() => showRoomPassword = !showRoomPassword}
                    disabled={!canManageRoom || isLoading}
                    aria-label={showRoomPassword ? '隱藏密碼' : '顯示密碼'}
                  >
                    {#if showRoomPassword}
                      <svg class="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L5.636 5.636m4.242 4.242L15.12 15.12m-4.242-4.242L5.636 5.636m9.484 9.484L15.12 15.12M9.878 9.878l4.242 4.242" />
                      </svg>
                    {:else}
                      <svg class="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                    {/if}
                  </button>
                </div>
            </div>
            -->

            <!-- 儲存按鈕 -->
            {#if canManageRoom}
              <div class="flex justify-end space-x-2 pt-4 border-t">
                <Button
                  variant="ghost"
                  onclick={handleClose}
                  disabled={isLoading}
                >
                  取消
                </Button>
                <Button
                  variant="primary"
                  onclick={updateRoomSettings}
                  loading={isLoading}
                  disabled={!roomName.trim()}
                >
                  儲存設定
                </Button>
              </div>
            {/if}
          </div>

        <!-- 邀請管理和申請審核功能暫時隱藏，等后端 API 實作完成 -->
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-box {
    @apply w-full;
  }

  .tab {
    @apply flex-1;
  }

  .card {
    @apply shadow-sm;
  }

  .badge-success {
    @apply bg-green-500 text-white;
  }

  .badge-error {
    @apply bg-red-500 text-white;
  }
</style>