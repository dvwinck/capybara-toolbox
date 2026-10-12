#!/usr/bin/env python3
# ar-board 1.1.0 - painel local de aprovar/rejeitar (somente stdlib, sem rede externa)
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Diogo Winck
#
# Uso:
#   ar_board.py serve   DIR [--port N] [--open] [--exit-on-finish]
#   ar_board.py wait    DIR [--timeout SEGUNDOS]     # bloqueia ate o usuario clicar "Concluir"
#   ar_board.py summary DIR [--json]                  # resumo das decisoes (le decisions.json)
#   ar_board.py build   DIR                           # gera board.html offline (fallback sem localhost)
#   ar_board.py check   DIR                           # valida batch.json
import argparse
import base64
import json
import mimetypes
import os
import re
import secrets
import signal
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

VERSION = "1.1.0"
DECISIONS = {"approved", "rejected", "maybe"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
MAX_BODY = 1_000_000
MAX_COMMENT = 5000

# Capybara Toolbox mascot: inline in the page header and as the favicon (CSP allows img-src data:).
MASCOT_BODY = '<defs><clipPath id="cbx-disc"><circle cx="128" cy="128" r="124"/></clipPath></defs> <circle cx="128" cy="128" r="124" fill="#CDEBE8"/> <path d="M26 206c22-9 38 9 62 0s38 9 62 0 38 9 62 0 22 5 28 2" stroke="#7CC6C4" stroke-width="7" fill="none" stroke-linecap="round" opacity=".75" clip-path="url(#cbx-disc)"/> <ellipse cx="116" cy="132" rx="72" ry="58" fill="#B98B5B"/> <rect x="140" y="116" width="86" height="64" rx="28" fill="#A97A4C"/> <ellipse cx="84" cy="86" rx="15" ry="13" fill="#8F6740"/> <ellipse cx="84" cy="87" rx="8" ry="7" fill="#D3AE82"/> <ellipse cx="156" cy="142" rx="10" ry="6.5" fill="#D98E6A" opacity=".55"/> <circle cx="146" cy="115" r="6.5" fill="#2B1D14"/> <circle cx="148.2" cy="112.8" r="2.2" fill="#fff"/> <ellipse cx="216" cy="131" rx="10.5" ry="8.5" fill="#3A2A20"/> <path d="M166 156q15 9 30 0" stroke="#3A2A20" stroke-width="3.6" fill="none" stroke-linecap="round"/> <circle cx="112" cy="70" r="19" fill="#F2A93B"/> <circle cx="105" cy="64" r="5" fill="#F8C766" opacity=".8"/> <path d="M112 52c2-8 10-13 19-11-2 8-10 13-19 11z" fill="#5F8F3F"/> <rect x="44" y="170" width="168" height="66" rx="12" fill="#C8553D"/> <path d="M44 182a12 12 0 0 1 12-12h144a12 12 0 0 1 12 12v8H44z" fill="#9E3F2C"/> <rect x="112" y="184" width="32" height="20" rx="5" fill="#E9C46A"/> <rect x="124" y="190" width="8" height="8" rx="2" fill="#9E3F2C"/> <circle cx="62" cy="222" r="3.2" fill="#E7B8A8"/> <circle cx="194" cy="222" r="3.2" fill="#E7B8A8"/>'
MASCOT_SVG = '<svg class="mascot" viewBox="0 0 256 256" aria-hidden="true" focusable="false">' + MASCOT_BODY + "</svg>"
FAVICON = "data:image/svg+xml;base64," + base64.b64encode(
    ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">' + MASCOT_BODY + "</svg>").encode("utf-8")
).decode("ascii")


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def write_private(path, text):
    """Grava texto com permissao 0600 desde a criacao e sem seguir symlinks plantados."""
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)


# ---------------------------------------------------------------- batch

