# FindMyJob - Buscador de Vagas

Buscador de vagas de emprego que utiliza "dorks" (consultas avançadas de busca) para encontrar vagas em portais de emprego e sistemas de acompanhamento de candidatos (ATS).

## Funcionalidades

- **Múltiplas fontes de busca**: Indeed, LinkedIn, Glassdoor + ATS (Greenhouse, Lever, Workday, SmartRecruiters, Ashby, Workable)
- **Suporte a 11 países**: Brasil, Portugal, EUA, Reino Unido, Canadá, Alemanha, Espanha, México, Argentina, Colômbia e Chile
- **Dois backends de busca**: DuckDuckGo (padrão) ou Google Custom Search API
- **Filtros por palavras-chave**: Incluir ou excluir termos nos resultados
- **Filtro por data**: Idade máxima, data mínima/máxima e modo estrito
- **Enriquecimento**: empresa extraída do link/título e descrição a partir do snippet
- **Saída em JSON, XLSX e CSV**: Planilha formatada com hyperlinks e filtros
- **Banco SQLite**: Deduplicação por URL normalizada, ideal para cronjobs
- **Utilitários de banco**: Subcomandos `db stats`, `db export` e `db purge`
- **Logging e exit codes**: `--quiet`, `--log-file` e código de saída para cronjobs
- **Retry automático**: Tentativas configuráveis em caso de falha de rede
- **Modo interativo ou CLI**: Interface amigável ou argumentos de linha de comando

## Instalação

### Instalação como pacote (recomendado)

```bash
# Instalar a partir do diretório do projeto
pip install .

# Ou em modo desenvolvimento (alterações refletem imediatamente)
pip install -e .
```

### Instalação manual (desenvolvimento)

```bash
# Crie um ambiente virtual
python -m venv env
source env/bin/activate  # Linux/Mac
# env\Scripts\activate   # Windows

# Instale as dependências
pip install -r requirements.txt
```

## Uso

Após instalar o pacote (`pip install .`), você pode usar o comando `findmyjob` diretamente.

### Modo Interativo

```bash
findmyjob
```

O script irá perguntar sobre o cargo, país, local e fontes de busca.

### Modo CLI (Linha de Comando)

```bash
# Busca geral
findmyjob "backend engineer" -l remote -l latam

# Busca apenas no Brasil
findmyjob "backend engineer" -c br

# Brasil + remoto + apenas ATS
findmyjob "backend engineer" -c br -l remote --group ats

# Com filtros de palavras-chave
findmyjob "backend engineer" --filter-include senior --filter-exclude junior

# Salvar em banco SQLite (ideal para cronjobs)
findmyjob "python developer" -c br --db ~/findmyjob.db

# Salvar apenas no banco, sem arquivos
findmyjob "golang" --db findmyjob.db --no-json --no-xlsx

# Também gerar CSV
findmyjob "golang" --csv

# Somente vagas publicadas nos últimos 3 dias (descarta as sem data)
findmyjob "backend engineer" -c br --max-days 3 --strict-dates

# Filtrar por intervalo de datas
findmyjob "backend engineer" --min-date 2026-09-01 --max-date 2026-10-01

# Modo silencioso + log em arquivo (bom para cron)
findmyjob "backend engineer" --db ~/findmyjob.db --quiet --log-file ~/findmyjob.log

# Listar países disponíveis
findmyjob --list-countries

# Apenas mostrar as queries (sem executar busca)
findmyjob "backend engineer" --show-queries
```

Também é possível usar como módulo Python:

```bash
python -m findmyjob "backend engineer" -c br
```

### Utilitários do banco

```bash
# Estatísticas do banco
findmyjob db --db ~/findmyjob.db stats

# Exportar tudo para JSON ou CSV (stdout ou arquivo)
findmyjob db --db ~/findmyjob.db export --format csv -o vagas.csv

# Exportar apenas as vagas dos últimos 7 dias
findmyjob db --db ~/findmyjob.db export --since-days 7

# Remover vagas vistas há mais de 30 dias (pede confirmação)
findmyjob db --db ~/findmyjob.db purge --older-than 30
```

### Uso em cronjob

O comando retorna código de saída `2` quando **todas** as queries falham e `1`
em erros fatais — útil para monitoramento. Exemplo de entrada no `crontab`:

