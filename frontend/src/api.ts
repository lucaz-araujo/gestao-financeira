const AUTH = '/clientes/api/auth/';
let access: string | null = null;
let generation = 0;
let refreshFlight: Promise<void> | null = null;
let csrfToken = '';
let onSessionExpired = () => {};
export function setSessionExpiredHandler(handler: () => void) { onSessionExpired = handler; }
export function clearAccess() { access = null; generation++; }
export class ApiError extends Error {
  constructor(public status: number, public data: Record<string, unknown>) {
    super(typeof data.detail === 'string' ? data.detail : 'Não foi possível concluir a solicitação.');
  }
}
async function decode(response: Response) {
  const data = response.status === 204 ? null : await response.json().catch(() => ({ detail: 'Resposta inválida do servidor.' }));
  if (!response.ok) throw new ApiError(response.status, data ?? {});
  return data;
}
export async function ensureCsrf() {
  const data = await decode(await fetch(AUTH + 'csrf/', { credentials: 'same-origin' }));
  csrfToken = data.csrfToken;
}
async function authPost(path: string, body = {}) {
  if (!csrfToken) await ensureCsrf();
  const data = await decode(await fetch(AUTH + path + '/', { method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken }, body: JSON.stringify(body) }));
  if (data?.csrfToken) csrfToken = data.csrfToken;
  return data;
}
export async function login(username: string, password: string) {
  await ensureCsrf();
  const data = await authPost('login', { username, password });
  access = data.access; generation++;
}
export async function refreshSession() {
  if (!refreshFlight) {
    const current = generation;
    refreshFlight = authPost('refresh').then(data => {
      if (generation === current) access = data.access;
    }).finally(() => { refreshFlight = null; });
  }
  return refreshFlight;
}
export async function logout() {
  // Invalida renovações em andamento antes de limpar o cookie no servidor.
  clearAccess();
  await refreshFlight?.catch(() => {});
  await authPost('logout');
}
export async function api<T>(path: string, options: RequestInit = {}, empresa?: number, retry = true): Promise<T> {
  const token = access;
  const headers = new Headers(options.headers);
  if (access) headers.set('Authorization', 'Bearer ' + access);
  if (empresa) headers.set('X-Empresa-ID', String(empresa));
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const response = await fetch(path, { ...options, headers, credentials: 'same-origin' });
  if (response.status === 401 && retry) {
    // Uma requisição que terminou após outra renovar usa o novo token sem renovar de novo.
    try { if (token === access) await refreshSession(); }
    catch (error) {
      if (error instanceof ApiError && error.status === 401) { clearAccess(); onSessionExpired(); }
      throw error;
    }
    return api<T>(path, options, empresa, false);
  }
  if (response.status === 401) { clearAccess(); onSessionExpired(); }
  return decode(response);
}
export function errorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 403) return error.message === 'Não foi possível concluir a solicitação.' ? 'Você não tem permissão para esta operação.' : error.message;
    if (error.status === 401) return 'Sua sessão expirou. Entre novamente.';
    if (error.status === 429) return 'Muitas tentativas. Aguarde um minuto para tentar novamente.';
    if (error.status >= 500) return 'O servidor está indisponível. Tente novamente em instantes.';
    const messages = Object.values(error.data).flat().filter(x => typeof x === 'string');
    return messages.join(' ') || error.message;
  }
  return 'Não foi possível acessar o servidor. Verifique sua conexão e tente novamente.';
}

export async function publicUserPost(path: string, body: Record<string, unknown>) {
  await ensureCsrf();
  return decode(await fetch(path, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken }, body: JSON.stringify(body) }));
}
