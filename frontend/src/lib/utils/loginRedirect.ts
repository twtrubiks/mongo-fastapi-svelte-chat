// 登入後回到原頁面：未登入時把原路徑帶在 /login?redirect= 上，登入成功後導回去。
// 只接受站內 /app 底下的路徑，避免 open redirect（例如 ?redirect=//evil.com）

// 只用來把相對路徑解析成 URL 以比對 origin，不會實際連線
const PARSE_BASE = 'http://localhost';

// 驗證 redirect 參數：合法回傳正規化後的站內路徑，否則回傳 null
export function safeReturnPath(raw: string | null | undefined): string | null {
  if (!raw || !raw.startsWith('/')) return null;

  let url: URL;
  try {
    url = new URL(raw, PARSE_BASE);
  } catch {
    return null;
  }

  // //evil.com、/\evil.com 會被解析成其他 host
  if (url.origin !== PARSE_BASE) return null;
  if (url.pathname !== '/app' && !url.pathname.startsWith('/app/')) return null;

  return url.pathname + url.search + url.hash;
}

// 導向登入頁的網址；returnTo 不是可回去的頁面時就不帶 redirect
export function loginUrl(returnTo: string): string {
  const target = safeReturnPath(returnTo);
  return target ? `/login?redirect=${encodeURIComponent(target)}` : '/login';
}
