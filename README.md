# FinControl

Sistema acadêmico de controle financeiro pessoal, com interface Streamlit e dados persistidos no MongoDB Atlas. Todas as consultas e operações de gravação são realizadas pelo PyMongo.

## Tecnologias

- Python 3.14, Streamlit, PyMongo, python-dotenv
- MongoDB Atlas (cluster gratuito M0)
- Git e GitHub

## Funcionalidades

- Cadastro, consulta, edição e exclusão de receitas e despesas.
- Dashboard com receitas, despesas, saldo e transações recentes.
- Filtros combináveis por tipo, categoria, data inicial e final, valor mínimo e máximo, e trecho da descrição; ordenação por data.
- Valores armazenados como centavos inteiros e apresentados em reais (R$).

## Estrutura

```text
app.py                    Interface, dashboard e formulários
database.py               Conexão, índices, validação, CRUD, filtros e indicadores
requirements.txt          Dependências Python
.env.example              Modelo de configuração sem credenciais
.env                      Configuração local (ignorada pelo Git)
tests/test_database.py    Testes de validação e construção de consultas
tests/test_atlas_integration.py  Testes reais no Atlas, com limpeza dos dados de teste
```

## Configurar MongoDB Atlas

1. Crie ou reutilize um projeto **FinControl** e um cluster **FinControlCluster** no plano **M0 gratuito**.
2. Crie um usuário de banco com permissão `readWrite` somente no banco `controle_financeiro`.
3. Autorize somente o IP público da máquina que executará o aplicativo em **Network Access**. Se o IP mudar, atualize essa entrada.
4. Copie `.env.example` para `.env` e preencha `MONGODB_URI` com a URI `mongodb+srv://...` do cluster. Se a senha contiver caracteres especiais, codifique-a para URL. Mantenha `.env` fora do Git.
5. Na primeira conexão, o aplicativo executa `ping`, cria a coleção `transacoes` e cria os índices necessários. O banco e a coleção passam a existir no Atlas após essa operação.

Variáveis:

```dotenv
MONGODB_URI=mongodb+srv://USUARIO:SENHA@SEU_CLUSTER.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=controle_financeiro
```

## Executar no Windows

No PowerShell, dentro da pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Se o `venv` falhar ao acessar a pasta temporária no ambiente de execução, defina `TMP` e `TEMP` para uma pasta gravável antes de criá-lo.

## Usar

Na aba **Transações**, cadastre uma receita, por exemplo “Salário”, categoria “Salário”, R$ 2.500,00. Cadastre uma despesa, como “Mercado”, categoria “Alimentação”, R$ 180,50. O **Dashboard** mostra os totais. Em **Consultar e gerenciar**, combine “Despesa”, “Alimentação” e um intervalo de datas; selecione uma linha para ver detalhes, editar ou excluir mediante confirmação.

## Como o código demonstra os requisitos

Em `database.py`, `create_transaction()` chama `insert_one()`, `list_transactions()` chama `find()`, `update_transaction()` chama `update_one()` com `_id`, e `delete_transaction()` chama `delete_one()`. A função `build_query()` constrói o filtro MongoDB com `$gte`, `$lt`, `$lte` e `$regex`; `list_transactions()` envia esse filtro diretamente ao `find()` e ordena com `sort()`. `get_totals()` usa uma agregação MongoDB com `$group` e `$sum`. A interface chama essas funções em `app.py`.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Com `MONGODB_URI` configurada, os testes de integração executam `ping`, CRUD, consultas por categoria, tipo, data, valor, filtros simultâneos e indicadores no Atlas. Os registros de teste recebem um marcador único na observação e somente eles são removidos ao final. Sem URI, os testes de integração são ignorados e **não** comprovam conexão com o Atlas.
