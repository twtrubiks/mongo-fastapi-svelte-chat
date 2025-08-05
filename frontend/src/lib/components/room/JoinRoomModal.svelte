<script lang="ts">
  import { Button, Loading } from '$lib/components/ui';
  import { roomStore } from '$lib/stores/room.svelte';
  import type { Room, RoomJoinRequest, RoomType, JoinPolicy } from '$lib/types';
  
  interface Props {
    room: Room;
    show: boolean;
    onClose: () => void;
    onSuccess?: (room: Room) => void;
  }
  
  let {
    room,
    show = false,
    onClose,
    onSuccess = undefined
  }: Props = $props();
  
  // 狀態
  let isLoading = $state(false);
  let error = $state<string | null>(null);
  let step = $state<'check' | 'password' | 'invite' | 'approval' | 'success'>('check');
  let requirements = $state<any>(null);
  
  // 表單數據
  let password = $state('');
  let inviteCode = $state('');
  let requestMessage = $state('');
  let showPassword = $state(false);
  
  // 重置狀態
  function resetState() {
    step = 'check';
    error = null;
    password = '';
    inviteCode = '';
    requestMessage = '';
    showPassword = false;
    requirements = null;
  }
  
  // 檢查加入要求
  async function checkJoinRequirements() {
    if (!room?.id) return;
    
    isLoading = true;
    error = null;
    
    try {
      const result = await roomStore.checkJoinRequirements(room.id);
      requirements = result;
      
      if (result.isMember) {
        // 如果已經是成員，直接成功並關閉模態框
        onSuccess?.(room);
        return;
      }
      
      // 根據要求決定下一步
      if (result.requirements.canDirectJoin) {
        await attemptJoin();
      } else if (result.requirements.needsPassword) {
        step = 'password';
      } else if (result.requirements.needsInviteCode) {
        step = 'invite';
      } else if (result.requirements.needsApproval) {
        step = 'approval';
      }
      
    } catch (err: any) {
      error = err.message || '檢查加入要求失敗';
    } finally {
      isLoading = false;
    }
  }
  
  // 嘗試加入房間
  async function attemptJoin(joinRequest?: RoomJoinRequest) {
    if (!room?.id) return;
    
    isLoading = true;
    error = null;
    
    try {
      const result = await roomStore.joinRoom(room.id, joinRequest);
      
      if (result.success) {
        step = 'success';
        onSuccess?.(result.room || room);
      } else if (result.requiresAction) {
        // 根據需要的操作切換步驟
        switch (result.requiresAction.type) {
          case 'password':
            step = 'password';
            break;
          case 'invite_code':
            step = 'invite';
            break;
          case 'approval':
            step = 'approval';
            break;
          case 'error':
            error = result.requiresAction.message;
            break;
          default:
            error = result.message;
        }
      }
      
    } catch (err: any) {
      error = err.message || '加入房間失敗';
    } finally {
      isLoading = false;
    }
  }
  
  // 提交密碼
  async function submitPassword() {
    if (!password.trim()) {
      error = '請輸入密碼';
      return;
    }
    
    if (!room?.id) return;
    
    isLoading = true;
    error = null;
    
    try {
      const result = await roomStore.joinRoom(room.id, { password: password.trim() });
      
      if (result.success) {
        step = 'success';
        onSuccess?.(result.room || room);
      } else if (result.requiresAction?.type === 'error') {
        // 密碼錯誤，保持在密碼步驟並顯示錯誤
        error = result.requiresAction.message;
      } else {
        error = result.message || '加入房間失敗';
      }
      
    } catch (err: any) {
      error = err.message || '加入房間失敗';
    } finally {
      isLoading = false;
    }
  }
  
  // 提交邀請碼
  async function submitInviteCode() {
    if (!inviteCode.trim()) {
      error = '請輸入邀請碼';
      return;
    }
    
    await attemptJoin({ invite_code: inviteCode.trim() });
  }
  
  // 提交加入申請
  async function submitJoinRequest() {
    if (!room?.id) return;
    
    isLoading = true;
    error = null;
    
    try {
      await roomStore.createJoinRequest(room.id, {
        room_id: room.id,
        message: requestMessage.trim() || undefined
      });
      
      step = 'success';
      
    } catch (err: any) {
      error = err.message || '提交加入申請失敗';
    } finally {
      isLoading = false;
    }
  }
  
  // 關閉模態框
  function handleClose() {
    resetState();
    onClose();
  }
  
  // 獲取房間類型標籤
  function getRoomTypeLabel(roomType?: RoomType): string {
    switch (roomType) {
      case 'public': return '公開房間';
      case 'private': return '私人房間';
      case 'protected': return '受保護房間';
      case 'organization': return '組織房間';
      default: return '一般房間';
    }
  }
  
  // 監聽 show 變化，自動檢查要求
  $effect(() => {
    if (show && room?.id) {
      // 每次顯示時重置狀態
      resetState();
      checkJoinRequirements();
    }
  });
</script>

