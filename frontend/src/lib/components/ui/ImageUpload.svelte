<script lang="ts">
  import { Button, Loading } from '$lib/components/ui';
  import { formatFileSize, isImageFile, isFileSizeValid } from '$lib/utils';
  
  interface Props {
    accept?: string;
    maxSizeMB?: number;
    multiple?: boolean;
    disabled?: boolean;
    preview?: boolean;
    dragDrop?: boolean;
    compact?: boolean;
    onFileSelected?: (data: { file: File }) => void;
    onUpload?: (data: { file: File }) => void;
    onUploaded?: (data: { file: File; url: string; filename: string }) => void;
    onFileRemoved?: () => void;
    onError?: (data: { message: string }) => void;
  }
  
  let { 
    accept = 'image/*',
    maxSizeMB = 5,
    multiple = false,
    disabled = false,
    preview = true,
    dragDrop = true,
    compact = false,
    onFileSelected,
    onUpload,
    onUploaded,
    onFileRemoved,
    onError
  }: Props = $props();
  
  let fileInput: HTMLInputElement = $state(null!);
  let isDragging = $state(false);
  let dragCounter = $state(0);
  let isUploading = $state(false);
  let uploadProgress = $state(0);
  let previewUrl = $state<string | null>(null);
  let selectedFile = $state<File | null>(null);
  
  // 處理文件選擇
  function handleFileSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    const files = input.files;
    
    if (files && files.length > 0) {
      processFile(files[0]);
    }
  }
  
  // 處理拖拽
  function handleDragEnter(event: DragEvent) {
    if (!dragDrop || disabled) return;
    
    event.preventDefault();
    event.stopPropagation();
    dragCounter++;
    isDragging = true;
  }
  
  function handleDragOver(event: DragEvent) {
    if (!dragDrop || disabled) return;
    
    event.preventDefault();
    event.stopPropagation();
  }
  
  function handleDragLeave(event: DragEvent) {
    if (!dragDrop || disabled) return;
    
    event.preventDefault();
    dragCounter--;
    if (dragCounter === 0) {
      isDragging = false;
    }
  }
  
  function handleDrop(event: DragEvent) {
    if (!dragDrop || disabled) return;
    
    event.preventDefault();
    event.stopPropagation();
    isDragging = false;
    dragCounter = 0;
    
    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      processFile(files[0]);
    }
  }
  
  // 處理文件
  function processFile(file: File) {
    // 檢查文件類型
    if (!isImageFile(file)) {
      onError?.({ message: '請選擇圖片文件' });
      return;
    }
    
    // 檢查文件大小
    if (!isFileSizeValid(file, maxSizeMB)) {
      onError?.({ message: `文件大小不能超過 ${maxSizeMB}MB` });
      return;
    }
    
    selectedFile = file;
    
    // 生成預覽
    if (preview) {
      const reader = new FileReader();
      reader.onload = (e) => {
        previewUrl = e.target?.result as string;
      };
      reader.readAsDataURL(file);
    }
    
    onFileSelected?.({ file });
  }
  
  // 上傳文件
  export async function upload() {
    if (!selectedFile) return;
    
    isUploading = true;
    uploadProgress = 0;
    
    try {
      // 模擬上傳進度
      const interval = setInterval(() => {
        uploadProgress += 10;
        if (uploadProgress >= 90) {
          clearInterval(interval);
        }
      }, 100);
      
      onUpload?.({ file: selectedFile });
      
      // 清理
      clearInterval(interval);
      uploadProgress = 100;
      
      setTimeout(() => {
        isUploading = false;
        uploadProgress = 0;
        reset();
      }, 500);
      
    } catch (error) {
      isUploading = false;
      uploadProgress = 0;
      onError?.({ message: '上傳失敗' });
    }
  }
  
  // 上傳文件到後端
  export async function uploadToServer() {
    if (!selectedFile) return;
    
    isUploading = true;
    uploadProgress = 0;
    
    try {
      // 使用實際的上傳 API
      const { apiClient } = await import('$lib/api/client');
      
      // 模擬上傳進度
      const interval = setInterval(() => {
        uploadProgress += 10;
        if (uploadProgress >= 90) {
          clearInterval(interval);
        }
      }, 100);
      
      const result = await apiClient.files.uploadImage(selectedFile);
      
      // 清理
      clearInterval(interval);
      uploadProgress = 100;
      
      onUploaded?.({ 
        file: selectedFile, 
        url: result.url,
        filename: result.filename 
      });
      
      setTimeout(() => {
        isUploading = false;
        uploadProgress = 0;
        reset();
      }, 500);
      
    } catch (error: any) {
      isUploading = false;
      uploadProgress = 0;
      onError?.({ message: '上傳失敗: ' + (error.detail || error.message) });
    }
  }
  
  // 重置
  function reset() {
    selectedFile = null;
    previewUrl = null;
    if (fileInput) {
      fileInput.value = '';
    }
  }
  
  // 移除文件
  function removeFile() {
    reset();
    onFileRemoved?.();
  }
  
  // 打開文件選擇器
  function openFileSelector() {
    if (!disabled) {
      fileInput?.click();
    }
  }
</script>

