<script lang="ts">
  import { roomStore } from '$lib/stores';
  import { copyToClipboard } from '$lib/utils/clipboard';
  import { extractErrorMessage } from '$lib/utils/error';
  import { Button, Toast } from '$lib/components/ui';
  import Modal from '$lib/components/ui/Modal.svelte';
  import PasswordInput from '$lib/components/ui/PasswordInput.svelte';
  import { RoomType, JoinPolicy } from '$lib/types';
  import type { RoomSummary, RoomCreate } from '$lib/types';

  interface Props {
    open: boolean;
    onSuccess: (room: RoomSummary) => void;
    onClose: () => void;
  }

  let {
    open = $bindable(false),
    onSuccess,
    onClose
  }: Props = $props();

  // 兩階段流程：填表 → 邀請碼顯示
  let step = $state<'form' | 'invite-code'>('form');
  let createdRoom = $state<RoomSummary | null>(null);
  let createdInviteCode = $state('');

  // 表單狀態
  let newRoomName = $state('');
  let newRoomDescription = $state('');
  let newRoomType = $state<RoomType>(RoomType.PUBLIC);
  let newPassword = $state('');
  let isCreating = $state(false);

  // Toast 狀態
  let toastState = $state({ show: false, message: '', type: 'error' as 'error' | 'warning' });

  function showToast(message: string, type: 'error' | 'warning' = 'error') {
    toastState = { show: true, message, type };
  }

  // 衍生驗證
  let trimmedRoomName = $derived(newRoomName.trim());
  let trimmedPassword = $derived(newPassword.trim());
  let isPasswordValid = $derived(trimmedPassword.length === 0 || trimmedPassword.length >= 6);

  // 當房間類型改為私人時，清空密碼欄位
  $effect(() => {
    if (newRoomType === RoomType.PRIVATE) {
      newPassword = '';
    }
  });

  // 當 modal 關閉時重置狀態
  $effect(() => {
    if (!open) {
      resetForm();
    }
  });

  function resetForm() {
    step = 'form';
    createdRoom = null;
    createdInviteCode = '';
    newRoomName = '';
    newRoomDescription = '';
    newRoomType = RoomType.PUBLIC;
    newPassword = '';
    isCreating = false;
    toastState = { show: false, message: '', type: 'error' };
  }

  async function createRoom() {
    if (!trimmedRoomName) return;
    if (!isPasswordValid) {
      showToast('密碼至少需要 6 個字符', 'warning');
      return;
    }

    isCreating = true;
    try {
      // 根據房間類型和密碼設置自動決定加入策略
      let joinPolicy: JoinPolicy;
      if (newRoomType === RoomType.PRIVATE) {
        joinPolicy = JoinPolicy.INVITE;
      } else if (trimmedPassword) {
        joinPolicy = JoinPolicy.PASSWORD;
      } else {
        joinPolicy = JoinPolicy.DIRECT;
      }

      const createData: RoomCreate = {
        name: trimmedRoomName,
        is_public: newRoomType === RoomType.PUBLIC,
        room_type: newRoomType,
        join_policy: joinPolicy,
        max_members: 100,
      };
      if (newRoomDescription.trim()) {
        createData.description = newRoomDescription.trim();
      }
      if (newRoomType === RoomType.PUBLIC && trimmedPassword) {
        createData.password = trimmedPassword;
      }

      const room = await roomStore.createRoom(createData);

      // 邀請制房間：顯示邀請碼
      if (room.join_policy === JoinPolicy.INVITE && room.invite_code) {
        createdRoom = room;
        createdInviteCode = room.invite_code;
        step = 'invite-code';
      } else {
        // 非邀請制：直接通知 parent
        open = false;
        onSuccess(room);
      }
    } catch (error: unknown) {
      showToast(extractErrorMessage(error, '創建房間時發生錯誤'));
    } finally {
      isCreating = false;
    }
  }

  function handleInviteCodeConfirm() {
    const room = createdRoom;
    open = false;
    if (room) {
      onSuccess(room);
    }
  }

  function handleClose() {
    open = false;
    onClose();
  }

  let modalTitle = $derived(step === 'form' ? '創建新聊天室' : '🎉 房間創建成功！');
</script>

