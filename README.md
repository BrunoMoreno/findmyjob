# JobSearch - Buscador de Vagas

Buscador de vagas de emprego que utiliza "dorks" (consultas avançadas de busca) para encontrar vagas em portais de emprego e sistemas de acompanhamento de candidatos (ATS).

## Funcionalidades

- **Múltiplas fontes de busca**: Indeed, LinkedIn, Glassdoor + ATS (Greenhouse, Lever, Workday, SmartRecruiters, Ashby, Workable)
- **Suporte a 11 países**: Brasil, Portugal, EUA, Reino Unido, Canadá, Alemanha, Espanha, México, Argentina, Colômbia e Chile
- **Dois backends de busca**: DuckDuckGo (padrão) ou Google Custom Search API
- **Filtros por palavras-chave**: Incluir ou excluir termos nos resultados
- **Saída em JSON e XLSX**: Planilha formatada com hyperlinks e filtros
- **Salvamento em banco SQLite**: Ideal para cronjobs e evitar duplicados
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

Após instalar o pacote (`pip install .`), você pode usar o comando `jobsearch` diretamente.

### Modo Interativo

```bash
jobsearch
```

O script irá perguntar sobre o cargo, país, local e fontes de busca.

### Modo CLI (Linha de Comando)

```bash
# Busca geral
jobsearch "backend engineer" -l remote -l latam

# Busca apenas no Brasil
jobsearch "backend engineer" -c br

# Brasil + remoto + apenas ATS
jobsearch "backend engineer" -c br -l remote --group ats

# Com filtros de palavras-chave
jobsearch "backend engineer" --filter-include senior --filter-exclude junior

# Salvar em banco SQLite (ideal para cronjobs)
jobsearch "python developer" -c br --db ~/jobsearch.db

# Salvar apenas no banco, sem arquivos
jobsearch "golang" --db jobsearch.db --no-json --no-xlsx

# Listar países disponíveis
jobsearch --list-countries

# Apenas mostrar as queries (sem executar busca)
jobsearch "backend engineer" --show-queries
```

Também é possível usar como módulo Python:

```bash
python -m jobsearch "backend engineer" -c br
```

### Usando Google Custom Search (Opcional)

```bash
export GOOGLE_API_KEY="sua_chave"
export GOOGLE_CX="seu_cx"
jobsearch "backend engineer" -b google
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
| `--db` | Salvar resultados em banco SQLite (ex.: jobsearch.db) |
| `--no-json` | Não salvar arquivo JSON |
| `--no-xlsx` | Não salvar arquivo XLSX |

## Saída

O script gera dois arquivos:

1. **`.json`**: Dados brutos com metadados da busca
2. **`.xlsx`**: Planilha formatada com:
   - Aba "Vagas": Lista de vagas com hyperlinks
   - Aba "Busca": Metadados da pesquisa
3. **Banco SQLite** (opcional): Salva no banco com deduplicação automática por link - ideal para execução periódica via cron.

## Testes

```bash
# Com pytest (se instalado)
python -m pytest tests/test_main.py -v

# Ou executando diretamente
python tests/test_main.py
```

## Estrutura do Projeto

```
jobsearch/
├── .github/
│   └── workflows/
│       └── publish-pypi.yml   # CI: publica no PyPI ao criar release
├── src/
│   └── jobsearch/
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
├── jobsearch.db               # Banco SQLite (gerado com --db)
├── vagas_*.json               # Resultados em JSON
└── vagas_*.xlsx               # Resultados em Excel
```

## Exemplos de Uso

### Buscar vagas de Python no Brasil

```bash
jobsearch "python developer" -c br -l remote
```

### Buscar vagas de Go com filtro

```bash
jobsearch "golang" --filter-include backend --filter-exclude senior
```

### Buscar em todos os ATS

```bash
jobsearch "backend engineer" -g ats -m 10
```

## Contribuindo

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

## Licença

Este projeto é uso pessoal/educação.
