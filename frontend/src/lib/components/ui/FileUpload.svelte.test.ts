// 檔案上傳：選檔與拖放、類型與大小檢查、上傳結果回報，以及上傳中的狀態
import { fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { bffApiClient, type FileUploadData } from '$lib/bff-api-client';
import type { BFFResponse } from '$lib/bff-types';
import FileUpload from './FileUpload.svelte';

function makeFile(name: string, type: string, size = 1024): File {
  const file = new File(['x'], name, { type });
  Object.defineProperty(file, 'size', { value: size });
  return file;
}

const png = (name = 'photo.png', size = 1024) => makeFile(name, 'image/png', size);

const uploaded: BFFResponse<FileUploadData> = {
  success: true,
  data: { file: { url: '/uploads/photo.png', filename: 'photo.png' } } as FileUploadData,
};

function setup(props: Record<string, unknown> = {}) {
  const callbacks = {
    onFilesSelected: vi.fn(),
    onUploaded: vi.fn(),
    onFileRemoved: vi.fn(),
    onAllFilesRemoved: vi.fn(),
    onError: vi.fn(),
  };
  const { container, component } = render(FileUpload, { ...callbacks, ...props });
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  const area = container.querySelector('.upload-area') as HTMLElement;
  const choose = (...files: File[]) => fireEvent.change(input, { target: { files } });
  return { ...callbacks, component, input, area, choose };
}

// 可以控制何時完成的上傳請求
function deferredUpload() {
  let resolve!: (value: BFFResponse<FileUploadData>) => void;
  const upload = vi.spyOn(bffApiClient.files, 'upload').mockImplementation(
    () => new Promise((r) => { resolve = r; }),
  );
  return { upload, finish: (value = uploaded) => resolve(value) };
}

describe('選擇檔案', () => {
  it('顯示檔名、類型與大小，並回報選到的檔案', async () => {
    const { choose, onFilesSelected } = setup({ preview: false });
    const file = png('photo.png', 2048);

    await choose(file);

    expect(screen.getByText('photo.png')).toBeTruthy();
    expect(screen.getByText('圖片')).toBeTruthy();
    expect(screen.getByText('2 KB')).toBeTruthy();
    expect(onFilesSelected).toHaveBeenCalledWith({ files: [file] });
  });

  it('圖片顯示預覽縮圖', async () => {
    const { choose } = setup();

    await choose(png());

    expect((await screen.findByAltText('Preview')).getAttribute('src')).toMatch(/^data:image\/png;base64,/);
  });

  it('不支援的類型不加入列表，並說明原因', async () => {
    const { choose, onError, onFilesSelected } = setup();

    await choose(makeFile('setup.exe', 'application/x-msdownload'));

    expect(onError).toHaveBeenCalledWith({ message: '檔案 "setup.exe" 不是支援的類型。支援：圖片、文檔、影片、音檔' });
    expect(onFilesSelected).not.toHaveBeenCalled();
    expect(screen.queryByText('setup.exe')).toBeNull();
  });

  it('只允許部分類型時，說明可上傳的類型並拒絕其他類型', async () => {
    const { choose, onError } = setup({ allowedTypes: ['image', 'audio'] });
    expect(screen.getByText('支援圖片、音檔')).toBeTruthy();

    await choose(makeFile('report.pdf', 'application/pdf'));

    // 類型以中文說明，不顯示內部代碼（image、audio）
    expect(onError).toHaveBeenCalledWith({ message: '檔案 "report.pdf" 不是支援的類型。支援：圖片、音檔' });
    expect(screen.queryByText('report.pdf')).toBeNull();
  });

  it('超過該類型的大小上限時不加入，並說明上限', async () => {
    const { choose, onError, onFilesSelected } = setup();

    await choose(png('huge.png', 10 * 1024 * 1024 + 1));

    expect(onError).toHaveBeenCalledWith({ message: '檔案 "huge.png" 超過大小限制 10MB' });
    expect(onFilesSelected).not.toHaveBeenCalled();
  });

  it('單檔模式再選一次會取代原本的檔案', async () => {
    const { choose } = setup({ preview: false });

    await choose(png('a.png'));
    await choose(png('b.png'));

    expect(screen.queryByText('a.png')).toBeNull();
    expect(screen.getByText('b.png')).toBeTruthy();
    expect(screen.getByRole('button', { name: '上傳 (1)' })).toBeTruthy();
  });

  it('點擊上傳區開啟檔案選擇，停用時不開啟', async () => {
    const enabled = setup();
    const openPicker = vi.spyOn(enabled.input, 'click').mockImplementation(() => {});
    await fireEvent.click(enabled.area);
    await fireEvent.keyDown(enabled.area, { key: 'Enter' });
    expect(openPicker).toHaveBeenCalledTimes(2);

    const disabled = setup({ disabled: true });
    const blocked = vi.spyOn(disabled.input, 'click').mockImplementation(() => {});
    await fireEvent.click(disabled.area);
    expect(blocked).not.toHaveBeenCalled();
  });
});

describe('拖放', () => {
  it('拖入時提示放開，放下後加入檔案', async () => {
    const { area, onFilesSelected } = setup({ preview: false });
    const file = png();

    await fireEvent.dragEnter(area);
    expect(screen.getByText('釋放以上傳檔案')).toBeTruthy();
    await fireEvent.drop(area, { dataTransfer: { files: [file] } });

    expect(screen.queryByText('釋放以上傳檔案')).toBeNull();
    expect(screen.getByText('photo.png')).toBeTruthy();
    expect(onFilesSelected).toHaveBeenCalledWith({ files: [file] });
  });

  it('拖到子元素再離開不會提早收起提示，完全離開才收起', async () => {
    const { area } = setup();

    await fireEvent.dragEnter(area);
    await fireEvent.dragEnter(area);
    await fireEvent.dragLeave(area);
    expect(screen.getByText('釋放以上傳檔案')).toBeTruthy();

    await fireEvent.dragLeave(area);
    expect(screen.queryByText('釋放以上傳檔案')).toBeNull();
  });

  it('停用時不接受拖放', async () => {
    const { area, onFilesSelected } = setup({ disabled: true });

    await fireEvent.dragEnter(area);
    await fireEvent.drop(area, { dataTransfer: { files: [png()] } });

    expect(screen.queryByText('釋放以上傳檔案')).toBeNull();
    expect(onFilesSelected).not.toHaveBeenCalled();
  });
});

describe('上傳', () => {
  it('按上傳後依檔案類型呼叫 API，回報檔案與結果', async () => {
    const upload = vi.spyOn(bffApiClient.files, 'upload').mockResolvedValue(uploaded);
    const { choose, onUploaded } = setup({ preview: false });
    const file = png();

    await choose(file);
    await fireEvent.click(screen.getByRole('button', { name: '上傳 (1)' }));

    await waitFor(() => expect(onUploaded).toHaveBeenCalledOnce());
    expect(upload).toHaveBeenCalledWith(file, 'image');
    expect(onUploaded).toHaveBeenCalledWith({ files: [file], results: [{ file, result: uploaded }] });
  });

  it('上傳中顯示進度並隱藏操作按鈕', async () => {
    const { finish } = deferredUpload();
    const { choose, onUploaded } = setup({ preview: false });

    await choose(png());
    await fireEvent.click(screen.getByRole('button', { name: '上傳 (1)' }));

    expect(await screen.findByText(/上傳中\.\.\. 50%/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: '上傳 (1)' })).toBeNull();
    expect(screen.queryByRole('button', { name: '清除全部' })).toBeNull();

    finish();
    await waitFor(() => expect(onUploaded).toHaveBeenCalledOnce());
  });

  it('自動上傳：選檔後直接上傳，完成後清空等待下一個檔案', async () => {
    const upload = vi.spyOn(bffApiClient.files, 'upload').mockResolvedValue(uploaded);
    const { choose, onUploaded } = setup({ autoUpload: true, preview: false });

    await choose(png());

    await waitFor(() => expect(onUploaded).toHaveBeenCalledOnce());
    expect(upload).toHaveBeenCalledOnce();
    await waitFor(() => expect(screen.queryByText('photo.png')).toBeNull());
    expect(screen.getByText('點擊或拖拽檔案到此處')).toBeTruthy();
  });

  it('BFF 回傳錯誤時歸入該檔案的 error，不丟出例外', async () => {
    const error = { code: 'HTTP_ERROR', message: 'HTTP 413: Payload Too Large' };
    vi.spyOn(bffApiClient.files, 'upload').mockResolvedValue({ success: false, error });
    const { choose, onUploaded, onError } = setup({ autoUpload: true, preview: false });
    const file = png();

    await choose(file);

    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith({ files: [file], results: [{ file, error }] }));
    expect(onError).not.toHaveBeenCalled();
  });

  it('網路錯誤同樣歸入該檔案的 error', async () => {
    const networkError = new TypeError('Failed to fetch');
    vi.spyOn(bffApiClient.files, 'upload').mockRejectedValue(networkError);
    const { choose, onUploaded } = setup({ autoUpload: true, preview: false });
    const file = png();

    await choose(file);

    await waitFor(() =>
      expect(onUploaded).toHaveBeenCalledWith({ files: [file], results: [{ file, error: networkError }] }),
    );
  });

  // 目前無法中途取消上傳：若上傳中還能按移除，檔案從畫面消失，上傳完成後卻照樣回報（訊息照樣送出）
  it('上傳中不能移除檔案', async () => {
    const { upload, finish } = deferredUpload();
    const { choose, onUploaded } = setup({ autoUpload: true, preview: false });
    const file = png();

    await choose(file);
    await waitFor(() => expect(upload).toHaveBeenCalledOnce());

    const remove = screen.getByRole('button', { name: '移除檔案' }) as HTMLButtonElement;
    expect(remove.disabled).toBe(true);
    expect(screen.getByText('photo.png')).toBeTruthy();
    finish();
    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith({ files: [file], results: [{ file, result: uploaded }] }));
  });

  // 上傳中再加入的檔案若照收，會跟著另外上傳一次（自動上傳時兩個都送出）
  it('上傳中不接受新的檔案（選檔、拖放、貼上），說明原因且不另外上傳', async () => {
    const { upload, finish } = deferredUpload();
    const { choose, area, input, component, onUploaded, onError } = setup({ autoUpload: true, preview: false });
    const first = png('first.png');
    await choose(first);
    await waitFor(() => expect(upload).toHaveBeenCalledOnce());

    expect(input.disabled).toBe(true);
    await choose(png('second.png'));
    await fireEvent.drop(area, { dataTransfer: { files: [png('third.png')] } });
    component.processFiles([png('pasted.png')]); // 貼上圖片由外層直接呼叫

    expect(onError).toHaveBeenCalledTimes(3);
    expect(onError).toHaveBeenLastCalledWith({ message: '檔案上傳中，請稍候再加入其他檔案' });
    expect(screen.queryByText('second.png')).toBeNull();
    expect(screen.queryByText('third.png')).toBeNull();
    finish();
    await waitFor(() => expect(onUploaded).toHaveBeenCalledOnce());
    expect(upload).toHaveBeenCalledOnce();
    expect(onUploaded).toHaveBeenCalledWith({ files: [first], results: [{ file: first, result: uploaded }] });
  });
});