<div class="image-upload" class:compact class:disabled>
  <!-- 隱藏的文件輸入 -->
  <input
    bind:this={fileInput}
    type="file"
    {accept}
    {multiple}
    {disabled}
    class="hidden"
    onchange={handleFileSelect}
  />
  
  <!-- 上傳區域 -->
  <div
    class="upload-area"
    class:dragging={isDragging}
    class:has-file={selectedFile}
    ondragenter={handleDragEnter}
    ondragover={handleDragOver}
    ondragleave={handleDragLeave}
    ondrop={handleDrop}
    onclick={openFileSelector}
    role="button"
    tabindex="0"
    onkeydown={(e) => e.key === 'Enter' && openFileSelector()}
  >
    {#if selectedFile}
      <!-- 文件預覽 -->
      <div class="file-preview">
        {#if previewUrl}
          <div class="preview-image">
            <img src={previewUrl} alt="Preview" />
            <div class="preview-overlay">
              <Button
                variant="ghost"
                size="sm"
                onclick={(e) => { e.stopPropagation(); removeFile(); }}
                aria-label="移除文件"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </Button>
            </div>
          </div>
        {/if}
        
        <div class="file-info">
          <div class="file-name">{selectedFile.name}</div>
          <div class="file-size">{formatFileSize(selectedFile.size)}</div>
        </div>
      </div>
    {:else}
      <!-- 上傳提示 -->
      <div class="upload-prompt">
        <div class="upload-icon">
          <svg class="w-8 h-8 text-base-content opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
        </div>
        
        {#if !compact}
          <div class="upload-text">
            <p class="upload-primary">點擊或拖拽圖片到此處</p>
            <p class="upload-secondary">
              支援 JPG、PNG、GIF，最大 {maxSizeMB}MB
            </p>
          </div>
        {/if}
      </div>
    {/if}
    
    <!-- 拖拽指示器 -->
    {#if isDragging}
      <div class="drag-indicator">
        <div class="drag-content">
          <svg class="w-12 h-12 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <p class="drag-text">釋放以上傳圖片</p>
        </div>
      </div>
    {/if}
  </div>
  
  <!-- 上傳進度 -->
  {#if isUploading}
    <div class="upload-progress">
      <div class="progress-bar">
        <div class="progress-fill" style="width: {uploadProgress}%"></div>
      </div>
      <div class="progress-text">
        <Loading size="xs" />
        上傳中... {uploadProgress}%
      </div>
    </div>
  {/if}
  
  <!-- 操作按鈕 -->
  {#if selectedFile && !isUploading}
    <div class="upload-actions">
      <Button
        variant="ghost"
        size="sm"
        onclick={removeFile}
      >
        取消
      </Button>
      <Button
        variant="primary"
        size="sm"
        onclick={uploadToServer}
        disabled={disabled}
      >
        上傳
      </Button>
    </div>
  {/if}
</div>

<style>
  .image-upload {
    @apply w-full;
  }
  
  .image-upload.disabled {
    @apply opacity-50 cursor-not-allowed;
  }
  
  .upload-area {
    @apply relative border-2 border-dashed border-base-300 rounded-lg p-6 text-center transition-all duration-200 cursor-pointer hover:border-primary hover:opacity-50 hover:bg-base-200;
  }
  
  .upload-area.dragging {
    @apply border-primary bg-primary opacity-10;
  }
  
  .upload-area.has-file {
    @apply border-solid border-base-200 bg-base-100;
  }
  
  .compact .upload-area {
    @apply p-4;
  }
  
  .upload-prompt {
    @apply flex flex-col items-center space-y-3;
  }
  
  .upload-icon {
    @apply flex-shrink-0;
  }
  
  .upload-text {
    @apply text-center;
  }
  
  .upload-primary {
    @apply text-base-content font-medium;
  }
  
  .upload-secondary {
    @apply text-sm text-base-content opacity-60 mt-1;
  }
  
  .file-preview {
    @apply flex items-center space-x-4;
  }
  
  .preview-image {
    @apply relative flex-shrink-0 w-16 h-16 rounded-lg overflow-hidden bg-base-200;
  }
  
  .preview-image img {
    @apply w-full h-full object-cover;
  }
  
  .preview-overlay {
    @apply absolute inset-0 bg-black opacity-50 flex items-center justify-center opacity-0 transition-opacity duration-200;
  }
  
  .preview-image:hover .preview-overlay {
    @apply opacity-100;
  }
  
  .file-info {
    @apply flex-1 text-left;
  }
  
  .file-name {
    @apply font-medium text-base-content truncate;
  }
  
  .file-size {
    @apply text-sm text-base-content opacity-60;
  }
  
  .drag-indicator {
    @apply absolute inset-0 bg-primary opacity-10 backdrop-blur-sm rounded-lg flex items-center justify-center;
  }
  
  .drag-content {
    @apply flex flex-col items-center space-y-2;
  }
  
  .drag-text {
    @apply text-primary font-medium;
  }
  
  .upload-progress {
    @apply mt-4 space-y-2;
  }
  
  .progress-bar {
    @apply w-full bg-base-200 rounded-full h-2;
  }
  
  .progress-fill {
    @apply h-full bg-primary rounded-full transition-all duration-300;
  }
  
  .progress-text {
    @apply flex items-center justify-center space-x-2 text-sm text-base-content opacity-70;
  }
  
  .upload-actions {
    @apply flex justify-end space-x-2 mt-4;
  }
  
  .hidden {
    @apply sr-only;
  }
</style>