def validate(b):
    errs = []
    if not isinstance(b, dict):
        return ["a raiz do batch.json deve ser um objeto"]
    for k in ("batch_id", "title"):
        if not isinstance(b.get(k), str) or not b[k].strip():
            errs.append(f"campo '{k}' e obrigatorio (string)")
    if "round" in b and (not isinstance(b["round"], int) or isinstance(b["round"], bool) or b["round"] < 1):
        errs.append("campo 'round' deve ser inteiro >= 1")
    items = b.get("items")
    if not isinstance(items, list) or not items:
        return errs + ["'items' deve ser uma lista nao vazia"]
    seen = set()
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            errs.append(f"item {i}: deve ser objeto")
            continue
        iid = it.get("id")
        if not isinstance(iid, str) or not iid:
            errs.append(f"item {i}: 'id' obrigatorio")
        elif iid in seen:
            errs.append(f"item {i}: id duplicado '{iid}'")
        else:
            seen.add(iid)
        if not isinstance(it.get("title"), str) or not it["title"].strip():
            errs.append(f"item {i}: 'title' obrigatorio")
        for k in ("tag", "image"):
            if it.get(k) is not None and not isinstance(it[k], str):
                errs.append(f"item {i}: '{k}' deve ser string")
        if it.get("meta") is not None and not isinstance(it["meta"], dict):
            errs.append(f"item {i}: 'meta' deve ser objeto")
        r = it.get("risk")
        if r is not None and (not isinstance(r, dict) or any(k in r and not isinstance(r[k], str) for k in ("level", "text"))):
            errs.append(f"item {i}: 'risk' deve ser objeto com 'level' e 'text' em texto")
        f = it.get("fields")
        if f is None:  # null conta como omitido, como nos outros campos opcionais
            f = []
        if not isinstance(f, list) or any(
            not isinstance(x, dict) or not isinstance(x.get("label"), str) or not isinstance(x.get("text"), str)
            for x in f
        ):
            errs.append(f"item {i}: 'fields' deve ser lista de {{label, text}} (texto)")
    return errs


def load_batch(d):
    p = Path(d) / "batch.json"
    if not p.exists():
        raise SystemExit(f"nao encontrei {p}")
    try:
        b = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"batch.json nao e JSON valido: {e}")
    errs = validate(b)
    if errs:
        raise SystemExit("batch.json invalido:\n- " + "\n- ".join(errs))
    return b


def round_of(b):
    return int(b.get("round", 1))


def valid_state(s):
    """True se s tem o formato que o Store escreve (protege contra edicao manual do arquivo)."""
    if not isinstance(s, dict) or not isinstance(s.get("items"), dict):
        return False
    r = s.get("round")
    if not isinstance(r, int) or isinstance(r, bool):
        return False  # 'round' vira parte do nome do arquivo arquivado: so inteiro
    if not isinstance(s.get("batch_note", ""), str):
        return False
    for e in s["items"].values():
        if not isinstance(e, dict):
            return False
        d, c = e.get("decision"), e.get("comment")
        if d is not None and (not isinstance(d, str) or d not in DECISIONS):
            return False
        if c is not None and not isinstance(c, str):
            return False
    return True


