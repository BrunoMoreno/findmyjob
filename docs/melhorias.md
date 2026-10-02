# Análise e Plano de Melhorias - JobSearch

Documento detalhado com o diagnóstico do projeto, problemas identificados, oportunidades de evolução e o plano de implementação técnica por branches.

---

## 1. Diagnóstico do Projeto

O **JobSearch** é um buscador de vagas focado em portais de emprego e sistemas ATS (Applicant Tracking Systems) via dorks de motores de busca (DuckDuckGo e Google Custom Search). O projeto possui uma proposta enxuta e eficiente, mas acumulou algumas inconsistências técnicas, campos incompletos e ausência de automação de testes e consultas.

---

## 2. Problemas e Limitações Identificados

### 2.1 Incompatibilidade de Versão Python
- **Local:** `pyproject.toml` e `src/jobsearch/cli.py`
- **Problema:** O `pyproject.toml` especifica `requires-python = ">=3.8"`, mas o código em `cli.py` utiliza anotações de tipo de união da PEP 604 (`dict | None`, `list[str] | None`), válidas nativamente apenas no Python 3.10+. No Python 3.8/3.9 ocorre erro fatal ao importar o pacote.
- **Ação:** Adicionar `from __future__ import annotations` nos arquivos de código para retrocompatibilidade ou atualizar a restrição do projeto.

### 2.2 Código Incompleto e Efeito Colateral em `filter_jobs`
- **Local:** `src/jobsearch/cli.py` (`filter_jobs`)
- **Problema:**
  1. Os parâmetros `min_date` e `max_date` constam na assinatura da função e na docstring, mas não têm nenhuma linha de implementação no corpo da função.
  2. `max_days: int = 3` é o valor padrão. Quando o usuário executa `--filter-include termo`, a função descarta silenciosamente qualquer vaga com mais de 3 dias caso haja data, enquanto uma busca sem filtros não descarta. Além disso, não há opção `--max-days` na linha de comando.
- **Ação:** Implementar o filtro real de datas (`min_date` e `max_date`), ajustar o padrão de `max_days` para não filtrar datas inesperadamente e expor flag CLI `--max-days`.

### 2.3 Dados Descartados e Colunas Vazias no SQLite
- **Local:** `src/jobsearch/cli.py` (`search_ddg`, `search_google`, `main`, `save_to_db`)
- **Problema:**
  1. O campo `body` retornado pelo DuckDuckGo e `snippet` retornado pelo Google contêm o resumo/descrição da vaga, mas são descartados nos backends.
  2. A tabela SQLite possui colunas `company TEXT` e `description TEXT`, mas no loop principal (`main`) esses campos sequer são adicionados ao dicionário da vaga. O banco sempre salva `NULL` nessas colunas.
  3. A extração de empresa (Company) não existe, mesmo sendo trivial extraí-la a partir de URLs de ATS (ex.: `jobs.lever.co/<empresa>/...`, `boards.greenhouse.io/<empresa>/...`, `<empresa>.gupy.io`) e de títulos formatados.
- **Ação:** Capturar `body`/`snippet`, extrair a empresa automaticamente de URLs e títulos, preencher os campos `company` e `description` no fluxo principal e exibi-los no JSON, Excel e SQLite.

### 2.4 Deduplicação e Parâmetros de Tracking em URLs
- **Local:** `src/jobsearch/cli.py` (`main`)
- **Problema:** URLs que apontam para a mesma vaga mas trazem parâmetros de campanhas ou analytics (ex.: `utm_source`, `utm_medium`, `lever-source`) são tratadas como vagas distintas, gerando duplicidade no conjunto em memória e no banco SQLite.
- **Ação:** Implementar função de normalização de URLs (removendo UTMs e parâmetros de rastreamento conhecidos).

### 2.5 Exportação e Ferramentas do Banco SQLite
- **Local:** `src/jobsearch/cli.py`
- **Problema:**
  1. O usuário salva no SQLite com `--db`, mas a ferramenta não oferece comandos para listar ou analisar o que foi salvo.
  2. Falta de formato CSV, que é padrão, leve e sem dependências extras.
  3. O modo interativo não pergunta sobre o uso do banco SQLite.
- **Ação:**
  - Adicionar suporte à exportação CSV (`--csv`).
  - Adicionar utilitários CLI: `--db-stats` (estatísticas do banco), `--db-list` (listar últimas vagas) e `--db-export` (exportar do banco para arquivo).
  - Incluir pergunta sobre `--db` no modo interativo.

### 2.6 Cobertura de Testes e CI/CD
- **Local:** `tests/test_main.py` e `.github/workflows/`
- **Problema:**
  1. Nenhuma função de banco de dados (`save_to_db`, `_ensure_schema`, `_get_db_path`) possui testes unitários.
  2. Os testes atuais poluem o terminal com logs de retry do DuckDuckGo durante a execução.
  3. Não há workflow do GitHub Actions para rodar a suíte de testes automaticamente em PRs e pushes (há apenas o de publicação no PyPI em releases).
- **Ação:** Adicionar testes completos de SQLite e novos recursos, silenciar saída nos mocks de teste e criar workflow de CI `.github/workflows/tests.yml`.

### 2.7 Manutenção e Configuração do Repositório
- **Local:** `.gitignore` e `src/jobsearch/__init__.py`
- **Problema:**
  1. `.gitignore` não inclui arquivos de banco de dados (`*.db`, `*.sqlite`, `*.sqlite3`).
  2. `src/jobsearch/__init__.py` não atualizou `__all__` com as novas funções e exceções públicas.
- **Ação:** Atualizar `.gitignore` e alinhar `__all__`.

---

## 3. Plano de Implementação em Branches

Para manter o histórico do Git limpo, modular e de fácil revisão, a implementação será realizada nas seguintes branches:

1. **`fix/compat-exports-gitignore`**:
   - Adicionar `from __future__ import annotations`.
   - Atualizar `__all__` e exports em `src/jobsearch/__init__.py`.
   - Atualizar `.gitignore` para ignorar bancos SQLite (`*.db`, `*.sqlite`, `*.sqlite3`).

2. **`feat/data-enrichment-company-description`**:
   - Capturar `body`/`snippet` como descrição em `search_ddg` e `search_google`.
   - Implementar extração automática de empresa (`extract_company`) a partir de links de ATS e títulos.
   - Implementar normalização de URLs (`normalize_url`) para deduplicação limpa.
   - Integrar `company` e `description` ao fluxo principal, ao SQLite e às colunas do Excel com larguras dinâmicas.
   - Adicionar testes unitários para as novas funções.

3. **`fix/filter-jobs-and-date-handling`**:
   - Implementar suporte real para `min_date` e `max_date` em `filter_jobs`.
   - Tornar o filtro por idade opcional (`max_days: int | None = None`).
   - Adicionar flag CLI `--max-days`.
   - Adicionar testes unitários específicos para todos os cenários de filtro de data.

4. **`feat/csv-export-and-db-tools`**:
   - Implementar exportação para CSV (`save_csv` e flag `--csv`).
   - Implementar utilitários para o banco: `--db-stats`, `--db-list` e `--db-export`.
   - Atualizar o modo interativo para incluir a opção de banco SQLite.
   - Adicionar testes unitários para a camada SQLite e exportador CSV.

5. **`ci/github-actions-test-workflow`**:
   - Criar workflow `.github/workflows/tests.yml` com matriz de versões Python.
   - Silenciar saídas nos testes de retry.
   - Atualizar o `README.md` com as novas flags e exemplos.
