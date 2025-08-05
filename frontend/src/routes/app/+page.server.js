import { redirect } from '@sveltejs/kit';

/** @type {import('./$types').PageServerLoad} */
export async function load({ cookies, url }) {
  // 檢查是否有 auth token
  const token = cookies.get('auth_token');
  
  if (!token) {
    throw redirect(302, '/login');
  }
  
  // 重定向到聊天室列表
  throw redirect(302, '/app/rooms');
}