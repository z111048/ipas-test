#!/usr/bin/env python3
"""Annotate exam image assets with readable Markdown alternatives.

Some official exam questions embed code snippets as raster images. Those images
are still kept as source references, but when the code is readable and stable we
attach a text alternative so the frontend can show a code block first and fold
the original image behind a disclosure.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

BASE = Path('/home/james/projects/ipas-test')
VGG16_CODE_SRC = '/pdf-assets/中級/exam3/page_010/vgg16_code_p010.png'
VGG16_CODE_MARKDOWN = """from torchsummary import summary
from torchvision import models
model = models.vgg16(weights='IMAGENET1K_V1')
summary(model, (3, 150, 150))"""
GAME_PREVIEW_SRC = '/pdf-assets/中級/exam2/page_012/image_02_01.png'
GAME_YEAR_SRC = '/pdf-assets/中級/exam2/page_013/image_01_01.png'
MARKETING_LOAD_SRC = '/pdf-assets/中級/exam2/page_014/image_01_01.png'
MARKETING_PREVIEW_SRC = '/pdf-assets/中級/exam2/page_015/image_01_01.png'

ANNOTATIONS: dict[str, dict[str, str]] = {
    VGG16_CODE_SRC: {
        'markdown_language': 'python',
        'markdown_title': 'VGG16 載入程式碼',
        'markdown': VGG16_CODE_MARKDOWN,
    },
    GAME_PREVIEW_SRC: {
        'markdown_language': 'text',
        'markdown_title': 'vgsales 資料預覽',
        'markdown': """import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 載入資料
data = pd.read_csv("vgsales.csv")
data.head()

   Rank                       Name Platform    Year         Genre Publisher  NA_Sales  EU_Sales  JP_Sales  Other_Sales  Global_Sales
0     1                 Wii Sports      Wii  2006.0        Sports  Nintendo     41.49     29.02      3.77         8.46         82.74
1     2          Super Mario Bros.      NES  1985.0      Platform  Nintendo     29.08      3.58      6.81         0.77         40.24
2     3             Mario Kart Wii      Wii  2008.0        Racing  Nintendo     15.85     12.88      3.79         3.31         35.82
3     4          Wii Sports Resort      Wii  2009.0        Sports  Nintendo     15.75     11.01      3.28         2.96         33.00
4     5  Pokemon Red/Pokemon Blue       GB  1996.0  Role-Playing  Nintendo     11.27      8.89     10.22         1.00         31.37""",
    },
    GAME_YEAR_SRC: {
        'markdown_language': 'text',
        'markdown_title': "data['Year'] 輸出",
        'markdown': """data['Year']

0        2006.0
1        1985.0
2        2008.0
3        2009.0
4        1996.0
          ...
16593    2002.0
16594    2003.0
16595    2008.0
16596    2010.0
16597    2003.0
Name: Year, Length: 16598, dtype: float64""",
    },
    '/pdf-assets/中級/exam2/page_010/image_01_01.png': {
        'markdown_language': 'text',
        'markdown_title': '虛擬程式碼',
        'markdown': """Input:
  - data_set: 包含 N 筆資料的資料集
  - model_training_function: 用來訓練模型的函式
  - model_evaluation_function: 用來評估模型的函式（如計算誤差或準確率）

Output:
  - 平均評估指標（如平均準確率或平均誤差）

Algorithm:
1. 初始化評估指標列表 metrics = []
2. 對 i = 1 到 N:
   a. 將第 i 筆資料作為測試集 test_data
   b. 將其餘 N-1 筆資料作為訓練集 train_data
   c. 使用 model_training_function 在 train_data 上訓練模型
   d. 使用訓練好的模型對 test_data 做預測，計算評估指標 metric_i
   e. 將 metric_i 加入 metrics
3. 計算 metrics 的平均值 mean_metric
4. 回傳 mean_metric""",
    },
    '/pdf-assets/中級/exam2/page_011/image_01_01.png': {
        'markdown_language': 'text',
        'markdown_title': '虛擬程式碼',
        'markdown': """Input:
  - data_points: N 筆資料，每筆資料有 D 個特徵
  - X: 要分成的群數

