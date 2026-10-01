# JobSearch - Buscador de Vagas

Buscador de vagas de emprego que utiliza "dorks" (consultas avançadas de busca) para encontrar vagas em portais de emprego e sistemas de acompanhamento de candidatos (ATS).

## Funcionalidades

- **Múltiplas fontes de busca**: Indeed, LinkedIn, Glassdoor + ATS (Greenhouse, Lever, Workday, SmartRecruiters, Ashby, Workable)
- **Suporte a 11 países**: Brasil, Portugal, EUA, Reino Unido, Canadá, Alemanha, Espanha, México, Argentina, Colômbia e Chile
- **Dois backends de busca**: DuckDuckGo (padrão) ou Google Custom Search API
- **Filtros por palavras-chave**: Incluir ou excluir termos nos resultados
- **Saída em JSON e XLSX**: Planilha formatada com hyperlinks e filtros
- **Retry automático**: Tentativas configuráveis em caso de falha de rede
- **Modo interativo ou CLI**: Interface amigável ou argumentos de linha de comando

## Instalação

```bash
# Crie um ambiente virtual
python -m venv env
source env/bin/activate  # Linux/Mac
# env\Scripts\activate   # Windows

# Instale as dependências
pip install -r requirements.txt
```

## Uso

### Modo Interativo

```bash
python main.py
```

O script irá perguntar sobre o cargo, país, local e fontes de busca.

### Modo CLI (Linha de Comando)

```bash
# Busca geral
python main.py "backend engineer" -l remote -l latam

# Busca apenas no Brasil
python main.py "backend engineer" -c br

# Brasil + remoto + apenas ATS
python main.py "backend engineer" -c br -l remote --group ats

# Com filtros de palavras-chave
python main.py "backend engineer" --filter-include senior --filter-exclude junior

# Listar países disponíveis
python main.py --list-countries

# Apenas mostrar as queries (sem executar busca)
python main.py "backend engineer" --show-queries
```

### Usando Google Custom Search (Opcional)

```bash
export GOOGLE_API_KEY="sua_chave"
export GOOGLE_CX="seu_cx"
python main.py "backend engineer" -b google
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

## Saída

O script gera dois arquivos:

1. **`.json`**: Dados brutos com metadados da busca
2. **`.xlsx`**: Planilha formatada com:
   - Aba "Vagas": Lista de vagas com hyperlinks
   - Aba "Busca": Metadados da pesquisa

## Testes

```bash
python -m pytest test_main.py -v
# ou
python test_main.py
```

## Estrutura do Projeto

```
jobsearch/
├── main.py                 # Script principal
├── test_main.py            # Testes automatizados
├── requirements.txt        # Dependências
├── .gitignore             # Arquivos ignorados pelo git
├── __init__.py            # Torna o diretório um pacote Python
├── env/                   # Virtual environment
├── vagas_*.json           # Resultados em JSON
└── vagas_*.xlsx           # Resultados em Excel
```

## Exemplos de Uso

### Buscar vagas de Python no Brasil

```bash
python main.py "python developer" -c br -l remote
```

### Buscar vagas de Go com filtro

```bash
python main.py "golang" --filter-include backend --filter-exclude senior
```

### Buscar em todos os ATS

```bash
python main.py "backend engineer" -g ats -m 10
```

## Contribuindo

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

## Licença

Este projeto é uso pessoal/educação.
