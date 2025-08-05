<script lang="ts">
  import { onMount } from 'svelte';
  import { 
    notificationSettings, 
    browserNotificationPermission, 
    soundEnabled,
    browserNotificationManager,
    soundNotificationManager,
    notificationStore
  } from '$lib/stores/notification.svelte';
  import Button from './Button.svelte';
  import Modal from './Modal.svelte';

  interface Props {
    open?: boolean;
    onClose?: () => void;
  }

  let { open = $bindable(false), onClose }: Props = $props();

  let settings = $state(notificationSettings.value);
  let permission = $state(browserNotificationPermission.value);
  let testSoundPlaying = $state(false);

  // 更新設置
  function updateSettings() {
    notificationStore.updateSettings(settings);
    
    // 儲存到 localStorage
    if (typeof window !== 'undefined') {
      localStorage.setItem('notificationSettings', JSON.stringify(settings));
    }
  }

  // 請求瀏覽器通知權限
  async function requestBrowserNotificationPermission() {
    const newPermission = await browserNotificationManager.requestPermission();
    permission = newPermission;
    
    if (newPermission === 'granted') {
      settings.browserNotifications = true;
      updateSettings();
      
      // 顯示測試通知
      browserNotificationManager.showNotification('通知權限已開啟', {
        body: '您現在可以接收瀏覽器推送通知了！',
        icon: '/favicon.svg'
      });
    }
  }

  // 測試聲音通知
  function testSound() {
    if (testSoundPlaying) return;
    
    testSoundPlaying = true;
    soundNotificationManager.playNotificationSound();
    
    setTimeout(() => {
      testSoundPlaying = false;
    }, 1000);
  }

  // 創建測試通知
  async function createTestNotification() {
    try {
      const response = await fetch('/api/notifications/test', {
        method: 'POST',
        credentials: 'include'
      });

      if (response.ok) {
        const result = await response.json();
        
        // 顯示瀏覽器通知作為反饋
        if (settings.browserNotifications && permission === 'granted') {
          browserNotificationManager.showNotification('測試通知創建成功', {
            body: '測試通知已成功發送',
            icon: '/favicon.svg'
          });
        }
      } else {
        const errorData = await response.json();
        alert(`創建測試通知失敗: ${errorData.error || '未知錯誤'}`);
      }
    } catch (error) {
      alert('創建測試通知時發生錯誤');
    }
  }

  onMount(() => {
    // 從 localStorage 載入設置
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('notificationSettings');
      if (saved) {
        try {
          settings = { ...settings, ...JSON.parse(saved) };
        } catch (e) {
        }
      }
    }
  });

  // 響應式更新 - 移除自動更新，改為手動觸發
  // $effect(() => {
  //   if (settings) {
  //     updateSettings();
  //   }
  // });

  // 獲取權限狀態文字
  function getPermissionText(perm: NotificationPermission): string {
    switch (perm) {
      case 'granted':
        return '已允許';
      case 'denied':
        return '已拒絕';
      default:
        return '未設置';
    }
  }

  // 獲取權限狀態顏色
  function getPermissionColor(perm: NotificationPermission): string {
    switch (perm) {
      case 'granted':
        return 'text-green-600';
      case 'denied':
        return 'text-red-600';
      default:
        return 'text-yellow-600';
    }
  }
</script>

<Modal bind:open {onClose} title="通知設置">
  <div class="space-y-6">
    
    <!-- 瀏覽器通知設置 -->
    <div class="border-b pb-4">
      <h3 class="text-lg font-semibold text-gray-900 mb-4">瀏覽器通知</h3>
      
      <div class="space-y-4">
        <div class="flex items-center justify-between">
          <div>
            <p class="font-medium text-gray-700">啟用瀏覽器通知</p>
            <p class="text-sm text-gray-500">在瀏覽器中顯示新訊息通知</p>
          </div>
          <label class="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              bind:checked={settings.browserNotifications}
              disabled={permission !== 'granted'}
              class="sr-only peer"
              onchange={() => updateSettings()}
            />
            <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
          </label>
        </div>

        <div class="bg-gray-50 p-3 rounded-lg">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium text-gray-700">
                權限狀態: <span class="{getPermissionColor(permission)}">{getPermissionText(permission)}</span>
              </p>
              {#if permission === 'denied'}
                <p class="text-xs text-red-600 mt-1">
                  請在瀏覽器設置中手動允許通知權限
                </p>
              {/if}
            </div>
            
            {#if permission !== 'granted'}
              <Button
                size="sm"
                onclick={requestBrowserNotificationPermission}
                disabled={permission === 'denied'}
              >
                {permission === 'denied' ? '已拒絕' : '請求權限'}
              </Button>
            {/if}
          </div>
        </div>
      </div>
    </div>

    <!-- 聲音通知設置 -->
    <div class="border-b pb-4">
      <h3 class="text-lg font-semibold text-gray-900 mb-4">聲音提醒</h3>
      
      <div class="space-y-4">
        <div class="flex items-center justify-between">
          <div>
            <p class="font-medium text-gray-700">啟用聲音提醒</p>
            <p class="text-sm text-gray-500">新訊息時播放提示音</p>
          </div>
          <label class="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              bind:checked={settings.sound}
              class="sr-only peer"
              onchange={() => updateSettings()}
            />
            <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
          </label>
        </div>

        <div class="bg-gray-50 p-3 rounded-lg">
          <Button
            size="sm"
            variant="outline"
            onclick={testSound}
            disabled={testSoundPlaying || !settings.sound}
          >
            {testSoundPlaying ? '播放中...' : '測試聲音'}
          </Button>
        </div>
      </div>
    </div>

    <!-- 郵件通知設置 - 暫時隱藏，尚未實作 -->
    <!--
    <div class="border-b pb-4">
      <h3 class="text-lg font-semibold text-gray-900 mb-4">郵件通知</h3>
      
      <div class="space-y-4">
        <div class="flex items-center justify-between">
          <div>
            <p class="font-medium text-gray-700">啟用郵件通知</p>
            <p class="text-sm text-gray-500">重要通知會發送到您的郵箱</p>
          </div>
          <label class="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              bind:checked={settings.email}
              class="sr-only peer"
              onchange={() => updateSettings()}
            />
            <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
          </label>
        </div>
      </div>
    </div>
    -->

    <!-- 推送通知設置 - 暫時隱藏，尚未實作 -->
    <!--
    <div class="border-b pb-4">
      <h3 class="text-lg font-semibold text-gray-900 mb-4">推送通知</h3>
      
      <div class="space-y-4">
        <div class="flex items-center justify-between">
          <div>
            <p class="font-medium text-gray-700">啟用推送通知</p>
            <p class="text-sm text-gray-500">透過服務器推送接收通知</p>
          </div>
          <label class="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              bind:checked={settings.push}
              class="sr-only peer"
              onchange={() => updateSettings()}
            />
            <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
          </label>
        </div>
      </div>
    </div>
    -->

    <!-- 測試區域 -->
    <div>
      <h3 class="text-lg font-semibold text-gray-900 mb-4">測試通知</h3>
      <p class="text-sm text-gray-500 mb-4">創建一個測試通知來驗證設置是否正常工作</p>
      
      <Button
        variant="outline"
        onclick={createTestNotification}
      >
        創建測試通知
      </Button>
    </div>
  </div>
</Modal>

{#snippet actions()}
  <Button variant="outline" onclick={onClose}>
    關閉
  </Button>
{/snippet}