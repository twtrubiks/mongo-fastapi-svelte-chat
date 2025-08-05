<script lang="ts">
  import { generateAvatarColor, generateAvatarText } from '$lib/utils';
  
  interface Props {
    user?: { username: string; avatar?: string } | null;
    size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
    online?: boolean;
    alt?: string;
  }
  
  let {
    user = null,
    size = 'md',
    online = false,
    alt = ''
  }: Props = $props();
  
  let username = $derived(user?.username || 'User');
  let avatar = $derived(user?.avatar);
  let displayText = $derived(generateAvatarText(username));
  let backgroundColor = $derived(generateAvatarColor(username));
  
  let sizeClasses = $derived({
    xs: 'w-6 h-6 text-xs',
    sm: 'w-8 h-8 text-sm',
    md: 'w-10 h-10 text-base',
    lg: 'w-12 h-12 text-lg',
    xl: 'w-16 h-16 text-xl',
  });
  
  let indicatorSizes = $derived({
    xs: 'w-2 h-2',
    sm: 'w-2.5 h-2.5',
    md: 'w-3 h-3',
    lg: 'w-3.5 h-3.5',
    xl: 'w-4 h-4',
  });
  
  let imageError = $state(false);
  
  // 當 avatar URL 改變時，重置錯誤狀態
  $effect(() => {
    if (avatar) {
      imageError = false;
    }
    // console.log('[Avatar] user:', user);
    // console.log('[Avatar] avatar URL:', avatar);
    // console.log('[Avatar] imageError:', imageError);
  });
  
  function handleImageError() {
    // 如果是 base64 格式且太長，不要重試
    if (avatar && avatar.startsWith('data:') && avatar.length > 1000) {
      console.error('頭像 base64 字符串太長');
    } else {
      console.error('頭像載入失敗:', avatar);
    }
    imageError = true;
  }
</script>

<div class="avatar {online ? 'online' : ''}">
  <div class="rounded-full {sizeClasses[size]} relative">
    {#if avatar && !imageError}
      <img
        src={avatar.includes('?') ? `${avatar}&t=${Date.now()}` : `${avatar}?t=${Date.now()}`}
        alt={alt || `${username}的頭像`}
        class="rounded-full object-cover w-full h-full"
        onerror={handleImageError}
      />
    {:else}
      <div
        class="rounded-full flex items-center justify-center font-semibold text-white w-full h-full"
        style="background-color: {backgroundColor}"
      >
        {displayText}
      </div>
    {/if}
    
    {#if online}
      <span
        class="absolute bottom-0 right-0 block {indicatorSizes[size]} bg-green-400 rounded-full ring-2 ring-white"
        aria-label="在線"
      ></span>
    {/if}
  </div>
</div>

<style>
  .avatar {
    @apply relative inline-flex;
  }
  
  .avatar.online {
    @apply relative;
  }
  
  img {
    @apply transition-opacity duration-200;
  }
  
  img:hover {
    @apply opacity-90;
  }
</style>