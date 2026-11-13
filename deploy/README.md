# Publicação e pendências operacionais

O ambiente atual continua local. Os arquivos deste diretório são modelos revisáveis; não foram instalados em `/etc`, não houve emissão fiscal ou envio de e-mail, nem alteração dos dados de negócio. Não publicar com `runserver`.

## Ativação de produção

1. Definir o domínio real e apontar o DNS para o servidor. Providenciar o certificado HTTPS desse domínio.
2. Copiar `production.env.example` para arquivo privado fora do Git, modo 0600. Preencher domínio, URL HTTPS, login restrito do PostgreSQL e segredo de integração contratado com os consumidores. Configurar SMTP/remetente reais. O modelo contém placeholders e não serve como configuração ativa.
3. Ativar `DJANGO_SETTINGS_MODULE=layCliente.production` e `DJANGO_ENV_FILE=/caminho/privado/production.env`. O perfil recusa domínio ausente, wildcard, URL fora dos hosts, segredo padrão e login administrativo do banco. Impõe DEBUG falso, HTTPS, cookies seguros e HSTS inicial de uma hora. A operação local mantém HTTP e DEBUG próprios de desenvolvimento, com hosts limitados a localhost por padrão.
4. Usar os modelos Gunicorn/systemd e Nginx, substituindo todos os caminhos, usuário e domínio. Gunicorn deve ouvir somente `127.0.0.1:8001`. O Nginx termina TLS, sobrescreve `X-Real-IP`/`X-Forwarded-Proto` e limita tentativas nos endpoints de autenticação, inclusive `/admin/login/`. Só habilitar `TRUST_PROXY_HTTPS` com esse isolamento. Ajustar `TRUSTED_PROXY_IPS` se o proxy não usar loopback. Não expor o backend à internet.
5. Gerar os estáticos com `manage.py collectstatic --noinput` sob o perfil de produção; executar `manage.py check --deploy` e `gunicorn --check-config layCliente.wsgi:application`. Conferir a configuração efetiva com `nginx -t` no servidor, antes de iniciar/recarregar o serviço. O template Nginx não foi validado contra domínio/certificados reais, que ainda não foram fornecidos.
6. Conferir cookies, login, empresa, upload de avatar, estáticos e acesso direto a rotas pelo domínio HTTPS real. O perfil inicial mantém `SECURE_HSTS_INCLUDE_SUBDOMAINS=False` e `SECURE_HSTS_PRELOAD=False`; por isso Django informa W005/W021. Não suprimir esses avisos nem habilitar as opções antes de verificar o HTTPS de todos os subdomínios e os efeitos do preload. Aumentar a duração do HSTS após validar a publicação.

O cache de produção padrão usa arquivos privados compartilhados pelos processos no mesmo servidor. Se houver vários servidores, configurar `CACHE_URL` com Redis e instalar a dependência `redis` em todos; o limite Nginx também deve estar no ponto de entrada compartilhado. Não usar cache em memória como limite único de autenticação em vários processos. Os aliases JWT agora compartilham o limite de login React (10/min/IP) e o refresh tem limite independente de 60/min/IP. O DRF ignora X-Forwarded-For não confiável; o middleware só aplica o IP do proxy explicitamente confiável.

## E-mail

Configurar `PUBLIC_APP_URL` real, `EMAIL_HOST`, porta, TLS/SSL, usuário, senha e `DEFAULT_FROM_EMAIL` no arquivo privado. Fornecer a senha por mecanismo seguro, nunca por mensagem, argumento de comando ou commit. TLS e SSL não devem ser habilitados simultaneamente. Verificar SPF/DKIM e autorização do remetente no provedor.

`manage.py verificar_operacao --smtp --report /caminho/privado/relatorio-novo.json` testa somente conexão/TLS/autenticação e fecha a conexão; não envia mensagens. A entrega real requer um destinatário autorizado e teste de recuperação pelo fluxo da aplicação. Sem SMTP configurado, o comando registra a pendência; não simula sucesso.