{#if show}
  <div class="modal modal-open">
    <div class="modal-box max-w-md">
      <div class="flex items-center justify-between mb-4">
        <h3 class="font-bold text-lg">加入聊天室</h3>
        <button 
          class="btn btn-sm btn-circle btn-ghost" 
          onclick={handleClose}
          disabled={isLoading}
        >
          ✕
        </button>
      </div>
      
      <!-- 房間資訊 -->
      <div class="bg-base-200 rounded-lg p-4 mb-4">
        <div class="flex items-center space-x-3">
          <div class="avatar placeholder">
            <div class="bg-primary text-primary-content rounded-full w-12">
              <span class="text-lg font-bold">
                {room.name.charAt(0).toUpperCase()}
              </span>
            </div>
          </div>
          <div>
            <h4 class="font-semibold">{room.name}</h4>
            {#if room.description}
              <p class="text-sm text-base-content/70">{room.description}</p>
            {/if}
            <div class="flex items-center space-x-2 mt-1">
              <span class="badge badge-sm">
                {getRoomTypeLabel(room.room_type)}
              </span>
              {#if requirements}
                <span class="text-xs text-base-content/60">
                  {requirements.room.member_count} 成員
                </span>
              {/if}
            </div>
          </div>
        </div>
      </div>
      
      {#if error}
        <div class="alert alert-error mb-4">
          <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>{error}</span>
        </div>
      {/if}
      
      <!-- 載入中 -->
      {#if isLoading && step === 'check'}
        <div class="flex justify-center py-8">
          <Loading text="檢查加入要求..." />
        </div>
      
      <!-- 密碼驗證 -->
      {:else if step === 'password'}
        <div class="space-y-4">
          <div class="text-center">
            <div class="text-4xl mb-2">🔒</div>
            <p class="text-base-content/70">此聊天室需要密碼才能加入</p>
          </div>
          
          <div class="form-control">
            <label class="label" for="room-password">
              <span class="label-text">請輸入房間密碼</span>
            </label>
            <div class="relative">
              <input
                id="room-password"
                type={showPassword ? 'text' : 'password'}
                placeholder="房間密碼"
                class="input input-bordered w-full pr-12"
                bind:value={password}
                disabled={isLoading}
                onkeydown={(e) => e.key === 'Enter' && submitPassword()}
              />
              <button
                type="button"
                class="absolute inset-y-0 right-0 flex items-center pr-3"
                onclick={() => showPassword = !showPassword}
                disabled={isLoading}
                aria-label={showPassword ? '隱藏密碼' : '顯示密碼'}
              >
                {#if showPassword}
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
          
          <div class="flex space-x-2">
            <Button
              variant="ghost"
              class="flex-1"
              onclick={handleClose}
              disabled={isLoading}
            >
              取消
            </Button>
            <Button
              variant="primary"
              class="flex-1"
              onclick={submitPassword}
              loading={isLoading}
              disabled={!password.trim()}
            >
              加入
            </Button>
          </div>
        </div>
      
      <!-- 邀請碼驗證 -->
      {:else if step === 'invite'}
        <div class="space-y-4">
          <div class="text-center">
            <div class="text-4xl mb-2">📧</div>
            <p class="text-base-content/70">此聊天室需要邀請碼才能加入</p>
          </div>
          
          <div class="form-control">
            <label class="label" for="invite-code">
              <span class="label-text">請輸入邀請碼</span>
            </label>
            <input
              id="invite-code"
              type="text"
              placeholder="邀請碼"
              class="input input-bordered"
              bind:value={inviteCode}
              disabled={isLoading}
              onkeydown={(e) => e.key === 'Enter' && submitInviteCode()}
            />
          </div>
          
          <div class="flex space-x-2">
            <Button
              variant="ghost"
              class="flex-1"
              onclick={handleClose}
              disabled={isLoading}
            >
              取消
            </Button>
            <Button
              variant="primary"
              class="flex-1"
              onclick={submitInviteCode}
              loading={isLoading}
              disabled={!inviteCode.trim()}
            >
              加入
            </Button>
          </div>
        </div>
      
      <!-- 申請審核 -->
      {:else if step === 'approval'}
        <div class="space-y-4">
          <div class="text-center">
            <div class="text-4xl mb-2">📝</div>
            <p class="text-base-content/70">此聊天室需要提交加入申請</p>
          </div>
          
          <div class="form-control">
            <label class="label" for="request-message">
              <span class="label-text">申請理由（可選）</span>
            </label>
            <textarea
              id="request-message"
              placeholder="請簡述您想加入此聊天室的理由..."
              class="textarea textarea-bordered"
              rows="3"
              bind:value={requestMessage}
              disabled={isLoading}
            ></textarea>
          </div>
          
          <div class="flex space-x-2">
            <Button
              variant="ghost"
              class="flex-1"
              onclick={handleClose}
              disabled={isLoading}
            >
              取消
            </Button>
            <Button
              variant="primary"
              class="flex-1"
              onclick={submitJoinRequest}
              loading={isLoading}
            >
              提交申請
            </Button>
          </div>
        </div>
      
      <!-- 成功 -->
      {:else if step === 'success'}
        <div class="text-center space-y-4">
          <div class="text-6xl">✅</div>
          
          {#if requirements?.isMember}
            <div>
              <h4 class="text-lg font-semibold mb-2">您已經是成員</h4>
              <p class="text-base-content/70">您已經是此聊天室的成員了</p>
            </div>
          {:else if step === 'success' && requestMessage}
            <div>
              <h4 class="text-lg font-semibold mb-2">申請已提交</h4>
              <p class="text-base-content/70">您的加入申請已提交，請等待房主審核</p>
            </div>
          {:else}
            <div>
              <h4 class="text-lg font-semibold mb-2">加入成功！</h4>
              <p class="text-base-content/70">歡迎加入 {room.name}</p>
            </div>
          {/if}
          
          <Button
            variant="primary"
            onclick={handleClose}
            class="w-full"
          >
            確定
          </Button>
        </div>
      {/if}
    </div>
  </div>
{/if}