Output:
  - clusters: 每筆資料所屬的群組號
  - centroids: 每個群的中心點

Algorithm:
1. 隨機選擇 X 個資料點作為初始中心
2. 重複以下步驟直到收斂:
   a. 分群:
      對每個資料點，計算它到每個中心點的距離
      將資料點指派給距離最近的中心
   b. 更新中心:
      對每個群，計算該群中所有資料點的平均值
      將群中心更新為這個平均值
3. 當群中心不再變動時，停止

回傳每筆資料的群組號 clusters，以及最後的群中心 centroids""",
    },
    '/pdf-assets/中級/exam2/page_012/image_01_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Python 程式碼',
        'markdown': """import numpy as np
from scipy.stats import poisson

lambda_poisson = 5
print(poisson.pmf(5, lambda_poisson))""",
    },
    '/pdf-assets/中級/exam2/page_014/image_01_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Python 程式碼',
        'markdown': """import pandas as pd
df = pd.read_csv("marketing.csv")""",
    },
    '/pdf-assets/中級/exam2/page_015/image_01_01.png': {
        'markdown_language': 'text',
        'markdown_title': '資料預覽與描述統計',
        'markdown': """>>> df.head()
   youtube  facebook  newspaper  sales
0   276.12     45.36      83.04  26.52
1    53.40       NaN      54.12  12.48
2    20.64     55.08      83.16  11.16
3   181.80     49.56      70.20  22.20
4   216.96     12.96      70.08  15.48

>>> df.describe()
          youtube    facebook   newspaper       sales
count  200.000000  199.000000  200.000000  200.000000
mean   176.451000   27.820101   36.664800   16.827000
std    103.025084   17.808410   26.134345    6.260948
min      0.840000    0.000000    0.360000    1.920000
25%     89.250000   11.940000   15.300000   12.450000
50%    179.700000   27.000000   30.900000   15.480000
75%    262.590000   43.680000   54.120000   20.880000
max    355.680000   59.520000  136.800000   32.400000""",
    },
    '/pdf-assets/中級/exam2/page_015/image_02_01.png': {
        'markdown_language': 'text',
        'markdown_title': '執行結果',
        'markdown': """youtube      0
facebook     1
newspaper    0
sales        0
dtype: int64""",
    },
    '/pdf-assets/中級/exam2/page_016/image_01_01.png': {
        'markdown_language': 'text',
        'markdown_title': '程式碼與執行結果',
        'markdown': """from sklearn.linear_model import LinearRegression
import statsmodels.api as sm

X = df[["youtube", "facebook", "newspaper"]]
y = df["sales"]
reg = 空格1
print(reg.coef_)
X2 = sm.add_constant(X)
model_sm = 空格2
print(model_sm.summary())

OLS Regression Results
Dep. Variable: sales
Model: OLS
R-squared: 0.898
Adj. R-squared: 0.896
F-statistic: 573.0
Prob (F-statistic): 1.03e-96

coef      std err      t      P>|t|
const      3.5561     0.373    9.537   0.000
youtube    0.0455     0.001   32.702   0.000
facebook   0.1891     0.009   21.960   0.000
newspaper -0.0006     0.006   -0.108   0.914""",
    },
    '/pdf-assets/中級/exam3/page_009/exam3_q38_visual_p009.png': {
        'markdown_language': 'python',
        'markdown_title': 'Python 程式碼',
        'markdown': """def metric(y_true, y_pred):
    return sum((y_true - y_pred) ** 2) / len(y_true)""",
    },
    '/pdf-assets/中級/exam3/page_009/image_02_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Python 程式碼',
        'markdown': """def forward(x, p, training=True):
    if training:
        mask = np.random.binomial(1, p, size=x.shape)
        return x * mask / p
    else:
        return x""",
    },
    '/pdf-assets/中級/exam3/page_009/image_03_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Python 程式碼',
        'markdown': """import numpy as np

v1 = np.array([1, 2, 3])
v2 = np.array([4, 5, 6])
A = np.array([[1, 2], [3, 4]])""",
    },
    '/pdf-assets/中級/exam3/page_010/image_01_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Python 程式碼',
        'markdown': """import numpy as np

