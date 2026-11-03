# Vistore: contexto do projeto

> Resumo para o Claude Code. Salve este arquivo como **`CLAUDE.md` na raiz do repositório**:
> a extensão do Claude Code (VS Code) e o Claude Code no terminal leem esse arquivo
> automaticamente em toda conversa nova.

## 1. O que é

Sistema web de **manutenção predial com segurança do trabalho integrada** para as unidades do
**SENAC-DF** (Taguatinga, Ennius Muniz...). Lema: *nenhum serviço começa sem segurança*. O técnico
só recebe um serviço se tiver as NRs exigidas (NR-10, NR-35) em dia, e só inicia depois de
confirmar o checklist de segurança.

- Projeto acadêmico **solo**, 6 meses, com apresentação final. Também vai para o portfólio:
  código limpo e commits pequenos e claros.
- Autor: **desenvolvedor júnior**. Explique as decisões importantes de forma simples, para que
  ele consiga defender o código na banca. Ao fim de cada etapa, gere um `.txt` com a explicação
  do que foi feito, para a apresentação.
- Repositório: `github.com/ravinrabit/Vistore` (branch `main`).

## 2. Stack (obrigatória)

- Python 3.12 + **Django 5.2 LTS**
- **MySQL/MariaDB** com o driver `mysqlclient` (o Django 5.2 exige **MariaDB 10.5+** ou MySQL 8+)
- Front-end: templates do Django + HTML/CSS/JS + **Bootstrap 5.3** e Bootstrap Icons (via CDN).
  **Sem React/Vue.**
- Configurações sensíveis no **`.env`**, lido com `python-decouple`. O `.env` nunca vai para o Git.
- Idioma: interface, models, campos e mensagens em **português**

## 3. Ambiente de desenvolvimento (Windows)

O MySQL80 da máquina tem senha desconhecida e o MariaDB do XAMPP é 10.4 (incompatível). Por isso,
usamos o **MariaDB portátil (ZIP), na porta 3309, com root sem senha**.

Primeira vez numa máquina (o PC do laboratório pode apagar arquivos ao reiniciar):
```powershell
# baixar em https://mariadb.org/download -> Windows, x86_64, pacote ZIP
cd $HOME\mariadb-XX-winx64          # entrar na pasta que contém a pasta "bin"
.\bin\mariadb-install-db.exe --datadir="$PWD\data" --port=3309
```
Toda vez (deixe esta janela aberta):
```powershell
.\bin\mariadbd.exe --defaults-file="$PWD\data\my.ini" --console
```
Projeto (em outro terminal):
```powershell
pip install -r requirements.txt
python -c "import MySQLdb; c=MySQLdb.connect(host='127.0.0.1', port=3309, user='root', passwd=''); c.cursor().execute('CREATE DATABASE IF NOT EXISTS vistore CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')"
python manage.py migrate
python manage.py popular_dados
python manage.py runserver
```
`.env` (raiz do projeto, ao lado do `manage.py`):
```
SECRET_KEY=<gerar com: python -c "from django.core.management.utils import get_random_secret_key as g; print(g())">
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_NAME=vistore
DB_USER=root
DB_PASSWORD=
DB_HOST=127.0.0.1
DB_PORT=3309
```
Erros já resolvidos (para diagnosticar rápido):
- 2002 (10061): o servidor não está rodando ou a porta está errada.
- 1045: senha errada. Quase sempre significa que o Django conectou no MySQL80 em vez do MariaDB
  portátil; confira o `DB_PORT`.
- 1049: o banco não foi criado nesse servidor.
- "MariaDB 10.5 or later is required (found 10.4.28)": o Django está conectando no XAMPP.

Usuários de exemplo (`popular_dados`), todos com a senha **`vistore123`**: `admin@vistore.test`,
`gestor@vistore.test` (Taguatinga), `tecnico@vistore.test` (Taguatinga),
`solicitante@vistore.test` (Taguatinga).

