<script lang="ts">
  import { debounce } from '$lib/utils';

  interface Props {
    currentTab: 'joined' | 'explore';
    searchValue: string;
    onSearch: (value: string) => void;
    onClear: () => void;
  }

  let {
    currentTab,
    searchValue = $bindable(''),
    onSearch,
    onClear
  }: Props = $props();

  const debouncedSearch = debounce((value: string) => {
    onSearch(value);
  }, 300);

  function handleInput(event: Event) {
    const value = (event.target as HTMLInputElement).value;
    searchValue = value;
    if (currentTab === 'explore') {
      debouncedSearch(value);
    }
  }
</script>

<div class="px-2 pb-2">
  <label class="input input-sm input-bordered flex items-center gap-2 w-full">
    <svg class="w-4 h-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
    <input
      type="text"
      class="grow"
      placeholder={currentTab === 'joined' ? '搜尋已加入的房間...' : '搜尋公開房間...'}
      value={searchValue}
      oninput={handleInput}
    />
    {#if searchValue}
      <button
        class="btn btn-ghost btn-xs btn-circle"
        onclick={onClear}
        aria-label="清除搜尋"
      >
        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    {/if}
  </label>
</div>