np.random.seed(123)
n = 100000
dice_rolls = np.random.randint(1, 7, size=n)

A = (dice_rolls % 2 == 0)
B = (dice_rolls > 3)
A_and_B = A & B""",
    },
    '/pdf-assets/中級/exam3/page_013/image_01_01.png': {
        'markdown_language': 'python',
        'markdown_title': '選項 A 程式碼',
        'markdown': """import torch
import torchvision.models as models

model = models.vgg16(pretrained=True)
for param in model.parameters():
    param.requires_grad = False
model.classifier[6] = torch.nn.Linear(4096, 10)""",
    },
    '/pdf-assets/中級/exam3/page_013/image_02_01.png': {
        'markdown_language': 'python',
        'markdown_title': '選項 B 程式碼',
        'markdown': """import torch
import torchvision.models as models

model = models.vgg16(pretrained=True)
for param in model.features.parameters():
    param.requires_grad = False
model.classifier[6] = torch.nn.Linear(4096, 10)""",
    },
    '/pdf-assets/中級/exam3/page_013/image_03_01.png': {
        'markdown_language': 'python',
        'markdown_title': '選項 C 程式碼',
        'markdown': """import torch
import torchvision.models as models

model = models.vgg16(pretrained=True)
for param in model.classifier.parameters():
    param.requires_grad = False
model.classifier[6] = torch.nn.Linear(4096, 10)""",
    },
    '/pdf-assets/中級/exam3/page_013/image_04_01.png': {
        'markdown_language': 'python',
        'markdown_title': '選項 D 程式碼',
        'markdown': """import torch
import torchvision.models as models

model = models.vgg16(pretrained=True)
model.requires_grad = False
model.classifier[6] = torch.nn.Linear(4096, 10)""",
    },
    '/pdf-assets/中級/exam3/page_014/image_05_01.png': {
        'markdown_language': 'python',
        'markdown_title': '程式碼 A',
        'markdown': """# 程式碼 A:
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.neighbors import KNeighborsClassifier

X, y = digits.data, digits.target
model = KNeighborsClassifier(n_neighbors=3)
cv = StratifiedKFold(n_splits=5, shuffle=True)
scores = cross_val_score(model, X, y, cv=cv, scoring="accuracy")
print(scores.mean())""",
    },
    '/pdf-assets/中級/exam3/page_015/image_01_01.png': {
        'markdown_language': 'python',
        'markdown_title': '程式碼 B',
        'markdown': """# 程式碼 B:
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.neighbors import KNeighborsClassifier

X, y = digits.data, digits.target
model = KNeighborsClassifier(n_neighbors=3)
cv = StratifiedKFold(n_splits=5, shuffle=True)
scores = cross_val_score(model, X, y, cv=cv, scoring="f1")
print(scores.mean())""",
    },
    '/pdf-assets/中級/exam3/page_015/image_02_01.png': {
        'markdown_language': 'python',
        'markdown_title': '程式碼 C',
        'markdown': """# 程式碼 C:
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.neighbors import KNeighborsClassifier

X, y = digits.data, digits.target
model = KNeighborsClassifier(n_neighbors=3)
scores = cross_val_score(model, X, y, cv=5, scoring="accuracy")
print(scores.mean())""",
    },
    '/pdf-assets/中級/exam3/page_015/image_03_01.png': {
        'markdown_language': 'python',
        'markdown_title': '程式碼 D',
        'markdown': """# 程式碼 D:
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.neighbors import KNeighborsClassifier

X, y = digits.data, digits.target
model = KNeighborsClassifier(n_neighbors=3)
scores = cross_val_score(model, X, y, cv=5, scoring="f1")
print(scores.mean())""",
    },
    '/pdf-assets/中級/exam3/page_015/image_04_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Python 程式碼',
        'markdown': """import numpy as np
import pandas as pd
from keras import Sequential
from keras.layers import Input, Dense

