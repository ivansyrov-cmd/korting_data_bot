# -*- coding: utf-8 -*-
"""Статическая страница сверки ТТХ для GitHub Pages."""
from __future__ import annotations

import json
from pathlib import Path

from .paths import CHANGELOG_PAGE

PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>KORTING — изменения ТТХ</title>
  <style>
    :root {
      --bg: #f4f1ec;
      --ink: #161616;
      --muted: #6b6560;
      --card: #fff;
      --line: #e4ddd4;
      --old: #8a2f2f;
      --new: #1f6a45;
      --accent: #c45c26;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font: 16px/1.45 "Segoe UI", "Helvetica Neue", Arial, sans-serif;
      background: var(--bg);
      color: var(--ink);
    }
    header {
      background: #161616;
      color: #fff;
      padding: 28px 20px 24px;
    }
    header .wrap, main, .empty { max-width: 980px; margin: 0 auto; }
    header h1 { margin: 0 0 6px; font-size: 24px; font-weight: 650; letter-spacing: .02em; }
    header p { margin: 0; color: #cfc8c0; font-size: 14px; }
    .stats {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      margin: -18px auto 20px;
      max-width: 980px;
      padding: 0 20px;
    }
    .stat {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 14px 16px;
      box-shadow: 0 8px 24px rgba(22,22,22,.04);
    }
    .stat b { display: block; font-size: 28px; line-height: 1.1; }
    .stat span { color: var(--muted); font-size: 13px; }
    .toolbar {
      max-width: 980px;
      margin: 0 auto 18px;
      padding: 0 20px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }
    input[type="search"] {
      flex: 1 1 240px;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px 12px;
      font: inherit;
    }
    .tabs { display: flex; gap: 6px; flex-wrap: wrap; }
    .tabs button {
      border: 1px solid var(--line);
      background: #fff;
      border-radius: 999px;
      padding: 8px 12px;
      font: inherit;
      cursor: pointer;
    }
    .tabs button.on { background: #161616; color: #fff; border-color: #161616; }
    .card {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px 18px;
      margin: 0 20px 12px;
      max-width: 980px;
      margin-left: auto;
      margin-right: auto;
    }
    .card h2 { margin: 0 0 4px; font-size: 18px; }
    .card h2 a { color: inherit; text-decoration: none; border-bottom: 1px solid var(--accent); }
    .card .cat { color: var(--muted); font-size: 13px; margin-bottom: 6px; }
    .card .prod-link { display: inline-block; font-size: 13px; margin: 0 0 10px; color: var(--accent); word-break: break-all; }
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th, td { text-align: left; padding: 8px 6px; vertical-align: top; border-top: 1px solid var(--line); }
    th { color: var(--muted); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
    .old { color: var(--old); }
    .new { color: var(--new); }
    .empty {
      padding: 48px 20px;
      color: var(--muted);
    }
    footer { padding: 24px 20px 40px; color: var(--muted); font-size: 13px; text-align: center; }
    @media (max-width: 700px) {
      .stats { grid-template-columns: 1fr; }
      th:nth-child(1), td:nth-child(1) { width: 28%; }
    }
  </style>
</head>
<body>
  <header>
    <div class="wrap">
      <h1>KORTING · изменения ТТХ</h1>
      <p id="dates">Сверка появится после обновления таблицы на Диске</p>
    </div>
  </header>
  <section class="stats" id="stats" hidden>
    <div class="stat"><b id="n-changed">0</b><span>моделей с изменёнными ТТХ</span></div>
    <div class="stat"><b id="n-added">0</b><span>новых моделей</span></div>
    <div class="stat"><b id="n-removed">0</b><span>нет в выгрузке</span></div>
  </section>
  <div class="toolbar" id="toolbar" hidden>
    <input type="search" id="q" placeholder="Поиск: модель, категория, параметр">
    <div class="tabs">
      <button type="button" data-tab="changed" class="on">Изменённые</button>
      <button type="button" data-tab="added">Новые</button>
      <button type="button" data-tab="removed">Нет в выгрузке</button>
    </div>
  </div>
  <main id="list"></main>
  <p class="empty" id="empty">Сверки изменений пока нет. Когда таблица на Яндекс.Диске обновится, здесь появится сравнение: модель, параметр, было → стало.</p>
  <footer id="foot"></footer>
  <script id="data" type="application/json">__CHANGELOG_JSON__</script>
  <script>
    const data = JSON.parse(document.getElementById("data").textContent);
    const has = (data.changed && data.changed.length) || (data.added && data.added.length) || (data.removed && data.removed.length);
    const $ = (id) => document.getElementById(id);
    function label(name) {
      return String(name || "");
    }
    function cell(text) {
      const td = document.createElement("td");
      td.textContent = text || "—";
      return td;
    }
    function render() {
      const tab = document.querySelector(".tabs button.on").dataset.tab;
      const q = ($("q").value || "").trim().toLowerCase();
      const list = $("list");
      list.innerHTML = "";
      let rows = data[tab] || [];
      if (q) {
        rows = rows.filter((m) => {
          const blob = [m.model, m.name, m.category, m.url, ...(m.fields || []).map((f) => [f.name, f.old, f.new].join(" "))].join(" ").toLowerCase();
          return blob.includes(q);
        });
      }
      if (!rows.length) {
        const p = document.createElement("p");
        p.className = "empty";
        p.textContent = has ? "Ничего не найдено" : "Сверки изменений пока нет.";
        list.appendChild(p);
        return;
      }
      for (const m of rows) {
        const card = document.createElement("div");
        card.className = "card";
        const h = document.createElement("h2");
        if (m.url) {
          const a = document.createElement("a");
          a.href = m.url;
          a.textContent = m.model || "без модели";
          a.target = "_blank";
          a.rel = "noopener";
          h.appendChild(a);
        } else {
          h.textContent = m.model || "без модели";
        }
        card.appendChild(h);
        const cat = document.createElement("div");
        cat.className = "cat";
        cat.textContent = [m.category, m.name].filter(Boolean).join(" · ");
        if (cat.textContent) card.appendChild(cat);
        if (m.url) {
          const link = document.createElement("a");
          link.className = "prod-link";
          link.href = m.url;
          link.textContent = m.url;
          link.target = "_blank";
          link.rel = "noopener";
          card.appendChild(link);
        }
        if (tab === "changed" && m.fields && m.fields.length) {
          const table = document.createElement("table");
          table.innerHTML = "<thead><tr><th>Параметр</th><th>Было</th><th>Стало</th><th>Ссылка</th></tr></thead>";
          const tb = document.createElement("tbody");
          m.fields.forEach((f, i) => {
            const tr = document.createElement("tr");
            tr.appendChild(cell(label(f.name)));
            const o = cell(f.old);
            o.className = "old";
            const n = cell(f.new);
            n.className = "new";
            tr.appendChild(o);
            tr.appendChild(n);
            const urlCell = document.createElement("td");
            if (i === 0 && m.url) {
              const a = document.createElement("a");
              a.href = m.url;
              a.textContent = "korting.ru";
              a.target = "_blank";
              a.rel = "noopener";
              urlCell.appendChild(a);
            } else {
              urlCell.textContent = i === 0 ? "—" : "";
            }
            tr.appendChild(urlCell);
            tb.appendChild(tr);
          });
          table.appendChild(tb);
          card.appendChild(table);
        } else if (tab === "added") {
          const p = document.createElement("div");
          p.textContent = "Новая модель в выгрузке";
          card.appendChild(p);
        } else if (tab === "removed") {
          const p = document.createElement("div");
          p.textContent = "Больше нет в выгрузке";
          card.appendChild(p);
        }
        list.appendChild(card);
      }
    }
    if (has) {
      $("empty").hidden = true;
      $("stats").hidden = false;
      $("toolbar").hidden = false;
      $("n-changed").textContent = (data.changed || []).length;
      $("n-added").textContent = (data.added || []).length;
      $("n-removed").textContent = (data.removed || []).length;
      const dates = [];
      if (data.old_date || data.new_date) dates.push("Было: " + (data.old_date || "—") + " → стало: " + (data.new_date || "—"));
      $("dates").textContent = dates.join(" ");
      $("foot").textContent = data.generated ? ("Сверка собрана " + data.generated) : "";
      $("q").addEventListener("input", render);
      document.querySelectorAll(".tabs button").forEach((btn) => {
        btn.addEventListener("click", () => {
          document.querySelectorAll(".tabs button").forEach((b) => b.classList.remove("on"));
          btn.classList.add("on");
          render();
        });
      });
      render();
    }
  </script>
</body>
</html>
"""


def render_changelog_page(payload: dict | None, path: Path = CHANGELOG_PAGE) -> Path:
    data = payload or {
        "old_date": "",
        "new_date": "",
        "generated": "",
        "changed": [],
        "added": [],
        "removed": [],
    }
    raw = json.dumps(data, ensure_ascii=False)
    raw = raw.replace("<", "\\u003c").replace(">", "\\u003e")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PAGE.replace("__CHANGELOG_JSON__", raw), encoding="utf-8")
    return path
