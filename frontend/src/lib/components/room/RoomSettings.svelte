<script lang="ts">
  import { roomStore } from '$lib/stores/room.svelte';
  import { currentUser } from '$lib/stores/auth.svelte';
  import { copyToClipboard } from '$lib/utils/clipboard';
  import { extractErrorMessage } from '$lib/utils/error';
  import Modal from '$lib/components/ui/Modal.svelte';
  import PasswordInput from '$lib/components/ui/PasswordInput.svelte';
  import { RoomType } from '$lib/types';
  import type { Room, RoomCreate } from '$lib/types';

  interface Props {
    room: Room;
    show: boolean;
    onClose: () => void;
    onUpdate?: (room: Room) => void;
  }

  let {
    room,
    show = $bindable(false),
    onClose,
    onUpdate = undefined
  }: Props = $props();

  // 狀態管理
  let activeTab = $state<'general'>('general');
  let isLoading = $state(false);
  let error = $state<string | null>(null);

  // 一般設定
  let roomName = $state('');
  let roomDescription = $state('');
  let roomType = $state<RoomType>(RoomType.PUBLIC);
  let roomPassword = $state('');
  let successMessage = $state<string | null>(null);
  let showInviteCode = $state(false);
  let inviteCodeCopied = $state(false);
  let copyTimerId: ReturnType<typeof setTimeout> | null = null;

  // 創建本地的響應式變數
  let user = $derived(currentUser());

  // 權限檢查 - 檢查當前用戶是否為房間擁有者
  let canManageRoom = $derived.by(() => {
    if (!user || !room) return false;
    return room.owner_id === user.id;
  });


  // 更新房間設定
  async function updateRoomSettings() {
    if (!room?.id || !canManageRoom) {
      error = '您沒有權限修改這個房間的設定。只有房間擁有者才能修改房間設定。';
      return;
    }

    isLoading = true;
    error = null;
    successMessage = null;

    try {
      const settings: Partial<RoomCreate> = {
        name: roomName.trim(),
        description: roomDescription.trim()
      };

      if (roomPassword.trim()) {
        settings.password = roomPassword;
      }

      const updatedRoom = await roomStore.updateRoomSettings(room.id, settings);
      onUpdate?.(updatedRoom);
      successMessage = '房間設定已更新';
      roomPassword = '';

    } catch (err: unknown) {
      console.error('[RoomSettings] 更新失敗:', err);
      const msg = extractErrorMessage(err, '更新失敗');
      if (msg.includes('只有房間擁有者可以修改')) {
        error = '您沒有權限修改這個房間的設定。只有房間擁有者才能修改房間設定。';
      } else {
        error = msg;
      }
    } finally {
      isLoading = false;
    }
  }

  // TODO: 邀請和申請管理功能等后端 API 實作完成後再添加

  function markCopied() {
    if (copyTimerId) clearTimeout(copyTimerId);
    inviteCodeCopied = true;
    copyTimerId = setTimeout(() => { inviteCodeCopied = false; copyTimerId = null; }, 2000);
  }

  // 複製邀請碼到剪貼簿
  async function copyInviteCode() {
    if (!room?.invite_code) return;
    await copyToClipboard(room.invite_code);
    markCopied();
  }

  // 關閉模態框
  function handleClose() {
    activeTab = 'general';
    error = null;
    successMessage = null;
    showInviteCode = false;
    inviteCodeCopied = false;
    if (copyTimerId) { clearTimeout(copyTimerId); copyTimerId = null; }
    onClose();
  }

  // 獲取房間類型標籤
  function getRoomTypeLabel(type: RoomType): string {
    switch (type) {
      case RoomType.PUBLIC: return '🌍 公開房間';
      case RoomType.PRIVATE: return '🔒 私人房間';
      default: return '🌍 公開房間';
    }
  }


  // 監聽 show 變化，自動載入資料
  $effect(() => {
    if (show && room?.id) {
      // 重置表單為當前房間資料
      roomName = room.name || '';
      roomDescription = room.description || '';
      roomType = room.room_type || RoomType.PUBLIC;
      roomPassword = '';
      showInviteCode = false;
      inviteCodeCopied = false;
    }
  });