np.random.seed(123)
df_train = pd.read_csv("titanic_train.csv")
df_test = pd.read_csv("titanic_test.csv")""",
    },
    '/pdf-assets/中級/exam3/page_016/image_01_01.png': {
        'markdown_language': 'text',
        'markdown_title': 'df_train.head()',
        'markdown': """df_train.head()

   pclass  sex   age  sibsp  parch      fare  embarked_C  embarked_Q  embarked_S  survived
0       1    1  29.0      0      0  211.3375       False       False        True         1
1       1    0  0.9167    1      2  151.5500       False       False        True         1
2       1    1  2.0       1      2  151.5500       False       False        True         0
3       1    0  30.0      1      0  151.5500        True       False       False         0
4       1    0  48.0      0      0   26.5500       False       False        True         1""",
    },
    '/pdf-assets/中級/exam3/page_016/image_02_01.png': {
        'markdown_language': 'text',
        'markdown_title': 'df_test.head()',
        'markdown': """df_test.head()

   pclass  sex      age  sibsp  parch      fare  embarked_C  embarked_Q  embarked_S  survived
0       1    1  25.0000      1      2  151.5500       False       False        True         0
1       1    1  18.0000      1      0  227.5250        True       False       False         1
2       1    0  29.881135    0      0   25.9250       False       False        True         0
3       1    1  32.0000      0      0   76.2917        True       False       False         1
4       1    1  47.0000      1      1   52.5542       False       False        True         1""",
    },
    '/pdf-assets/中級/exam3/page_016/image_03_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Python 程式碼',
        'markdown': """dataset_train = df_train.values.astype("float32")
dataset_test = df_test.values.astype("float32")

X_train = dataset_train[:, 0:9]
y_train = dataset_train[:, 9]
X_test = dataset_test[:, 0:9]
y_test = dataset_test[:, 9]""",
    },
    '/pdf-assets/中級/exam3/page_016/image_04_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Python 程式碼',
        'markdown': """X_train -= X_train.mean(axis=0)
X_train /= X_train.std(axis=0)
X_test -= X_test.mean(axis=0)
X_test /= X_test.std(axis=0)""",
    },
    '/pdf-assets/中級/exam3/page_017/image_01_01.png': {
        'markdown_language': 'text',
        'markdown_title': '模型程式碼與摘要',
        'markdown': """model = Sequential()
model.add(Input(shape=(X_train.shape[1],)))
model.add(Dense(10, activation="relu"))
model.add(Dense(10, activation="relu"))
model.add(Dense(1, activation="sigmoid"))
model.summary()
model.compile(loss="binary_crossentropy", optimizer="adam", metrics=["accuracy"])

Model: "sequential"

Layer (type)        Output Shape    Param #
dense (Dense)       (None, 10)      空格1
dense_1 (Dense)     (None, 10)      空格2
dense_2 (Dense)     (None, 1)       11""",
    },
    '/pdf-assets/中級/exam3/page_017/image_04_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Python 程式碼',
        'markdown': """import matplotlib.pyplot as plt

loss = history.history["loss"]
epochs = range(1, len(loss) + 1)
val_loss = history.history["val_loss"]
plt.plot(epochs, loss, 空格1, label="Training Loss")
plt.plot(epochs, val_loss, 空格2, label="Validation Loss")
plt.title("Training and Validation Loss")
plt.xlabel("Epochs")
plt.ylabel("Loss")
plt.legend()
plt.show()""",
    },
    '/pdf-assets/中級/sample/page_006/image_02_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Notebook 程式碼與輸出',
        'markdown': """from tensorflow.keras import datasets, utils
import pandas as pd

(x_train, y_train), (x_test, y_test) = datasets.cifar10.load_data()

type(x_train)
# numpy.ndarray

print(x_train.shape, y_train.shape, x_test.shape, y_test.shape)
# (50000, 32, 32, 3) (50000, 1) (10000, 32, 32, 3) (10000, 1)

print(x_train.min())
# 0

print(x_train.max())
# 255""",
    },
    '/pdf-assets/中級/sample/page_009/image_02_01.png': {
        'markdown_language': 'python',
        'markdown_title': '程式碼片段',
        'markdown': """# a.
from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# b.
from sklearn.linear_model import LogisticRegression
model = LogisticRegression()
model.fit(X_train, y_train)

# c.
import pandas as pd
data = pd.read_csv("data.csv")
X = data[["Age", "Spending"]]
y = data["HighValue"]

# d.
y_pred = model.predict(X_test)
print("Predictions:", y_pred[:5])""",
    },
}


