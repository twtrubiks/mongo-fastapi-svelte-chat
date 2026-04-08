<script lang="ts">
  interface Props {
    subtitle?: string;
  }

  let { subtitle = '選擇左側的聊天室開始聊天，或創建一個新的聊天室' }: Props = $props();
</script>

<div class="h-full flex flex-col items-center justify-center p-8 text-center">
  <div class="mb-6">
    <svg class="w-16 h-16 mx-auto text-base-content opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
    </svg>
  </div>
  <h2 class="text-2xl font-bold text-base-content mb-4">歡迎使用聊天室</h2>
  <p class="text-base-content opacity-60 max-w-md">{subtitle}</p>
</div>
