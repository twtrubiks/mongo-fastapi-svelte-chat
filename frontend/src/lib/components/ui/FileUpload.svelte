<script lang="ts">
  import { Button, Loading } from '$lib/components/ui';
  import { 
    formatFileSize, 
    isSupportedFileType, 
    isFileSizeValid, 
    getFileIcon, 
    getFileTypeLabel, 
    getMaxFileSize, 
    getAcceptString,
    getFileType 
  } from '$lib/utils';
  
  interface Props {
    allowedTypes?: string[] | undefined; // ['image', 'document', 'video', 'audio'] 或 undefined 為全部
    multiple?: boolean;
    disabled?: boolean;
    preview?: boolean;
    dragDrop?: boolean;
    compact?: boolean;
    autoUpload?: boolean; // 自動上傳
    onFilesSelected?: (data: { files: File[] }) => void;
    onUploaded?: (data: { files: File[]; results: any[] }) => void;
    onFileRemoved?: (data: { file: File }) => void;
    onAllFilesRemoved?: () => void;
    onError?: (data: { message: string }) => void;
  }
  
  let {
    allowedTypes = undefined,
    multiple = false,
    disabled = false,
    preview = true,
    dragDrop = true,
    compact = false,
    autoUpload = false,
    onFilesSelected,
    onUploaded,
    onFileRemoved,
    onAllFilesRemoved,
    onError
  }: Props = $props();
  
  // 狀態
  let fileInput: HTMLInputElement = $state(null!);
  let isDragging = $state(false);
  let dragCounter = $state(0);
  let isUploading = $state(false);
  let uploadProgress = $state(0);
  let selectedFiles = $state<File[]>([]);
  let previewUrls = $state<Map<File, string>>(new Map());
  
  // 計算接受的檔案類型
  let accept = $derived(getAcceptString(allowedTypes));
  
  // 處理檔案選擇
  function handleFileSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    const files = input.files;
    
    if (files && files.length > 0) {
      const fileArray = Array.from(files);
      if (multiple) {
        processFiles(fileArray);
      } else {
        processFiles([fileArray[0]]);
      }
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
      const fileArray = Array.from(files);
      if (multiple) {
        processFiles(fileArray);
      } else {
        processFiles([fileArray[0]]);
      }
    }
  }
  
  // 處理檔案
  export function processFiles(files: File[]) {
    const validFiles: File[] = [];
    const errors: string[] = [];
    
    for (const file of files) {
      // 檢查檔案類型
      if (!isSupportedFileType(file, allowedTypes)) {
        const supportedTypes = allowedTypes?.map(type => type).join('、') || '所有支援的類型';
        errors.push(`檔案 "${file.name}" 不是支援的類型。支援：${supportedTypes}`);
        continue;
      }
      
      // 檢查檔案大小
      if (!isFileSizeValid(file)) {
        const maxSize = getMaxFileSize(file);
        errors.push(`檔案 "${file.name}" 超過大小限制 ${maxSize}MB`);
        continue;
      }
      
      validFiles.push(file);
    }
    
    // 顯示錯誤
    if (errors.length > 0) {
      onError?.({ message: errors.join('\n') });
    }
    
    // 處理有效檔案
    if (validFiles.length > 0) {
      if (multiple) {
        selectedFiles = [...selectedFiles, ...validFiles];
      } else {
        selectedFiles = [validFiles[0]];
        previewUrls.clear();
      }
      
      // 生成預覽
      if (preview) {
        for (const file of validFiles) {
          generatePreview(file);
        }
      }
      
      onFilesSelected?.({ files: validFiles });
      
      // 自動上傳
      if (autoUpload) {
        uploadToServer();
      }
    }
  }
  
  // 生成預覽
  function generatePreview(file: File) {
    const fileType = getFileType(file);
    
    if (fileType === 'image') {
      const reader = new FileReader();
      reader.onload = (e) => {
        previewUrls.set(file, e.target?.result as string);
        previewUrls = new Map(previewUrls);
      };
      reader.readAsDataURL(file);
    }
  }
  
  // 上傳檔案到後端
  export async function uploadToServer() {
    if (selectedFiles.length === 0) return;
    
    isUploading = true;
    uploadProgress = 0;
    
    try {
      const { bffApiClient } = await import('$lib/bff-api-client');
      const uploadResults = [];
      
      for (let i = 0; i < selectedFiles.length; i++) {
        const file = selectedFiles[i];
        const fileType = getFileType(file);
        
        // 更新進度
        uploadProgress = Math.round(((i + 0.5) / selectedFiles.length) * 100);
        
        try {
          const result = await bffApiClient.files.upload(file, fileType);
          uploadResults.push({ file, result });
        } catch (error) {
          uploadResults.push({ file, error });
        }
      }
      
      uploadProgress = 100;
      
      onUploaded?.({ 
        files: selectedFiles,
        results: uploadResults
      });
      
      setTimeout(() => {
        isUploading = false;
        uploadProgress = 0;
        if (!multiple) {
          reset();
        }
      }, 500);
      
    } catch (error: any) {
      isUploading = false;
      uploadProgress = 0;
      onError?.({ message: '上傳失敗: ' + (error.detail || error.message) });
    }
  }
  
  // 重置
  function reset() {
    selectedFiles = [];
    previewUrls.clear();
    previewUrls = new Map();
    if (fileInput) {
      fileInput.value = '';
    }
  }
  
  // 移除單個檔案
  function removeFile(file: File) {
    selectedFiles = selectedFiles.filter(f => f !== file);
    previewUrls.delete(file);
    previewUrls = new Map(previewUrls);
    onFileRemoved?.({ file });
  }
  
  // 移除所有檔案
  function removeAllFiles() {
    reset();
    onAllFilesRemoved?.();
  }
  
  // 打開檔案選擇器
  function openFileSelector() {
    if (!disabled) {
      fileInput?.click();
    }
  }
  
  // 獲取支援的檔案類型描述
  function getSupportedTypesDescription(): string {
    if (!allowedTypes || allowedTypes.includes('general')) {
      return '支援圖片、文檔、影片、音檔';
    }
    
    const typeLabels = allowedTypes.map(type => {
      switch (type) {
        case 'image': return '圖片';
        case 'document': return '文檔';
        case 'video': return '影片';
        case 'audio': return '音檔';
        default: return type;
      }
    });
    
    return `支援 ${typeLabels.join('、')}`;
  }