LAYER_ROW_RE = (
    r'(Conv2d-\d+|ReLU-\d+|MaxPool2d-\d+|AdaptiveAvgPool2d-\d+|'
    r'Linear-\d+|Dropout-\d+|Total params:|Trainable params:|'
    r'Non-trainable params:|Input size \(MB\):|Forward/backward pass size \(MB\):|'
    r'Params size \(MB\):|Estimated Total Size \(MB\):)'
)


def split_vgg16_context(context: str) -> tuple[str, str] | None:
    marker = '----------------------------------------------------------------'
    marker_index = context.find(marker)
    if marker_index < 0 or 'Layer (type)' not in context:
        return None

    intro = context[:marker_index].strip()
    block = format_vgg16_block(context[marker_index:].strip())
    return intro, block


def format_vgg16_block(block: str) -> str:
    block = re.sub(r'^(----------------------------------------------------------------)\s+', r'\1\n', block)
    block = block.replace(' ================================================================ ', '\n================================================================\n')
    block = block.replace(' ---------------------------------------------------------------- ', '\n----------------------------------------------------------------\n')
    block = block.replace(' Layer (type) Output Shape Param # ', '\nLayer (type)                          Output Shape           Param #\n')
    block = block.replace(' ================================================================', '\n================================================================')
    block = block.replace(' ----------------------------------------------------------------', '\n----------------------------------------------------------------')
    block = re.sub(r'\s+' + LAYER_ROW_RE, r'\n\1', block)
    block = re.sub(r'\n{3,}', '\n\n', block).strip()
    return block


def annotate_context_blocks(question: dict[str, Any]) -> bool:
    if question.get('id') not in {'exam3_q42', 'exam3_q43', 'exam3_q44', 'exam3_q45'}:
        question.pop('context_blocks', None)
        return False

    changed = False

    context = question.get('context')
    split = split_vgg16_context(context) if isinstance(context, str) else None

    if split:
        intro, block = split
        context_blocks = [{
            'title': 'VGG16 模型摘要',
            'language': 'text',
            'markdown': block,
        }]
        if question.get('context') != intro:
            question['context'] = intro
            changed = True
        if question.get('context_blocks') != context_blocks:
            question['context_blocks'] = context_blocks
            changed = True
    else:
        context_blocks = question.get('context_blocks')
        if isinstance(context_blocks, list) and context_blocks:
            filtered_blocks = [
                block for block in context_blocks
                if block.get('title') != 'VGG16 載入程式碼'
            ]
            if filtered_blocks != context_blocks:
                question['context_blocks'] = filtered_blocks
                context_blocks = filtered_blocks
                changed = True
            block = context_blocks[0]
            markdown = block.get('markdown')
            if isinstance(markdown, str):
                formatted = format_vgg16_block(markdown)
                if formatted != markdown:
                    block['markdown'] = formatted
                    changed = True

    if question.get('id') == 'exam3_q45':
        options = question.get('options')
        expected_options = {
            'A': '見下方選項 A 程式碼',
            'B': '見下方選項 B 程式碼',
            'C': '見下方選項 C 程式碼',
            'D': '見下方選項 D 程式碼',
        }
        if isinstance(options, dict) and any(not str(options.get(key, '')).strip() for key in expected_options):
            question['options'] = expected_options
            changed = True

    images = question.setdefault('images', [])
    if isinstance(images, list) and not any(image.get('src') == VGG16_CODE_SRC for image in images):
        images.insert(0, {
            'type': 'image',
            'src': VGG16_CODE_SRC,
            'alt': 'exam3 第 11 頁 VGG16 載入程式碼',
            'page_index': 10,
            'page_number': 11,
            'bbox': [120, 541.33, 413.33, 581.33],
            'placement': 'context',
            'markdown_language': 'python',
            'markdown_title': 'VGG16 載入程式碼',
            'markdown': VGG16_CODE_MARKDOWN,
        })
        changed = True
    return changed


