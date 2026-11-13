import { defineConfig } from 'vite';
export default defineConfig({
  root: 'frontend', base: '/static/clientes-app/',
  build: { outDir: '../static/clientes-app', emptyOutDir: true, manifest: true, rolldownOptions: { onwarn(warning, handler) { if (warning.code !== "MODULE_LEVEL_DIRECTIVE") handler(warning); }, output: { codeSplitting: { groups: [{ name: "antd", test: /node_modules\/(antd|@ant-design|@rc-component)/ }, { name: "react", test: /node_modules\/(react|react-dom|react-router|scheduler)/ }] } } } },
  server: { host: '127.0.0.1', port: 5173, strictPort: true, proxy: {
    '/financeiro/api': 'http://127.0.0.1:8000', '/contabil/api': 'http://127.0.0.1:8000', '/compras/api': 'http://127.0.0.1:8000', '/servico/api': 'http://127.0.0.1:8000', '/agenda/api': 'http://127.0.0.1:8000', '/chave/api': 'http://127.0.0.1:8000', '/empresa/api': 'http://127.0.0.1:8000', '/configambiente/api': 'http://127.0.0.1:8000', '/recadclientes/api': 'http://127.0.0.1:8000', '/dashboard/api': 'http://127.0.0.1:8000', '/usuario/api': 'http://127.0.0.1:8000', '/conta/api': 'http://127.0.0.1:8000', '/notas/api': 'http://127.0.0.1:8000', '/contratos/api': 'http://127.0.0.1:8000', '/produtos/api': 'http://127.0.0.1:8000', '/clientes/api': 'http://127.0.0.1:8000', '/clientes/retorna_cep': 'http://127.0.0.1:8000',
  } },
});