<Modal bind:open title={modalTitle} size="lg" onClose={handleClose}>
  {#if step === 'form'}
    <!-- 建房表單 -->
    <div class="form-control mb-4">
      <label class="label" for="room-name">
        <span class="label-text">聊天室名稱</span>
      </label>
      <input
        id="room-name"
        type="text"
        placeholder="請輸入聊天室名稱"
        class="input input-bordered w-full"
        bind:value={newRoomName}
        maxlength="100"
      />
    </div>

    <div class="form-control mb-4">
      <label class="label" for="room-description">
        <span class="label-text">描述（可選）</span>
      </label>
      <textarea
        id="room-description"
        placeholder="請輸入聊天室描述"
        class="textarea textarea-bordered w-full"
        bind:value={newRoomDescription}
        maxlength="500"
      ></textarea>
    </div>

    <!-- 房間類型選擇 -->
    <div class="form-control mb-4">
      <div class="label">
        <span class="label-text">房間類型</span>
      </div>
      <div class="space-y-3">
        <label class="flex items-start space-x-3 p-3 border rounded-lg cursor-pointer transition-colors" class:hover:bg-base-200={newRoomType !== RoomType.PUBLIC} class:bg-primary={newRoomType === RoomType.PUBLIC} class:text-primary-content={newRoomType === RoomType.PUBLIC}>
          <input
            type="radio"
            name="room-type"
            value={RoomType.PUBLIC}
            bind:group={newRoomType}
            class="radio radio-primary mt-1"
          />
          <div class="flex-1">
            <div class="font-medium">🌍 公開房間</div>
            <div class="text-sm" class:opacity-60={newRoomType !== RoomType.PUBLIC} class:opacity-90={newRoomType === RoomType.PUBLIC}>任何人都可以看到並加入，可選密碼保護</div>
          </div>
        </label>
        <label class="flex items-start space-x-3 p-3 border rounded-lg cursor-pointer transition-colors" class:hover:bg-base-200={newRoomType !== RoomType.PRIVATE} class:bg-primary={newRoomType === RoomType.PRIVATE} class:text-primary-content={newRoomType === RoomType.PRIVATE}>
          <input
            type="radio"
            name="room-type"
            value={RoomType.PRIVATE}
            bind:group={newRoomType}
            class="radio radio-primary mt-1"
          />
          <div class="flex-1">
            <div class="font-medium">🔒 私人房間</div>
            <div class="text-sm" class:opacity-60={newRoomType !== RoomType.PRIVATE} class:opacity-90={newRoomType === RoomType.PRIVATE}>僅通過邀請碼加入</div>
          </div>
        </label>
      </div>
    </div>

    <!-- 密碼設置（僅公開房間可用） -->
    {#if newRoomType === RoomType.PUBLIC}
    <div class="form-control mb-4">
      <label class="label" for="room-password">
        <span class="label-text">房間密碼（可選）</span>
        <span class="label-text-alt">設置密碼以增加安全性</span>
      </label>
      <PasswordInput
        id="room-password"
        bind:value={newPassword}
        placeholder="留空表示無密碼保護"
        disabled={isCreating}
        maxlength={50}
      />
      {#if trimmedPassword && trimmedPassword.length < 6}
        <div class="label">
          <span class="label-text-alt text-error">密碼至少需要 6 個字符</span>
        </div>
      {/if}
    </div>
    {/if}

  {:else}
    <!-- 邀請碼顯示階段 -->
    <div class="mb-6">
      <p class="mb-3">您的房間邀請碼如下，請分享給其他人以便他們加入房間：</p>

      <div class="bg-base-200 p-4 rounded-lg mb-4">
        <div class="flex items-center justify-between">
          <code class="text-lg font-mono text-primary flex-1 mr-3">{createdInviteCode}</code>
          <button
            class="btn btn-outline btn-sm"
            onclick={() => copyToClipboard(createdInviteCode)}
            title="複製邀請碼"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
            </svg>
            複製
          </button>
        </div>
      </div>

      <div class="text-sm text-base-content/70">
        <p class="mb-2">📝 使用方法：</p>
        <ul class="list-disc list-inside space-y-1 ml-2">
          <li>將邀請碼分享給其他用戶</li>
          <li>他們可以通過「加入房間」功能輸入此邀請碼</li>
          <li>或者直接提供邀請碼讓他們手動輸入</li>
        </ul>
      </div>
    </div>
  {/if}

  <Toast bind:show={toastState.show} type={toastState.type} message={toastState.message} />

  {#snippet actions()}
    {#if step === 'form'}
      <Button
        variant="ghost"
        onclick={handleClose}
        disabled={isCreating}
      >
        取消
      </Button>
      <Button
        variant="primary"
        onclick={createRoom}
        loading={isCreating}
        disabled={!trimmedRoomName || isCreating || !isPasswordValid}
      >
        創建
      </Button>
    {:else}
      <button class="btn btn-primary" onclick={handleInviteCodeConfirm}>
        知道了
      </button>
    {/if}
  {/snippet}
</Modal>