describe('多檔', () => {
  it('移除單一檔案與清除全部', async () => {
    const { choose, onFileRemoved, onAllFilesRemoved } = setup({ multiple: true, preview: false });
    const first = png('a.png');
    const second = makeFile('notes.txt', 'text/plain');

    await choose(first, second);
    const [firstRow] = screen.getAllByText(/a\.png|notes\.txt/).map((el) => el.closest('.file-item') as HTMLElement);
    await fireEvent.click(within(firstRow!).getByRole('button', { name: '移除檔案' }));

    expect(onFileRemoved).toHaveBeenCalledWith({ file: first });
    expect(screen.queryByText('a.png')).toBeNull();
    expect(screen.getByRole('button', { name: '上傳 (1)' })).toBeTruthy();

    await fireEvent.click(screen.getByRole('button', { name: '清除全部' }));
    expect(onAllFilesRemoved).toHaveBeenCalledOnce();
    expect(screen.queryByText('notes.txt')).toBeNull();
  });

  // 例如兩次貼上的截圖都叫 image.png
  it('先後加入同名的不同檔案時兩個都保留', async () => {
    const { choose } = setup({ multiple: true, preview: false });

    await choose(png('image.png', 100));
    await choose(png('image.png', 200));

    expect(screen.getAllByText('image.png')).toHaveLength(2);
    expect(screen.getByRole('button', { name: '上傳 (2)' })).toBeTruthy();
  });
});
