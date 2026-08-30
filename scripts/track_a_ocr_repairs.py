#!/usr/bin/env python3
"""Deterministic, source-reviewed repair overlay and gate for Track A.

The page extraction remains a faithful transcription of the supplied PDFs.  This
module is the intentionally small publication overlay for defects that cannot be
resolved safely by the generic formula matcher (flattened formula geometry,
official errata, and two printed formula typos).  The same declarations drive
the exporter and the post-export audit so a future regeneration cannot silently
drop a repair.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

from guide_publication_overlays import DEMOTE_HEADINGS, PROMOTE_HEADINGS, SHORTEN_HEADINGS


BASE = Path(__file__).resolve().parents[1]
SIGNATURE_REGISTRY_PATH = Path(__file__).with_name('track_a_ocr_expected_signatures.json')


def formula(latex: str, display: bool = True) -> dict[str, Any]:
    """Return a formula entry without nested math delimiters."""
    value = latex.strip()
    if value.startswith('$$') and value.endswith('$$'):
        value = value[2:-2].strip()
    elif value.startswith('$') and value.endswith('$'):
        value = value[1:-1].strip()
    return {'latex': value, 'display': display}


# key = (level, guide key, zero-based PDF page index).  Every listed page is
# cleared first, then rebuilt from formulas verified against the source page.
# `match` is a stable source-text fragment rather than a generated block id.
FORMULA_PAGE_REPAIRS: dict[tuple[str, str, int], list[dict[str, Any]]] = {
    ('初級', 'guide1', 45): [
        {'match': '𝑿𝒔𝒄𝒂𝒍𝒆𝒅= 𝑿−𝑿𝒎𝒊𝒏', 'latex': [r'X_{\mathrm{scaled}}=\frac{X-X_{\min}}{X_{\max}-X_{\min}}'], 'only': True},
        {'match': '𝑿𝒔𝒄𝒂𝒍𝒆𝒅= 𝑿−𝝁', 'latex': [r'X_{\mathrm{scaled}}=\frac{X-\mu}{\sigma}'], 'only': True},
    ],
    ('初級', 'guide1', 46): [
        {'match': '𝑀𝑆𝐸=', 'latex': [r'MSE=\frac{1}{n}\sum_{i=1}^{n}(y_i-\hat y_i)^2'], 'only': True},
    ],
    # These four pages contain ROI prose but no source equation.  Empty lists
    # deliberately remove the old heuristic-generated equation.
    ('初級', 'guide2', 10): [],
    ('初級', 'guide2', 17): [],
    ('初級', 'guide2', 40): [],
    ('初級', 'guide2', 48): [],
    ('中級', 'guide1', 57): [
        {'match': 'IOU = AreaIntersection', 'latex': [r'IOU=\frac{Area_{\mathrm{Intersection}}}{Area_{\mathrm{Union}}}'], 'only': True},
    ],
    ('中級', 'guide1', 58): [
        {'match': 'IOU 計算', 'latex': [r'IOU=\frac{\mathrm{Intersection}}{\mathrm{Union}}=\frac{40}{140}\approx0.286'], 'only': False},
    ],
    ('中級', 'guide1', 99): [
        {'match': 'ROI =', 'latex': [r'ROI=\frac{\text{投資回報}-\text{投資成本}}{\text{投資成本}}\times100\%'], 'only': True},
        {'match': 'NPV =', 'latex': [r'NPV=\sum_{t=1}^{n}\frac{CF_t}{(1+r)^t}-I_0'], 'only': True},
        {'match': '回收期 =', 'latex': [r'\text{回收期}=\frac{\text{初期投資成本}}{\text{每年淨現金流}}'], 'only': True},
    ],
    ('中級', 'guide2', 11): [
        {'match': '中位數= 𝑥(𝑛+1', 'latex': [r'\text{中位數}=x_{\left(\frac{n+1}{2}\right)}'], 'only': True},
        {'match': '𝑥(𝑛 2) + 𝑥(𝑛 2+1)', 'latex': [r'\text{中位數}=\frac{x_{\left(\frac n2\right)}+x_{\left(\frac n2+1\right)}}{2}'], 'only': True},
    ],
    ('中級', 'guide2', 12): [
        {'match': '變異數公式', 'latex': [r'\sigma^2=\frac1N\sum_{i=1}^{N}(x_i-\mu)^2'], 'only': True},
        {'match': '標準差公式', 'latex': [r'\sigma=\sqrt{\frac1N\sum_{i=1}^{N}(x_i-\mu)^2}'], 'only': True},
    ],
    ('中級', 'guide2', 21): [
        {'match': '∑𝑃(𝑋=', 'latex': [r'\sum_{x_i}P(X=x_i)=1'], 'only': True},
        {'match': '𝑃(𝑎≤𝑋≤𝑏)', 'latex': [r'P(a\le X\le b)=\int_a^b f(x)\,dx'], 'only': True},
    ],
    ('中級', 'guide2', 22): [
        {'match': 'E (X) = p Var', 'latex': [r'E(X)=p', r'\operatorname{Var}(X)=p(1-p)'], 'only': True},
    ],
    ('中級', 'guide2', 23): [
        {'match': '𝑃(𝑋= 𝑘) = (𝑛 𝑘)', 'latex': [r'P(X=k)={n\choose k}p^k(1-p)^{n-k},\quad k=0,1,\ldots,n'], 'only': True},
        {'match': '(𝑛 𝑘) =', 'latex': [r'{n\choose k}=\frac{n!}{k!(n-k)!}'], 'only': True},
        {'match': 'E (X) = np Var', 'latex': [r'E(X)=np', r'\operatorname{Var}(X)=np(1-p)'], 'only': True},
        {'match': '𝜆𝑘𝑒−𝜆', 'latex': [r'P(X=k)=\frac{\lambda^k e^{-\lambda}}{k!},\quad k=0,1,\ldots'], 'only': True},
    ],
    ('中級', 'guide2', 24): [
        {'match': 'E(X) = Var(X)', 'latex': [r'E(X)=\lambda', r'\operatorname{Var}(X)=\lambda'], 'only': True},
        {'match': '𝑓(𝑥) =', 'latex': [r'f(x)=\frac{1}{\sigma\sqrt{2\pi}}\exp\!\left(-\frac{(x-\mu)^2}{2\sigma^2}\right)'], 'only': True},
    ],
    ('中級', 'guide2', 25): [
        {'match': 'E(X) = Var(X) = 2', 'latex': [r'E(X)=\mu', r'\operatorname{Var}(X)=\sigma^2'], 'only': True},
        {'match': 'f (x)=e-x', 'latex': [r'f(x)=\lambda e^{-\lambda x},\quad x\ge0'], 'only': True},
        {'match': '𝐸(𝑋) = 1 𝜆', 'latex': [r'E(X)=\frac1\lambda', r'\operatorname{Var}(X)=\frac1{\lambda^2}'], 'only': True},
    ],
    ('中級', 'guide2', 27): [
        {'match': '𝑓(𝑥) = 𝑥', 'latex': [r'f(x)=\frac{x^{k/2-1}e^{-x/2}}{2^{k/2}\Gamma(k/2)},\quad x\ge0'], 'only': True},
        {'match': 'E(X) = k Var', 'latex': [r'E(X)=k', r'\operatorname{Var}(X)=2k'], 'only': True},
    ],
    ('中級', 'guide2', 43): [
        {'match': 'n p0 5', 'latex': [r'n p_0\ge5', r'n(1-p_0)\ge5'], 'only': True},
        {'match': '虛無假設（H₀）', 'latex': [r'p=p_0'], 'only': False},
    ],
    ('中級', 'guide2', 44): [
        {'match': '符合常態近似條件', 'latex': [r'np\ge5', r'n(1-p)\ge5'], 'only': False},
    ],
    ('中級', 'guide3', 9): [
        {'match': '擲骰子時', 'latex': [r'\sum_{x_i}P(X=x_i)=1'], 'only': False},
    ],
    ('中級', 'guide3', 11): [
        {'match': '𝑃(𝐴|𝐵)', 'latex': [r'P(A\mid B)=\frac{P(A\cap B)}{P(B)}'], 'only': True},
        {'match': '分類任務中的條件預測', 'latex': [r'P(Y\mid X)'], 'only': False},
    ],
    ('中級', 'guide3', 15): [
        {'match': '一筆5 維的樣本輸入', 'latex': [
            r'\mathbf{x}=[x_1,x_2,x_3,x_4,x_5]^\top',
            r'\boldsymbol\theta=[\theta_1,\theta_2,\ldots,\theta_d]',
            r'\hat Y=\boldsymbol\theta^\top\mathbf{x}',
        ], 'only': False},
    ],
    ('中級', 'guide3', 16): [
        {'match': '特徵矩陣 𝑋', 'latex': [r'X\in\mathbb{R}^{n\times d}'], 'only': False},
        {'match': '權重矩陣 𝑊', 'latex': [r'W\in\mathbb{R}^{d\times k}'], 'only': False},
        {'match': '預測值可由', 'latex': [r'\hat y=X\theta'], 'only': False},
        {'match': 'z(l) =', 'latex': [r'\mathbf z^{(l)}=\mathbf W^{(l)}\mathbf a^{(l-1)}+\mathbf b^{(l)}'], 'only': True},
    ],
    ('中級', 'guide3', 17): [
        {'match': '當一個向量 x', 'latex': [r'x\in\mathbb{R}^d', r'A\in\mathbb{R}^{k\times d}', r'Ax\in\mathbb{R}^k'], 'only': False},
    ],
    ('中級', 'guide3', 19): [
        {'match': '高維矩陣 𝑋', 'latex': [r'X\in\mathbb{R}^{m\times n}'], 'only': False},
        {'match': '將矩陣 𝐴', 'latex': [r'A\in\mathbb{R}^{n\times n}'], 'only': False},
        {'match': '𝐴= 𝑄⋀𝑄⊺', 'latex': [r'A=Q\Lambda Q^\top'], 'only': True},
    ],
    ('中級', 'guide3', 20): [
        {'match': '任意實數矩陣', 'latex': [r'X\in\mathbb{R}^{m\times n}'], 'only': False},
        {'match': '𝑋= 𝑈Σ𝑉⊺', 'latex': [r'X=U\Sigma V^\top'], 'only': True},
        {'match': '𝑈∈ℝ', 'latex': [r'U\in\mathbb{R}^{m\times m}'], 'only': False},
        {'match': 'Σ ∈ℝ', 'latex': [r'\Sigma\in\mathbb{R}^{m\times n}'], 'only': False},
        {'match': '𝑉∈ℝ', 'latex': [r'V\in\mathbb{R}^{n\times n}'], 'only': False},
    ],
    ('中級', 'guide3', 21): [
        {'match': '將非負矩陣 𝑋', 'latex': [r'X\in\mathbb{R}^{m\times n}', r'X\ge0'], 'only': False},
        {'match': '分解為兩個非負矩陣', 'latex': [r'X\approx WH'], 'only': False},
        {'match': '𝑊∈ℝ', 'latex': [r'W\in\mathbb{R}^{m\times k}', r'W\ge0'], 'only': False},
        {'match': '𝐻∈ℝ', 'latex': [r'H\in\mathbb{R}^{k\times n}', r'H\ge0'], 'only': False},
    ],
    ('中級', 'guide3', 50): [
        {'match': 'y = β0', 'latex': [r'y=\beta_0+\beta_1x_1+\beta_2x_2+\cdots+\beta_nx_n+\varepsilon'], 'only': True},
        {'match': 'β0：', 'latex': [r'\beta_0'], 'only': False},
        {'match': 'β1, β2', 'latex': [r'(\beta_1,\beta_2,\ldots,\beta_n)'], 'only': False},
        {'match': '𝔁1, 𝔁2', 'latex': [r'(x_1,x_2,\ldots,x_n)'], 'only': False},
        {'match': 'ε：', 'latex': [r'\varepsilon'], 'only': False},
        {'match': '決定係數 𝑅2', 'latex': [r'R^2'], 'only': False},
    ],
    ('中級', 'guide3', 63): [
        {'match': '𝑝= 1 1 +', 'latex': [r'p=\frac1{1+e^{-(\beta_0+\beta_1x_1+\cdots+\beta_nx_n)}}'], 'only': True},
    ],
    ('中級', 'guide3', 65): [
        {'match': 'w ‧ x + b = 0', 'latex': [r'w\cdot x+b=0'], 'only': True},
        {'match': '若w · x + b > 0', 'latex': [r'w\cdot x+b>0'], 'only': False},
        {'match': '若w · x + b < 0', 'latex': [r'w\cdot x+b<0'], 'only': False},
        {'match': '𝑓(𝑥) = ∑', 'latex': [r'f(x)=\sum_i\alpha_i y_i K(x_i,x)+b'], 'only': True},
    ],
    ('中級', 'guide3', 72): [
        {'match': '若X=（x1', 'latex': [r'X=(x_1,x_2,\ldots,x_n)', r'P(X\mid C)=\prod_{i=1}^{n}P(x_i\mid C)'], 'only': False},
    ],
    ('中級', 'guide3', 86): [
        {'match': '數學上表示為 P（B∣A）', 'latex': [r'P(B\mid A)=\frac{\operatorname{Support}(A\cup B)}{\operatorname{Support}(A)}'], 'only': False},
        {'match': 'Lift（A ⇒ B）=', 'latex': [r'\operatorname{Lift}(A\Rightarrow B)=\frac{\operatorname{Confidence}(A\Rightarrow B)}{P(B)}'], 'only': True},
        {'match': '若Lift > 1', 'latex': [r'\operatorname{Lift}>1'], 'only': False},
        {'match': '若Lift < 1', 'latex': [r'\operatorname{Lift}<1', r'\operatorname{Lift}=1'], 'only': False},
    ],
    ('中級', 'guide3', 92): [
        {'match': '𝑍= 𝑤1𝑥1', 'latex': [r'Z=w_1x_1+w_2x_2+\cdots+w_nx_n+b=\sum_{i=1}^{n}w_ix_i+b'], 'only': True},
    ],
    ('中級', 'guide3', 154): [
        {'match': '公式：Accuracy', 'latex': [r'\operatorname{Accuracy}=\frac{TP+TN}{TP+TN+FP+FN}'], 'only': True},
        {'match': '公式：Precision', 'latex': [r'\operatorname{Precision}=\frac{TP}{TP+FP}'], 'only': True},
        {'match': '公式：Recall', 'latex': [r'\operatorname{Recall}=\frac{TP}{TP+FN}'], 'only': True},
        {'match': '公式：F1', 'latex': [r'F_1=2\frac{\operatorname{Precision}\cdot\operatorname{Recall}}{\operatorname{Precision}+\operatorname{Recall}}'], 'only': True},
    ],
    ('中級', 'guide3', 155): [
        {'match': '公式：MSE', 'latex': [r'MSE=\frac1n\sum_{i=1}^{n}(y_i-\hat y_i)^2'], 'only': True},
    ],
    ('中級', 'guide3', 156): [
        {'match': '公式：MAE', 'latex': [r'MAE=\frac1n\sum_{i=1}^{n}|y_i-\hat y_i|'], 'only': True},
        {'match': '公式：RMSE', 'latex': [r'RMSE=\sqrt{\frac1n\sum_{i=1}^{n}(y_i-\hat y_i)^2}'], 'only': True},
        {'match': '𝑅2 = 1 −', 'latex': [r'R^2=1-\frac{\sum_{i=1}^{n}(y_i-\hat y_i)^2}{\sum_{i=1}^{n}(y_i-\bar y)^2}=1-\frac{RSS}{TSS}'], 'only': True},
    ],
    # Extra source-math correction requested after the original 169-item audit:
    # the supplied PDF prints z_i in the denominator; publication uses z_j.
    ('中級', 'guide3', 168): [
        {'match': 'Softmax(𝑧𝑖)', 'latex': [r'\operatorname{Softmax}(z_i)=\frac{e^{z_i}}{\sum_{j=1}^{K}e^{z_j}}'], 'only': True},
    ],
    ('中級', 'guide3', 169): [
        {'match': 'ReLU(x)', 'latex': [r'\operatorname{ReLU}(x)=\max(0,x)'], 'only': True},
        {'match': 'σ(𝑥)', 'latex': [r'\sigma(x)=\frac1{1+e^{-x}}'], 'only': True},
    ],
    ('中級', 'guide3', 170): [
        {'match': 'tanh(𝑥)', 'latex': [r'\tanh(x)=\frac{e^x-e^{-x}}{e^x+e^{-x}}'], 'only': True},
    ],
    ('中級', 'guide3', 172): [
        {'match': '𝜃𝑡+1 = 𝜃𝑡−𝜂', 'latex': [r'\theta_{t+1}=\theta_t-\eta\nabla_\theta L(\theta_t)'], 'only': True},
    ],
    ('中級', 'guide3', 173): [
        {'match': '𝑣𝑡+1 =', 'latex': [r'v_{t+1}=\gamma v_t+\eta\nabla_\theta L(\theta_t)', r'\theta_{t+1}=\theta_t-v_{t+1}'], 'only': False},
        {'match': '公式為：𝐺𝑡=', 'latex': [r'G_t=G_{t-1}+(\nabla_\theta L(\theta_t))^2', r'\theta_{t+1}=\theta_t-\frac{\eta}{\sqrt{G_t}+\epsilon}\nabla_\theta L(\theta_t)'], 'only': False},
    ],
    ('中級', 'guide3', 174): [
        {'match': '𝑚𝑡= 𝛽1', 'latex': [r'm_t=\beta_1m_{t-1}+(1-\beta_1)\nabla_\theta L(\theta_t)'], 'only': True},
        {'match': '𝑣𝑡= 𝛽2', 'latex': [r'v_t=\beta_2v_{t-1}+(1-\beta_2)(\nabla_\theta L(\theta_t))^2'], 'only': True},
        {'match': '𝑚̂𝑡=', 'latex': [r'\hat m_t=\frac{m_t}{1-\beta_1^t}', r'\hat v_t=\frac{v_t}{1-\beta_2^t}'], 'only': True},
        {'match': '𝜃𝑡+1 = 𝜃𝑡−𝜂∙𝑚̂𝑡', 'latex': [r'\theta_{t+1}=\theta_t-\frac{\eta\hat m_t}{\sqrt{\hat v_t}+\epsilon}'], 'only': True},
    ],
    ('中級', 'guide3', 176): [
        {'match': 'Loss = 原始損失', 'latex': [r'\mathrm{Loss}=\text{原始損失}+\lambda\sum_i|\theta_i|'], 'only': False},
    ],
    ('中級', 'guide3', 177): [
        {'match': 'Loss = 原始損失', 'latex': [r'\mathrm{Loss}=\text{原始損失}+\lambda\sum_i\theta_i^2'], 'only': False},
    ],
}


# Publication text overlays.  Official errata and source-print corrections are
# kept out of guide_ocr/page_extract SSOT; original screenshots remain visible.
TEXT_REPAIRS: dict[tuple[str, str], list[tuple[str, str]]] = {
    ('初級', 'guide1'): [
        ('Type II 錯誤 ( $ \\alpha $)', 'Type I 錯誤 ( $ \\alpha $)'),
        ('Type II 錯誤（α）', 'Type I 錯誤（α）'),
        ('𝑿𝒎𝒂𝒏', '𝑿𝒎𝒂𝒙'),
    ],
    ('中級', 'guide3'): [
        ('公式：Recall = 𝑇𝑃+𝐹𝑃', '公式：Recall = 𝑇𝑃+𝐹𝑁'),
        ('∑ 𝑒𝑧𝑖 𝐾 𝑗=1', '∑ 𝑒𝑧𝑗 𝐾 𝑗=1'),
    ],
}


# Formula fragments that are removed from prose once the adjacent source
# equation is rendered.  This prevents the numerator/denominator OCR fragments
# from appearing as a second, flattened equation.
TEXT_SIMPLIFICATIONS: dict[tuple[str, str, int], list[tuple[str, str]]] = {
    ('中級', 'guide3', 154): [
        ('準確率（Accuracy） 𝑇𝑃+𝑇𝑁', '準確率（Accuracy）'),
        ('精確率（Precision） 𝑇𝑃', '精確率（Precision）'),
        ('召回率（Recall） 𝑇𝑃', '召回率（Recall）'),
        ('F1 分數（F1-Score） Precision∙Recall', 'F1 分數（F1-Score）'),
    ],
    ('中級', 'guide3', 155): [
        ('均方誤差（Mean Squared Error, MSE） 1 𝑛∑ (𝑦𝑖−𝑦̂𝑖)2 𝑛 𝑖=1', '均方誤差（Mean Squared Error, MSE）'),
    ],
    ('中級', 'guide3', 156): [
        ('平均絕對誤差（Mean Absolute Error, MAE） 1 𝑛∑ |𝑦𝑖−𝑦̂𝑖| 𝑛 𝑖=1', '平均絕對誤差（Mean Absolute Error, MAE）'),
        ('均方根誤差（Root Mean Squared Error, RMSE） 1 𝑛∑ (𝑦𝑖−𝑦̂𝑖)2 𝑛 𝑖=1', '均方根誤差（Root Mean Squared Error, RMSE）'),
    ],
}


# Page-scoped official errata overlays.  Keep these separate from key-wide
# replacements: page 92 legitimately contains the expanded first term w_1x_1,
# while the summation on page 93 must use the indexed term w_i x_i.
PAGE_TEXT_REPAIRS: dict[tuple[str, str, int], list[tuple[str, str]]] = {
    ('中級', 'guide3', 93): [
        ('∑ 𝑤1𝑥1', '∑ 𝑤𝑖𝑥𝑖'),
    ],
}


SEMANTIC_VISUAL_PAGES: dict[tuple[str, str, int], str] = {
    ('初級', 'guide1', 54): '鑑別式 AI 與生成式 AI 關係圖',
    ('中級', 'guide2', 14): '箱形圖構成示意',
    ('中級', 'guide2', 17): '機率與統計原圖',
    ('中級', 'guide2', 18): '機率分佈原圖',
    **{('中級', 'guide2', page): '資料處理流程原圖' for page in range(117, 127)},
    ('中級', 'guide3', 60): '分類模型原圖',
    ('中級', 'guide3', 149): '模型評估原圖',
    ('中級', 'guide3', 155): '迴歸評估原圖',
}


OCR_VISUAL_FALLBACKS: dict[tuple[str, str, int], dict[str, Any]] = {
    ('初級', 'guide1', 54): {
        'source': BASE / 'data/初級/guide_ocr/guide1/pages/page_0055/imgs/img_in_image_box_431_978_1958_1475.jpg',
        'filename': 'source_visual_01.jpg',
        'bbox': [103.4, 234.7, 470.0, 354.0],
    },
    ('中級', 'guide2', 14): {
        'source': BASE / 'data/中級/guide_ocr/guide2/pages/page_0015/imgs/img_in_chart_box_322_1113_2044_1767.jpg',
        'filename': 'source_visual_01.jpg',
        'bbox': [77.3, 267.1, 490.6, 424.1],
    },
}


# The inventory registries below are the committed, machine-readable projection of
# `/tmp/ocr_defects_track_a.json`.  They deliberately name the route that a
# reader actually opens; looking for a page in any aggregate node is not a
# sufficient audit because the same physical page can occur in several nodes.
# IDs are stored as values, never inferred from insertion/iteration order.
FORMULA_INVENTORY_BY_PAGE: dict[tuple[str, str, int], dict[str, str]] = {
    ('初級', 'guide1', 45): {'id': 'TA-001', 'node': 's1c3'},
    ('初級', 'guide1', 46): {'id': 'TA-002', 'node': 's1c3'},
    ('初級', 'guide2', 10): {'id': 'TA-003', 'node': 's2c1'},
    ('初級', 'guide2', 17): {'id': 'TA-004', 'node': 's2pdf-c3'},
    ('初級', 'guide2', 40): {'id': 'TA-005', 'node': 's2c3'},
    ('初級', 'guide2', 48): {'id': 'TA-006', 'node': 's2c3'},
    ('中級', 'guide1', 57): {'id': 'TA-007', 'node': 'mid-s1c2'},
    ('中級', 'guide1', 58): {'id': 'TA-008', 'node': 'mid-s1c2'},
    ('中級', 'guide1', 99): {'id': 'TA-009', 'node': 'mid-s1c5'},
    ('中級', 'guide2', 11): {'id': 'TA-010', 'node': 'mid-s2c1'},
    ('中級', 'guide2', 12): {'id': 'TA-011', 'node': 'mid-s2c1'},
    ('中級', 'guide2', 21): {'id': 'TA-012', 'node': 'mid-s2c2'},
    ('中級', 'guide2', 22): {'id': 'TA-013', 'node': 'mid-s2c2'},
    ('中級', 'guide2', 23): {'id': 'TA-014', 'node': 'mid-s2c2'},
    ('中級', 'guide2', 24): {'id': 'TA-015', 'node': 'mid-s2c2'},
    ('中級', 'guide2', 25): {'id': 'TA-016', 'node': 'mid-s2c2'},
    ('中級', 'guide2', 27): {'id': 'TA-017', 'node': 'mid-s2c2'},
    ('中級', 'guide2', 43): {'id': 'TA-018', 'node': 'mid-s2c3'},
    ('中級', 'guide2', 44): {'id': 'TA-019', 'node': 'mid-s2c3'},
    ('中級', 'guide3', 9): {'id': 'TA-020', 'node': 'mid-s3c1'},
    ('中級', 'guide3', 11): {'id': 'TA-021', 'node': 'mid-s3c1'},
    ('中級', 'guide3', 15): {'id': 'TA-022', 'node': 'mid-s3c2'},
    ('中級', 'guide3', 16): {'id': 'TA-023', 'node': 'mid-s3c2'},
    ('中級', 'guide3', 17): {'id': 'TA-024', 'node': 'mid-s3c2'},
    ('中級', 'guide3', 19): {'id': 'TA-025', 'node': 'mid-s3c2'},
    ('中級', 'guide3', 20): {'id': 'TA-026', 'node': 'mid-s3c2'},
    ('中級', 'guide3', 21): {'id': 'TA-027', 'node': 'mid-s3c2'},
    ('中級', 'guide3', 50): {'id': 'TA-028', 'node': 'mid-s3c5'},
    ('中級', 'guide3', 63): {'id': 'TA-029', 'node': 'mid-s3c5'},
    ('中級', 'guide3', 65): {'id': 'TA-030', 'node': 'mid-s3c5'},
    ('中級', 'guide3', 72): {'id': 'TA-031', 'node': 'mid-s3c5'},
    ('中級', 'guide3', 86): {'id': 'TA-032', 'node': 'mid-s3c5'},
    ('中級', 'guide3', 92): {'id': 'TA-033', 'node': 'mid-s3c6'},
    ('中級', 'guide3', 154): {'id': 'TA-034', 'node': 'mid-s3c9'},
    ('中級', 'guide3', 155): {'id': 'TA-035', 'node': 'mid-s3c9'},
    ('中級', 'guide3', 156): {'id': 'TA-036', 'node': 'mid-s3c9'},
    ('中級', 'guide3', 169): {'id': 'TA-037', 'node': 'mid-s3c10'},
    ('中級', 'guide3', 170): {'id': 'TA-038', 'node': 'mid-s3c10'},
    ('中級', 'guide3', 172): {'id': 'TA-039', 'node': 'mid-s3c10'},
    ('中級', 'guide3', 173): {'id': 'TA-040', 'node': 'mid-s3c10'},
    ('中級', 'guide3', 174): {'id': 'TA-041', 'node': 'mid-s3c10'},
    ('中級', 'guide3', 176): {'id': 'TA-042', 'node': 'mid-s3c10'},
    ('中級', 'guide3', 177): {'id': 'TA-043', 'node': 'mid-s3c10'},
}


EXERCISE_PROVENANCE_PAGES: dict[tuple[str, str, str], list[int]] = {
    ('初級', 'guide1', 's1c1'): [26, 27, 28],
    ('初級', 'guide1', 's1c2'): [35, 36, 37],
    ('初級', 'guide1', 's1c3'): [50, 51, 52],
    ('初級', 'guide1', 's1c4'): [66, 67, 68],
    ('初級', 'guide2', 's2c1'): [18, 19, 20, 21],
    ('初級', 'guide2', 's2c2'): [33, 34, 35],
    ('初級', 'guide2', 's2c3'): [58, 59],
    ('中級', 'guide1', 'mid-s1c4'): [91, 92, 93],
    ('中級', 'guide1', 'mid-s1c7'): [138, 139, 140],
    ('中級', 'guide1', 'mid-s1c9'): [164, 165, 166],
    ('中級', 'guide2', 'mid-s2c3'): [53, 54],
    ('中級', 'guide2', 'mid-s2c6'): [85, 86, 87],
    ('中級', 'guide2', 'mid-s2c9'): [135, 136, 137],
    ('中級', 'guide2', 'mid-s2c13'): [178, 179, 180],
    ('中級', 'guide3', 'mid-s3c3'): [35, 36, 37],
    ('中級', 'guide3', 'mid-s3c6'): [131, 132, 133],
    ('中級', 'guide3', 'mid-s3c10'): [187, 188, 189, 190],
    ('中級', 'guide3', 'mid-s3c12'): [218, 219, 220, 221],
}


TABLE_PROVENANCE_REPAIRS: list[dict[str, Any]] = [
    {'id': 'TA-106', 'level': '中級', 'key': 'guide2', 'node': 'mid-s2pdf-c1', 'block': 'block-1', 'pages': [4, 5]},
    {'id': 'TA-107', 'level': '中級', 'key': 'guide1', 'node': 'mid-s1c1', 'block': 'block-95', 'pages': [18, 19]},
    {'id': 'TA-108', 'level': '中級', 'key': 'guide1', 'node': 'mid-s1c2', 'block': 'block-15', 'pages': [47, 48]},
]


OFF_BY_ONE_REPAIRS: list[dict[str, Any]] = [
    {'id': 'TA-109', 'level': '初級', 'key': 'guide1', 'node': 's1c1', 'block': 'block-54', 'page': 10},
    {'id': 'TA-110', 'level': '初級', 'key': 'guide1', 'node': 's1c1', 'block': 'block-190', 'page': 18},
    {'id': 'TA-111', 'level': '初級', 'key': 'guide1', 'node': 's1c1', 'block': 'block-256', 'page': 23},
    {'id': 'TA-112', 'level': '初級', 'key': 'guide1', 'node': 's1c3', 'block': 'block-5', 'page': 39},
    {'id': 'TA-113', 'level': '初級', 'key': 'guide1', 'node': 's1c3', 'block': 'block-36', 'page': 43},
    {'id': 'TA-114', 'level': '初級', 'key': 'guide1', 'node': 's1c3', 'block': 'block-45', 'page': 44},
    {'id': 'TA-115', 'level': '初級', 'key': 'guide1', 'node': 's1c4', 'block': 'block-159', 'page': 64},
    {'id': 'TA-116', 'level': '初級', 'key': 'guide2', 'node': 's2c1', 'block': 'block-8', 'page': 7},
    {'id': 'TA-117', 'level': '初級', 'key': 'guide2', 'node': 's2c1', 'block': 'block-54', 'page': 10},
    {'id': 'TA-118', 'level': '初級', 'key': 'guide2', 'node': 's2c2', 'block': 'block-11', 'page': 23},
    {'id': 'TA-119', 'level': '初級', 'key': 'guide2', 'node': 's2c3', 'block': 'block-107', 'page': 45},
    {'id': 'TA-120', 'level': '初級', 'key': 'guide2', 'node': 's2c3', 'block': 'block-113', 'page': 46},
    {'id': 'TA-121', 'level': '中級', 'key': 'guide1', 'node': 'mid-s1c1', 'block': 'block-49', 'page': 14},
    {'id': 'TA-122', 'level': '中級', 'key': 'guide1', 'node': 'mid-s1c1', 'block': 'block-59', 'page': 15},
    {'id': 'TA-123', 'level': '中級', 'key': 'guide1', 'node': 'mid-s1c1', 'block': 'block-68', 'page': 16},
    {'id': 'TA-124', 'level': '中級', 'key': 'guide1', 'node': 'mid-s1c1', 'block': 'block-87', 'page': 18},
    {'id': 'TA-125', 'level': '中級', 'key': 'guide1', 'node': 'mid-s1c1', 'block': 'block-224', 'page': 28},
    {'id': 'TA-126', 'level': '中級', 'key': 'guide1', 'node': 'mid-s1c1', 'block': 'block-273', 'page': 32},
    {'id': 'TA-127', 'level': '中級', 'key': 'guide1', 'node': 'mid-s1c1', 'block': 'block-281', 'page': 33},
    {'id': 'TA-128', 'level': '中級', 'key': 'guide1', 'node': 'mid-s1c1', 'block': 'block-402', 'page': 45},
    {'id': 'TA-129', 'level': '中級', 'key': 'guide1', 'node': 'mid-s1c2', 'block': 'block-120', 'page': 58},
    {'id': 'TA-130', 'level': '中級', 'key': 'guide1', 'node': 'mid-s1c3', 'block': 'block-33', 'page': 69},
    {'id': 'TA-131', 'level': '中級', 'key': 'guide1', 'node': 'mid-s1c3', 'block': 'block-80', 'page': 73},
    {'id': 'TA-132', 'level': '中級', 'key': 'guide1', 'node': 'mid-s1c5', 'block': 'block-67', 'page': 101},
    {'id': 'TA-133', 'level': '中級', 'key': 'guide1', 'node': 'mid-s1c6', 'block': 'block-9', 'page': 109},
    {'id': 'TA-134', 'level': '中級', 'key': 'guide1', 'node': 'mid-s1c6', 'block': 'block-140', 'page': 119},
    {'id': 'TA-135', 'level': '中級', 'key': 'guide1', 'node': 'mid-s1c7', 'block': 'block-136', 'page': 132},
    {'id': 'TA-136', 'level': '中級', 'key': 'guide1', 'node': 'mid-s1c8', 'block': 'block-11', 'page': 143},
    {'id': 'TA-137', 'level': '中級', 'key': 'guide1', 'node': 'mid-s1c9', 'block': 'block-11', 'page': 155},
    {'id': 'TA-138', 'level': '中級', 'key': 'guide2', 'node': 'mid-s2c2', 'block': 'block-11', 'page': 20},
    {'id': 'TA-139', 'level': '中級', 'key': 'guide2', 'node': 'mid-s2c3', 'block': 'block-88', 'page': 38},
    {'id': 'TA-140', 'level': '中級', 'key': 'guide2', 'node': 'mid-s2c3', 'block': 'block-315', 'page': 51},
    {'id': 'TA-141', 'level': '中級', 'key': 'guide2', 'node': 'mid-s2c8', 'block': 'block-113', 'page': 105},
    {'id': 'TA-142', 'level': '中級', 'key': 'guide2', 'node': 'mid-s2c9', 'block': 'block-93', 'page': 129},
    {'id': 'TA-143', 'level': '中級', 'key': 'guide2', 'node': 'mid-s2c10', 'block': 'block-40', 'page': 143},
    {'id': 'TA-144', 'level': '中級', 'key': 'guide2', 'node': 'mid-s2c10', 'block': 'block-108', 'page': 148},
    {'id': 'TA-145', 'level': '中級', 'key': 'guide3', 'node': 'mid-s3c5', 'block': 'block-57', 'page': 52},
    {'id': 'TA-146', 'level': '中級', 'key': 'guide3', 'node': 'mid-s3c5', 'block': 'block-268', 'page': 63},
    {'id': 'TA-147', 'level': '中級', 'key': 'guide3', 'node': 'mid-s3c5', 'block': 'block-777', 'page': 88},
    {'id': 'TA-148', 'level': '中級', 'key': 'guide3', 'node': 'mid-s3c6', 'block': 'block-114', 'page': 98},
    {'id': 'TA-149', 'level': '中級', 'key': 'guide3', 'node': 'mid-s3c6', 'block': 'block-396', 'page': 115},
    {'id': 'TA-150', 'level': '中級', 'key': 'guide3', 'node': 'mid-s3c6', 'block': 'block-410', 'page': 116},
    {'id': 'TA-151', 'level': '中級', 'key': 'guide3', 'node': 'mid-s3c7', 'block': 'block-35', 'page': 137},
    {'id': 'TA-152', 'level': '中級', 'key': 'guide3', 'node': 'mid-s3c12', 'block': 'block-45', 'page': 208},
]


VISUAL_INVENTORY_BY_PAGE: dict[tuple[str, str, int], dict[str, str]] = {
    ('初級', 'guide1', 54): {'id': 'TA-153', 'node': 's1c4'},
    ('中級', 'guide2', 14): {'id': 'TA-154', 'node': 'mid-s2c1'},
    ('中級', 'guide2', 17): {'id': 'TA-155', 'node': 'mid-s2c1'},
    ('中級', 'guide2', 18): {'id': 'TA-156', 'node': 'mid-s2c1'},
    ('中級', 'guide2', 117): {'id': 'TA-157', 'node': 'mid-s2c9'},
    ('中級', 'guide2', 118): {'id': 'TA-158', 'node': 'mid-s2c9'},
    ('中級', 'guide2', 119): {'id': 'TA-159', 'node': 'mid-s2c9'},
    ('中級', 'guide2', 120): {'id': 'TA-160', 'node': 'mid-s2c9'},
    ('中級', 'guide2', 121): {'id': 'TA-161', 'node': 'mid-s2c9'},
    ('中級', 'guide2', 122): {'id': 'TA-162', 'node': 'mid-s2c9'},
    ('中級', 'guide2', 123): {'id': 'TA-163', 'node': 'mid-s2c9'},
    ('中級', 'guide2', 124): {'id': 'TA-164', 'node': 'mid-s2c9'},
    ('中級', 'guide2', 125): {'id': 'TA-165', 'node': 'mid-s2c9'},
    ('中級', 'guide2', 126): {'id': 'TA-166', 'node': 'mid-s2c9'},
    ('中級', 'guide3', 60): {'id': 'TA-167', 'node': 'mid-s3c5'},
    ('中級', 'guide3', 149): {'id': 'TA-168', 'node': 'mid-s3c8'},
    ('中級', 'guide3', 155): {'id': 'TA-169', 'node': 'mid-s3c9'},
}


def _block_text(block: dict[str, Any]) -> str:
    return str(block.get('text') or block.get('title') or '')


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def _block_signature_sha256(block_type: Any, content: str) -> str:
    """Return the exact semantic signature used by the release gate."""
    return _sha256_json({'type': block_type, 'content': content})


@lru_cache(maxsize=1)
def _off_by_one_signatures() -> dict[str, dict[str, Any]]:
    """Load and validate the signed TA-109..152 publication contracts."""
    registry = json.loads(SIGNATURE_REGISTRY_PATH.read_text(encoding='utf-8'))
    if registry.get('schema') != 'track-a-ocr-signatures-v2':
        raise ValueError('unsupported Track-A signature registry schema')
    signatures = registry.get('off_by_one') or {}
    repair_ids = {repair['id'] for repair in OFF_BY_ONE_REPAIRS}
    if set(signatures) != repair_ids:
        raise ValueError('off-by-one signature registry IDs differ from repair inventory')
    for repair in OFF_BY_ONE_REPAIRS:
        expected = signatures[repair['id']]
        digest = expected.get('blockSignatureSha256')
        source_pages = expected.get('sourcePageIndexes')
        if not isinstance(digest, str) or re.fullmatch(r'[0-9a-f]{64}', digest) is None:
            raise ValueError(f"{repair['id']} has an invalid block signature")
        if expected.get('pageIndex') != repair['page']:
            raise ValueError(f"{repair['id']} signed page differs from repair inventory")
        if (
            not isinstance(source_pages, list)
            or not source_pages
            or any(not isinstance(page, int) for page in source_pages)
        ):
            raise ValueError(f"{repair['id']} has invalid signed source-page provenance")
    return signatures


_SAFE_CONTINUATION_FRAGMENT_KEYS = {
    'bbox',
    'depth',
    'id',
    'indentFirstLine',
    'kind',
    'marker',
    'nodeId',
    'pageIndex',
    'source',
    'sourcePageIndexes',
    'text',
    'type',
}


def _off_by_one_signature_candidates(
    blocks: list[dict[str, Any]],
    *,
    expected_digest: str,
    expected_page: int,
) -> list[dict[str, Any]]:
    """Find exact single blocks or adjacent cross-page fragment windows.

    A fresh guide-tree build can leave a sentence split between the bottom of
    page N-1 and the top of page N.  The reviewed publication signature is the
    authority: each boundary permits only the two source-observed forms
    (no separator, or one ASCII space), without Unicode/whitespace
    normalization, and is accepted only when the resulting signature is an
    exact match.  Continuations are deliberately limited to plain paragraph
    fragments so merging cannot silently discard formulas or other semantics.
    """
    candidates: list[dict[str, Any]] = []
    for index, block in enumerate(blocks):
        content = _block_text(block)
        if content and _block_signature_sha256(block.get('type'), content) == expected_digest:
            candidates.append({
                'kind': 'block',
                'start': index,
                'end': index,
                'content': content,
            })

    previous_page = expected_page - 1
    for start, first in enumerate(blocks):
        first_content = _block_text(first)
        if (
            first.get('pageIndex') != previous_page
            or first.get('type') not in {'paragraph', 'list_item'}
            or not first_content
        ):
            continue
        parts = [first_content]
        last_page = previous_page
        for end in range(start + 1, len(blocks)):
            continuation = blocks[end]
            continuation_page = continuation.get('pageIndex')
            if (
                continuation_page not in {previous_page, expected_page}
                or continuation_page < last_page
            ):
                break
            if (
                continuation.get('type') != 'paragraph'
                or continuation.get('marker') not in (None, '')
                or not set(continuation).issubset(_SAFE_CONTINUATION_FRAGMENT_KEYS)
            ):
                break
            continuation_content = _block_text(continuation)
            if not continuation_content:
                break
            parts.append(continuation_content)
            last_page = continuation_page
            if continuation_page != expected_page:
                continue
            for content in (''.join(parts), ' '.join(parts)):
                if _block_signature_sha256(first.get('type'), content) == expected_digest:
                    candidates.append({
                        'kind': 'window',
                        'start': start,
                        'end': end,
                        'content': content,
                    })
    return candidates


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _exercise_block_identifier(block: dict[str, Any]) -> str | None:
    match = re.match(r'^\s*(\d+)\.', str(block.get('text') or ''))
    if block.get('type') not in ('question', 'answer') or not match:
        return None
    return f'{block["type"]}:{int(match.group(1))}'


def _normalize_source_text(value: str) -> str:
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', value or ''))


def _clean_page_lines(level: str, key: str, page_index: int, base: Path = BASE) -> list[str]:
    page_path = base / 'data' / level / 'page_clean' / key / 'pages' / f'page_{page_index:03d}.json'
    page = json.loads(page_path.read_text(encoding='utf-8'))
    return [
        normalized
        for line in page.get('cleaned_lines') or []
        if (normalized := _normalize_source_text(str(line)))
    ]


def _block_page_evidence(
    block: dict[str, Any],
    level: str,
    key: str,
    page_index: int,
    base: Path = BASE,
) -> list[str]:
    """Return exact, non-trivial source lines contained in a generated block."""
    block_text = _normalize_source_text(_block_text(block))
    return [
        line for line in _clean_page_lines(level, key, page_index, base)
        if len(line) >= 10 and line in block_text
    ]


def infer_exercise_block_pages(
    block: dict[str, Any],
    level: str,
    key: str,
    candidate_pages: list[int],
    base: Path = BASE,
) -> list[int]:
    """Infer the exact source pages contributing to one exercise block.

    The old exporter assigned every question and answer the union of all
    exercise pages.  Here a page is attached only when an exact cleaned source
    line occurs in that block.  A numbered question/answer marker is also used
    because two manually corrected short answers no longer contain a long
    verbatim source line.
    """
    normalized = _normalize_source_text(_block_text(block))
    block_type = block.get('type')
    number_match = re.match(r'^(\d+)\.', normalized)
    number = number_match.group(1) if number_match else None
    result: list[int] = []
    for page_index in candidate_pages:
        lines = _clean_page_lines(level, key, page_index, base)
        exact_lines = [line for line in lines if len(line) >= 10 and line in normalized]
        marker_match = False
        if number:
            if block_type == 'answer':
                marker_match = any(line.startswith(f'{number}.Ans') for line in lines)
            elif block_type == 'question':
                # The question stem, rather than a bare number, must match.
                prefix = normalized[: min(24, len(normalized))]
                marker_match = len(prefix) >= 12 and any(line.startswith(prefix) for line in lines)
        if exact_lines or marker_match:
            result.append(page_index)
    return result


def _source_blocks(level: str, key: str, node: str, base: Path = BASE) -> list[dict[str, Any]]:
    path = base / 'data' / level / 'guide_tree' / key / 'blocks.json'
    return json.loads(path.read_text(encoding='utf-8')).get(node) or []


def apply_track_a_block_repairs(
    level: str,
    key: str,
    node: str,
    blocks: list[dict[str, Any]],
    *,
    require_prebuilt_matches: bool = False,
) -> list[dict[str, Any]]:
    """Repair guide-tree structure/provenance without mutating source SSOT."""
    repaired = [dict(block) for block in blocks]

    # TA-109..152: locate by the exact reviewed semantic signature.  Block IDs
    # are only historical metadata: a fresh guide-tree build can split a
    # cross-page sentence and shift every subsequent ID.  A unique adjacent
    # fragment window may be merged only when byte-for-byte concatenation
    # recreates the signed block.  Zero or multiple matches always fail closed.
    route_repairs = [
        repair for repair in OFF_BY_ONE_REPAIRS
        if (repair['level'], repair['key'], repair['node']) == (level, key, node)
    ]
    signatures = _off_by_one_signatures() if route_repairs else {}
    for repair in route_repairs:
        expected = signatures[repair['id']]
        expected_page = int(expected['pageIndex'])
        candidates = _off_by_one_signature_candidates(
            repaired,
            expected_digest=expected['blockSignatureSha256'],
            expected_page=expected_page,
        )
        if len(candidates) != 1:
            raise ValueError(
                f"{repair['id']} signed semantic target matched {len(candidates)}, expected 1 "
                f"in {level}/{key}/{node}"
            )
        candidate = candidates[0]
        start = int(candidate['start'])
        end = int(candidate['end'])
        target = dict(repaired[start])
        if candidate['kind'] == 'window':
            target['text'] = candidate['content']
            target.pop('title', None)
            repaired[start:end + 1] = [target]
        elif target.get('pageIndex') not in (expected_page - 1, expected_page):
            raise ValueError(
                f"{repair['id']} signed target has unexpected pageIndex {target.get('pageIndex')}"
            )
        target['pageIndex'] = expected_page
        target['sourcePageIndexes'] = list(expected['sourcePageIndexes'])
        target['trackARepairId'] = repair['id']
        target['trackAOriginalBlockId'] = repair['block']
        repaired[start] = target

    # TA-106..108: the merged rows are source-faithful, but their two fragment
    # pages must remain explicit on the exact audited table.
    for repair in TABLE_PROVENANCE_REPAIRS:
        if (repair['level'], repair['key'], repair['node']) != (level, key, node):
            continue
        target = next((block for block in repaired if block.get('id') == repair['block']), None)
        if target is None:
            if require_prebuilt_matches:
                raise ValueError(f"{repair['id']} source table {repair['block']} missing from {node}")
            continue
        target['sourcePageIndexes'] = list(repair['pages'])
        target['trackARepairId'] = repair['id']
        target['trackAOriginalBlockId'] = repair['block']

    # TA-051..105: infer provenance independently for every question/answer.
    exercise_pages = EXERCISE_PROVENANCE_PAGES.get((level, key, node))
    if exercise_pages:
        candidate_pages = list(range(min(exercise_pages) - 1, max(exercise_pages) + 1))
        for block in repaired:
            if block.get('type') not in ('question', 'answer'):
                continue
            source_pages = infer_exercise_block_pages(block, level, key, candidate_pages)
            if not source_pages:
                if require_prebuilt_matches:
                    raise ValueError(f'Cannot resolve exercise provenance for {node}/{block.get("id")}')
                continue
            block['pageIndex'] = source_pages[0]
            block['sourcePageIndexes'] = source_pages
            block['trackAExerciseProvenance'] = True

    # TA-048..050: source-reviewed hierarchy repairs.  All paragraph content is
    # retained; only the omitted/corrupt heading boundary changes.
    if (level, key, node) == ('初級', 'guide1', 's1c1'):
        title = '1. 人工智慧技術的多樣化應用'
        if not any(block.get('type') == 'heading' and block.get('title') == title for block in repaired):
            target_index = next((
                index for index, block in enumerate(repaired)
                if block.get('type') == 'paragraph' and _block_text(block).startswith(title)
            ), None)
            if target_index is None:
                if require_prebuilt_matches:
                    raise ValueError('TA-048 source paragraph missing from s1c1')
            else:
                source = repaired[target_index]
                detail = _block_text(source)[len(title):].lstrip()
                heading = {
                    'type': 'heading', 'depth': 3, 'title': title,
                    'anchor': _normalize_source_text(title),
                    'pageIndex': source.get('pageIndex'), 'bbox': source.get('bbox'),
                    'sourcePageIndexes': [source.get('pageIndex')],
                    'trackARepairId': 'TA-048',
                    'trackAOriginalBlockId': source.get('id'),
                }
                paragraph = dict(source)
                paragraph['text'] = detail
                paragraph.pop('id', None)
                repaired[target_index:target_index + 1] = [heading, paragraph]
    elif (level, key, node) == ('初級', 'guide1', 's1c3'):
        title = '1. 機器學習基本理論'
        if not any(block.get('type') == 'heading' and block.get('title') == title for block in repaired):
            target_index = next((
                index for index, block in enumerate(repaired)
                if block.get('type') == 'heading' and block.get('title') == '（1）基本原理'
            ), None)
            if target_index is None:
                if require_prebuilt_matches:
                    raise ValueError('TA-049 insertion point missing from s1c3')
            else:
                source = repaired[target_index]
                repaired.insert(target_index, {
                    'type': 'heading', 'depth': 3, 'title': title,
                    'anchor': _normalize_source_text(title),
                    'pageIndex': source.get('pageIndex'), 'bbox': source.get('bbox'),
                    'sourcePageIndexes': [source.get('pageIndex')],
                    'trackARepairId': 'TA-049',
                    'trackAOriginalBlockId': source.get('id'),
                })
    elif (level, key, node) == ('初級', 'guide1', 's1c4'):
        title = '1. 鑑別式 AI 與生成式 AI 的基本原理'
        if not any(block.get('type') == 'heading' and block.get('title') == title for block in repaired):
            target = next((block for block in repaired if _block_text(block) == '1. AI AI'), None)
            if target is None:
                if require_prebuilt_matches:
                    raise ValueError('TA-050 corrupt heading source missing from s1c4')
            else:
                original_block_id = target.get('id')
                target.pop('text', None)
                target['type'] = 'heading'
                target['depth'] = 3
                target['title'] = title
                target['anchor'] = _normalize_source_text(title)
                target['trackARepairId'] = 'TA-050'
                target['trackAOriginalBlockId'] = original_block_id
                target['sourcePageIndexes'] = [target.get('pageIndex')]

    return repaired


def apply_markdown_structure_repairs(node: str, markdown: str) -> str:
    """Keep Markdown fallback aligned with the structured heading overlay."""
    if node == 's1c1':
        title = '1. 人工智慧技術的多樣化應用'
        markdown = markdown.replace(f'{title}正在', f'### {title}\n\n正在', 1)
    elif node == 's1c3' and '### 1. 機器學習基本理論' not in markdown:
        markdown = markdown.replace('#### （1）基本原理', '### 1. 機器學習基本理論\n\n#### （1）基本原理', 1)
    elif node == 's1c4':
        markdown = re.sub(
            r'(?m)^\s*(?:###\s*)?1\.\s*AI\s+AI\s*$',
            '### 1. 鑑別式 AI 與生成式 AI 的基本原理',
            markdown,
            count=1,
        )
    return markdown


def _replace_nested(value: Any, old: str, new: str) -> Any:
    if isinstance(value, str):
        return value.replace(old, new)
    if isinstance(value, list):
        return [_replace_nested(item, old, new) for item in value]
    if isinstance(value, dict):
        return {key: _replace_nested(item, old, new) for key, item in value.items()}
    return value


TEXT_BLOCK_TARGETS: dict[tuple[str, str, str], dict[str, Any]] = {
    ('初級', 'guide1', 's1c2'): {
        'required': 'Type I 錯誤（α）',
        'forbidden': ['Type II 錯誤（α）', 'Type II 錯誤 ( $ \\alpha $)'],
    },
    ('初級', 'guide1', 's1c3'): {
        'required': '𝑿𝒎𝒂𝒙',
        'forbidden': ['𝑿𝒎𝒂𝒏'],
        'pageIndex': 45,
    },
    ('中級', 'guide3', 'mid-s3c6'): {
        'required': '∑ 𝑤𝑖𝑥𝑖',
        'forbidden': ['∑ 𝑤1𝑥1'],
        'pageIndex': 93,
    },
    ('中級', 'guide3', 'mid-s3c9'): {
        'required': '公式：Recall = 𝑇𝑃+𝐹𝑁',
        'forbidden': ['公式：Recall = 𝑇𝑃+𝐹𝑃'],
        'pageIndex': 154,
    },
    ('中級', 'guide3', 'mid-s3c10'): {
        'required': '∑ 𝑒𝑧𝑗 𝐾 𝑗=1',
        'forbidden': ['∑ 𝑒𝑧𝑖 𝐾 𝑗=1'],
        'pageIndex': 168,
    },
}


def apply_text_repairs(
    level: str,
    key: str,
    blocks: list[dict[str, Any]],
    *,
    node: str | None = None,
    strict: bool = False,
) -> list[dict[str, Any]]:
    repaired = [dict(block) for block in blocks]
    for old, new in TEXT_REPAIRS.get((level, key), []):
        repaired = [_replace_nested(block, old, new) for block in repaired]
    for (repair_level, repair_key, page_index), replacements in PAGE_TEXT_REPAIRS.items():
        if (repair_level, repair_key) != (level, key):
            continue
        for block in repaired:
            if block.get('pageIndex') != page_index:
                continue
            for old, new in replacements:
                block.update(_replace_nested(block, old, new))
    for (repair_level, repair_key, page_index), replacements in TEXT_SIMPLIFICATIONS.items():
        if (repair_level, repair_key) != (level, key):
            continue
        for block in repaired:
            if block.get('pageIndex') != page_index:
                continue
            for old, new in replacements:
                if block.get('text') == old:
                    block['text'] = new
    target = TEXT_BLOCK_TARGETS.get((level, key, node or ''))
    if strict and target:
        target_blocks = [
            block for block in repaired
            if target.get('pageIndex') is None or block.get('pageIndex') == target['pageIndex']
        ]
        serialized = json.dumps(target_blocks, ensure_ascii=False)
        if target['required'] not in serialized or any(value in serialized for value in target['forbidden']):
            raise ValueError(f'{level}/{key}/{node}: exact Track-A text repair target missing')
    return repaired


def apply_markdown_repairs(level: str, key: str, markdown: str) -> str:
    for old, new in TEXT_REPAIRS.get((level, key), []):
        markdown = markdown.replace(old, new)
    for (repair_level, repair_key, _), replacements in TEXT_SIMPLIFICATIONS.items():
        if (repair_level, repair_key) != (level, key):
            continue
        for old, new in replacements:
            markdown = markdown.replace(old, new)
    for (repair_level, repair_key, _), replacements in PAGE_TEXT_REPAIRS.items():
        if (repair_level, repair_key) != (level, key):
            continue
        for old, new in replacements:
            markdown = markdown.replace(old, new)
    if (level, key) == ('中級', 'guide3'):
        # The page text stores the Recall denominator on the next line, so the
        # ordinary same-line replacement above cannot see it.  Scope this to
        # the Recall label; Precision correctly retains TP+FP.
        markdown = re.sub(
            r'(公式：Recall\s*=\s*\n+\s*𝑇𝑃\s*\+)\s*𝐹𝑃',
            r'\1𝐹𝑁',
            markdown,
        )
    return markdown


def apply_formula_repairs(
    level: str,
    key: str,
    blocks: list[dict[str, Any]],
    *,
    node: str | None = None,
    strict: bool = False,
) -> list[dict[str, Any]]:
    """Replace generic formula matches on reviewed pages with exact mappings."""
    repaired = [dict(block) for block in blocks]
    for (repair_level, repair_key, page_index), assignments in FORMULA_PAGE_REPAIRS.items():
        if (repair_level, repair_key) != (level, key):
            continue
        page_blocks = [block for block in repaired if block.get('pageIndex') == page_index]
        inventory = FORMULA_INVENTORY_BY_PAGE.get((level, key, page_index))
        target_node = inventory['node'] if inventory else (
            'mid-s3c10' if (level, key, page_index) == ('中級', 'guide3', 168) else None
        )
        required_here = strict and node == target_node
        if not page_blocks:
            if required_here:
                raise ValueError(f'{level}/{key}/{node}/page_{page_index:03d}: formula page missing')
            continue
        for block in page_blocks:
            block.pop('formulas', None)
            block.pop('latex', None)
            block.pop('formulaOnly', None)
        for assignment in assignments:
            match = assignment['match']
            targets = [block for block in page_blocks if match in _block_text(block)]
            if required_here and len(targets) != 1:
                raise ValueError(
                    f'{level}/{key}/{node}/page_{page_index:03d}: '
                    f'formula target {match!r} matched {len(targets)}, expected 1'
                )
            if not targets:
                continue
            target = targets[0]
            target['formulas'] = [formula(latex, assignment.get('display', True)) for latex in assignment['latex']]
            if assignment.get('only'):
                target['formulaOnly'] = True
    return repaired


def _content_path(level: str, key: str, node: str, content_root: Path) -> Path:
    return content_root / f'{level}-{key}' / f'{node}.json'


def audit_generated_track_a(
    base: Path = BASE,
    *,
    content_root: Path | None = None,
    public_root: Path | None = None,
    source_screenshot_root: Path | None = None,
    signature_registry_path: Path | None = None,
    check_optional_reading_seed: bool = True,
) -> dict[str, Any]:
    """Return one exact result for every TA-001..TA-169 inventory item.

    This function is pure/read-only and is the integration entry point for
    ``audit_resources.py``.  A category total is never used as a proxy for
    coverage: the function asserts that all 169 stable IDs were evaluated.
    """
    content_root = content_root or base / 'frontend/src/generated/guideContent'
    public_root = public_root or base / 'frontend/public'
    source_screenshot_root = source_screenshot_root or public_root
    signature_registry_path = signature_registry_path or SIGNATURE_REGISTRY_PATH
    checks: dict[str, str | None] = {}
    content_cache: dict[Path, dict[str, Any]] = {}
    signature_registry = json.loads(signature_registry_path.read_text(encoding='utf-8'))
    if signature_registry.get('schema') != 'track-a-ocr-signatures-v2':
        raise AssertionError('unsupported Track-A signature registry schema')
    original_formula_keys = [key for key in FORMULA_PAGE_REPAIRS if key != ('中級', 'guide3', 168)]
    if set(original_formula_keys) != set(FORMULA_INVENTORY_BY_PAGE):
        raise AssertionError('formula repair and explicit inventory route registries differ')
    if {entry['id'] for entry in FORMULA_INVENTORY_BY_PAGE.values()} != {
        f'TA-{index:03d}' for index in range(1, 44)
    }:
        raise AssertionError('formula inventory IDs are incomplete or duplicated')
    if set(VISUAL_INVENTORY_BY_PAGE) != set(SEMANTIC_VISUAL_PAGES):
        raise AssertionError('source-visual repair and inventory route registries differ')
    if {entry['id'] for entry in VISUAL_INVENTORY_BY_PAGE.values()} != {
        f'TA-{index:03d}' for index in range(153, 170)
    }:
        raise AssertionError('source-visual inventory IDs are incomplete or duplicated')

    def load(path: Path) -> dict[str, Any]:
        if path not in content_cache:
            content_cache[path] = json.loads(path.read_text(encoding='utf-8'))
        return content_cache[path]

    def record(item_id: str, ok: bool, reason: str) -> None:
        if item_id in checks:
            raise AssertionError(f'duplicate Track-A audit id: {item_id}')
        checks[item_id] = None if ok else reason

    # TA-001..043: exact formula multiset on the intended route/page, plus an
    # exact target block check for each attachment.  This detects both missing
    # correct formulas and any extra/wrong formula left on the same page.
    for page_key, inventory in FORMULA_INVENTORY_BY_PAGE.items():
        level, key, page_index = page_key
        item_id = inventory['id']
        node = inventory['node']
        data = load(_content_path(level, key, node, content_root))
        page_blocks = [block for block in data.get('blocks', []) if block.get('pageIndex') == page_index]
        assignments = FORMULA_PAGE_REPAIRS[page_key]
        expected_page_latex = [
            formula(latex)['latex']
            for assignment in assignments
            for latex in assignment['latex']
        ]
        actual_page_latex = [
            str(entry.get('latex'))
            for block in page_blocks
            for entry in block.get('formulas') or []
        ]
        assignment_ok = True
        for assignment in assignments:
            targets = [block for block in page_blocks if assignment['match'] in _block_text(block)]
            expected = [formula(latex)['latex'] for latex in assignment['latex']]
            exact_targets = [
                block for block in targets
                if [entry.get('latex') for entry in block.get('formulas') or []] == expected
            ]
            if len(exact_targets) != 1:
                assignment_ok = False
                continue
            if bool(exact_targets[0].get('formulaOnly')) != bool(assignment.get('only')):
                assignment_ok = False
        ok = (
            bool(page_blocks)
            and assignment_ok
            and sorted(actual_page_latex) == sorted(expected_page_latex)
        )
        record(item_id, ok, f'{level}/{key}/{node}/page_{page_index:03d}: formula signature mismatch')

    # TA-044 official Type-I erratum and TA-045 Recall content/seed parity.
    s1c2 = load(_content_path('初級', 'guide1', 's1c2', content_root))
    # sourcePages intentionally retain the printed source table/screenshot.
    s1c2_serialized = json.dumps({
        'content': s1c2.get('content'), 'blocks': s1c2.get('blocks'),
    }, ensure_ascii=False)
    bad_type_i = ('Type II 錯誤 ( $ \\alpha $)', 'Type II 錯誤（α）')
    type_i_ok = all(value not in s1c2_serialized for value in bad_type_i) and (
        'Type I 錯誤 ( $ \\alpha $)' in s1c2_serialized or 'Type I 錯誤（α）' in s1c2_serialized
    )
    record('TA-044', type_i_ok, 's1c2 still contains the Type-II/alpha source error')

    recall = load(_content_path('中級', 'guide3', 'mid-s3c9', content_root))
    seed_path = base / 'data/中級/guide/subject3_reading_guide.json'
    def recall_section_correct(content: str) -> bool:
        start = content.find('召回率（Recall）')
        end = content.find('F1 分數', start + 1)
        if start < 0 or end < 0:
            return False
        section = _normalize_source_text(content[start:end])
        return 'TP+FN' in section and 'TP+FP' not in section

    recall_ok = recall_section_correct(str(recall.get('content') or ''))
    recall_ok = recall_ok and any(
        block.get('pageIndex') == 154
        and '公式：Recall = 𝑇𝑃+𝐹𝑁' in _block_text(block)
        and [entry.get('latex') for entry in block.get('formulas') or []]
        == [r'\operatorname{Recall}=\frac{TP}{TP+FN}']
        for block in recall.get('blocks') or []
    )
    # reading_guide is intentionally gitignored.  When the standard local
    # post-export step produced it, audit it deeply; a fresh clone gates the
    # committed guideContent and does not fail merely because the snapshot is
    # absent.
    if check_optional_reading_seed and seed_path.exists():
        seed = json.loads(seed_path.read_text(encoding='utf-8'))
        seed_chapter = next((chapter for chapter in seed.get('chapters') or [] if chapter.get('id') == 'mid-s3c9'), None)
        recall_ok = recall_ok and bool(seed_chapter) and recall_section_correct(str(seed_chapter.get('content') or ''))
    record('TA-045', recall_ok, 'Recall FP→FN correction is not aligned in guideContent and reading seed')

    # TA-046..047: exact committed heading/table content and provenance.  A
    # generic "some table has >=10 rows" check would allow replacement or
    # truncation of the actual bibliography to pass.
    bibliography_signatures = signature_registry.get('bibliography') or {}
    if set(bibliography_signatures) != {'TA-046', 'TA-047'}:
        raise AssertionError('bibliography signature registry IDs differ from inventory')
    for item_id, expected in bibliography_signatures.items():
        level, key, node = expected['level'], expected['key'], expected['node']
        data = load(_content_path(level, key, node, content_root))
        blocks = data.get('blocks') or []
        expected_heading = expected['heading']
        headings = [block for block in blocks if block.get('id') == expected_heading['blockId']]
        semantic_headings = [
            block for block in blocks
            if block.get('type') == 'heading' and block.get('title') == expected_heading['title']
        ]
        heading_ok = (
            len(headings) == 1
            and len(semantic_headings) == 1
            and headings[0].get('type') == 'heading'
            and headings[0].get('title') == expected_heading['title']
            and headings[0].get('depth') == expected_heading['depth']
            and headings[0].get('pageIndex') == expected_heading['pageIndex']
        )
        expected_table = expected['table']
        tables = [block for block in blocks if block.get('id') == expected_table['blockId']]
        semantic_tables = [
            block for block in blocks
            if block.get('type') == 'table'
            and _sha256_json(block.get('rows')) == expected_table['rowsSha256']
        ]
        table_ok = (
            len(tables) == 1
            and len(semantic_tables) == 1
            and tables[0].get('type') == 'table'
            and tables[0].get('pageIndex') == expected_table['pageIndex']
            and tables[0].get('sourcePageIndexes') == expected_table['sourcePageIndexes']
            and _sha256_json(tables[0].get('rows')) == expected_table['rowsSha256']
        )
        swallowed = any(block.get('type') == 'answer' and '參考書目' in _block_text(block) for block in blocks)
        record(item_id, heading_ok and table_ok and not swallowed, f'{node} exact bibliography signature mismatch')

    # TA-048..050 exact block identity, page provenance, and repair metadata.
    # TA-048's inventory page_index 7 is where the first depth-4 child exposes
    # the missing-parent jump.  The promoted parent's text/bbox is physically
    # on page_index 6 (sourcePages.page 7, printed label 3-1).  Both facts are
    # committed so an apparent off-by-one cannot be silently "fixed".
    heading_signatures = signature_registry.get('headings') or {}
    if set(heading_signatures) != {'TA-048', 'TA-049', 'TA-050'}:
        raise AssertionError('heading signature registry IDs differ from inventory')
    if (
        heading_signatures['TA-048'].get('inventoryPageIndex') != 7
        or heading_signatures['TA-048'].get('pageIndex') != 6
    ):
        raise AssertionError('TA-048 inventory/source page reconciliation changed')
    for item_id, expected in heading_signatures.items():
        level, key, node, title = (
            expected['level'], expected['key'], expected['node'], expected['title'],
        )
        data = load(_content_path(level, key, node, content_root))
        semantic_matches = [
            block for block in data.get('blocks', [])
            if block.get('type') == 'heading' and block.get('title') == title
        ]
        matches = [block for block in semantic_matches if block.get('id') == expected['blockId']]
        ok = (
            len(semantic_matches) == 1
            and len(matches) == 1
            and matches[0].get('depth') == expected['depth']
            and matches[0].get('pageIndex') == expected['pageIndex']
            and matches[0].get('sourcePageIndexes') == expected['sourcePageIndexes']
            and matches[0].get('trackARepairId') == item_id
            and matches[0].get('trackAOriginalBlockId') == expected['trackAOriginalBlockId']
        )
        record(item_id, ok, f'{node} exact heading identity/provenance mismatch: {title}')

    # TA-051..105: compare every exercise block against the committed exact
    # signature registry.  CI does not need the gitignored page caches, and a
    # blanket chapter-wide union fails because every block has its own expected
    # pageIndex/sourcePageIndexes tuple.
    exercise_inventory = signature_registry.get('exerciseInventoryIdByRoutePage') or {}
    expected_exercise_keys = {
        f'{level}/{key}/{node}/{page_index}'
        for (level, key, node), audited_pages in EXERCISE_PROVENANCE_PAGES.items()
        for page_index in audited_pages
    }
    if set(exercise_inventory) != expected_exercise_keys:
        raise AssertionError('exercise inventory route/page keys are incomplete or unexpected')
    if set(exercise_inventory.values()) != {f'TA-{index:03d}' for index in range(51, 106)}:
        raise AssertionError('exercise inventory IDs are incomplete or duplicated')
    for (level, key, node), audited_pages in EXERCISE_PROVENANCE_PAGES.items():
        data = load(_content_path(level, key, node, content_root))
        blocks = [block for block in data.get('blocks', []) if block.get('type') in ('question', 'answer')]
        route_key = f'{level}/{key}/{node}'
        expected_node = signature_registry['exercise'][route_key]
        if expected_node.get('auditedPages') != audited_pages:
            raise AssertionError(f'{route_key} audited-page registry mismatch')
        actual_by_id: dict[str, list[dict[str, Any]]] = {}
        for block in blocks:
            identifier = _exercise_block_identifier(block)
            if identifier:
                actual_by_id.setdefault(identifier, []).append(block)
        for page_index in audited_pages:
            expected_blocks = expected_node['blocks']
            contributors = [
                identifier for identifier, expected in expected_blocks.items()
                if page_index in expected['sourcePageIndexes']
            ]
            exact = bool(contributors)
            identifiers = set(expected_blocks) | set(actual_by_id)
            for identifier in identifiers:
                expected = expected_blocks.get(identifier)
                matches = actual_by_id.get(identifier) or []
                actual_claims_page = any(
                    page_index in list(block.get('sourcePageIndexes') or [block.get('pageIndex')])
                    for block in matches
                )
                expected_claims_page = bool(expected and page_index in expected['sourcePageIndexes'])
                if not actual_claims_page and not expected_claims_page:
                    continue
                exact = exact and expected is not None and len(matches) == 1
                if expected is None or len(matches) != 1:
                    continue
                block = matches[0]
                exact = exact and block.get('trackAExerciseProvenance') is True
                exact = exact and block.get('pageIndex') == expected['pageIndex']
                exact = exact and block.get('sourcePageIndexes') == expected['sourcePageIndexes']
                exact = exact and _sha256_json({
                    'type': block.get('type'),
                    'content': _normalize_source_text(str(block.get('text') or '')),
                }) == expected['blockSignatureSha256']
            record(
                exercise_inventory[f'{route_key}/{page_index}'],
                exact,
                f'{level}/{key}/{node}/page_{page_index:03d}: non-exact exercise provenance',
            )

    # TA-106..108: exact committed row signature + exact two-page provenance.
    for repair in TABLE_PROVENANCE_REPAIRS:
        expected = signature_registry['tables'][repair['id']]
        data = load(_content_path(repair['level'], repair['key'], repair['node'], content_root))
        matches = [block for block in data.get('blocks', []) if block.get('trackARepairId') == repair['id']]
        ok = (
            len(matches) == 1
            and matches[0].get('type') == 'table'
            and _sha256_json(matches[0].get('rows')) == expected['rowsSha256']
            and matches[0].get('sourcePageIndexes') == repair['pages']
        )
        record(repair['id'], ok, f"{repair['node']}/{repair['block']}: merged table provenance mismatch")

    # TA-109..152: exact committed block signature, corrected pageIndex, and
    # deterministic fragment provenance.  Also reject an uncorrected duplicate.
    for repair in OFF_BY_ONE_REPAIRS:
        expected = signature_registry['off_by_one'][repair['id']]
        data = load(_content_path(repair['level'], repair['key'], repair['node'], content_root))
        matches = [block for block in data.get('blocks', []) if block.get('trackARepairId') == repair['id']]
        signature_duplicates = [block for block in data.get('blocks', []) if _sha256_json({
            'type': block.get('type'), 'content': _block_text(block),
        }) == expected['blockSignatureSha256']]
        ok = (
            len(matches) == 1
            and len(signature_duplicates) == 1
            and _sha256_json({'type': matches[0].get('type'), 'content': _block_text(matches[0])})
            == expected['blockSignatureSha256']
            and matches[0].get('pageIndex') == expected['pageIndex']
            and matches[0].get('sourcePageIndexes') == expected['sourcePageIndexes']
        )
        record(repair['id'], ok, f"{repair['node']}/{repair['block']}: exact pageIndex/provenance signature mismatch")

    # TA-153..169: exact PDF/OCR source assets inline on the specified route.
    visual_signatures = signature_registry.get('visuals') or {}
    if set(visual_signatures) != {f'TA-{index:03d}' for index in range(153, 170)}:
        raise AssertionError('visual signature registry IDs are incomplete or unexpected')
    for page_key, inventory in VISUAL_INVENTORY_BY_PAGE.items():
        level, key, page_index = page_key
        item_id = inventory['id']
        node = inventory['node']
        expected = visual_signatures[item_id]
        expected_location = {
            'level': level, 'key': key, 'node': node, 'pageIndex': page_index,
        }
        if any(expected.get(field) != value for field, value in expected_location.items()):
            raise AssertionError(f'{item_id} visual signature location differs from explicit inventory')
        data = load(_content_path(level, key, node, content_root))
        matches = [
            block for block in data.get('blocks', [])
            if block.get('type') == 'source_image'
            and block.get('pageIndex') == page_index
        ]
        src_occurrences = [
            block for block in data.get('blocks', [])
            if block.get('type') == 'source_image' and block.get('src') == expected.get('src')
        ]
        asset = public_root / str(expected.get('src') or '').lstrip('/')
        assets_ok = (
            len(matches) == 1
            and len(src_occurrences) == 1
            and matches[0] is src_occurrences[0]
            and matches[0].get('src') == expected.get('src')
            and matches[0].get('alt') == expected.get('alt')
            and matches[0].get('sourcePageIndexes') == [page_index]
            and asset.is_file()
            and _sha256_file(asset) == expected.get('assetSha256')
        )
        record(
            item_id,
            assets_ok,
            f'{level}/{key}/{node}/page_{page_index:03d}: exact source visual is not inline',
        )

    expected_ids = {f'TA-{index:03d}' for index in range(1, 170)}
    if set(checks) != expected_ids:
        missing = sorted(expected_ids - set(checks))
        extra = sorted(set(checks) - expected_ids)
        raise AssertionError(f'Track-A gate coverage mismatch; missing={missing}, extra={extra}')

    category_ranges = {
        'formula_and_errata': range(1, 46),
        'bibliography': range(46, 48),
        'heading': range(48, 51),
        'exercise_provenance': range(51, 106),
        'table_provenance': range(106, 109),
        'block_page_index': range(109, 153),
        'source_visual': range(153, 170),
    }
    category_totals = {name: len(list(indexes)) for name, indexes in category_ranges.items()}
    category_remaining = {
        name: sum(checks[f'TA-{index:03d}'] is not None for index in indexes)
        for name, indexes in category_ranges.items()
    }
    failures = [f'{item_id}: {reason}' for item_id, reason in checks.items() if reason is not None]

    # Three reviewed source-print corrections are outside the 169 OCR inventory,
    # but are release-blocking publication overlays requested by the project.
    x_max = load(_content_path('初級', 'guide1', 's1c3', content_root))
    x_max_serialized = json.dumps({'content': x_max.get('content'), 'blocks': x_max.get('blocks')}, ensure_ascii=False)
    x_max_latex = [entry.get('latex') for block in x_max.get('blocks') or [] for entry in block.get('formulas') or []]
    softmax = load(_content_path('中級', 'guide3', 'mid-s3c10', content_root))
    softmax_blocks = [block for block in softmax.get('blocks', []) if block.get('pageIndex') == 168]
    softmax_latex = [entry.get('latex') for block in softmax_blocks for entry in block.get('formulas') or []]
    perceptron = load(_content_path('中級', 'guide3', 'mid-s3c6', content_root))
    perceptron_blocks = [block for block in perceptron.get('blocks', []) if block.get('pageIndex') == 93]
    perceptron_serialized = json.dumps(perceptron_blocks, ensure_ascii=False)
    perceptron_content = _normalize_source_text(str(perceptron.get('content') or ''))
    perceptron_latex = [
        entry.get('latex')
        for block in perceptron_blocks
        for entry in block.get('formulas') or []
    ]
    source_screenshot_signatures = signature_registry.get('publicationSourceScreenshots') or {}
    expected_overlay_names = {
        'source-math:X_max',
        'source-math:softmax-z_j',
        'official-errata:perceptron-w_i-x_i',
    }
    if set(source_screenshot_signatures) != expected_overlay_names:
        raise AssertionError('publication source-screenshot signature names differ from release contract')
    expected_overlay_locations = {
        'source-math:X_max': ('初級', 'guide1', 's1c3', 45),
        'source-math:softmax-z_j': ('中級', 'guide3', 'mid-s3c10', 168),
        'official-errata:perceptron-w_i-x_i': ('中級', 'guide3', 'mid-s3c6', 93),
    }
    for overlay_name, (level, key, node, page_index) in expected_overlay_locations.items():
        expected = source_screenshot_signatures[overlay_name]
        if (
            expected.get('level'), expected.get('key'), expected.get('node'), expected.get('pageIndex')
        ) != (level, key, node, page_index):
            raise AssertionError(f'{overlay_name} source-screenshot location differs from release contract')

    def source_screenshot_preserved(overlay_name: str, data: dict[str, Any]) -> bool:
        """Require the exact source-page URL and committed source-image bytes.

        The screenshot is provenance, not decoration: merely retaining any
        non-empty ``/pdf-assets`` URL would let a correction cite the wrong PDF
        page while still passing the publication overlay gate.
        """
        expected = source_screenshot_signatures[overlay_name]
        page_index = expected['pageIndex']
        source_pages = [
            page for page in data.get('sourcePages') or []
            if page.get('index') == page_index
        ]
        if len(source_pages) != 1 or source_pages[0].get('image') != expected['src']:
            return False
        asset = source_screenshot_root / expected['src'].lstrip('/')
        return asset.is_file() and _sha256_file(asset) == expected['assetSha256']

    if check_optional_reading_seed and seed_path.exists():
        seed = json.loads(seed_path.read_text(encoding='utf-8'))
        seed_chapter = next(
            (chapter for chapter in seed.get('chapters') or [] if chapter.get('id') == 'mid-s3c6'),
            None,
        )
        perceptron_seed_ok = bool(seed_chapter) and (
            '∑wixi' in _normalize_source_text(str(seed_chapter.get('content') or ''))
            and '∑w1x1' not in _normalize_source_text(str(seed_chapter.get('content') or ''))
        )
    else:
        perceptron_seed_ok = True

    overlay_checks = {
        'source-math:X_max': (
            '𝑿𝒎𝒂𝒏' not in x_max_serialized
            and '𝑿𝒎𝒂𝒙' in x_max_serialized
            and any(r'X_{\max}' in str(latex) for latex in x_max_latex)
            and source_screenshot_preserved('source-math:X_max', x_max)
        ),
        'source-math:softmax-z_j': (
            r'\operatorname{Softmax}(z_i)=\frac{e^{z_i}}{\sum_{j=1}^{K}e^{z_j}}' in softmax_latex
            and '∑ 𝑒𝑧𝑖 𝐾 𝑗=1' not in json.dumps(softmax, ensure_ascii=False)
            and source_screenshot_preserved('source-math:softmax-z_j', softmax)
        ),
        'official-errata:perceptron-w_i-x_i': (
            '∑ 𝑤1𝑥1' not in perceptron_serialized
            and '∑ 𝑤𝑖𝑥𝑖' in perceptron_serialized
            and '∑w1x1' not in perceptron_content
            and '∑wixi' in perceptron_content
            and r'\left(Z=\sum_{i=1}^{n} w_{i}x_{i} + b\right)' in perceptron_latex
            and perceptron_seed_ok
            and source_screenshot_preserved('official-errata:perceptron-w_i-x_i', perceptron)
        ),
    }
    overlay_failures = [name for name, ok in overlay_checks.items() if not ok]

    # Exporter-owned publication hierarchy overlays must be present in the
    # staged candidate itself.  This prevents a schema-valid export from
    # silently reverting the s1c2/s1c4 Markdown and relying on a later manual
    # file edit to repair live output.
    publication_structure_checks: dict[str, bool] = {}
    hypothesis_title, hypothesis_depth = PROMOTE_HEADINGS['s1c2']
    hypothesis_markdown = str(s1c2.get('content') or '')
    hypothesis_headings = s1c2.get('headings') or []
    publication_structure_checks['manual-heading:s1c2-hypothesis'] = (
        hypothesis_markdown.count(f'\n{"#" * hypothesis_depth} {hypothesis_title}\n') == 1
        and hypothesis_markdown.count(f'\n{hypothesis_title}\n') == 0
        and sum(
            heading.get('title') == hypothesis_title
            and heading.get('level') == hypothesis_depth
            for heading in hypothesis_headings
        ) == 1
    )

    s1c4 = load(_content_path('初級', 'guide1', 's1c4', content_root))
    s1c4_markdown = str(s1c4.get('content') or '')
    s1c4_lines = s1c4_markdown.splitlines()
    s1c4_headings = s1c4.get('headings') or []
    demoted_exact = all(
        s1c4_lines.count(f'### {title}') == 1
        and s1c4_lines.count(f'#### {title}') == 0
        and sum(
            heading.get('title') == title and heading.get('level') == 3
            for heading in s1c4_headings
        ) == 1
        for title in DEMOTE_HEADINGS
    )
    shortened_exact = all(
        sum(heading.get('title') == short_title for heading in s1c4_headings) == 1
        and all(heading.get('title') != long_title for heading in s1c4_headings)
        for long_title, short_title in SHORTEN_HEADINGS.items()
    )
    publication_structure_checks['manual-heading:s1c4-hierarchy'] = demoted_exact and shortened_exact
    structure_failures = [name for name, ok in publication_structure_checks.items() if not ok]
    return {
        'inventory_total': len(expected_ids),
        'checked_total': len(checks),
        'category_totals': category_totals,
        'category_remaining': category_remaining,
        'remaining': len(failures),
        'failures': failures,
        'checked_ids': sorted(checks),
        'publication_overlay_total': len(overlay_checks),
        'publication_overlay_names': sorted(overlay_checks),
        'publication_overlay_remaining': len(overlay_failures),
        'publication_overlay_failures': overlay_failures,
        'publication_structure_total': len(publication_structure_checks),
        'publication_structure_names': sorted(publication_structure_checks),
        'publication_structure_remaining': len(structure_failures),
        'publication_structure_failures': structure_failures,
    }


def main() -> None:
    result = audit_generated_track_a()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(
        1 if (
            result['remaining']
            or result['publication_overlay_remaining']
            or result['publication_structure_remaining']
        ) else 0
    )


if __name__ == '__main__':
    main()
