import { redirect } from '@sveltejs/kit';
import { clearAuthCookies } from '$lib/bff-cookie';

/** @type {import('./$types').LayoutServerLoad} */
export async function load({ cookies, fetch }) {
  const token = cookies.get('auth_token');

  if (token) {
    try {
      const response = await fetch('/api/auth/me');

      if (response.ok) {
        throw redirect(302, '/app');
      } else {
        clearAuthCookies(cookies);
      }
    } catch (error) {
      if (error && typeof error === 'object' && 'status' in error && 'location' in error) {
        throw error;
      }
      clearAuthCookies(cookies);
    }
  }

  return {};
}