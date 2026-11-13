import { beforeEach, describe, expect, it, vi } from 'vitest';

let client: typeof import('../src/api');
let fetchMock: ReturnType<typeof vi.fn>;
const response = (status: number, data: unknown = {}) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
beforeEach(async () => { vi.resetModules(); fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock); client = await import('../src/api'); });
async function signIn() { fetchMock.mockResolvedValueOnce(response(200, { csrfToken: 'csrf' })).mockResolvedValueOnce(response(200, { access: 'access-old' })); await client.login('user', 'secret'); fetchMock.mockReset(); }
describe('cliente HTTP autenticado', () => {
  it('renova uma única vez para requisições concorrentes e repete com o token novo', async () => {
    await signIn();
    fetchMock.mockImplementation(async (url: string, options: RequestInit) => {
      if (url.endsWith('/refresh/')) { await new Promise(resolve => setTimeout(resolve, 10)); return response(200, { access: 'access-new' }); }
      return new Headers(options.headers).get('Authorization') === 'Bearer access-new' ? response(200, { ok: true }) : response(401);
    });
    const results = await Promise.all([client.api('/data', {}, 1), client.api('/data', {}, 1)]);
    expect(results).toEqual([{ ok: true }, { ok: true }]);
    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith('/refresh/'))).toHaveLength(1);
    expect(new Headers(fetchMock.mock.calls.at(-1)![1].headers).get('X-Empresa-ID')).toBe('1');
  });
  it('encerra a sessão quando o refresh é inválido, sem entrar em loop', async () => {
    await signIn(); const expired = vi.fn(); client.setSessionExpiredHandler(expired);
    fetchMock.mockResolvedValue(response(401, { code: 'token_not_valid' }));
    await expect(client.api('/data')).rejects.toBeInstanceOf(client.ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(2); expect(expired).toHaveBeenCalledTimes(1);
  });
  it('não renova tokens para falta de permissão ou falhas do servidor', async () => {
    await signIn();
    fetchMock.mockResolvedValueOnce(response(403)).mockResolvedValueOnce(response(500));
    await expect(client.api('/data')).rejects.toMatchObject({ status: 403 });
    await expect(client.api('/data')).rejects.toMatchObject({ status: 500 });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
  it('preserva a sessão em uma falha temporária na renovação', async () => {
    await signIn(); const expired = vi.fn(); client.setSessionExpiredHandler(expired);
    fetchMock.mockResolvedValueOnce(response(401)).mockRejectedValueOnce(new TypeError('offline'));
    await expect(client.api('/data')).rejects.toThrow('offline');
    expect(expired).not.toHaveBeenCalled();
  });
});


describe('CSRF e recuperação de acesso', () => {
  it('acompanha a rotação do CSRF no login e na renovação', async () => {
    fetchMock.mockResolvedValueOnce(response(200, { csrfToken: 'csrf-inicial' })).mockResolvedValueOnce(response(200, { access: 'access', csrfToken: 'csrf-login' }));
    await client.login('user', 'test-password'); fetchMock.mockReset();
    fetchMock.mockResolvedValueOnce(response(200, { access: 'renovado', csrfToken: 'csrf-renovado' }));
    await client.refreshSession();
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get('X-CSRFToken')).toBe('csrf-login');
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    await client.logout();
    expect(new Headers(fetchMock.mock.calls[1][1].headers).get('X-CSRFToken')).toBe('csrf-renovado');
  });
  it('recuperação solicita CSRF atual e não envia access token', async () => {
    await signIn();
    fetchMock.mockResolvedValueOnce(response(200, { csrfToken: 'csrf-recuperacao' })).mockResolvedValueOnce(response(200, { detail: 'Resposta genérica.' }));
    await client.publicUserPost('/usuario/api/recuperacao/solicitar/', { username: 'user', email: 'user@example.test' });
    const headers = new Headers(fetchMock.mock.calls[1][1].headers);
    expect(headers.get('X-CSRFToken')).toBe('csrf-recuperacao'); expect(headers.has('Authorization')).toBe(false);
  });
});
