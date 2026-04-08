<script lang="ts">
  import { roomStore } from '$lib/stores';
  import { extractErrorMessage } from '$lib/utils/error';
  import Modal from '$lib/components/ui/Modal.svelte';
  import PasswordInput from '$lib/components/ui/PasswordInput.svelte';
  import { Toast } from '$lib/components/ui';
  import type { RoomSummary } from '$lib/types';

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

  let inviteCodeInput = $state('');
  let isJoining = $state(false);
  let toastState = $state({ show: false, message: '' });

  // 當 modal 關閉時重置狀態
  $effect(() => {
    if (!open) {
      resetForm();
    }
  });

  function resetForm() {
    inviteCodeInput = '';
    isJoining = false;
    toastState = { show: false, message: '' };
  }

  async function joinByInviteCode() {
    const code = inviteCodeInput.trim();
    if (!code) return;

    isJoining = true;
    try {
      const result = await roomStore.validateInvitation(code);

      if (result.room) {
        await roomStore.joinRoom(result.room.id, { invite_code: code });
        open = false;
        onSuccess(result.room as unknown as RoomSummary);
      }
    } catch (error: unknown) {
      toastState = { show: true, message: `邀請碼驗證失敗：${extractErrorMessage(error, '未知錯誤')}` };
    } finally {
      isJoining = false;
    }
  }

  function handleClose() {
    open = false;
    onClose();
  }
</script>

<Modal bind:open title="🔑 通過邀請碼加入房間" size="sm" onClose={handleClose}>
  <div class="mb-6">
    <p class="mb-4 text-sm text-base-content/70">
      請輸入其他用戶分享給您的邀請碼來加入私人房間：
    </p>

    <div class="form-control mb-4">
      <label class="label" for="invite-code-input">
        <span class="label-text">邀請碼</span>
      </label>
      <PasswordInput
        id="invite-code-input"
        placeholder="請輸入邀請碼"
        bind:value={inviteCodeInput}
        onkeydown={(e) => e.key === 'Enter' && !isJoining && joinByInviteCode()}
        disabled={isJoining}
      />
    </div>

    <div class="text-xs text-base-content/50">
      💡 邀請碼通常是由房間創建者分享的一串字符
    </div>
  </div>

  <Toast bind:show={toastState.show} type="error" message={toastState.message} />

  {#snippet actions()}
    <button
      class="btn"
      onclick={handleClose}
      disabled={isJoining}
    >
      取消
    </button>
    <button
      class="btn btn-primary"
      onclick={joinByInviteCode}
      disabled={!inviteCodeInput.trim() || isJoining}
    >
      {#if isJoining}
        <span class="loading loading-spinner loading-sm"></span>
        加入中...
      {:else}
        加入房間
      {/if}
    </button>
  {/snippet}
</Modal>
