import { redirect } from '@sveltejs/kit';

/** @type {import('./$types').PageServerLoad} */
export async function load({ cookies, fetch, parent }) {
  // 獲取父 layout 的數據
  const { user, token } = await parent();
  
  try {
    // 載入聊天室列表
    const roomsResponse = await fetch('/api/rooms', {
      headers: {
        'Cookie': `auth_token=${token}`
      }
    });
    
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
  } catch (error) {
    return {
      rooms: [],
      error: '載入聊天室時發生錯誤',
      user
    };
  }
}