## 4. Perfis

| Perfil (`Usuario.perfil`) | Pode fazer |
| --- | --- |
| `SOLICITANTE` | Abrir chamados, acompanhar os próprios, avaliar serviço concluído |
| `TECNICO` | Ver serviços atribuídos, preencher checklist, iniciar/finalizar, registrar incidentes |
| `GESTOR` (Gestor de Segurança) | Classificar e atribuir chamados; cadastrar técnicos, treinamentos, EPIs e preventivas; relatórios da unidade |
| `ADMIN` | Tudo do Gestor em **todas** as unidades; unidades, usuários, tipos de serviço |

Cada usuário só vê os dados da própria unidade, exceto o Administrador (que pode ficar sem unidade).

## 5. Regras de negócio

- **RN01**: só pode ser atribuído o técnico com TODOS os treinamentos exigidos pelo tipo de serviço, válidos na data da atribuição.
- **RN02**: o serviço só inicia depois que o técnico confirma todos os itens do checklist de segurança.
- **RN03**: se um treinamento vencer com o serviço ainda não iniciado, a OS volta para "Aguardando atribuição" (status `CLASSIFICADO`).
- **RN04**: serviço elétrico exige NR-10; acima de 2 m exige NR-35 (campos `TipoServico.eletrico` e `TipoServico.trabalho_em_altura`).
- **RN05**: Aberto → Classificado → Atribuído → Em execução → Concluído. Qualquer status antes de Concluído pode ir para Cancelado.
- **RN06**: só o solicitante ou o gestor cancela, sempre com justificativa.
- **RN07**: chamado urgente aparece no topo das listas.
- **RN08**: incidente com afastamento ou lesão marca a OS (`requer_revisao_seguranca=True`) para revisão do Gestor.
- **RN09**: preventivas geram a OS 7 dias antes da data prevista.
- **RN10**: usuário desativado (`is_active=False`) não entra, mas o histórico é mantido. Nunca apagar usuário; as FKs usam `PROTECT`.

**RN01, RN02 e RN05 ficam na camada de modelo/serviço (`services.py` do app), nunca só na view, e
precisam de testes automatizados.**

O `Fluxograma.jpg`/`.pdf` na raiz desenha esse fluxo: abrir OS → classificar (preventiva entra
aqui 7 dias antes) → exige NR? → atribuir técnico → treinamentos em dia? (não: volta para
"Aguardando atribuição" e reatribuir) → checklist ok? → em execução → incidente com afastamento?
(sim: OS em revisão) → concluído. O cancelamento sai de qualquer etapa e exige autorização e
justificativa.

## 6. Organização do código

```
vistore/     settings.py (lê o .env), urls.py
contas/      Usuario (login por e-mail), Perfil, login/logout, painel por perfil,
             mixins.py (PerfilRequeridoMixin, GestaoMixin, SomenteAdminMixin, FiltroUnidadeMixin),
             forms.py (LoginForm, EstiloBootstrapMixin)
estrutura/   Unidade, Local, Equipamento + CRUD completo; comando popular_dados
seguranca/   Treinamento, TreinamentoTecnico (valido_em(data), calcula data_validade),
             EPI, TipoServico (eletrico, trabalho_em_altura, M2M treinamentos/EPIs), Incidente
ordens/      OrdemServico, HistoricoStatus, ChecklistSeguranca (1:1), Preventiva
             Choices: Status, Prioridade
templates/   base.html, partials/ (navbar por perfil, mensagens, paginação, card_numero,
             cabecalho_lista), crud/ (form.html e confirmar_exclusao.html genéricos),
             registration/login.html
static/css/vistore.css   cores: azul #004a8d, laranja #f7941d
```

## 7. Convenções