</script>

<div class="file-upload" class:compact class:disabled>
  <!-- 隱藏的檔案輸入 -->
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
    class:has-files={selectedFiles.length > 0}
    ondragenter={handleDragEnter}
    ondragover={handleDragOver}
    ondragleave={handleDragLeave}
    ondrop={handleDrop}
    onclick={openFileSelector}
    role="button"
    tabindex="0"
    onkeydown={(e) => e.key === 'Enter' && openFileSelector()}
  >
    {#if selectedFiles.length > 0}
      <!-- 檔案預覽列表 -->
      <div class="files-preview">
        {#each selectedFiles as file}
          <div class="file-item">
            <div class="file-preview">
              {#if previewUrls.has(file)}
                <!-- 圖片預覽 -->
                <div class="preview-image">
                  <img src={previewUrls.get(file)} alt="Preview" />
                </div>
              {:else}
                <!-- 檔案圖示 -->
                <div class="file-icon">
                  <span class="icon-emoji">{getFileIcon(file)}</span>
                </div>
              {/if}
            </div>
            
            <div class="file-info">
              <div class="file-name" title={file.name}>{file.name}</div>
              <div class="file-details">
                <span class="file-type">{getFileTypeLabel(file)}</span>
                <span class="file-size">{formatFileSize(file.size)}</span>
              </div>
            </div>
            
            <Button
              variant="ghost"
              size="sm"
              onclick={(e) => { e.stopPropagation(); removeFile(file); }}
              aria-label="移除檔案"
              class="remove-btn"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </Button>
          </div>
        {/each}
      </div>
    {:else}
      <!-- 上傳提示 -->
      <div class="upload-prompt">
        <div class="upload-icon">
          <svg class="w-10 h-10 text-base-content opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>
        
        {#if !compact}
          <div class="upload-text">
            <p class="upload-primary">點擊或拖拽檔案到此處</p>
            <p class="upload-secondary">
              {getSupportedTypesDescription()}
            </p>
          </div>
        {/if}
      </div>
    {/if}
    
    <!-- 拖拽指示器 -->
    {#if isDragging}
      <div class="drag-indicator">
        <div class="drag-content">
          <svg class="w-16 h-16 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <p class="drag-text">釋放以上傳檔案</p>
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
  {#if selectedFiles.length > 0 && !isUploading}
    <div class="upload-actions">
      <Button
        variant="ghost"
        size="sm"
        onclick={removeAllFiles}
        disabled={disabled}
      >
        清除全部
      </Button>
      <Button
        variant="primary"
        size="sm"
        onclick={uploadToServer}
        disabled={disabled}
      >
        上傳 ({selectedFiles.length})
      </Button>
    </div>
  {/if}
</div>

<style>
  .file-upload {
    @apply w-full;
  }
  
  .file-upload.disabled {
    @apply opacity-50 cursor-not-allowed;
  }
  
  .upload-area {
    @apply relative border-2 border-dashed border-base-300 rounded-lg p-6 text-center transition-all duration-200 cursor-pointer hover:border-primary hover:bg-base-200;
  }
  
  .upload-area.dragging {
    @apply border-primary bg-primary bg-opacity-10;
  }
  
  .upload-area.has-files {
    @apply border-solid border-base-200 bg-base-100 cursor-default hover:bg-base-100;
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
  
  /* 檔案預覽列表 */
  .files-preview {
    @apply space-y-2 max-h-96 overflow-y-auto;
  }
  
  .file-item {
    @apply flex items-center p-3 bg-base-100 border border-base-200 rounded-lg hover:bg-base-200 transition-colors;
  }
  
  .file-preview {
    @apply flex-shrink-0 mr-3;
  }
  
  .preview-image {
    @apply w-12 h-12 rounded-lg overflow-hidden bg-base-200;
  }
  
  .preview-image img {
    @apply w-full h-full object-cover;
  }
  
  .file-icon {
    @apply w-12 h-12 flex items-center justify-center bg-base-200 rounded-lg;
  }
  
  .icon-emoji {
    @apply text-2xl;
  }
  
  .file-info {
    @apply flex-1 min-w-0;
  }
  
  .file-name {
    @apply font-medium text-base-content truncate;
  }
  
  .file-details {
    @apply flex items-center space-x-2 text-sm text-base-content opacity-60 mt-1;
  }
  
  .file-type {
    @apply inline-block;
  }
  
  .file-size {
    @apply inline-block;
  }
  
  .remove-btn {
    @apply flex-shrink-0 ml-2 opacity-70 hover:opacity-100;
  }
  
  /* 拖拽指示器 */
  .drag-indicator {
    @apply absolute inset-0 bg-primary bg-opacity-10 backdrop-blur-sm rounded-lg flex items-center justify-center z-10;
  }
  
  .drag-content {
    @apply flex flex-col items-center space-y-3;
  }
  
  .drag-text {
    @apply text-primary font-medium text-lg;
  }
  
  /* 上傳進度 */
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
  
  /* 操作按鈕 */
  .upload-actions {
    @apply flex justify-end space-x-2 mt-4;
  }
  
  .hidden {
    @apply sr-only;
  }
</style>