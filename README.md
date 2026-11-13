# Gestão Financeira

Sistema de gestão financeira construído com Django, Django REST Framework, PostgreSQL e React 19 com TypeScript e Ant Design.

## Requisitos

- Git
- Python 3.13
- PostgreSQL 14 ou superior
- Node.js 26 e npm 11 ou superior

## Instalação local

Clone o repositório e entre na pasta do projeto:

```bash
git clone <URL_DO_REPOSITORIO>
cd gestaofinanceira
```

Crie um banco e um usuário PostgreSQL locais. Ajuste os nomes e a senha antes de executar:

```sql
CREATE USER gestao_financeira WITH PASSWORD 'uma-senha-local-segura';
CREATE DATABASE gestao_financeira OWNER gestao_financeira;
```

Crie o arquivo de configuração local e informe a URL do banco:

```bash
cp .env.example .env
```

Edite o valor de `DATABASE_URL` no `.env`. O arquivo `.env` não deve ser enviado ao Git.

Crie o ambiente Python e instale as dependências:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requeriments.txt
```

Instale as dependências do front-end e gere os arquivos estáticos do React:

```bash
node --version
npm --version
npm ci
npm run build
```

Execute as migrações, crie o primeiro administrador e inicie o Django:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Abra `http://localhost:8000/`. A aplicação React fica disponível após o login em `http://localhost:8000/clientes/app/`.

## Comandos úteis

```bash
# Testes do front-end
npm test

# Testes do Django
python manage.py test

# Verificar a configuração do Django
python manage.py check
```

## Segurança e arquivos locais

Não versione nem compartilhe pelo GitHub:

- `.env` e credenciais de banco, SMTP e integrações;
- certificados fiscais A1 (`.pfx`/`.p12`) e chaves privadas (`.pem`);
- dumps de banco de dados e a pasta `.private/`;
- arquivos enviados por usuários em `media/`.

O certificado fiscal, quando utilizado, deve ser configurado pela área administrativa do sistema e armazenado fora do repositório. Consulte [deploy/README.md](deploy/README.md) para orientações de produção.