```cron
# Todo dia às 8h: busca vagas recentes e grava no banco
0 8 * * * /usr/local/bin/findmyjob "backend engineer" -c br -l remote \
  --max-days 3 --strict-dates --db "$HOME/findmyjob.db" \
  --no-json --no-xlsx --quiet --log-file "$HOME/findmyjob.log"
```

### Usando Google Custom Search (Opcional)

```bash
export GOOGLE_API_KEY="sua_chave"
export GOOGLE_CX="seu_cx"
findmyjob "backend engineer" -b google
```

## Argumentos

| Argumento | Descrição |
|-----------|-----------|
| `role` | Cargo a buscar (ex: "backend engineer") |
| `-c, --country` | Limitar a um país (br, pt, us, uk, ca, de, es, mx, ar, co, cl) |
| `-l, --local` | Local/termo extra (repetível) |
| `-g, --group` | Grupo de fontes: boards, ats, all |
| `-b, --backend` | Backend de busca: ddg, google |
| `-m, --max` | Resultados por query (padrão: 8) |
| `-o, --output` | Nome base dos arquivos de saída |
| `-i, --interactive` | Forçar modo interativo |
| `--delay` | Segundos entre queries (padrão: 2.0) |
| `--retries` | Tentativas em caso de erro (padrão: 3) |
| `--show-queries` | Apenas imprimir as queries |
| `--no-color` | Desativar cores |
| `--list-countries` | Listar países disponíveis |
| `--filter-include` | Palavras-chave que devem estar no título |
| `--filter-exclude` | Palavras-chave que NÃO devem estar no título |
| `--max-days` | Idade máxima da vaga em dias (0 desativa; padrão: 3) |
| `--strict-dates` | Descarta vagas sem data identificável |
| `--min-date` | Data mínima de publicação (YYYY-MM-DD) |
| `--max-date` | Data máxima de publicação (YYYY-MM-DD) |
| `--db` | Salvar resultados em banco SQLite (ex.: findmyjob.db) |
| `--csv` | Também salvar arquivo CSV |
| `--no-json` | Não salvar arquivo JSON |
| `--no-xlsx` | Não salvar arquivo XLSX |
| `-q, --quiet` | Suprime saída de progresso |
| `-v, --verbose` | Log detalhado |
| `--log-file` | Arquivo de log (append) |

## Saída

O script pode gerar os seguintes arquivos (controláveis por flags):

1. **`.json`**: Dados brutos com metadados da busca
2. **`.xlsx`**: Planilha formatada com:
   - Aba "Vagas": Lista de vagas com hyperlinks, empresa e descrição
   - Aba "Busca": Metadados da pesquisa
3. **`.csv`** (opcional, com `--csv`): Versão leve sem dependências
4. **Banco SQLite** (opcional): Salva no banco com deduplicação automática por URL normalizada — ideal para execução periódica via cron.

## Testes

```bash
# Instale as dependências de desenvolvimento
pip install -e ".[dev]"

# Rode os testes
pytest -v

# Verificação de lint
ruff check .
```

## Estrutura do Projeto

```
findmyjob/
├── .github/
│   └── workflows/
│       ├── tests.yml          # CI: testes e lint em push/PR
│       └── publish-pypi.yml   # CI: publica no PyPI ao criar release
├── src/
│   └── findmyjob/
│       ├── __init__.py        # Exports do pacote
│       ├── cli.py             # Lógica principal + CLI
│       └── __main__.py        # Entry point para python -m
├── tests/
│   └── test_main.py           # Testes automatizados
├── pyproject.toml             # Configuração do pacote (PEP 621)
├── requirements.txt           # Dependências
├── README.md                  # Documentação
├── .gitignore                 # Arquivos ignorados pelo git
├── env/                       # Virtual environment (opcional)
├── findmyjob.db                 # Banco SQLite (gerado com --db)
├── vagas_*.json               # Resultados em JSON
├── vagas_*.csv                # Resultados em CSV (com --csv)
└── vagas_*.xlsx               # Resultados em Excel
```

## Exemplos de Uso

### Buscar vagas de Python no Brasil

```bash
findmyjob "python developer" -c br -l remote
```

### Buscar vagas de Go com filtro

```bash
findmyjob "golang" --filter-include backend --filter-exclude senior
```

### Buscar em todos os ATS

```bash
findmyjob "backend engineer" -g ats -m 10
```

## Contribuindo

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

## Licença

Este projeto é uso pessoal/educação.
