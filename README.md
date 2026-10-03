# ⚖️ Gestão do Escritório

App web para escritórios de advocacia controlarem **clientes, processos e honorários**, substituindo a planilha de "clientes ativos".

**Stack:** Python · Streamlit · SQLAlchemy · Supabase (PostgreSQL) · Plotly

## Funcionalidades

| Página | O que faz |
|---|---|
| **Dashboard** | Recebido no mês, a receber, em atraso, fluxo mensal (recebido x previsto), em aberto por área, maiores atrasos e próximos vencimentos |
| **Agenda de prazos** | Prazos, audiências e reuniões por processo. Calculadora em **dias úteis** a partir da intimação (sem fins de semana, feriados nacionais e recesso de 20/12 a 20/01), alertas de vencido/hoje/7 dias, "marcar como cumprido" e botão para o Google Agenda |
| **Cobrança** | Lista quem está atrasado ou vence em 7 dias e abre o WhatsApp com mensagem pronta (modelo editável) |
| **Clientes** | Cadastro PF/PJ com validação de CPF/CNPJ e telefone, busca por nome/CPF/telefone/nº do processo, CPF mascarado nas listas |
| **Processos e honorários** | Nº CNJ validado (dígito verificador), área, sistema (PROJUDI/PJE…), status. Honorário **fixo**, **êxito (%)** ou **fixo + êxito**. Gera entrada + parcelas mensais, lança o êxito sobre o valor do acordo/sentença e aceita parcelas avulsas |
| **Parcelas e recebimentos** | Filtros por status, área e período; registrar pagamento (pagamento parcial gera parcela de saldo), **recibo em PDF com logo e valor por extenso**, estornar e exportar para Excel |
| **Pendências de cadastro** | Clientes sem CPF/telefone, processos sem número ou sem parcelas |
| **Usuários e senha** | Login com senha criptografada (bcrypt), perfis admin/usuário e logout automático após 60 min parado |

## Rodar no computador (teste)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
python scripts/dados_demo.py    # opcional: dados FICTÍCIOS, login admin@demo.com / demo12345
streamlit run app.py
```

Sem `DATABASE_URL`, o app usa um SQLite local em `data/escritorio.db`. No primeiro acesso sem dados de demonstração, ele pede para criar o usuário administrador.

## Colocar no ar (Supabase + Streamlit Community Cloud)

### 1. Banco no Supabase
1. Crie um projeto em [supabase.com](https://supabase.com) e escolha a região **South America (São Paulo)**.
2. Anote a senha do banco.
3. Vá em **Connect** → **Connection string** → **Session pooler** e copie a URL.
4. Troque `postgresql://` por `postgresql+psycopg2://` e `[YOUR-PASSWORD]` pela senha.

As tabelas são criadas sozinhas no primeiro acesso. O app também **ativa RLS** em todas as tabelas, para que ninguém consiga ler os dados pela API pública do Supabase.

### 2. Código no GitHub
Suba a pasta para um repositório **privado**. O `.gitignore` já impede o envio de `secrets.toml` e do banco local.

### 3. Deploy no Streamlit Cloud
1. Em [share.streamlit.io](https://share.streamlit.io), clique em **Create app** e escolha o repositório, com `app.py` como arquivo principal.
2. Em **Advanced settings → Secrets**, cole:
   ```toml
   NOME_ESCRITORIO = "Nome do Escritório"
   DATABASE_URL = "postgresql+psycopg2://postgres.xxxx:SENHA@aws-0-sa-east-1.pooler.supabase.com:5432/postgres"
   ```
3. Abra o app e crie o usuário administrador. Depois, em **Usuários e senha**, cadastre a equipe.

> **Não rode `dados_demo.py` no banco de produção.**

## Personalizar recibo e marca
- Logo: troque `assets/logo_completo.png` e `assets/icone.png`.
- Dados do recibo (endereço, telefone, CPF/CNPJ): seção `[escritorio]` do `secrets.toml` (veja o exemplo).

> ⚠️ A calculadora de prazos **não conhece feriados estaduais/municipais nem suspensões do tribunal**. Sempre confira no calendário do TJPR/TRT.

## LGPD: cuidados já incluídos
- Acesso só com login; senhas guardadas com hash bcrypt (nunca em texto).
- CPF/CNPJ aparece mascarado nas listas e completo só na ficha do cliente.
- Logout automático por inatividade.
- RLS ativado no Supabase e segredos fora do código.
- Recomendações: repositório privado, senha forte, e ativar backups/PITR no Supabase conforme o plano contratado.

## Estrutura
```
app.py                 login, navegação e sessão do banco
core/db.py             modelos (usuarios, clientes, processos, parcelas) e conexão
core/repo.py           regras de negócio e consultas (sem Streamlit; testável)
core/validators.py     CPF, CNPJ, CNJ, telefone, moeda BR, link WhatsApp
core/auth.py           usuários e senhas
core/componentes.py    tabela/ações de parcelas reutilizadas
views/                 páginas
scripts/dados_demo.py  dados fictícios
tests/                 testes (pytest)
```

Testes: `python -m pytest -q`
