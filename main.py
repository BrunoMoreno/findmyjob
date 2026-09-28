#!/usr/bin/env python3
"""
Busca de vagas via dorks (site:dominio "cargo" "local").

Modo interativo (pergunta tudo):
    python job_search.py

Modo direto:
    python job_search.py "backend engineer" -l remote -l latam
    python job_search.py "node.js" -l brazil --group ats --max 5 -o vagas

Dependências:
    pip install ddgs requests openpyxl

Backend google (opcional):
    export GOOGLE_API_KEY=...
    export GOOGLE_CX=...
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# Portais de vagas tradicionais
BOARDS = [
    "indeed.com",
    "linkedin.com/jobs",
    "glassdoor.com.br",
    "gupy.io",
    "infojobs.com.br",
]

# ATS usados pelas empresas (ouro escondido)
ATS = [
    "boards.greenhouse.io",
    "jobs.lever.co",
    "myworkdayjobs.com",
    "smartrecruiters.com",
    "jobs.ashbyhq.com",
    "apply.workable.com",
]

GROUPS = {"boards": BOARDS, "ats": ATS, "all": BOARDS + ATS}


def build_query(domain: str, role: str, location: str) -> str:
    return f'site:{domain} "{role}" "{location}"'


def search_ddg(query: str, max_results: int) -> list[dict]:
    try:
        from ddgs import DDGS
    except ImportError:
        sys.exit("Instale com: pip install ddgs")
    results = DDGS().text(query, max_results=max_results)
    return [
        {"title": r.get("title", ""), "link": r.get("href", "")} for r in results
    ]


def search_google(query: str, max_results: int) -> list[dict]:
    key = os.environ.get("GOOGLE_API_KEY")
    cx = os.environ.get("GOOGLE_CX")
    if not key or not cx:
        sys.exit("Defina GOOGLE_API_KEY e GOOGLE_CX para usar o backend google.")
    resp = requests.get(
        "https://www.googleapis.com/customsearch/v1",
        params={"key": key, "cx": cx, "q": query, "num": min(max_results, 10)},
        timeout=15,
    )
    resp.raise_for_status()
    return [
        {"title": i.get("title", ""), "link": i.get("link", "")}
        for i in resp.json().get("items", [])
    ]


BACKENDS = {"ddg": search_ddg, "google": search_google}


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or default


def interactive_prompts(args: argparse.Namespace) -> None:
    print("=== Busca de vagas ===\n")
    while not args.role:
        args.role = ask("Qual vaga você está buscando? (ex: backend engineer)")

    locs = ask("Local(is), separados por vírgula", "remote, latam")
    args.local = [x.strip() for x in locs.split(",") if x.strip()]

    print("\nOnde buscar?")
    print("  1) Portais (Indeed, LinkedIn, Glassdoor, Gupy, InfoJobs)")
    print("  2) ATS das empresas (Greenhouse, Lever, Workday, ...)")
    print("  3) Todos")
    args.group = {"1": "boards", "2": "ats", "3": "all"}.get(ask("Opção", "3"), "all")

    max_raw = ask("Resultados por query", str(args.max))
    args.max = int(max_raw) if max_raw.isdigit() else args.max

    default_out = default_basename(args.role)
    args.output = ask("Nome base dos arquivos (gera .json e .xlsx)", default_out)
    print()


def default_basename(role: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", role.lower()).strip("-") or "vagas"
    return f"vagas_{slug}_{datetime.now():%Y%m%d_%H%M}"


def save_json(path: str, meta: dict, jobs: list[dict]) -> None:
    payload = {**meta, "total": len(jobs), "jobs": jobs}
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_xlsx(path: str, meta: dict, jobs: list[dict]) -> bool:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        print("[aviso] openpyxl não instalado (pip install openpyxl); .xlsx não foi gerado.")
        return False

    wb = Workbook()
    ws = wb.active
    ws.title = "Vagas"

    headers = ["#", "Título", "Link", "Domínio", "Local", "Query"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="305496")
        cell.alignment = Alignment(vertical="center")

    for i, j in enumerate(jobs, start=1):
        ws.append([i, j["title"], j["link"], j["domain"], j["location"], j["query"]])
        link_cell = ws.cell(row=i + 1, column=3)
        link_cell.hyperlink = j["link"]
        link_cell.font = Font(color="0563C1", underline="single")

    for col, width in zip("ABCDEF", (5, 60, 70, 24, 14, 60)):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"
    if jobs:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(jobs) + 1}"

    info = wb.create_sheet("Busca")
    for k, v in meta.items():
        info.append([k, ", ".join(v) if isinstance(v, list) else v])
    info.append(["total", len(jobs)])
    info.column_dimensions["A"].width = 16
    info.column_dimensions["B"].width = 40

    wb.save(path)
    return True


def main() -> None:
    p = argparse.ArgumentParser(description="Busca de vagas com dorks de busca")
    p.add_argument("role", nargs="?", help='cargo, ex: "backend engineer" (omita para modo interativo)')
    p.add_argument("-l", "--local", action="append", default=[], help="local (repita para vários)")
    p.add_argument("-g", "--group", choices=GROUPS, default="all")
    p.add_argument("-b", "--backend", choices=BACKENDS, default="ddg")
    p.add_argument("-m", "--max", type=int, default=8, help="resultados por query")
    p.add_argument("-o", "--output", help="nome base dos arquivos de saída, gera .json e .xlsx (padrão: automático)")
    p.add_argument("-i", "--interactive", action="store_true", help="força o modo interativo")
    p.add_argument("--delay", type=float, default=2.0, help="segundos entre queries")
    p.add_argument("--show-queries", action="store_true", help="só imprime as queries")
    args = p.parse_args()

    if args.interactive or not args.role:
        interactive_prompts(args)

    locations = args.local or ["remote"]
    domains = GROUPS[args.group]
    queries = [
        (d, loc, build_query(d, args.role, loc))
        for d in domains
        for loc in locations
    ]

    if args.show_queries:
        for _, _, q in queries:
            print(q)
        return

    search = BACKENDS[args.backend]
    seen: set[str] = set()
    jobs: list[dict] = []

    try:
        for domain, loc, query in queries:
            print(f"\n== {domain} | {loc} ==")
            print(f"   {query}")
            try:
                results = search(query, args.max)
            except Exception as e:  # rede, rate limit, chave inválida...
                print(f"   [erro] {e}")
                time.sleep(args.delay)
                continue

            new = [r for r in results if r["link"] and r["link"] not in seen]
            if not new:
                print("   (nenhum resultado novo)")
            for r in new:
                seen.add(r["link"])
                jobs.append({
                    "title": r["title"],
                    "link": r["link"],
                    "domain": domain,
                    "location": loc,
                    "query": query,
                })
                print(f"   - {r['title']}\n     {r['link']}")
            time.sleep(args.delay)
    except KeyboardInterrupt:
        print("\n[interrompido] salvando o que foi encontrado até aqui...")

    base = args.output or default_basename(args.role)
    base = re.sub(r"\.(json|xlsx?)$", "", base, flags=re.IGNORECASE)
    meta = {
        "role": args.role,
        "locations": locations,
        "group": args.group,
        "backend": args.backend,
        "searched_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_json(f"{base}.json", meta, jobs)
    saved = [f"{base}.json"]
    if save_xlsx(f"{base}.xlsx", meta, jobs):
        saved.append(f"{base}.xlsx")
    print(f"\n{len(jobs)} vagas únicas encontradas. Salvo em: {', '.join(saved)}")


if __name__ == "__main__":
    main()