- Choices com `models.TextChoices`. Todo model tem `__str__`, `verbose_name` e `verbose_name_plural` em português.
- Login por e-mail (`USERNAME_FIELD = "email"`, sem `username`).
- Atalhos de perfil: `user.eh_admin`, `eh_gestor`, `eh_tecnico`, `eh_solicitante`.
- Acesso sempre via mixins de `contas/mixins.py`. O filtro por unidade fica no `get_queryset`, então
  um registro de outra unidade dá 404 (inclusive em editar/excluir).
- Forms recebem `usuario=` (via `UsuarioNoFormMixin`) e limitam as opções à unidade do usuário.
- Views baseadas em classe (ListView, CreateView...) e templates genéricos de `crud/`.
- Exclusão com `PROTECT` mostra mensagem amigável (`ExclusaoProtegidaMixin`).
- O autor removeu a maioria dos comentários/docstrings do código. Comente só o essencial.
- Commits em português, pequenos, no imperativo ("Adiciona fluxo de cancelamento").
- Testes: `python manage.py test` (precisa do MariaDB rodando; o root cria o `test_vistore`).

## 8. Andamento

| # | Etapa | Situação |
| --- | --- | --- |
| 1 | Documentação (requisitos, perfis, regras, modelo de dados, fluxograma) | feito |
| 2 | Base: Django + MySQL, login e perfis, unidades/locais/equipamentos, todos os models, `popular_dados`, 21 testes | **feito** |
| 3 | Ordens de serviço | **próxima** |
| 4 | Segurança | a fazer |
| 5 | Extras | a fazer |
| 6 | Testes, ajustes visuais, deploy, manual, apresentação final | a fazer |

### Etapa 3: ordens de serviço (próxima)
- Solicitante abre chamado (local, equipamento opcional, descrição, prioridade) e vê os próprios.
- Gestor classifica (tipo de serviço, riscos) e atribui o técnico.
- `ordens/services.py`: tabela de transições permitidas (RN05) e uma função única de mudança de
  status que grava `HistoricoStatus` e preenche `iniciada_em`/`concluida_em`.
- Urgentes no topo (RN07): ordenar com `Case/When` sobre `prioridade`.
- Cancelamento só pelo solicitante ou gestor, com justificativa obrigatória (RN06).
- Avaliação de 1 a 5 pelo solicitante após concluir.
- Telas: lista por perfil, detalhe da OS com linha do tempo do histórico.
- Testes da RN05/RN06/RN07.

### Etapa 4: segurança
- RN01/RN04: na atribuição, validar todas as NRs exigidas (M2M + NR-10 se `eletrico`, NR-35 se
  `trabalho_em_altura`) com `TreinamentoTecnico.valido_em(data)`. O select de técnicos mostra só
  os aptos.
- RN02: tela de checklist (EPIs exigidos pelo tipo + área isolada); só depois disso o técnico pode iniciar.
- RN03: comando agendável (`verificar_treinamentos`) que devolve para `CLASSIFICADO` as OS
  atribuídas cujo técnico ficou com NR vencida.
- RN08: registro de incidente; lesão ou afastamento marca `requer_revisao_seguranca`.
- CRUD de treinamentos, treinamentos dos técnicos, EPIs e tipos de serviço (Gestor/Admin).
- Testes da RN01, RN02, RN03 e RN08.

### Etapa 5: extras
- RN09: comando `gerar_preventivas` (cria a OS 7 dias antes e avança `proxima_data`).
- QR Code por equipamento (abre chamado já com o equipamento preenchido).
- Alertas por e-mail (no desenvolvimento, `EMAIL_BACKEND` de console).
- Painel com gráficos (Chart.js).

## 9. Pendências conhecidas

- O `.env.example` foi removido do repositório e o README ainda o cita. Recriar só com valores de exemplo.
- Validar se a migração `estrutura/0002_local_equipamento_local_local_unico_por_unidade.py` está
  coerente (`python manage.py makemigrations --check`).
- Preencher a autoria no README (nome e links).
