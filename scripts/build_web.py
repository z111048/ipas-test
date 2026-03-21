#!/usr/bin/env python3
"""Generate the complete iPAS study platform HTML file."""

import json
from pathlib import Path

ROOT = Path('/home/james/projects/ipas-test')
OUT = ROOT / 'data' / '初級'
DOCS_OUT = ROOT / 'docs'


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def js_str(s: str) -> str:
    """Escape string for JavaScript."""
    return s.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')


def build_html():
    s1q = load_json(OUT / 'questions' / 'subject1_questions.json')
    s2q = load_json(OUT / 'questions' / 'subject2_questions.json')
    m1 = load_json(OUT / 'questions' / 'mock_exam1.json')
    m2 = load_json(OUT / 'questions' / 'mock_exam2.json')
    sample = load_json(OUT / 'questions' / 'sample_exam.json')

    guide_dir = OUT / 'guide'
    s1g = load_json(guide_dir / 'subject1_guide.json') if (guide_dir / 'subject1_guide.json').exists() else {}
    s2g = load_json(guide_dir / 'subject2_guide.json') if (guide_dir / 'subject2_guide.json').exists() else {}

    data_js = f"""
const SUBJECT1_QUESTIONS = {json.dumps(s1q, ensure_ascii=False)};
const SUBJECT2_QUESTIONS = {json.dumps(s2q, ensure_ascii=False)};
const MOCK_EXAM1 = {json.dumps(m1, ensure_ascii=False)};
const MOCK_EXAM2 = {json.dumps(m2, ensure_ascii=False)};
const SAMPLE_EXAM = {json.dumps(sample, ensure_ascii=False)};
const SUBJECT1_GUIDE = {json.dumps(s1g, ensure_ascii=False)};
const SUBJECT2_GUIDE = {json.dumps(s2g, ensure_ascii=False)};
"""

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>iPAS AI應用規劃師（初級）備考平台</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --primary:#1e3a5f;
  --primary-light:#2d5480;
  --accent:#3498db;
  --accent-hover:#2980b9;
  --bg:#f0f4f8;
  --card:#ffffff;
  --text:#2c3e50;
  --text-light:#7f8c8d;
  --border:#dde3ea;
  --success:#27ae60;
  --error:#e74c3c;
  --warning:#f39c12;
  --sidebar-w:260px;
}}
body{{font-family:'Segoe UI',Arial,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;display:flex;flex-direction:column}}
/* Header */
header{{background:var(--primary);color:#fff;padding:0 1.5rem;height:56px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100;box-shadow:0 2px 8px rgba(0,0,0,.3)}}
header h1{{font-size:1.1rem;font-weight:700;letter-spacing:.5px}}
header span{{font-size:.8rem;opacity:.7}}
/* Layout */
.layout{{display:flex;flex:1;overflow:hidden}}
/* Sidebar */
aside{{width:var(--sidebar-w);background:var(--primary);color:#fff;overflow-y:auto;flex-shrink:0;padding-bottom:2rem}}
.sidebar-section{{padding:.5rem 0}}
.sidebar-label{{font-size:.7rem;text-transform:uppercase;letter-spacing:1px;color:rgba(255,255,255,.5);padding:.5rem 1rem .25rem;font-weight:600}}
.sidebar-item{{display:block;padding:.55rem 1rem .55rem 1.25rem;cursor:pointer;font-size:.85rem;border-left:3px solid transparent;transition:all .15s;text-decoration:none;color:rgba(255,255,255,.85)}}
.sidebar-item:hover{{background:rgba(255,255,255,.08);color:#fff}}
.sidebar-item.active{{background:rgba(255,255,255,.12);border-left-color:var(--accent);color:#fff;font-weight:600}}
.sidebar-divider{{height:1px;background:rgba(255,255,255,.1);margin:.5rem 1rem}}
/* Main */
main{{flex:1;overflow-y:auto;padding:1.5rem 2rem}}
.page{{display:none}}
.page.active{{display:block}}
/* Cards */
.card{{background:var(--card);border-radius:10px;padding:1.5rem;margin-bottom:1.25rem;box-shadow:0 1px 4px rgba(0,0,0,.08);border:1px solid var(--border)}}
.card h2{{color:var(--primary);margin-bottom:.75rem;font-size:1.1rem}}
.card h3{{color:var(--primary-light);margin-bottom:.5rem;font-size:1rem}}
/* Section headings */
.page-title{{font-size:1.4rem;font-weight:700;color:var(--primary);margin-bottom:.25rem}}
.page-sub{{color:var(--text-light);font-size:.9rem;margin-bottom:1.5rem}}
/* Practice Questions */
.q-card{{background:var(--card);border-radius:10px;padding:1.25rem 1.5rem;margin-bottom:1rem;border:1px solid var(--border);box-shadow:0 1px 3px rgba(0,0,0,.06)}}
.q-num{{font-size:.75rem;color:var(--text-light);margin-bottom:.4rem;font-weight:600;text-transform:uppercase;letter-spacing:.5px}}
.q-text{{font-size:.95rem;line-height:1.7;margin-bottom:.9rem;color:var(--text)}}
.options{{display:flex;flex-direction:column;gap:.4rem}}
.option-btn{{text-align:left;padding:.55rem .85rem;border:1.5px solid var(--border);border-radius:6px;cursor:pointer;font-size:.875rem;background:#fafbfc;transition:all .15s;line-height:1.5}}
.option-btn:hover{{border-color:var(--accent);background:#eaf4fb}}
.option-btn.correct{{background:#eafaf1;border-color:var(--success);color:#1a7a44;font-weight:600}}
.option-btn.wrong{{background:#fdf2f2;border-color:var(--error);color:#9b2020}}
.explanation{{margin-top:.9rem;padding:.75rem 1rem;background:#f0f7ff;border-left:3px solid var(--accent);border-radius:4px;font-size:.85rem;line-height:1.6;display:none}}
.explanation.show{{display:block}}
.reveal-btn{{margin-top:.7rem;padding:.45rem 1rem;background:var(--primary);color:#fff;border:none;border-radius:5px;cursor:pointer;font-size:.82rem;transition:background .15s}}
.reveal-btn:hover{{background:var(--primary-light)}}
/* Explanation card */
.card-toggle{{margin-top:.6rem;padding:.35rem .85rem;background:transparent;color:var(--accent);border:1.5px solid var(--accent);border-radius:5px;cursor:pointer;font-size:.78rem;transition:all .15s;display:none}}
.card-toggle.show{{display:inline-block}}
.card-toggle:hover{{background:var(--accent);color:#fff}}
.q-card-panel{{margin-top:.75rem;border:1.5px solid #c8e4f8;border-radius:8px;overflow:hidden;display:none}}
.q-card-panel.show{{display:block}}
.q-card-panel .card-header{{background:#1e3a5f;color:#fff;padding:.45rem .85rem;font-size:.78rem;font-weight:700;letter-spacing:.5px;text-transform:uppercase}}
.q-card-panel .card-body{{background:#f7fbff;padding:.75rem .9rem;display:flex;flex-direction:column;gap:.55rem}}
.card-row{{display:flex;gap:.5rem;align-items:flex-start;font-size:.83rem;line-height:1.5}}
.card-row .cr-icon{{flex-shrink:0;width:1.3rem;font-size:.9rem}}
.card-row .cr-label{{color:var(--text-light);font-weight:600;white-space:nowrap;min-width:4.5rem}}
.card-row .cr-val{{color:var(--text)}}
.freq-bar{{display:inline-flex;align-items:center;gap:.3rem}}
.freq-bar .fb-dot{{width:10px;height:10px;border-radius:50%;background:var(--border)}}
.freq-bar .fb-dot.filled{{background:var(--accent)}}
.freq-label{{font-size:.78rem;font-weight:700;color:var(--accent)}}
/* Guide content */
.guide-content{{font-size:.875rem;line-height:1.85;color:var(--text)}}
.guide-content p{{margin-bottom:.8rem}}
.guide-content p:last-child{{margin-bottom:0}}
.guide-notice{{background:#fff9ec;border:1px solid #f6c64a;border-radius:8px;padding:.75rem 1rem;margin-bottom:1rem;font-size:.84rem;line-height:1.6}}
.guide-subtopics{{margin-bottom:1rem}}
.guide-meta{{display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;margin-bottom:1rem}}
.guide-badge{{background:#e8f4fd;color:var(--primary);border-radius:12px;padding:.2rem .65rem;font-size:.75rem;font-weight:600}}
/* Chapter overview */
.chapter-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1rem}}
.chapter-card{{background:var(--card);border-radius:10px;padding:1.25rem;border:1px solid var(--border);border-top:3px solid var(--accent);box-shadow:0 1px 4px rgba(0,0,0,.06)}}
.chapter-card h3{{color:var(--primary);font-size:.95rem;margin-bottom:.5rem}}
.chapter-card p{{font-size:.82rem;color:var(--text-light);line-height:1.6}}
.chapter-card .tag{{display:inline-block;background:#eaf4fb;color:var(--accent);padding:.2rem .5rem;border-radius:4px;font-size:.72rem;margin-top:.5rem;margin-right:.25rem;font-weight:600}}
/* Mock Exam */
.exam-intro{{text-align:center;padding:2rem}}
.exam-intro h2{{color:var(--primary);font-size:1.3rem;margin-bottom:.5rem}}
.exam-intro .meta{{color:var(--text-light);margin-bottom:1.5rem;font-size:.9rem}}
.start-btn{{padding:.75rem 2rem;background:var(--primary);color:#fff;border:none;border-radius:8px;font-size:1rem;cursor:pointer;font-weight:600;transition:background .2s}}
.start-btn:hover{{background:var(--primary-light)}}
.exam-container{{display:none}}
.exam-header{{display:flex;justify-content:space-between;align-items:center;background:var(--primary);color:#fff;padding:.75rem 1.5rem;border-radius:8px;margin-bottom:1.25rem;position:sticky;top:0;z-index:10}}
.exam-timer{{font-size:1.1rem;font-weight:700;font-family:monospace}}
.exam-timer.warning{{color:#f39c12}}
.exam-timer.danger{{color:#e74c3c}}
.exam-progress{{font-size:.85rem;opacity:.85}}
.submit-exam-btn{{padding:.5rem 1.25rem;background:var(--accent);color:#fff;border:none;border-radius:5px;cursor:pointer;font-weight:600;font-size:.88rem}}
.exam-q{{background:var(--card);border-radius:10px;padding:1.25rem 1.5rem;margin-bottom:1rem;border:1px solid var(--border)}}
.exam-q-num{{font-size:.75rem;color:var(--text-light);margin-bottom:.4rem;font-weight:600}}
.exam-q-text{{font-size:.95rem;line-height:1.7;margin-bottom:.9rem}}
.exam-options{{display:flex;flex-direction:column;gap:.4rem}}
.exam-option{{display:flex;align-items:flex-start;gap:.6rem;padding:.55rem .85rem;border:1.5px solid var(--border);border-radius:6px;cursor:pointer;font-size:.875rem;background:#fafbfc;transition:all .15s;line-height:1.5}}
.exam-option:hover{{border-color:var(--accent);background:#eaf4fb}}
.exam-option.selected{{border-color:var(--accent);background:#eaf4fb;font-weight:600}}
.exam-option.result-correct{{background:#eafaf1;border-color:var(--success);color:#1a7a44}}
.exam-option.result-wrong{{background:#fdf2f2;border-color:var(--error);color:#9b2020}}
.exam-option input{{margin-top:2px;flex-shrink:0}}
/* Results */
.result-card{{text-align:center;padding:2rem;background:var(--card);border-radius:10px;border:1px solid var(--border)}}
.score-big{{font-size:3.5rem;font-weight:800;margin:.5rem 0}}
.score-big.pass{{color:var(--success)}}
.score-big.fail{{color:var(--error)}}
.score-label{{font-size:1rem;color:var(--text-light);margin-bottom:1rem}}
.result-detail{{margin-top:1.5rem;text-align:left}}
.result-detail .exam-q{{border-left:4px solid var(--border)}}
.result-detail .exam-q.correct-q{{border-left-color:var(--success)}}
.result-detail .exam-q.wrong-q{{border-left-color:var(--error)}}
.result-explanation{{margin-top:.75rem;padding:.65rem .9rem;background:#f0f7ff;border-left:3px solid var(--accent);border-radius:4px;font-size:.83rem;line-height:1.6}}
/* Stats */
.stats-row{{display:flex;gap:1rem;margin-bottom:1.5rem;flex-wrap:wrap}}
.stat-box{{flex:1;min-width:120px;background:var(--card);border-radius:8px;padding:1rem;text-align:center;border:1px solid var(--border)}}
.stat-num{{font-size:1.8rem;font-weight:800;color:var(--primary)}}
.stat-label{{font-size:.75rem;color:var(--text-light);margin-top:.2rem}}
/* Progress bar */
.progress-bar{{height:8px;background:var(--border);border-radius:4px;margin:.5rem 0 1rem;overflow:hidden}}
.progress-fill{{height:100%;background:var(--accent);border-radius:4px;transition:width .3s}}
/* Tag pills */
.pill{{display:inline-block;padding:.2rem .6rem;border-radius:12px;font-size:.75rem;font-weight:600;margin:.15rem}}
.pill-blue{{background:#eaf4fb;color:#2980b9}}
.pill-green{{background:#eafaf1;color:#27ae60}}
.pill-orange{{background:#fef5e7;color:#e67e22}}
/* Mobile menu button */
.menu-btn{{display:none;background:none;border:none;color:#fff;font-size:1.5rem;cursor:pointer;padding:.2rem .5rem;line-height:1;margin-right:.25rem;flex-shrink:0}}
/* Overlay */
.overlay{{display:none;position:fixed;inset:0;top:56px;background:rgba(0,0,0,.45);z-index:199}}
.overlay.show{{display:block}}
/* Responsive */
@media(max-width:900px){{
  aside{{width:220px}}
  main{{padding:1rem 1.25rem}}
}}
@media(max-width:768px){{
  .menu-btn{{display:block}}
  header span{{display:none}}
  aside{{position:fixed;top:56px;left:0;height:calc(100vh - 56px);width:280px;max-height:none;transform:translateX(-100%);transition:transform .25s ease;z-index:200;overflow-y:auto}}
  aside.open{{transform:translateX(0)}}
  main{{padding:1rem;width:100%}}
  .exam-header{{flex-wrap:wrap;gap:.5rem;padding:.65rem 1rem}}
  .exam-timer{{font-size:1rem}}
  .score-big{{font-size:2.5rem}}
  .stats-row{{gap:.6rem}}
  .stat-box{{min-width:80px;padding:.75rem .5rem}}
  .stat-num{{font-size:1.4rem}}
  .chapter-grid{{grid-template-columns:1fr}}
}}
@media(max-width:480px){{
  main{{padding:.75rem}}
  .option-btn{{padding:.65rem .85rem;font-size:.9rem}}
  .exam-option{{padding:.65rem .85rem;font-size:.9rem}}
  .page-title{{font-size:1.15rem}}
  .card{{padding:1rem}}
  .q-card{{padding:1rem}}
  .exam-q{{padding:1rem}}
  .exam-header{{position:relative;top:0}}
  .submit-exam-btn{{padding:.5rem .85rem;font-size:.82rem}}
}}
</style>
</head>
<body>
<header>
  <button class="menu-btn" onclick="toggleSidebar()" aria-label="選單">☰</button>
  <h1>📚 iPAS AI應用規劃師（初級）備考平台</h1>
  <span>科目一 × 科目二 完整備考系統</span>
</header>
<div class="overlay" id="overlay" onclick="toggleSidebar()"></div>
<div class="layout">
<aside>
  <div class="sidebar-section">
    <div class="sidebar-label">總覽</div>
    <a class="sidebar-item active" onclick="showPage('home')">🏠 首頁</a>
  </div>
  <div class="sidebar-divider"></div>
  <div class="sidebar-section">
    <div class="sidebar-label">科目一：人工智慧基礎概論</div>
    <a class="sidebar-item" onclick="showPage('s1-overview')">📖 章節總覽</a>
    <a class="sidebar-item" onclick="showPractice('s1','s1c1')">✏️ 人工智慧概念</a>
    <a class="sidebar-item" onclick="showPractice('s1','s1c2')">✏️ 資料處理與分析</a>
    <a class="sidebar-item" onclick="showPractice('s1','s1c3')">✏️ 機器學習概念</a>
    <a class="sidebar-item" onclick="showPractice('s1','s1c4')">✏️ 鑑別式AI與生成式AI</a>
    <a class="sidebar-item" onclick="showMock('mock1')">🎯 模擬考試（科目一）</a>
  </div>
  <div class="sidebar-divider"></div>
  <div class="sidebar-section">
    <div class="sidebar-label">科目二：生成式AI應用與規劃</div>
    <a class="sidebar-item" onclick="showPage('s2-overview')">📖 章節總覽</a>
    <a class="sidebar-item" onclick="showPractice('s2','s2c1')">✏️ No Code / Low Code</a>
    <a class="sidebar-item" onclick="showPractice('s2','s2c2')">✏️ 生成式AI應用與工具</a>
    <a class="sidebar-item" onclick="showPractice('s2','s2c3')">✏️ 生成式AI導入評估規劃</a>
    <a class="sidebar-item" onclick="showMock('mock2')">🎯 模擬考試（科目二）</a>
  </div>
  <div class="sidebar-divider"></div>
  <div class="sidebar-section">
    <div class="sidebar-label">樣題練習</div>
    <a class="sidebar-item" onclick="showMock('sample')">📝 考試樣題（114年9月版）</a>
  </div>
  <div class="sidebar-divider"></div>
  <div class="sidebar-section">
    <div class="sidebar-label">學習指引 科目一</div>
    <a class="sidebar-item" onclick="showGuide(1,'s1c1')">📖 人工智慧概念</a>
    <a class="sidebar-item" onclick="showGuide(1,'s1c2')">📖 資料處理分析統計</a>
    <a class="sidebar-item" onclick="showGuide(1,'s1c3')">📖 機器學習概念</a>
    <a class="sidebar-item" onclick="showGuide(1,'s1c4')">📖 鑑別式╱生成式AI</a>
  </div>
  <div class="sidebar-divider"></div>
  <div class="sidebar-section">
    <div class="sidebar-label">學習指引 科目二</div>
    <a class="sidebar-item" onclick="showGuide(2,'s2c1')">📖 No Code / Low Code</a>
    <a class="sidebar-item" onclick="showGuide(2,'s2c2')">📖 生成式AI應用與工具</a>
    <a class="sidebar-item" onclick="showGuide(2,'s2c3')">📖 導入評估規劃</a>
  </div>
</aside>

<main>
<!-- HOME -->
<div id="page-home" class="page active">
  <div class="page-title">歡迎使用 iPAS 備考平台</div>
  <div class="page-sub">iPAS AI應用規劃師初級能力鑑定 — 完整備考資源</div>
  <div class="stats-row">
    <div class="stat-box"><div class="stat-num">2</div><div class="stat-label">考試科目</div></div>
    <div class="stat-box"><div class="stat-num">7</div><div class="stat-label">章節單元</div></div>
    <div class="stat-box"><div class="stat-num" id="total-practice-q">0</div><div class="stat-label">章節練習題</div></div>
    <div class="stat-box"><div class="stat-num" id="total-mock-q">0</div><div class="stat-label">模擬考試題</div></div>
  </div>
  <div class="chapter-grid">
    <div class="chapter-card" onclick="showPage('s1-overview')" style="cursor:pointer">
      <h3>科目一：人工智慧基礎概論</h3>
      <p>涵蓋AI基礎概念、資料處理、機器學習及生成式AI等四大主題</p>
      <span class="tag">AI概念</span><span class="tag">資料分析</span><span class="tag">機器學習</span><span class="tag">生成式AI</span>
    </div>
    <div class="chapter-card" onclick="showPage('s2-overview')" style="cursor:pointer">
      <h3>科目二：生成式AI應用與規劃</h3>
      <p>涵蓋No Code/Low Code平台、生成式AI工具及企業導入規劃等三大主題</p>
      <span class="tag">No/Low Code</span><span class="tag">AI工具</span><span class="tag">導入規劃</span>
    </div>
  </div>
  <div class="card" style="margin-top:1rem">
    <h2>📋 考試說明</h2>
    <div style="overflow-x:auto;-webkit-overflow-scrolling:touch">
    <table style="width:100%;border-collapse:collapse;font-size:.88rem;margin-top:.5rem;min-width:360px">
      <tr style="background:#f5f7fa"><th style="padding:.5rem .75rem;text-align:left;border-bottom:1px solid var(--border)">項目</th><th style="padding:.5rem .75rem;text-align:left;border-bottom:1px solid var(--border)">科目一</th><th style="padding:.5rem .75rem;text-align:left;border-bottom:1px solid var(--border)">科目二</th></tr>
      <tr><td style="padding:.5rem .75rem;border-bottom:1px solid var(--border)">科目名稱</td><td style="padding:.5rem .75rem;border-bottom:1px solid var(--border)">人工智慧基礎概論</td><td style="padding:.5rem .75rem;border-bottom:1px solid var(--border)">生成式AI應用與規劃</td></tr>
      <tr><td style="padding:.5rem .75rem;border-bottom:1px solid var(--border)">題型</td><td style="padding:.5rem .75rem;border-bottom:1px solid var(--border)">四選一單選題</td><td style="padding:.5rem .75rem;border-bottom:1px solid var(--border)">四選一單選題</td></tr>
      <tr><td style="padding:.5rem .75rem;border-bottom:1px solid var(--border)">及格標準</td><td style="padding:.5rem .75rem;border-bottom:1px solid var(--border)">60分</td><td style="padding:.5rem .75rem;border-bottom:1px solid var(--border)">60分</td></tr>
      <tr><td style="padding:.5rem .75rem">考試時間</td><td style="padding:.5rem .75rem">90分鐘</td><td style="padding:.5rem .75rem">90分鐘</td></tr>
    </table>
    </div>
  </div>
  <div class="card">
    <h2>🎯 備考建議</h2>
    <ol style="margin-left:1.25rem;line-height:2;font-size:.9rem">
      <li>先閱讀各章節<strong>學習重點</strong>，理解核心概念</li>
      <li>完成各章<strong>章節練習題</strong>，找出薄弱環節</li>
      <li>透過<strong>模擬考試</strong>，熟悉答題節奏與時間管理</li>
      <li>針對錯誤題目，重新複習對應章節</li>
      <li>參考試題解析，理解命題方向與思路</li>
    </ol>
  </div>
</div>

<!-- S1 OVERVIEW -->
<div id="page-s1-overview" class="page">
  <div class="page-title">科目一：人工智慧基礎概論</div>
  <div class="page-sub">評鑑主題：人工智慧概念 / 資料處理與分析概念 / 機器學習概念 / 鑑別式AI與生成式AI概念</div>
  <div class="chapter-grid">
    <div class="chapter-card">
      <h3>3.1 人工智慧概念</h3>
      <p><strong>AI的定義與分類：</strong>分析型AI、預測型AI、生成型AI的特色與應用場景。</p>
      <p style="margin-top:.5rem"><strong>AI治理概念：</strong>人機互動模式（Human-in/over/out-of-the-loop）、EU AI Act風險分級（不可接受/高/有限/低風險）。</p>
      <p style="margin-top:.5rem"><strong>AI應用領域：</strong>醫療保健、金融、製造、教育、零售等行業的AI應用實例。</p>
      <span class="tag">AI分類</span><span class="tag">AI治理</span><span class="tag">EU AI Act</span>
    </div>
    <div class="chapter-card">
      <h3>3.2 資料處理與分析概念</h3>
      <p><strong>資料基本概念：</strong>結構化/非結構化資料、大數據5V特性（Volume/Velocity/Variety/Veracity/Value）。</p>
      <p style="margin-top:.5rem"><strong>ETL流程：</strong>Extract（擷取）→ Transform（轉換：清理、排序、正規化）→ Load（載入）。</p>
      <p style="margin-top:.5rem"><strong>資料隱私與安全：</strong>GDPR、個資法、異常值偵測（Z-score、IQR）。</p>
      <span class="tag">大數據5V</span><span class="tag">ETL</span><span class="tag">資料清理</span><span class="tag">GDPR</span>
    </div>
    <div class="chapter-card">
      <h3>3.3 機器學習概念</h3>
      <p><strong>學習類型：</strong>監督式、非監督式、半監督式、強化學習的定義與適用場景。</p>
      <p style="margin-top:.5rem"><strong>模型評估：</strong>過擬合/欠擬合、Bias-Variance Tradeoff、L1/L2正則化（Lasso/Ridge）。</p>
      <p style="margin-top:.5rem"><strong>常見模型：</strong>決策樹、KNN、SVM、Naive Bayes、K-means分群、PCA降維。</p>
      <span class="tag">監督學習</span><span class="tag">強化學習</span><span class="tag">過擬合</span><span class="tag">正則化</span>
    </div>
    <div class="chapter-card">
      <h3>3.4 鑑別式AI與生成式AI概念</h3>
      <p><strong>鑑別式AI：</strong>直接學習輸入特徵與標籤之間的邊界/關係，用於分類和回歸。</p>
      <p style="margin-top:.5rem"><strong>生成式AI：</strong>LLM、Transformer架構、擴散模型（Diffusion Models），可生成文字/圖像/語音/影片。</p>
      <p style="margin-top:.5rem"><strong>整合應用：</strong>RAG（檢索增強生成）、幻覺問題（Hallucination）、條件語言模型。</p>
      <span class="tag">LLM</span><span class="tag">Transformer</span><span class="tag">RAG</span><span class="tag">Diffusion</span>
    </div>
  </div>
  <div class="card">
    <h2>📊 章節練習題數量</h2>
    <div id="s1-chapter-stats"></div>
  </div>
</div>

<!-- S2 OVERVIEW -->
<div id="page-s2-overview" class="page">
  <div class="page-title">科目二：生成式AI應用與規劃</div>
  <div class="page-sub">評鑑主題：No Code/Low Code概念 / 生成式AI應用領域與工具使用 / 生成式AI導入評估規劃</div>
  <div class="chapter-grid">
    <div class="chapter-card">
      <h3>3.1 No Code / Low Code 概念</h3>
      <p><strong>基本概念：</strong>No Code透過視覺化拖放介面，無需程式碼即可開發；Low Code提供部分程式彈性。</p>
      <p style="margin-top:.5rem"><strong>AI民主化：</strong>讓非技術人員也能創建AI應用，降低技術門檻。</p>
      <p style="margin-top:.5rem"><strong>優勢與限制：</strong>快速原型、成本低，但客製化有限、複雜邏輯難以實現。</p>
      <span class="tag">No Code</span><span class="tag">Low Code</span><span class="tag">AI民主化</span><span class="tag">視覺化開發</span>
    </div>
    <div class="chapter-card">
      <h3>3.2 生成式AI應用領域與工具使用</h3>
      <p><strong>應用領域：</strong>文字生成（ChatGPT）、圖像生成（Midjourney/DALL-E/Stable Diffusion）、程式碼（GitHub Copilot）、語音（Whisper/ElevenLabs）。</p>
      <p style="margin-top:.5rem"><strong>Prompt Engineering：</strong>Zero-shot、Few-shot、Chain-of-Thought、Role Prompting、APE、Graph Prompting。</p>
      <span class="tag">Prompt工程</span><span class="tag">ChatGPT</span><span class="tag">Midjourney</span><span class="tag">RAG</span>
    </div>
    <div class="chapter-card">
      <h3>3.3 生成式AI導入評估規劃</h3>
      <p><strong>導入評估：</strong>業務需求分析、ROI評估、可行性分析、供應商選擇。</p>
      <p style="margin-top:.5rem"><strong>隱私保護：</strong>聯邦學習（Federated Learning）、同態加密、安全多方計算。</p>
      <p style="margin-top:.5rem"><strong>風險管理：</strong>幻覺問題、資料偏見、資安威脅、治理框架建立。</p>
      <span class="tag">聯邦學習</span><span class="tag">ROI評估</span><span class="tag">風險管理</span><span class="tag">AI治理</span>
    </div>
  </div>
  <div class="card">
    <h2>📊 章節練習題數量</h2>
    <div id="s2-chapter-stats"></div>
  </div>
</div>

<!-- PRACTICE PAGE -->
<div id="page-practice" class="page">
  <div class="page-title" id="practice-title">章節練習</div>
  <div class="page-sub" id="practice-sub"></div>
  <div id="practice-container"></div>
</div>

<!-- MOCK EXAM PAGE -->
<div id="page-mock" class="page">
  <div id="mock-intro" class="exam-intro">
    <h2 id="mock-title">模擬考試</h2>
    <div class="meta" id="mock-meta"></div>
    <button class="start-btn" onclick="startExam()">開始考試 ▶</button>
  </div>
  <div id="mock-container" class="exam-container">
    <div class="exam-header">
      <div>
        <div style="font-size:.8rem;opacity:.8">模擬考試</div>
        <div id="mock-exam-title" style="font-size:.9rem;font-weight:600"></div>
      </div>
      <div class="exam-timer" id="exam-timer">90:00</div>
      <div>
        <div class="exam-progress" id="exam-progress"></div>
        <button class="submit-exam-btn" onclick="submitExam()">繳卷</button>
      </div>
    </div>
    <div id="exam-questions"></div>
    <div style="text-align:center;padding:1rem">
      <button class="start-btn" onclick="submitExam()">繳卷交答案</button>
    </div>
  </div>
  <div id="mock-results" style="display:none">
    <div id="result-card"></div>
    <div class="result-detail" id="result-detail"></div>
  </div>
</div>

<!-- GUIDE CONTENT -->
<div id="page-guide" class="page">
  <div class="page-title" id="guide-title"></div>
  <div class="page-sub" id="guide-sub"></div>
  <div id="guide-notice" class="guide-notice" style="display:none"></div>
  <div class="card" style="margin-bottom:1rem">
    <div class="guide-meta" id="guide-meta"></div>
    <div class="guide-subtopics" id="guide-subtopics"></div>
  </div>
  <div class="card">
    <div class="guide-content" id="guide-content"></div>
  </div>
</div>

</main>
</div>

<script>
{data_js}

// ── Sidebar (mobile) ───────────────────────────────────────────────
function toggleSidebar() {{
  const aside = document.querySelector('aside');
  const overlay = document.getElementById('overlay');
  aside.classList.toggle('open');
  overlay.classList.toggle('show');
  document.body.style.overflow = aside.classList.contains('open') ? 'hidden' : '';
}}
function closeSidebar() {{
  document.querySelector('aside').classList.remove('open');
  document.getElementById('overlay').classList.remove('show');
  document.body.style.overflow = '';
}}

// ── State ──────────────────────────────────────────────────────────
let currentMockData = null;
let examTimer = null;
let examSeconds = 90 * 60;
let userAnswers = {{}};

// ── Navigation ─────────────────────────────────────────────────────
function showPage(pageId) {{
  closeSidebar();
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.sidebar-item').forEach(a => a.classList.remove('active'));
  document.getElementById('page-' + pageId).classList.add('active');
  // Update sidebar
  document.querySelectorAll('.sidebar-item').forEach(a => {{
    if(a.getAttribute('onclick') && a.getAttribute('onclick').includes("'" + pageId + "'")) {{
      a.classList.add('active');
    }}
  }});
  if(pageId==='s1-overview') renderChapterStats('s1');
  if(pageId==='s2-overview') renderChapterStats('s2');
}}

function renderChapterStats(subj) {{
  const data = subj==='s1' ? SUBJECT1_QUESTIONS : SUBJECT2_QUESTIONS;
  const container = document.getElementById(subj+'-chapter-stats');
  let html = '';
  data.chapters.forEach(ch => {{
    const n = ch.questions.length;
    html += `<div style="margin-bottom:.6rem">
      <div style="display:flex;justify-content:space-between;font-size:.85rem;margin-bottom:.2rem">
        <span>${{ch.title}}</span><span style="color:var(--accent);font-weight:600">${{n}}題</span>
      </div>
      <div class="progress-bar"><div class="progress-fill" style="width:${{(n/10)*100}}%"></div></div>
    </div>`;
  }});
  container.innerHTML = html;
}}

// ── Practice ───────────────────────────────────────────────────────
function showPractice(subjectKey, chapterId) {{
  showPage('practice');
  const data = subjectKey==='s1' ? SUBJECT1_QUESTIONS : SUBJECT2_QUESTIONS;
  const ch = data.chapters.find(c => c.id===chapterId);
  if(!ch) return;
  document.getElementById('practice-title').textContent = ch.title;
  document.getElementById('practice-sub').textContent =
    (subjectKey==='s1' ? '科目一：人工智慧基礎概論' : '科目二：生成式AI應用與規劃') +
    ' › ' + ch.title + ` (共 ${{ch.questions.length}} 題)`;
  
  // Update sidebar active
  document.querySelectorAll('.sidebar-item').forEach(a => a.classList.remove('active'));
  document.querySelectorAll('.sidebar-item').forEach(a => {{
    if(a.getAttribute('onclick') && a.getAttribute('onclick').includes(chapterId)) a.classList.add('active');
  }});

  let html = '';
  ch.questions.forEach((q, i) => {{
    html += `
    <div class="q-card" id="qcard-${{q.id}}">
      <div class="q-num">第 ${{i+1}} 題</div>
      <div class="q-text">${{q.question}}</div>
      <div class="options">
        ${{Object.entries(q.options).map(([k,v]) => `
          <button class="option-btn" id="opt-${{q.id}}-${{k}}" onclick="checkAnswer('${{q.id}}','${{k}}','${{q.answer}}')">
            <strong>(${{k}})</strong> ${{v}}
          </button>`).join('')}}
      </div>
      <button class="reveal-btn" id="reveal-${{q.id}}" onclick="revealAnswer('${{q.id}}','${{q.answer}}')">顯示答案與解析</button>
      <div class="explanation" id="exp-${{q.id}}">
        <strong>✅ 正確答案：(${{q.answer}}) ${{q.options[q.answer]}}</strong><br><br>${{q.explanation}}
      </div>
      ${{q.card ? `<button class="card-toggle" id="ctoggle-${{q.id}}" onclick="toggleCard('${{q.id}}')">📌 查看解說圖卡</button>
      <div class="q-card-panel" id="cpanel-${{q.id}}">
        <div class="card-header">解說圖卡</div>
        <div class="card-body">
          <div class="card-row"><span class="cr-icon">📌</span><span class="cr-label">核心概念</span><span class="cr-val">${{q.card.concept}}</span></div>
          <div class="card-row"><span class="cr-icon">🔑</span><span class="cr-label">記憶口訣</span><span class="cr-val">${{q.card.mnemonic}}</span></div>
          <div class="card-row"><span class="cr-icon">⚠️</span><span class="cr-label">常見混淆</span><span class="cr-val">${{q.card.confusion}}</span></div>
          <div class="card-row"><span class="cr-icon">📊</span><span class="cr-label">出題頻率</span><span class="cr-val">${{renderFreq(q.card.frequency)}}</span></div>
        </div>
      </div>` : ''}}
    </div>`;
  }});
  document.getElementById('practice-container').innerHTML = html;
  window.scrollTo(0,0);
}}

function checkAnswer(qid, selected, correct) {{
  const opts = document.querySelectorAll(`[id^="opt-${{qid}}"]`);
  opts.forEach(btn => btn.disabled = true);
  document.getElementById(`opt-${{qid}}-${{selected}}`).classList.add(selected===correct ? 'correct' : 'wrong');
  if(selected!==correct) document.getElementById(`opt-${{qid}}-${{correct}}`).classList.add('correct');
  revealAnswer(qid, correct);
}}

function revealAnswer(qid, correct) {{
  document.getElementById('exp-'+qid).classList.add('show');
  const btn = document.getElementById('reveal-'+qid);
  if(btn) btn.style.display='none';
  const ctoggle = document.getElementById('ctoggle-'+qid);
  if(ctoggle) ctoggle.classList.add('show');
}}

function toggleCard(qid) {{
  const panel = document.getElementById('cpanel-'+qid);
  const toggle = document.getElementById('ctoggle-'+qid);
  if(!panel) return;
  const isOpen = panel.classList.toggle('show');
  toggle.textContent = isOpen ? '📌 收起解說圖卡' : '📌 查看解說圖卡';
}}

function renderFreq(freq) {{
  const levels = {{'高':3,'中':2,'低':1}};
  const filled = levels[freq] || 1;
  const dots = [1,2,3].map(n =>
    `<span class="fb-dot${{n<=filled?' filled':''}}">&nbsp;</span>`
  ).join('');
  return `<span class="freq-bar">${{dots}}<span class="freq-label">${{freq}}</span></span>`;
}}

// ── Guide Content ──────────────────────────────────────────────────
function escHtml(s) {{
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}}

function guideContentToHtml(text) {{
  return text
    .split(/\\n{{2,}}/)
    .filter(p => p.trim())
    .map(p => '<p>' + escHtml(p).replace(/\\n/g,'<br>') + '</p>')
    .join('');
}}

// Chapters whose content in the guide spans multiple exam-chapter topics
const GUIDE_NOTICES = {{
  's1c1': '⚠️ 官方學習指引將「<strong>資料處理與分析概念</strong>」（ETL、資料類型、資料清洗、GDPR 等）的說明內容併入本章（3.1 人工智慧概念）。練習題雖分成 s1c1／s1c2 兩章節，但指引原文集中在此。',
}};

function showGuide(subjectNum, chapterId) {{
  const guide = subjectNum === 1 ? SUBJECT1_GUIDE : SUBJECT2_GUIDE;
  if (!guide || !guide.chapters) {{
    alert('學習指引資料尚未載入，請先執行 parse_guides.py 後重新建置。');
    return;
  }}
  const ch = guide.chapters.find(c => c.id === chapterId);
  if (!ch) return;

  document.getElementById('guide-title').textContent = ch.title;
  document.getElementById('guide-sub').textContent =
    guide.subject + '  ›  學習指引原文（共 ' + ch.content.length + ' 字元）';

  // Notice
  const noticeEl = document.getElementById('guide-notice');
  if (GUIDE_NOTICES[chapterId]) {{
    noticeEl.innerHTML = GUIDE_NOTICES[chapterId];
    noticeEl.style.display = 'block';
  }} else {{
    noticeEl.style.display = 'none';
  }}

  // Meta badges
  const charCount = ch.content.length;
  const paraCount = ch.content.split(/\\n{{2,}}/).filter(p=>p.trim()).length;
  document.getElementById('guide-meta').innerHTML =
    `<span class="guide-badge">📄 ${{paraCount}} 段落</span>` +
    `<span class="guide-badge">📝 ${{charCount.toLocaleString()}} 字元</span>`;

  // Subtopics
  const pillsHtml = ch.subtopics
    .map(s => `<span class="pill pill-blue">${{escHtml(s)}}</span>`)
    .join('');
  document.getElementById('guide-subtopics').innerHTML =
    '<strong style="font-size:.82rem;color:var(--text-light)">章節重點子主題</strong><br><br>' + pillsHtml;

  // Content
  document.getElementById('guide-content').innerHTML = guideContentToHtml(ch.content);

  // Sidebar active
  document.querySelectorAll('.sidebar-item').forEach(a => a.classList.remove('active'));
  document.querySelectorAll('.sidebar-item').forEach(a => {{
    if (a.getAttribute('onclick') && a.getAttribute('onclick').includes(chapterId)) {{
      a.classList.add('active');
    }}
  }});

  showPage('guide');
  window.scrollTo(0,0);
}}

// ── Mock Exam ──────────────────────────────────────────────────────
function showMock(mockKey) {{
  if(examTimer) clearInterval(examTimer);
  userAnswers = {{}};
  showPage('mock');
  document.getElementById('mock-intro').style.display='block';
  document.getElementById('mock-container').style.display='none';
  document.getElementById('mock-results').style.display='none';

  if(mockKey==='mock1') currentMockData = MOCK_EXAM1;
  else if(mockKey==='mock2') currentMockData = MOCK_EXAM2;
  else currentMockData = SAMPLE_EXAM;

  document.getElementById('mock-title').textContent = currentMockData.exam;
  document.getElementById('mock-meta').innerHTML =
    `共 <strong>${{currentMockData.total}}</strong> 題 &nbsp;|&nbsp; 考試時間：<strong>${{currentMockData.time_limit}}</strong> &nbsp;|&nbsp; 及格分數：<strong>${{currentMockData.passing_score}}分</strong>`;

  document.querySelectorAll('.sidebar-item').forEach(a => a.classList.remove('active'));
  document.querySelectorAll('.sidebar-item').forEach(a => {{
    if(a.getAttribute('onclick') && a.getAttribute('onclick').includes(mockKey)) a.classList.add('active');
  }});
}}

function startExam() {{
  document.getElementById('mock-intro').style.display='none';
  document.getElementById('mock-container').style.display='block';
  document.getElementById('mock-results').style.display='none';
  document.getElementById('mock-exam-title').textContent = currentMockData.exam;

  examSeconds = 90 * 60;
  updateTimer();
  examTimer = setInterval(() => {{
    examSeconds--;
    updateTimer();
    if(examSeconds<=0) submitExam();
  }}, 1000);

  renderExamQuestions();
  window.scrollTo(0,0);
}}

function updateTimer() {{
  const m = Math.floor(examSeconds/60);
  const s = examSeconds%60;
  const el = document.getElementById('exam-timer');
  el.textContent = `${{String(m).padStart(2,'0')}}:${{String(s).padStart(2,'0')}}`;
  el.className = 'exam-timer' + (examSeconds<=300?' danger':examSeconds<=600?' warning':'');
  
  const answered = Object.keys(userAnswers).length;
  document.getElementById('exam-progress').textContent = `已答：${{answered}} / ${{currentMockData.total}}`;
}}

function renderExamQuestions() {{
  let html = '';
  currentMockData.questions.forEach((q, i) => {{
    html += `
    <div class="exam-q" id="exam-qcard-${{i}}">
      <div class="exam-q-num">第 ${{i+1}} 題</div>
      <div class="exam-q-text">${{q.question}}</div>
      <div class="exam-options">
        ${{Object.entries(q.options).map(([k,v]) => `
          <label class="exam-option" id="exam-opt-${{i}}-${{k}}" onclick="selectAnswer(${{i}},'${{k}}')">
            <input type="radio" name="q${{i}}" value="${{k}}"> <span>(${{k}}) ${{v}}</span>
          </label>`).join('')}}
      </div>
    </div>`;
  }});
  document.getElementById('exam-questions').innerHTML = html;
}}

function selectAnswer(qi, key) {{
  userAnswers[qi] = key;
  // Remove selected from all options for this question
  document.querySelectorAll(`[id^="exam-opt-${{qi}}-"]`).forEach(el => el.classList.remove('selected'));
  document.getElementById(`exam-opt-${{qi}}-${{key}}`).classList.add('selected');
  updateTimer();
}}

function submitExam() {{
  if(examTimer) clearInterval(examTimer);
  document.getElementById('mock-container').style.display='none';
  document.getElementById('mock-results').style.display='block';

  let correct=0, wrong=0, skipped=0;
  const qs = currentMockData.questions;
  qs.forEach((q,i) => {{
    if(userAnswers[i]===q.answer) correct++;
    else if(userAnswers[i]) wrong++;
    else skipped++;
  }});
  const total = qs.length;
  const score = Math.round((correct/total)*100);
  const pass = score >= currentMockData.passing_score;

  document.getElementById('result-card').innerHTML = `
    <div class="result-card">
      <div style="font-size:1rem;color:var(--text-light);margin-bottom:.5rem">${{currentMockData.exam}}</div>
      <div class="score-big ${{pass?'pass':'fail'}}">${{score}}分</div>
      <div class="score-label">${{pass?'🎉 恭喜通過！':'❌ 尚未通過，繼續加油！'}}</div>
      <div class="stats-row" style="margin-top:1.5rem;justify-content:center">
        <div class="stat-box"><div class="stat-num" style="color:var(--success)">${{correct}}</div><div class="stat-label">答對</div></div>
        <div class="stat-box"><div class="stat-num" style="color:var(--error)">${{wrong}}</div><div class="stat-label">答錯</div></div>
        <div class="stat-box"><div class="stat-num" style="color:var(--text-light)">${{skipped}}</div><div class="stat-label">未答</div></div>
        <div class="stat-box"><div class="stat-num">${{total}}</div><div class="stat-label">總題數</div></div>
      </div>
      <div class="progress-bar" style="margin-top:1rem;height:12px">
        <div class="progress-fill" style="width:${{score}}%;background:${{pass?'var(--success)':'var(--error)'}}"></div>
      </div>
      <div style="font-size:.8rem;color:var(--text-light);margin-top:.3rem">及格線：${{currentMockData.passing_score}}分</div>
      <button class="reveal-btn" style="margin-top:1.5rem;padding:.6rem 1.5rem" onclick="showMock(currentMockKey)">重新考試</button>
    </div>`;

  let detailHtml = '<h2 style="margin-bottom:1rem;color:var(--primary)">📝 詳細解析</h2>';
  qs.forEach((q,i) => {{
    const ua = userAnswers[i];
    const isCorrect = ua===q.answer;
    const isSkipped = !ua;
    detailHtml += `
    <div class="exam-q ${{isCorrect?'correct-q':isSkipped?'':'wrong-q'}}">
      <div class="exam-q-num">
        第 ${{i+1}} 題 
        <span class="pill ${{isCorrect?'pill-green':isSkipped?'pill-orange':''}}" style="${{isSkipped?'background:#fef5e7;color:#e67e22':isCorrect?'':'background:#fdf2f2;color:#e74c3c'}}">${{isCorrect?'✓ 正確':isSkipped?'— 未作答':'✗ 錯誤'}}</span>
      </div>
      <div class="exam-q-text">${{q.question}}</div>
      <div style="font-size:.85rem;margin-top:.4rem">
        ${{!isCorrect&&!isSkipped?`<span style="color:var(--error)">您的答案：(${{ua}}) ${{q.options[ua]}}</span><br>`:''}}<span style="color:var(--success)">正確答案：(${{q.answer}}) ${{q.options[q.answer]}}</span>
      </div>
      ${{q.explanation ? `<div class="result-explanation">${{q.explanation}}</div>` : ''}}
    </div>`;
  }});
  document.getElementById('result-detail').innerHTML = detailHtml;
  window.scrollTo(0,0);
}}

// ── Init ───────────────────────────────────────────────────────────
let currentMockKey = 'mock1';
const origShowMock = showMock;
window.showMock = function(key) {{
  currentMockKey = key;
  origShowMock(key);
}};

(function init() {{
  const totalPractice = SUBJECT1_QUESTIONS.chapters.reduce((a,c)=>a+c.questions.length,0) +
                        SUBJECT2_QUESTIONS.chapters.reduce((a,c)=>a+c.questions.length,0);
  const totalMock = MOCK_EXAM1.total + MOCK_EXAM2.total + SAMPLE_EXAM.total;
  document.getElementById('total-practice-q').textContent = totalPractice;
  document.getElementById('total-mock-q').textContent = totalMock;
}})();
</script>
</body>
</html>"""
    return html


if __name__ == '__main__':
    html = build_html()
    docs_path = DOCS_OUT / 'index.html'

    DOCS_OUT.mkdir(exist_ok=True)
    docs_path.write_text(html, encoding='utf-8')
    (DOCS_OUT / '.nojekyll').write_text('', encoding='utf-8')

    size = docs_path.stat().st_size / 1024
    print(f"Saved {docs_path} ({size:.1f} KB)")

    # Log
    log_path = ROOT / 'logs' / 'generation.log'
    log_path.parent.mkdir(exist_ok=True)
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f"\n=== Web Interface ===\nSaved docs/index.html ({size:.1f} KB)\n")

    print("Done! Open docs/index.html in a browser.")
