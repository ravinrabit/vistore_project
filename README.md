# Vistore

Sistema web de **manutenção predial com segurança do trabalho integrada**,
desenvolvido para as unidades do **SENAC-DF** (Taguatinga, Ennius Muniz...).

A ideia central: **nenhum serviço de manutenção começa sem segurança**. O
técnico só pode ser designado para um serviço se tiver os treinamentos
exigidos (NR-10 para eletricidade, NR-35 para trabalho em altura) dentro da
validade, e só pode iniciar o serviço depois de confirmar o checklist de
segurança (EPIs, isolamento da área).

> Projeto acadêmico individual do SENAC-DF, também parte do meu portfólio.

## Funcionalidades

**Prontas (etapa 2: base do sistema)**

- Login por e-mail, com bloqueio de usuários desativados
- Quatro perfis (Solicitante, Técnico, Gestor de Segurança e Administrador), cada um com seu painel
- Cadastro de unidades, locais e equipamentos, com permissão por perfil e por unidade
- Todos os models do domínio criados e disponíveis no Django Admin
- Comando para popular o banco com dados de exemplo
- Testes automatizados de login, permissões e filtro por unidade

**Próximas etapas**

- Fluxo de ordens de serviço: abrir, classificar, atribuir, executar e concluir
- Bloqueio por NR, checklist de segurança, EPIs e incidentes
- Preventivas automáticas, QR Code, alertas por e-mail e painel com gráficos

## Tecnologias

- Python 3.11+ e Django 5.2 LTS
- MySQL 8 (ou MariaDB 10.6+) com o driver `mysqlclient`
- Templates do Django com Bootstrap 5 e Bootstrap Icons
- `python-decouple` para ler as configurações do `.env`

## Como rodar

### 1. Pré-requisitos

- Python 3.11 ou mais recente
- MySQL em execução
- Para compilar o `mysqlclient`:
  - **Windows**: normalmente o `pip` já baixa um pacote pronto
  - **Ubuntu/Debian**: `sudo apt install python3-dev default-libmysqlclient-dev build-essential pkg-config`

### 2. Banco de dados

No cliente do MySQL:

```sql
CREATE DATABASE vistore CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'vistore'@'localhost' IDENTIFIED BY 'sua-senha';
GRANT ALL PRIVILEGES ON vistore.* TO 'vistore'@'localhost';
-- Permissão para os testes criarem o banco temporário:
GRANT ALL PRIVILEGES ON test_vistore.* TO 'vistore'@'localhost';
```

### 3. Projeto

```bash
git clone https://github.com/ravinrabit/Vistore.git
cd Vistore

python -m venv venv
# Windows: venv\Scripts\activate
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env              # no Windows: copy .env.example .env
# Edite o .env: gere uma SECRET_KEY e preencha a senha do banco

python manage.py migrate
python manage.py popular_dados   
python manage.py runserver
```

Depois é só abrir http://127.0.0.1:8000.

### Problemas comuns

**`OperationalError: (2002, "Can't connect to server on 'localhost' (10061)")`**

O Django não encontrou o MySQL. Verifique, na ordem:

1. **O MySQL está ligado?**
   - XAMPP: abra o XAMPP Control Panel e clique em *Start* na linha do MySQL.
   - MySQL Server: `Win + R` → `services.msc` → procure o serviço **MySQL80** e clique em *Iniciar*.
2. **Use `DB_HOST=127.0.0.1` no `.env`.** No Windows, `localhost` pode ir para o IPv6 (`::1`) e o MySQL só escutar no IPv4.
3. **A porta está certa?** Teste no PowerShell: `Test-NetConnection 127.0.0.1 -Port 3306`. Se aparecer `TcpTestSucceeded : False`, o MySQL está parado ou usa outra porta; ajuste `DB_PORT` no `.env`.

**`(1045, "Access denied for user ...")`**: o usuário ou a senha do `.env` não conferem. No XAMPP, o padrão é `DB_USER=root` com `DB_PASSWORD=` vazio.

**`(1049, "Unknown database 'vistore'")`**: o banco ainda não foi criado. Rode o SQL da seção "Banco de dados".

### Usuários de exemplo

Estes usuários são criados pelo `popular_dados`. A senha de todos é `vistore123`.

| Perfil | E-mail | Unidade |
| --- | --- | --- |
| Administrador | admin@vistore.test | todas |
| Gestor de Segurança | gestor@vistore.test | Taguatinga |
| Técnico | tecnico@vistore.test | Taguatinga |
| Solicitante | solicitante@vistore.test | Taguatinga |

### Testes

```bash
python manage.py test
```

## Estrutura do projeto

```
vistore/      configurações (settings.py lê o .env) e URLs principais
contas/       Usuario, login/logout, painéis e mixins de permissão
estrutura/    Unidade, Local, Equipamento (CRUD) e o comando popular_dados
seguranca/    Treinamento, TreinamentoTecnico, EPI, TipoServico, Incidente
ordens/       OrdemServico, HistoricoStatus, ChecklistSeguranca, Preventiva
templates/    base.html, navbar, formulário genérico e parciais
static/       CSS próprio
```

## Perfis e permissões

| Perfil | Acesso atual |
| --- | --- |
| Administrador | Tudo, em todas as unidades, incluindo o Django Admin |
| Gestor de Segurança | Locais e equipamentos da própria unidade; edição dos dados da unidade |
| Técnico | Painel com os próprios treinamentos e serviços |
| Solicitante | Painel com os próprios chamados |

## Regras de negócio

| Código | Regra |
| --- | --- |
| RN01 | Só pode ser atribuído o técnico que tem todos os treinamentos exigidos em dia |
| RN02 | O serviço só inicia depois que o checklist de segurança é confirmado |
| RN03 | Se um treinamento vencer antes do início, o serviço volta para "Aguardando atribuição" |
| RN04 | Serviço elétrico exige NR-10; serviço acima de 2 m exige NR-35 |
| RN05 | Fluxo Aberto → Classificado → Atribuído → Em execução → Concluído (ou Cancelado) |
| RN06 | Só o solicitante ou o gestor cancela, sempre com justificativa |
| RN07 | Chamado urgente aparece no topo das listas |
| RN08 | Incidente com lesão ou afastamento marca a OS para revisão |
| RN09 | Preventivas geram a OS 7 dias antes da data prevista |
| RN10 | Usuário desativado não entra, mas o histórico é mantido |

## Autoria

Projeto individual desenvolvido no SENAC-DF. <!-- TODO: seu nome e links (GitHub/LinkedIn) -->