def image_payload(
    src: str,
    alt: str,
    page_index: int,
    page_number: int,
    bbox: list[float],
    placement: str = 'context',
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'type': 'image',
        'src': src,
        'alt': alt,
        'page_index': page_index,
        'page_number': page_number,
        'bbox': bbox,
        'placement': placement,
    }
    annotation = ANNOTATIONS.get(src)
    if annotation:
        payload.update(annotation)
    return payload


def add_unique_image(images: list[dict[str, Any]], payload: dict[str, Any], index: int | None = None) -> bool:
    if any(image.get('src') == payload.get('src') for image in images):
        return False
    if index is None:
        images.append(payload)
    else:
        images.insert(index, payload)
    return True


def annotate_exam2_group_images(question: dict[str, Any]) -> bool:
    question_id = question.get('id')
    if not isinstance(question_id, str) or not question_id.startswith('exam2_q'):
        return False

    try:
        qnum = int(question_id.rsplit('_q', 1)[1])
    except ValueError:
        return False

    changed = False
    images = question.setdefault('images', [])
    if not isinstance(images, list):
        return False

    if 43 <= qnum <= 47:
        changed |= add_unique_image(images, image_payload(
            GAME_PREVIEW_SRC,
            'exam2 第 13 頁 vgsales 資料預覽',
            12,
            13,
            [118.15, 584.0, 480.4, 712.05],
        ), 0)

    if qnum == 43:
        changed |= add_unique_image(images, image_payload(
            GAME_YEAR_SRC,
            "exam2 第 14 頁 data['Year'] 欄位輸出",
            13,
            14,
            [118.15, 132.15, 439.93, 295.7],
            'question',
        ), 0)

    if 48 <= qnum <= 50:
        changed |= add_unique_image(images, image_payload(
            MARKETING_LOAD_SRC,
            'exam2 第 15 頁 marketing.csv 載入程式碼',
            14,
            15,
            [118.15, 639.43, 452.57, 699.03],
        ), 0)
        changed |= add_unique_image(images, image_payload(
            MARKETING_PREVIEW_SRC,
            'exam2 第 16 頁 marketing.csv 資料預覽與描述統計',
            15,
            16,
            [118.15, 139.18, 487.07, 399.08],
        ), 1)

    return changed


def annotate_question_images(path: Path) -> int:
    data: dict[str, Any] = json.loads(path.read_text(encoding='utf-8'))
    changed = 0
    is_middle_exam2 = path.parts[-3:] == ('中級', 'questions', 'mock_exam2.json')
    middle_exam2_sources = {GAME_PREVIEW_SRC, GAME_YEAR_SRC, MARKETING_LOAD_SRC, MARKETING_PREVIEW_SRC}
    for question in data.get('questions') or []:
        if annotate_context_blocks(question):
            changed += 1
        if is_middle_exam2 and annotate_exam2_group_images(question):
            changed += 1
        if not is_middle_exam2 and isinstance(question.get('images'), list):
            before = len(question['images'])
            question['images'] = [
                image for image in question['images']
                if image.get('src') not in middle_exam2_sources
            ]
            if len(question['images']) != before:
                changed += 1
        for image in question.get('images') or []:
            src = image.get('src')
            annotation = ANNOTATIONS.get(src)
            if not annotation:
                for field in ('markdown', 'markdown_language', 'markdown_title'):
                    image.pop(field, None)
                continue
            for field, value in annotation.items():
                if image.get(field) != value:
                    image[field] = value
                    changed += 1
        if question.get('images') == []:
            question.pop('images')
            changed += 1
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return changed


def main() -> None:
    total = 0
    for level in ('初級', '中級'):
        questions_dir = BASE / 'data' / level / 'questions'
        for path in sorted(questions_dir.glob('*.json')):
            if path.name not in {'mock_exam1.json', 'mock_exam2.json', 'mock_exam3.json', 'sample_exam.json'}:
                continue
            changed = annotate_question_images(path)
            if changed:
                print(f'Annotated {path.relative_to(BASE)} ({changed} fields)')
                total += changed
    print(f'Done. annotated fields: {total}')


if __name__ == '__main__':
    main()
