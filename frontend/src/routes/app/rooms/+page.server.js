/** @type {import('./$types').PageServerLoad} */
export async function load({ fetch, parent }) {
  // 獲取父 layout 的數據（不再包含 token）
  const { user } = await parent();

  try {
    // 載入聊天室列表（httpOnly cookie 自動隨 fetch 送出）
    const roomsResponse = await fetch('/api/rooms');

    if (!roomsResponse.ok) {
      return {
        rooms: [],
        error: '載入聊天室失敗',
        user
      };
    }

    const roomsData = await roomsResponse.json();

    return {
      rooms: roomsData.data || [],
      error: null,
      user
    };
  } catch {
    return {
      rooms: [],
      error: '載入聊天室時發生錯誤',
      user
    };
  }
}