</script>

<Modal bind:open={show} title="房間設定" size="xl" closeable={!isLoading} onClose={handleClose}>
  <!-- 分隔線 -->
  <div class="divider mt-0"></div>

  <!-- 分頁標籤 -->
  <div class="tabs tabs-boxed mb-4">
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

  {#if successMessage}
    <div class="alert alert-success mb-4">
      <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <span>{successMessage}</span>
    </div>
  {/if}

  <!-- 內容區域 -->
  <div class="modal-body">
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

        <!-- 邀請碼顯示（僅房間擁有者 + 有邀請碼的房間） -->
        {#if canManageRoom && room.invite_code}
          <div class="form-control">
            <div class="label">
              <span class="label-text font-semibold">邀請碼</span>
              <span class="label-text-alt">分享給其他人以加入此房間</span>
            </div>
            <div class="bg-base-200 p-4 rounded-lg">
              <div class="flex items-center justify-between gap-3">
                {#if showInviteCode}
                  <code class="text-lg font-mono text-primary flex-1 break-all">{room.invite_code}</code>
                {:else}
                  <span class="text-lg flex-1 tracking-widest text-base-content/40">••••••••••••••••</span>
                {/if}
                <div class="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    class="btn btn-ghost btn-sm"
                    onclick={() => showInviteCode = !showInviteCode}
                    aria-label={showInviteCode ? '隱藏邀請碼' : '顯示邀請碼'}
                    title={showInviteCode ? '隱藏邀請碼' : '顯示邀請碼'}
                  >
                    {#if showInviteCode}
                      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L5.636 5.636m4.242 4.242L15.12 15.12m-4.242-4.242L5.636 5.636m9.484 9.484L15.12 15.12M9.878 9.878l4.242 4.242" />
                      </svg>
                    {:else}
                      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                    {/if}
                  </button>
                  <button
                    type="button"
                    class="btn btn-outline btn-sm"
                    onclick={copyInviteCode}
                    title="複製邀請碼"
                  >
                    {#if inviteCodeCopied}
                      <svg class="w-4 h-4 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                      </svg>
                      已複製
                    {:else}
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                      </svg>
                      複製
                    {/if}
                  </button>
                </div>
              </div>
            </div>
            <div class="text-sm text-base-content/60 mt-2">
              將此邀請碼分享給其他用戶，他們可以通過「加入房間」功能輸入此邀請碼加入。
            </div>
          </div>
        {/if}

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

        {#if roomType === RoomType.PUBLIC}
        <div class="form-control">
          <label class="label" for="room-password-settings">
            <span class="label-text font-semibold">房間密碼（可選）</span>
            <span class="label-text-alt">留空表示不修改</span>
          </label>
          <div class="text-sm text-base-content opacity-70 mb-3">
            有密碼時需要密碼才能加入，無密碼時可直接加入
          </div>
          <PasswordInput
            id="room-password-settings"
            bind:value={roomPassword}
            placeholder="輸入新密碼（可選）"
            disabled={!canManageRoom || isLoading}
            maxlength={50}
          />
        </div>
        {/if}

        <!-- 儲存按鈕 -->
        {#if canManageRoom}
          <div class="modal-action">
            <button
              class="btn btn-ghost"
              onclick={handleClose}
              disabled={isLoading}
            >
              取消
            </button>
            <button
              class="btn btn-primary"
              onclick={updateRoomSettings}
              disabled={isLoading || !roomName.trim()}
            >
              {#if isLoading}
                <span class="loading loading-spinner loading-sm"></span>
              {/if}
              儲存設定
            </button>
          </div>
        {/if}
      </div>

    <!-- 邀請管理和申請審核功能暫時隱藏，等后端 API 實作完成 -->
    {/if}
  </div>
</Modal>

<style>
	@reference "$lib/styles/tailwind.css";
  /* 使用 DaisyUI 原生類別，移除大部分自定義樣式 */

  /* 保留 tab 的樣式以確保平均分配寬度 */
  .tabs-boxed .tab {
    @apply flex-1;
  }
</style>
