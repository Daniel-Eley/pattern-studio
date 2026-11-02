export async function api(path, options = {}) {
  const token = document.cookie.split('; ').find(c => c.startsWith('csrftoken='))?.split('=')[1];
  const response = await fetch(`/api/${path}`, {
    credentials: 'same-origin', ...options,
    headers: { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), 'X-CSRFToken': token || '', ...options.headers },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status}). Refresh the page and try again.`);
  return data;
}