## Certificado fiscal

O certificado A1 PKCS#12 (.pfx/.p12) com senha deve ser fornecido pelo responsável fiscal e cadastrado em Ambiente fiscal. É diferente do certificado HTTPS do Nginx. O upload já valida formato, validade, chave privada RSA e correspondência da chave pública; o armazenamento é privado, com arquivo 0600, sem URL pública. Incluir `.private/certificados/` e os segredos de criptografia no backup privado.

A auditoria atual encontrou a configuração fiscal, mas o arquivo configurado está ausente. Não existe correção de código que substitua o certificado real. O titular, a cadeia de confiança, a revogação e a habilitação municipal precisam ser confirmados com o responsável/provedor antes de emissão real. Não transmitir nem alterar homologação/produção para testar a existência do arquivo. `verificar_operacao` usa somente o diagnóstico fiscal local.

## Rotação de credenciais

`manage.py preparar_rotacao --output /caminho/privado/rotacao-nova.json` gera candidatos criptograficamente aleatórios em arquivo 0600, não sobrescreve arquivo e não ativa nada. Não exibir nem anexar esse JSON em chat ou issue.

- **SECRET_KEY Django:** fazer backup privado do banco, do ambiente e dos certificados. Ativar a nova chave mantendo a anterior em `SECRET_KEY_FALLBACKS` durante a transição; as senhas fiscais cifradas dependem da chave anterior. Regravar essas credenciais sob a nova chave em uma janela sem operações fiscais, validar leitura e retirar o fallback antigo. O fallback de uma chave exposta não pode permanecer indefinidamente. O JWT usa a chave principal; planejar novo login dos usuários.
- **API_SECRET_KEY compartilhada:** o protocolo legado produz assinaturas/respostas/chaves persistidas com esse segredo. Alterá-lo isoladamente no servidor interromperia os consumidores e pode exigir reconciliação de chaves existentes. Distribuir a nova chave aos consumidores por canal seguro, validar em homologação e coordenar a ativação. O comando não altera liberações ou chaves históricas. MD5 legado continua sendo uma limitação a modernizar com os consumidores; não foi apresentado como autenticação moderna.
- **SMTP, banco e certificado:** a troca efetiva acontece no provedor/servidor emissor, seguida da configuração privada e teste. Uma variável nova no código não revoga a credencial antiga.

Não reescrever o histórico Git como substituto da rotação. Mesmo após a limpeza do histórico, credenciais já expostas devem ser consideradas comprometidas.

## Dados legados

`manage.py verificar_operacao --report /caminho/privado/auditoria-nova.json` abre transação PostgreSQL somente de leitura, produz o diagnóstico e salva detalhes/IDs em arquivo 0600. O terminal mostra apenas contagens. Não sobrescreve relatórios e não executa atualizações.

A auditoria de 10/11/2026 encontrou 9 grupos de identidades Layout/entidade ambíguas, 41 períodos com mais de uma liberação e 491 liberações com códigos diferentes do cadastro atual. Apenas o primeiro indicador comprova ambiguidade da identidade consultada pelo protocolo. Os demais podem refletir mudanças históricas legítimas, e não autorizam exclusão ou atualização automática.

Conferir cada grupo com o responsável pelos consumidores, definir qual identificação pertence a cada cliente e corrigir pelo cadastro após backup. Preservar liberações/chaves históricas até conciliação explícita. A API rejeita identidades ambíguas, e o serializer já impede novas combinações duplicadas. O relatório privado enumera os registros envolvidos para revisão; não escolhe códigos novos arbitrariamente.

`--fail-on-pending` faz o diagnóstico retornar erro se houver pendências, para impedir que uma verificação incompleta seja tratada como liberação para produção. Relatórios não contêm senhas, certificados, tokens ou chaves de acesso.

Referência: [checklist de publicação do Django](https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/).
