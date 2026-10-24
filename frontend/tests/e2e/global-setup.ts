// 先確認後端已啟動且連上 MongoDB / Redis，否則每個測試都會在註冊時才失敗
export default async function globalSetup() {
  const backend = process.env['BACKEND_URL'] ?? 'http://localhost:8000';
  let status: string | undefined;
  try {
    const res = await fetch(`${backend}/health`);
    const body = (await res.json()) as { infrastructure?: { status?: string } };
    status = body.infrastructure?.status;
  } catch {
    status = undefined;
  }
  if (status !== 'healthy') {
    throw new Error(`後端 ${backend} 未啟動，或尚未連上 MongoDB / Redis（見 tests/e2e/README.md）`);
  }
}