def read_state(d, batch):
    """Le decisions.json da pasta; None se ausente, ilegivel ou de outro lote/rodada."""
    try:
        s = json.loads((Path(d) / "decisions.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not valid_state(s):
        return None
    if s.get("batch_id") != batch["batch_id"] or s.get("round") != round_of(batch):
        return None
    return s


# ---------------------------------------------------------------- estado

class Store:
    def __init__(self, d):
        self.dir = Path(d).resolve()
        self.lock = threading.Lock()
        self.batch = load_batch(self.dir)
        self.path = self.dir / "decisions.json"
        self.ids = {it["id"] for it in self.batch["items"]}
        self.round = round_of(self.batch)
        self.exit_cb = None
        state = None
        if self.path.exists():
            try:
                state = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                state = None
            if not valid_state(state):
                state = None
        if state and (state.get("batch_id") != self.batch["batch_id"] or state.get("round") != self.round):
            n, old = 0, self.dir / f"decisions.r{state.get('round', 'x')}.json"
            while old.exists():
                n += 1
                old = self.dir / f"decisions.r{state.get('round', 'x')}.{n}.json"
            os.replace(self.path, old)
            state = None
        if state and state.get("finished"):
            state["finished"] = False  # painel reaberto: o usuario pode rejulgar; precisa concluir de novo
            state.pop("finished_at", None)
        if not state:
            state = {
                "batch_id": self.batch["batch_id"],
                "round": self.round,
                "started_at": now(),
                "updated_at": now(),
                "finished": False,
                "batch_note": "",
                "items": {},
            }
        self.state = state
        self.save()

    def save(self):
        self.state["updated_at"] = now()
        tmp = self.path.with_suffix(".tmp")
        write_private(tmp, json.dumps(self.state, ensure_ascii=False, indent=2))
        os.replace(tmp, self.path)

    def set_item(self, iid, body):
        if not isinstance(iid, str) or iid not in self.ids:
            raise ValueError("id desconhecido")
        has_d, has_c = "decision" in body, "comment" in body
        d, c = body.get("decision"), body.get("comment")
        if has_d and d is not None and (not isinstance(d, str) or d not in DECISIONS):
            raise ValueError("decisao invalida")
        if has_c and not isinstance(c, str):
            raise ValueError("comment deve ser string")
        with self.lock:
            e = {k: v for k, v in self.state["items"].get(iid, {}).items() if k != "at"}
            if has_d:
                if d is None:
                    e.pop("decision", None)
                else:
                    e["decision"] = d
            if has_c:
                c = c[:MAX_COMMENT]
                if c.strip():
                    e["comment"] = c
                else:
                    e.pop("comment", None)
            if e:
                e["at"] = now()
                self.state["items"][iid] = e
            else:
                self.state["items"].pop(iid, None)
            self.state["finished"] = False
            self.state.pop("finished_at", None)
            self.save()

    def set_note(self, text):
        if not isinstance(text, str):
            raise ValueError("text deve ser string")
        with self.lock:
            self.state["batch_note"] = text[:MAX_COMMENT]
            self.save()

    def set_finished(self, flag):
        with self.lock:
            self.state["finished"] = bool(flag)
            if flag:
                self.state["finished_at"] = now()
            else:
                self.state.pop("finished_at", None)
            self.save()

    def reset(self):
        with self.lock:
            self.state["items"] = {}
            self.state["batch_note"] = ""
            self.state["finished"] = False
            self.state.pop("finished_at", None)
            self.save()


def render_summary(batch, state, as_json=False):
    groups = {"approved": [], "rejected": [], "maybe": [], "pending": []}
    for it in batch["items"]:
        e = state.get("items", {}).get(it["id"], {})
        row = {"id": it["id"], "title": it["title"], "comment": e.get("comment", "")}
        groups[e.get("decision", "pending")].append(row)
    if as_json:
        return json.dumps(
            {
                "batch_id": batch["batch_id"],
                "round": state.get("round"),
                "finished": state.get("finished", False),
                "batch_note": state.get("batch_note", ""),
                **groups,
            },
            ensure_ascii=False,
            indent=2,
        )
    names = [("approved", "Aprovados"), ("rejected", "Rejeitados"), ("maybe", "Talvez"), ("pending", "Sem decisao")]
    out = [f"# AR board - {batch['title']} (lote {batch['batch_id']}, rodada {state.get('round')})"]
    out.append(f"Concluido pelo usuario: {'sim' if state.get('finished') else 'NAO (parcial)'}")
    for key, label in names:
        rows = groups[key]
        out.append(f"\n## {label} ({len(rows)})")
        for r in rows:
            line = f"- {r['id']} - {r['title']}"
            if r["comment"]:
                line += f"\n    comentario do usuario: {r['comment']!r}"
            out.append(line)
    if state.get("batch_note"):
        out.append(f"\n## Nota geral do lote\n{state['batch_note']}")
    return "\n".join(out)


# ---------------------------------------------------------------- pagina

PAGE = r"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<link rel="icon" href="__FAVICON__">
<style>
:root{color-scheme:dark;accent-color:var(--acc);--bg:#1a1410;--panel:#241c15;--panel2:#2e241b;--line:#46382b;--fg:#f4ebdf;--mut:#b09c85;--ok:#8cc474;--ok-bg:#1d2b1a;--no:#ef8570;--no-bg:#34201a;--mb:#ecb856;--mb-bg:#342a14;--acc:#f29a45;--accfg:#2a1a0c}
@media (prefers-color-scheme:light){:root{color-scheme:light;--bg:#f7f0e5;--panel:#fffaf2;--panel2:#f1e7d8;--line:#dccbb3;--fg:#2c2018;--mut:#6b5645;--ok:#2d6a1f;--ok-bg:#e3f0da;--no:#a8381f;--no-bg:#fbe4dd;--mb:#8a5a00;--mb-bg:#faecc8;--acc:#a24d0d;--accfg:#ffffff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:20px 16px 60px}
header{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap}
h1{font-size:22px;margin:0 0 4px}.sub{color:var(--mut);font-size:13px}
.badge{font-size:12px;padding:3px 10px;border-radius:99px;border:1px solid var(--line);white-space:nowrap}
.badge.on{color:var(--ok);border-color:var(--ok)}.badge.off{color:var(--mb);border-color:var(--mb)}
.keys{display:flex;flex-wrap:wrap;gap:6px 14px;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:14px 0 10px;font-size:13px;color:var(--mut)}
kbd{font:600 11px ui-monospace,Menlo,monospace;background:var(--panel2);border:1px solid var(--line);border-radius:5px;padding:1px 6px;color:var(--fg);margin-right:4px}
.keys .auto{margin-left:auto;cursor:pointer;color:var(--fg)}#hint{flex-basis:100%;color:var(--acc);font-weight:600}#hint:empty{display:none}
.bar{height:5px;background:var(--panel2);border-radius:9px;overflow:hidden;margin-bottom:16px}.bar>i{display:block;height:100%;width:0;background:var(--acc);transition:width .2s}
.grid{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:16px}
@media (max-width:860px){.grid{grid-template-columns:minmax(0,1fr)}}
.grid>*,.row>div,.meta b{min-width:0;overflow-wrap:anywhere}
.card,.side,.res{background:var(--panel);border:1px solid var(--line);border-radius:14px}
.card{padding:22px}.side{padding:16px;align-self:start}
.pill{display:inline-block;font-size:12px;color:var(--mut);border:1px solid var(--line);border-radius:99px;padding:2px 10px;margin-bottom:12px}
.card h2{font-size:21px;margin:0 0 16px;line-height:1.3}
.state{display:inline-block;margin-left:8px;font-size:12px;font-weight:600;padding:2px 10px;border-radius:99px}
.state.approved{color:var(--ok);background:var(--ok-bg)}.state.rejected{color:var(--no);background:var(--no-bg)}.state.maybe{color:var(--mb);background:var(--mb-bg)}
.box{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.row{display:grid;grid-template-columns:86px 1fr;gap:12px;padding:6px 0}
.row>b{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--mut);padding-top:3px}
code{font:13px ui-monospace,Menlo,monospace;background:var(--bg);border:1px solid var(--line);border-radius:5px;padding:0 5px}
.risk{display:inline-block;border-radius:99px;padding:2px 12px;font-size:13px;border:1px solid}
.risk.baixo{color:var(--ok);background:var(--ok-bg);border-color:var(--ok)}.risk.medio{color:var(--mb);background:var(--mb-bg);border-color:var(--mb)}.risk.alto{color:var(--no);background:var(--no-bg);border-color:var(--no)}
.card img{max-width:100%;border-radius:10px;border:1px solid var(--line);margin:0 0 14px;display:block}
.meta{margin:0 0 12px;font-size:13px}.meta div{display:flex;justify-content:space-between;gap:10px;padding:3px 0;border-bottom:1px dashed var(--line)}.meta span{color:var(--mut)}.meta b{text-align:right;font-weight:600}
.side label{display:block;font-size:12px;color:var(--mut);margin:6px 0}
textarea{width:100%;min-height:84px;resize:vertical;background:var(--panel2);color:var(--fg);border:1px solid var(--line);border-radius:10px;padding:10px;font:inherit;font-size:14px}
textarea:focus{outline:2px solid var(--acc);outline-offset:0}
.btns{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
button{font:inherit;font-size:14px;cursor:pointer;color:var(--fg);background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:8px 14px}
button:hover{border-color:var(--mut)}button kbd{margin:0 0 0 6px}
button.ok{color:var(--ok);border-color:var(--ok);background:var(--ok-bg)}button.no{color:var(--no);border-color:var(--no);background:var(--no-bg)}button.mb{color:var(--mb);border-color:var(--mb);background:var(--mb-bg)}
button.on{box-shadow:0 0 0 2px currentColor inset}
.chips{display:flex;flex-wrap:wrap;gap:6px}.chips button{width:34px;height:34px;padding:0;font-size:13px}
.chips .approved{background:var(--ok-bg);color:var(--ok);border-color:var(--ok)}.chips .rejected{background:var(--no-bg);color:var(--no);border-color:var(--no)}.chips .maybe{background:var(--mb-bg);color:var(--mb);border-color:var(--mb)}.chips .cur{outline:2px solid var(--acc);outline-offset:1px}
.res{margin-top:16px;padding:18px}.res h3{margin:0 0 10px;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--mut)}
.counts{display:flex;gap:16px;flex-wrap:wrap;font-size:14px;margin-bottom:12px}
.done{display:none;margin-top:12px;padding:12px 14px;border-radius:10px;background:var(--ok-bg);border:1px solid var(--ok);color:var(--ok)}
button.go{background:var(--acc);border-color:var(--acc);color:var(--accfg);font-weight:600}
.brand{display:flex;align-items:center;gap:14px}.mascot{width:56px;height:56px;flex:none}
.foot{margin-top:28px;text-align:center;font-size:12px;color:var(--mut)}
</style></head><body><div class="wrap">
<header><div class="brand">__MASCOT__<div><h1 id="ttl"></h1><div class="sub" id="sub"></div></div></div><span class="badge" id="live"></span></header>
<div class="keys"><span><kbd>A</kbd>aprovar</span><span><kbd>R</kbd>rejeitar</span><span><kbd>M</kbd>talvez</span><span><kbd>S</kbd>pular</span><span><kbd>C</kbd>comentar</span><span><kbd>Esc</kbd>sair do campo</span><span><kbd>&larr;</kbd><kbd>&rarr;</kbd>navegar</span><label class="auto"><input type="checkbox" id="auto" checked> avancar ao decidir</label><span id="hint"></span></div>
<div class="bar"><i id="prog"></i></div>
<div class="grid">
  <section class="card" id="card"></section>
  <aside class="side">
    <div class="meta" id="meta"></div>
    <label for="cmt">Comentario deste item (C foca &middot; salva sozinho). Vale para qualquer decisao.</label>
    <textarea id="cmt" placeholder="Por que aprovou, rejeitou ou ficou em duvida? Isso e o que mais treina o agente."></textarea>
    <div class="btns">
      <button class="ok" id="bA">&#10003; Aprovar<kbd>A</kbd></button>
      <button class="no" id="bR">&#10007; Rejeitar<kbd>R</kbd></button>
      <button class="mb" id="bM">&asymp; Talvez<kbd>M</kbd></button>
      <button id="bS">Pular<kbd>S</kbd></button>
      <button id="bP">&larr; Anterior</button><button id="bN">Proximo &rarr;</button>
    </div>
    <div class="chips" id="chips"></div>
  </aside>
</div>
<section class="res">
  <h3>Resultado</h3>
  <div class="counts" id="counts"></div>
  <label for="note" class="sub">Nota geral do lote (batch_note)</label>
  <textarea id="note" placeholder="Observacao geral sobre este lote inteiro..."></textarea>
  <div class="btns">
    <button class="go" id="bF">Concluir e avisar o agente</button>
    <button id="bD">Baixar JSON</button><button id="bC">Copiar</button><button id="bX">Limpar</button>
  </div>
  <div class="done" id="done"></div>
</section>
<div class="foot">ar-board &middot; Capybara Toolbox</div>
</div>
<script>
(function(){
const BOOT = __BOOT__;
const B = BOOT.batch, items = B.items, S = BOOT.state;
S.items = S.items || {};
const $ = s => document.querySelector(s);
const LBL = {approved:'Aprovado', rejected:'Rejeitado', maybe:'Talvez'};
const LS = 'ar-board:' + B.batch_id + ':r' + (B.round || 1);
let idx = 0, timers = {};

function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function rich(s){return esc(s).replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\n/g,'<br>');}
function norm(s){return String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();}
function ent(id){return S.items[id] || (S.items[id] = {});}
function tidy(id){const e=S.items[id]; if(e && !e.decision && !e.comment) delete S.items[id];}

function persistLocal(){try{localStorage.setItem(LS, JSON.stringify(S));}catch(e){}}
function setLive(ok){
  const b = $('#live');
  if(!BOOT.live){b.className='badge off';b.textContent='arquivo local \u2014 use Copiar';return;}
  b.className = 'badge ' + (ok ? 'on' : 'off');
  b.textContent = ok ? '\u25CF ao vivo' : 'sem conexao \u2014 use Copiar';
}
const inflight = new Set();
function post(path, body){
  if(!BOOT.live){persistLocal();return Promise.resolve(true);}
  const pr = fetch(path,{method:'POST',keepalive:true,headers:{'Content-Type':'application/json','X-AR-Token':BOOT.token},body:JSON.stringify(body)})
    .then(r=>{if(!r.ok)throw new Error(r.status);setLive(true);return true;})
    .catch(()=>{setLive(false);persistLocal();return false;});
  inflight.add(pr); pr.then(() => inflight.delete(pr));
  return pr;
}
let pend = {};
function queue(key, path, body){
  pend[key] = {path:path, body:body};
  clearTimeout(timers[key]);
  timers[key] = setTimeout(() => sendPend(key), 350);
}
function sendPend(key){
  const q = pend[key]; clearTimeout(timers[key]);
  if(!q) return Promise.resolve(true);
  delete pend[key];
  return post(q.path, q.body);
}
function flushAll(){return Promise.all(Object.keys(pend).map(sendPend));}
window.addEventListener('pagehide', flushAll);
document.addEventListener('visibilitychange', () => {if(document.visibilityState === 'hidden') flushAll();});
if(!BOOT.live){try{const raw=localStorage.getItem(LS); if(raw){const o=JSON.parse(raw); S.items=o.items||{}; S.batch_note=o.batch_note||'';}}catch(e){}}

function counts(){
  const c={approved:0,rejected:0,maybe:0};
  items.forEach(it=>{const d=(S.items[it.id]||{}).decision; if(d) c[d]++;});
  c.pending = items.length - c.approved - c.rejected - c.maybe;
  return c;
}
function exportObj(){
  return {batch_id:B.batch_id, round:B.round||1, finished:!!S.finished, batch_note:S.batch_note||'',
    items: items.map(it=>{const e=S.items[it.id]||{}; return {id:it.id,title:it.title,decision:e.decision||null,comment:e.comment||''};})};
}
function imgSrc(p){return /^data:/.test(p) ? p : '/files/' + p.split('/').map(encodeURIComponent).join('/') + '?t=' + encodeURIComponent(BOOT.token);}

function render(){
  const it = items[idx], e = S.items[it.id] || {};
  $('#ttl').textContent = B.title;
  $('#sub').textContent = (B.subtitle ? B.subtitle + ' \u00B7 ' : '') + 'Lote: ' + B.batch_id + ' \u00B7 ' + items.length + ' itens \u00B7 rodada ' + (B.round || 1);
  let h = '<span class="pill">' + (idx+1) + '/' + items.length + ' \u00B7 ' + esc(it.id) + (it.tag ? ' \u00B7 ' + esc(it.tag) : '') + '</span>';
  if(e.decision) h += '<span class="state ' + e.decision + '">' + LBL[e.decision] + '</span>';
  h += '<h2>' + esc(it.title) + '</h2>';
  if(it.image) h += '<img alt="" src="' + esc(imgSrc(it.image)) + '">';
  h += '<div class="box">';
  (it.fields || []).forEach(f => { h += '<div class="row"><b>' + esc(f.label) + '</b><div>' + rich(f.text) + '</div></div>'; });
  if(it.risk){
    const lvl = norm(it.risk.level);
    h += '<div class="row"><b>Risco</b><div><span class="risk ' + (['baixo','medio','alto'].includes(lvl) ? lvl : 'medio') + '">' + esc(it.risk.level || '') + (it.risk.text ? ' \u2014 ' + esc(it.risk.text) : '') + '</span></div></div>';
  }
  h += '</div>';
  $('#card').innerHTML = h;
  $('#meta').innerHTML = Object.entries(it.meta || {}).map(([k,v]) => '<div><span>' + esc(k) + '</span><b>' + esc(v) + '</b></div>').join('');
  const cm = $('#cmt'); if(cm.value !== (e.comment || '')) cm.value = e.comment || '';
  ['A:approved','R:rejected','M:maybe'].forEach(p => { const [k,d] = p.split(':'); $('#b'+k).classList.toggle('on', e.decision === d); });
  $('#chips').innerHTML = items.map((x,i) => { const d=(S.items[x.id]||{}).decision||''; return '<button class="' + d + (i===idx?' cur':'') + '" data-i="' + i + '" title="' + esc(x.title) + '">' + (i+1) + '</button>'; }).join('');
  const c = counts();
  $('#prog').style.width = ((items.length - c.pending) / items.length * 100) + '%';
  $('#counts').innerHTML = '<span style="color:var(--ok)">\u2713 ' + c.approved + ' aprovados</span><span style="color:var(--no)">\u2717 ' + c.rejected + ' rejeitados</span><span style="color:var(--mb)">\u2248 ' + c.maybe + ' talvez</span><span style="color:var(--mut)">' + c.pending + ' sem decisao</span>';
  const n = $('#note'); if(n.value !== (S.batch_note || '')) n.value = S.batch_note || '';
  $('#bF').style.display = BOOT.live ? '' : 'none';
  const dn = $('#done');
  if(S.finished){dn.style.display='block';dn.textContent='Concluido. Volte ao Claude Code e diga "terminei" \u2014 o agente le as decisoes sozinho.';} else dn.style.display='none';
}

function go(i){idx = Math.max(0, Math.min(items.length-1, i)); render();}
function decide(d){
  const it = items[idx], e = ent(it.id);
  if(e.decision === d) delete e.decision; else e.decision = d;
  tidy(it.id); S.finished = false;
  post('/api/item', {id: it.id, decision: e.decision || null});
  const decided = S.items[it.id] && S.items[it.id].decision;
  if(auto && decided && idx < items.length-1){
    idx++;
    showHint(LBL[decided] + ': ' + it.id + ' — use ← para voltar e comentar');
  }
  render();
}
let auto = true, hintTimer;
try{auto = localStorage.getItem('ar-board:auto') !== '0';}catch(e){}
$('#auto').checked = auto;
$('#auto').onchange = ev => {auto = ev.target.checked; try{localStorage.setItem('ar-board:auto', auto ? '1' : '0');}catch(e){}};
function showHint(t){const h = $('#hint'); h.textContent = t; clearTimeout(hintTimer); hintTimer = setTimeout(() => h.textContent = '', 4500);}

$('#cmt').addEventListener('input', ev => {
  const id = items[idx].id, v = ev.target.value;
  const e = ent(id); if(v.trim()) e.comment = v; else delete e.comment; tidy(id);
  queue('c:' + id, '/api/item', {id: id, comment: v});
  if(S.finished){S.finished = false; render();}
});
$('#note').addEventListener('input', ev => {
  S.batch_note = ev.target.value;
  queue('note', '/api/note', {text: S.batch_note});
});
$('#chips').addEventListener('click', ev => {const b = ev.target.closest('button'); if(b) go(+b.dataset.i);});
$('#bA').onclick = () => decide('approved'); $('#bR').onclick = () => decide('rejected'); $('#bM').onclick = () => decide('maybe');
$('#bS').onclick = () => go(idx+1); $('#bN').onclick = () => go(idx+1); $('#bP').onclick = () => go(idx-1);

document.addEventListener('keydown', ev => {
  if(ev.ctrlKey || ev.metaKey || ev.altKey) return;
  if(ev.repeat && ev.key === 'Enter' && ev.target.tagName === 'BUTTON'){ev.preventDefault(); return;}
  const typing = (ev.target.tagName || '').toLowerCase() === 'textarea';
  if(ev.key === 'Escape'){ if(typing) ev.target.blur(); return; }
  if(typing) return;
  const k = ev.key.toLowerCase();
  if(ev.repeat && (k === 'a' || k === 'r' || k === 'm')) return;
  if(k === 'a') decide('approved');
  else if(k === 'r') decide('rejected');
  else if(k === 'm') decide('maybe');
  else if(k === 's') go(idx+1);
  else if(k === 'c'){ev.preventDefault(); $('#cmt').focus();}
  else if(ev.key === 'ArrowRight') go(idx+1);
  else if(ev.key === 'ArrowLeft') go(idx-1);
});

function flash(btn, txt){const o = btn.textContent; btn.textContent = txt; setTimeout(() => btn.textContent = o, 1400);}
$('#bC').onclick = () => {
  const txt = 'AR-BOARD-RESULT\n' + JSON.stringify(exportObj(), null, 2);
  const fallback = () => {const t = document.createElement('textarea'); t.value = txt; document.body.appendChild(t); t.select(); try{document.execCommand('copy');}catch(e){} t.remove();};
  (navigator.clipboard ? navigator.clipboard.writeText(txt).catch(fallback) : Promise.resolve(fallback())).then(() => flash($('#bC'), 'Copiado!'));
};
$('#bD').onclick = () => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(exportObj(), null, 2)], {type:'application/json'}));
  a.download = 'ar-board-' + B.batch_id + '-r' + (B.round || 1) + '.json'; a.click();
};
$('#bX').onclick = () => {
  if(!confirm('Limpar todas as decisoes e comentarios deste lote?')) return;
  Object.keys(timers).forEach(k => clearTimeout(timers[k])); pend = {};
  S.items = {}; S.batch_note = ''; S.finished = false; Promise.all(Array.from(inflight)).then(() => post('/api/reset', {})); persistLocal(); idx = 0; render();
};
$('#bF').onclick = () => {
  const c = counts();
  if(c.pending && !confirm(c.pending + ' itens sem decisao. Concluir mesmo assim?')) return;
  flushAll().then(() => post('/api/finish', {finished: true})).then(ok => {
    S.finished = ok; render();
    if(!ok) alert('Sem conexao com o servidor. Use Copiar e cole o resultado no chat.');
  });
};

setLive(BOOT.live);
const first = items.findIndex(it => !(S.items[it.id] || {}).decision);
idx = first < 0 ? 0 : first;
render();
})();
</script></body></html>
"""


def render_page(batch, state, token, live):
    boot = json.dumps({"batch": batch, "state": state, "token": token, "live": live}, ensure_ascii=False)
    boot = boot.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    title = batch["title"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    values = {"TITLE": title, "BOOT": boot, "MASCOT": MASCOT_SVG, "FAVICON": FAVICON}
    # one pass: substituted text (user title/batch) is never rescanned for tokens
    return re.sub(r"__(TITLE|BOOT|MASCOT|FAVICON)__", lambda m: values[m.group(1)], PAGE).encode("utf-8")


# ---------------------------------------------------------------- servidor

def make_handler(store, token):
    class H(BaseHTTPRequestHandler):
        server_version = "ar-board"
        sys_version = ""  # o cabecalho Server nao revela a versao do Python

        def version_string(self):
            return self.server_version

        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype, extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _host_ok(self):
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
            return host in ("127.0.0.1", "localhost")

        def _token_ok(self, qs):
            got = self.headers.get("X-AR-Token") or (qs.get("t") or [""])[0]
            return secrets.compare_digest(got.encode("utf-8"), token.encode("utf-8"))

        def do_GET(self):
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            if not self._host_ok() or not self._token_ok(qs):
                return self._json(403, {"error": "forbidden"})
            if u.path == "/":
                csp = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                       "img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'; "
                       "frame-ancestors 'none'")
                with store.lock:
                    page = render_page(store.batch, store.state, token, True)
                return self._send(200, page, "text/html; charset=utf-8", {"Content-Security-Policy": csp})
            if u.path == "/api/state":
                with store.lock:
                    snap = json.loads(json.dumps(store.state))
                return self._json(200, snap)
            if u.path.startswith("/files/"):
                rel = unquote(u.path[len("/files/"):])
                p = (store.dir / rel).resolve()
                if store.dir not in p.parents or p.suffix.lower() not in IMG_EXT or not p.is_file():
                    return self._json(404, {"error": "not found"})
                ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
                return self._send(200, p.read_bytes(), ctype, {"Content-Security-Policy": "sandbox"})
            return self._json(404, {"error": "not found"})

        def do_POST(self):
            u = urlparse(self.path)
            if not self._host_ok() or not self._token_ok({}):
                return self._json(403, {"error": "forbidden"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n < 0:
                    raise ValueError("content-length invalido")
                if n > MAX_BODY:
                    return self._json(413, {"error": "too large"})
                body = json.loads(self.rfile.read(n) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError("corpo deve ser objeto")
                if u.path == "/api/item":
                    store.set_item(body.get("id"), body)
                elif u.path == "/api/note":
                    store.set_note(body.get("text", ""))
                elif u.path == "/api/finish":
                    flag = body.get("finished", True)
                    if not isinstance(flag, bool):
                        raise ValueError("finished deve ser booleano")
                    store.set_finished(flag)
                    if flag and store.exit_cb:
                        threading.Thread(target=store.exit_cb, daemon=True).start()
                elif u.path == "/api/reset":
                    store.reset()
                else:
                    return self._json(404, {"error": "not found"})
                return self._json(200, {"ok": True})
            except (ValueError, json.JSONDecodeError) as e:
                return self._json(400, {"error": str(e)})

    return H


# ---------------------------------------------------------------- comandos

def cmd_serve(a):
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", a.port), BaseHTTPRequestHandler)
    except OSError as e:
        raise SystemExit(f"nao consegui abrir a porta {a.port}: {e}")
    try:
        store = Store(a.dir)
    except BaseException:
        srv.server_close()
        raise
    token = secrets.token_urlsafe(16)
    srv.RequestHandlerClass = make_handler(store, token)
    if a.exit_on_finish:
        store.exit_cb = lambda: (time.sleep(0.6), srv.shutdown())
    signal.signal(signal.SIGTERM, lambda s, f: threading.Thread(target=srv.shutdown, daemon=True).start())
    url = f"http://127.0.0.1:{srv.server_address[1]}/?t={token}"
    info = store.dir / "server.json"
    write_private(info, json.dumps({"url": url, "pid": os.getpid(), "started_at": now()}))
    print(f"AR-BOARD URL: {url}", flush=True)
    print(f"AR-BOARD DECISOES: {store.path}", flush=True)
    if a.open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            info.unlink()
        except OSError:
            pass


def cmd_wait(a):
    batch = load_batch(a.dir)
    end = time.time() + a.timeout if a.timeout else None
    while True:
        s = read_state(a.dir, batch)
        if s and s.get("finished"):
            print(render_summary(batch, s))
            return 0
        if end and time.time() > end:
            print("TIMEOUT: o usuario ainda nao concluiu o lote.")
            return 2
        time.sleep(1)


def cmd_summary(a):
    batch = load_batch(a.dir)
    state = read_state(a.dir, batch) or {"round": round_of(batch), "items": {}}
    print(render_summary(batch, state, as_json=a.json))
    return 0


def cmd_build(a):
    batch = json.loads(json.dumps(load_batch(a.dir)))
    root = Path(a.dir).resolve()
    for it in batch["items"]:
        img = it.get("image")
        if img and not img.startswith("data:"):
            p = (root / img).resolve()
            if root in p.parents and p.suffix.lower() in IMG_EXT and p.is_file() and p.stat().st_size < 2_000_000:
                ctype = mimetypes.guess_type(p.name)[0] or "image/png"
                it["image"] = f"data:{ctype};base64," + base64.b64encode(p.read_bytes()).decode()
            else:
                it.pop("image")
    state = {"batch_id": batch["batch_id"], "round": int(batch.get("round", 1)), "items": {}, "batch_note": ""}
    out = root / "board.html"
    out.write_bytes(render_page(batch, state, "", False))
    print(f"AR-BOARD ARQUIVO: {out}")
    return 0


def cmd_check(a):
    b = load_batch(a.dir)
    print(f"ok: {len(b['items'])} itens, lote {b['batch_id']}, rodada {b.get('round', 1)}")
    return 0


def main():
    ap = argparse.ArgumentParser(prog="ar_board.py", description="ar-board: painel local de aprovar/rejeitar (somente stdlib).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    s.add_argument("dir")
    s.add_argument("--port", type=int, default=0)
    s.add_argument("--open", action="store_true")
    s.add_argument("--exit-on-finish", action="store_true")
    s.set_defaults(fn=cmd_serve)
    w = sub.add_parser("wait")
    w.add_argument("dir")
    w.add_argument("--timeout", type=int, default=0)
    w.set_defaults(fn=cmd_wait)
    m = sub.add_parser("summary")
    m.add_argument("dir")
    m.add_argument("--json", action="store_true")
    m.set_defaults(fn=cmd_summary)
    b = sub.add_parser("build")
    b.add_argument("dir")
    b.set_defaults(fn=cmd_build)
    c = sub.add_parser("check")
    c.add_argument("dir")
    c.set_defaults(fn=cmd_check)
    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)


if __name__ == "__main__":
    main()
