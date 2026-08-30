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

from resource_catalog import exam_entries, level_entry

BASE = Path(__file__).resolve().parents[1]
VGG16_CODE_SRC = '/pdf-assets/中級/mid_1141_s3/page_010/image_02_01.png'
VGG16_CODE_MARKDOWN = """from torchsummary import summary
from torchvision import models
model = models.vgg16(weights='IMAGENET1K_V1')
summary(model, (3, 150, 150))"""
VGG16_SUMMARY_MARKDOWN = """----------------------------------------------------------------
Layer (type) Output Shape Param #
================================================================
Conv2d-1 [-1, 64, 150, 150] 1,792
ReLU-2 [-1, 64, 150, 150] 0
Conv2d-3 [-1, 64, 150, 150] 36,928
ReLU-4 [-1, 64, 150, 150] 0
MaxPool2d-5 [-1, 64, 75, 75] 0
Conv2d-6 [-1, 128, 75, 75] 73,856
ReLU-7 [-1, 128, 75, 75] 0
Conv2d-8 [-1, 128, 75, 75] 147,584
ReLU-9 [-1, 128, 75, 75] 0
MaxPool2d-10 [-1, 128, 37, 37] 0
Conv2d-11 [-1, 256, 37, 37] 295,168
ReLU-12 [-1, 256, 37, 37] 0
Conv2d-13 [-1, 256, 37, 37] 590,080
ReLU-14 [-1, 256, 37, 37] 0
Conv2d-15 [-1, 256, 37, 37] 590,080
ReLU-16 [-1, 256, 37, 37] 0
MaxPool2d-17 [-1, 256, 18, 18] 0
Conv2d-18 [-1, 512, 18, 18] 1,180,160
ReLU-19 [-1, 512, 18, 18] 0
Conv2d-20 [-1, 512, 18, 18] 2,359,808
ReLU-21 [-1, 512, 18, 18] 0
Conv2d-22 [-1, 512, 18, 18] 2,359,808
ReLU-23 [-1, 512, 18, 18] 0
MaxPool2d-24 [-1, 512, 9, 9] 0
Conv2d-25 [-1, 512, 9, 9] 2,359,808
ReLU-26 [-1, 512, 9, 9] 0
Conv2d-27 [-1, 512, 9, 9] 2,359,808
ReLU-28 [-1, 512, 9, 9] 0
Conv2d-29 [-1, 512, 9, 9] 2,359,808
ReLU-30 [-1, 512, 9, 9] 0
MaxPool2d-31 [-1, 512, 4, 4] 0
AdaptiveAvgPool2d-32 [-1, 512, 7, 7] 0
Linear-33 [-1, 4096] 102,764,544
ReLU-34 [-1, 4096] 0
Dropout-35 [-1, 4096] 0
Linear-36 [-1, 4096] 16,781,312
ReLU-37 [-1, 4096] 0
Dropout-38 [-1, 4096] 0
Linear-39 [-1, 1000] 4,097,000
================================================================
Total params: 138,357,544
Trainable params: 138,357,544
Non-trainable params: 0
----------------------------------------------------------------
Input size (MB): 0.26
Forward/backward pass size (MB): 96.93
Params size (MB): 527.79
Estimated Total Size (MB): 624.98
----------------------------------------------------------------"""
MID_1151_S3_TRANSFER_SRC = '/pdf-assets/中級/mid_1151_s3/page_011/image_02_01.png'
MID_1151_S3_TRANSFER_CONTEXT = (
    '下圖為使用 ResNet 進行遷移學習（Transfer Learning）的 Python 程式片段。'
    '請回答第 42~43 題。'
)
GAME_PREVIEW_SRC = '/pdf-assets/中級/mid_1141_s2/page_012/image_02_01.png'
GAME_YEAR_SRC = '/pdf-assets/中級/mid_1141_s2/page_013/image_01_01.png'
MARKETING_LOAD_SRC = '/pdf-assets/中級/mid_1141_s2/page_014/image_01_01.png'
MARKETING_PREVIEW_SRC = '/pdf-assets/中級/mid_1141_s2/page_015/image_01_01.png'

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
    '/pdf-assets/中級/mid_1141_s2/page_010/image_01_01.png': {
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
    '/pdf-assets/中級/mid_1141_s2/page_011/image_01_01.png': {
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
    '/pdf-assets/中級/mid_1141_s2/page_012/image_01_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Python 程式碼',
        'markdown': """import numpy as np
from scipy.stats import poisson

lambda_poisson = 5
print(poisson.pmf(5, lambda_poisson))""",
    },
    '/pdf-assets/中級/mid_1141_s2/page_014/image_01_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Python 程式碼',
        'markdown': """import pandas as pd
df = pd.read_csv("marketing.csv")""",
    },
    '/pdf-assets/中級/mid_1141_s2/page_015/image_01_01.png': {
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
    '/pdf-assets/中級/mid_1141_s2/page_015/image_02_01.png': {
        'markdown_language': 'text',
        'markdown_title': '執行結果',
        'markdown': """youtube      0
facebook     1
newspaper    0
sales        0
dtype: int64""",
    },
    '/pdf-assets/中級/mid_1141_s2/page_016/image_01_01.png': {
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
    '/pdf-assets/中級/mid_1141_s3/page_009/image_01_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Python 程式碼',
        'markdown': """def metric(y_true, y_pred):
    return sum((y_true - y_pred) ** 2) / len(y_true)""",
    },
    '/pdf-assets/中級/mid_1141_s3/page_014/image_02_01.png': {
        'markdown_language': 'python',
        'markdown_title': '製造雜訊影像',
        'markdown': """import numpy as np
noisy = np.random.normal(digits.data, 4)""",
    },
    '/pdf-assets/中級/mid_1141_s3/page_014/image_04_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'PCA 降噪程式碼（A~E）',
        'markdown': """from sklearn.decomposition import PCA          # 程式碼A
pca = PCA()                                    # 程式碼B
pca.fit(noisy)                                 # 程式碼C
components = pca.transform(noisy)              # 程式碼D
filtered = pca.inverse_transform(components)   # 程式碼E""",
    },
    '/pdf-assets/中級/mid_1141_s3/page_017/image_03_01.png': {
        'markdown_language': 'python',
        'markdown_title': '模型訓練與評估',
        'markdown': """history = model.fit(X_train, y_train, validation_split=0.2, epochs=100, batch_size=10)
loss, accuracy = model.evaluate(X_train, y_train, verbose=0)""",
    },
    '/pdf-assets/中級/mid_1141_s3/page_009/image_02_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Python 程式碼',
        'markdown': """def forward(x, p, training=True):
    if training:
        mask = np.random.binomial(1, p, size=x.shape)
        return x * mask / p
    else:
        return x""",
    },
    '/pdf-assets/中級/mid_1141_s3/page_009/image_03_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Python 程式碼',
        'markdown': """import numpy as np

v1 = np.array([1, 2, 3])
v2 = np.array([4, 5, 6])
A = np.array([[1, 2], [3, 4]])""",
    },
    '/pdf-assets/中級/mid_1141_s3/page_010/image_01_01.png': {
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
    '/pdf-assets/中級/mid_1141_s3/page_013/image_01_01.png': {
        'markdown_language': 'python',
        'markdown_title': '選項 A 程式碼',
        'markdown': """import torch
import torchvision.models as models

model = models.vgg16(pretrained=True)
for param in model.parameters():
    param.requires_grad = False
model.classifier[6] = torch.nn.Linear(4096, 10)""",
    },
    '/pdf-assets/中級/mid_1141_s3/page_013/image_02_01.png': {
        'markdown_language': 'python',
        'markdown_title': '選項 B 程式碼',
        'markdown': """import torch
import torchvision.models as models

model = models.vgg16(pretrained=True)
for param in model.features.parameters():
    param.requires_grad = False
model.classifier[6] = torch.nn.Linear(4096, 10)""",
    },
    '/pdf-assets/中級/mid_1141_s3/page_013/image_03_01.png': {
        'markdown_language': 'python',
        'markdown_title': '選項 C 程式碼',
        'markdown': """import torch
import torchvision.models as models

model = models.vgg16(pretrained=True)
for param in model.classifier.parameters():
    param.requires_grad = False
model.classifier[6] = torch.nn.Linear(4096, 10)""",
    },
    '/pdf-assets/中級/mid_1141_s3/page_013/image_04_01.png': {
        'markdown_language': 'python',
        'markdown_title': '選項 D 程式碼',
        'markdown': """import torch
import torchvision.models as models

model = models.vgg16(pretrained=True)
model.requires_grad = False
model.classifier[6] = torch.nn.Linear(4096, 10)""",
    },
    '/pdf-assets/中級/mid_1141_s3/page_014/image_05_01.png': {
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
    '/pdf-assets/中級/mid_1141_s3/page_015/image_01_01.png': {
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
    '/pdf-assets/中級/mid_1141_s3/page_015/image_02_01.png': {
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
    '/pdf-assets/中級/mid_1141_s3/page_015/image_03_01.png': {
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
    '/pdf-assets/中級/mid_1141_s3/page_015/image_04_01.png': {
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
    '/pdf-assets/中級/mid_1141_s3/page_016/image_01_01.png': {
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
    '/pdf-assets/中級/mid_1141_s3/page_016/image_02_01.png': {
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
    '/pdf-assets/中級/mid_1141_s3/page_016/image_03_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Python 程式碼',
        'markdown': """dataset_train = df_train.values.astype("float32")
dataset_test = df_test.values.astype("float32")

X_train = dataset_train[:, 0:9]
y_train = dataset_train[:, 9]
X_test = dataset_test[:, 0:9]
y_test = dataset_test[:, 9]""",
    },
    '/pdf-assets/中級/mid_1141_s3/page_016/image_04_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Python 程式碼',
        'markdown': """X_train -= X_train.mean(axis=0)
X_train /= X_train.std(axis=0)
X_test -= X_test.mean(axis=0)
X_test /= X_test.std(axis=0)""",
    },
    '/pdf-assets/中級/mid_1141_s3/page_017/image_01_01.png': {
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
    '/pdf-assets/中級/mid_1141_s3/page_017/image_04_01.png': {
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
    # 115年第一次 中級 科目二
    '/pdf-assets/中級/mid_1151_s2/page_000/mid_1151_s2_q2_visual_p000.png': {
        'markdown_language': 'text',
        'markdown_title': '吉尼不純度公式',
        'markdown': 'G = 1 - Σᵢ₌₁ᵏ pᵢ²\n\n其中 pᵢ 為第 i 類樣本在節點中所占的比例，k 為類別總數',
    },
    '/pdf-assets/中級/mid_1151_s2/page_001/mid_1151_s2_q8_visual_p001.png': {
        'markdown_language': 'text',
        'markdown_title': 'Z 檢定統計量公式',
        'markdown': 'Z = (x̄ - μ₀) / (σ / √n)\n\n其中 x̄ 為樣本平均數、μ₀ 為虛無假說均值、σ 為母體標準差、n 為樣本數',
    },
    '/pdf-assets/中級/mid_1151_s2/page_011/image_02_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Python 程式碼',
        'markdown': """def process_record(record, tags=[]):
    tags.append("checked")
    record['tags'] = tags
    return record

row1 = process_record({"id": 1})
row2 = process_record({"id": 2})""",
    },
    '/pdf-assets/中級/mid_1151_s2/page_011/image_03_01.png': {
        'markdown_language': 'text',
        'markdown_title': 'KNN 虛擬程式碼',
        'markdown': """Input:
  - train_data: 訓練資料集，每筆包含特徵和標籤
  - test_point: 要預測的資料點
  - X: 要考慮的最近鄰個數

Output:
  - 預測的分類標籤

Algorithm:
1. 初始化一個空列表 distances
2. 對於每個訓練資料集的樣本 sample：
   a. 計算 sample 與 test_point 的距離 distance
   b. 把 (distance, sample) 加到 distances 中
3. 按照距離對 distances 升序排序
4. 取出 X 個距離最小的項目，記錄它們的標籤
5. 統計這 X 個標籤中出現次數最多的那個標籤
6. 返回該標籤作為 test_point 的預測結果""",
    },
    '/pdf-assets/中級/mid_1151_s2/page_012/image_02_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Python 程式碼',
        'markdown': """import pandas as pd

df = pd.read_csv('driver_daily_stats.csv')
print(df['daily_earnings'].describe()[['mean', '50%', 'max']])""",
    },
    '/pdf-assets/中級/mid_1151_s2/page_013/image_02_01.png': {
        'markdown_language': 'text',
        'markdown_title': '分類報告',
        'markdown': """              precision    recall  f1-score

           0       1.00      1.00      1.00
           1       1.00      1.00      1.00

    accuracy                           1.00
   macro avg       1.00      1.00      1.00
weighted avg       1.00      1.00      1.00""",
    },
    '/pdf-assets/中級/mid_1151_s2/page_016/image_05_01.png': {
        'markdown_language': 'python',
        'markdown_title': '選項 A 程式碼',
        'markdown': """X_train, X_test, y_train, y_test = train_test_split(y, X_norm, train_size=0.2, random_state=123)
log_reg = LogisticRegression(solver="lbfgs")
log_reg.fit(X_train, y_train)""",
    },
    '/pdf-assets/中級/mid_1151_s2/page_016/mid_1151_s2_q50_visual_p016.png': {
        'markdown_language': 'text',
        'markdown_title': '模型評估程式碼與輸出',
        'markdown': """>>> y_pred = log_reg.predict(X_test)
>>> cm = confusion_matrix(y_test, y_pred)
>>> f1 = f1_score(y_test, y_pred, average="weighted")
>>> print(cm)
[[13  0  0]
 [ 0  6  0]
 [ 0  1 10]]
>>> print("F1-score (Weighted):", f1)
F1-score (Weighted): 0.9671550671550672
>>> print("Classification Report:\\n", classification_report(y_test, y_pred, target_names=target_names))
Classification Report:
              precision    recall  f1-score  support
      setosa       1.00      1.00      1.00       13
  versicolor       0.86      1.00      0.92        6
   virginica       1.00      0.91      0.95       11
    accuracy                           0.97       30
   macro avg       0.95      0.97      0.96       30
weighted avg       0.97      0.97      0.97       30""",
    },
    # 115年第一次 中級 科目三
    '/pdf-assets/中級/mid_1151_s3/page_010/image_02_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Python 程式碼（含填空）',
        'markdown': """from tensorflow.keras import Sequential
from tensorflow.keras.layers import Dense

model = Sequential([
    Dense(64, activation='relu', input_shape=(784,)),
    Dense(10, activation='___(A)___')
])
model.compile(loss='___(B)___', optimizer='adam')""",
    },
    '/pdf-assets/中級/mid_1151_s3/page_010/image_03_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'PyTorch 資料增強程式碼',
        'markdown': """import torchvision.transforms as transforms

transform = transforms.Compose([
    transforms.RandomHorizontalFlip(p=0.5),
    transforms.RandomRotation(15),
    transforms.ColorJitter(brightness=0.3),
    transforms.ToTensor(),
])""",
    },
    MID_1151_S3_TRANSFER_SRC: {
        'markdown_language': 'python',
        'markdown_title': 'PyTorch 遷移學習程式碼（含填空）',
        'markdown': """import torch
import torch.nn as nn
import torchvision

model = torchvision.models.resnet50(pretrained=True)
for param in model.parameters():
    param.requires_grad = False  # 行(A)

model.fc = nn.Linear(2048, 2)
optimizer = torch.optim.Adam(model.fc.parameters(), lr=1e-4)""",
    },
    '/pdf-assets/中級/mid_1151_s3/page_012/image_02_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Iris 資料載入程式碼',
        'markdown': """from ucimlrepo import fetch_ucirepo

# 線上載入資料
iris = fetch_ucirepo(id=53)

# 讀取資料的輸入欄位與預測目標欄位
X = iris.data.features
y = iris.data.targets['class']""",
    },
    '/pdf-assets/中級/mid_1151_s3/page_012/image_05_01.png': {
        'markdown_language': 'text',
        'markdown_title': 'y.head() 輸出',
        'markdown': """# 預測目標欄位的概況
y.head()

0    Iris-setosa
1    Iris-setosa
2    Iris-setosa
3    Iris-setosa
4    Iris-setosa
Name: class, dtype: object""",
    },
    '/pdf-assets/中級/mid_1151_s3/page_013/image_02_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'LDA + KNN 交叉驗證程式碼',
        'markdown': """from sklearn.model_selection import cross_val_score
from sklearn.neighbors import KNeighborsClassifier
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis

lda = LinearDiscriminantAnalysis()
X_new = lda.fit_transform(X, y)

model = KNeighborsClassifier(n_neighbors=3)
scores = cross_val_score(model, X_new, y, cv=5, scoring="accuracy")
scores.mean()

0.9733333333333334""",
    },
    '/pdf-assets/中級/mid_1151_s3/page_013/image_03_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'KNN 交叉驗證程式碼（含填空）',
        'markdown': """from sklearn.model_selection import cross_val_score
from sklearn.neighbors import KNeighborsClassifier
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis

model = KNeighborsClassifier(n_neighbors=3)

# 填入程式碼

scores = cross_val_score(model, X, y, cv=cv, scoring="accuracy")
scores.mean()""",
    },
    '/pdf-assets/中級/mid_1151_s3/page_014/image_02_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'TensorFlow CIFAR-10 資料載入',
        'markdown': """import tensorflow as tf
from tensorflow.keras import datasets, layers, models
import matplotlib.pyplot as plt

(x_train, y_train), (x_test, y_test) = datasets.cifar10.load_data()""",
    },
    '/pdf-assets/中級/mid_1151_s3/page_014/image_03_01.png': {
        'markdown_language': 'text',
        'markdown_title': 'x_train[0] 陣列輸出',
        'markdown': """>>> x_train[0]
array([[[ 59,  62,  63],
        [ 43,  46,  45],
        [ 50,  48,  43],
        ...,
        [158, 132, 108],
        [152, 125, 102],
        [148, 124, 103]],

       [[ 16,  20,  20],
        [  0,   0,   0],
        [ 18,   8,   0],
        ...""",
    },
    '/pdf-assets/中級/mid_1151_s3/page_014/image_05_01.png': {
        'markdown_language': 'python',
        'markdown_title': '資料正規化與標籤編碼',
        'markdown': """x_train, x_test = x_train / 255.0, x_test / 255.0
y_train = tf.keras.utils.to_categorical(y_train, 10)
y_test = tf.keras.utils.to_categorical(y_test, 10)""",
    },
    '/pdf-assets/中級/mid_1151_s3/page_012/image_04_01.png': {
        'markdown_language': 'text',
        'markdown_title': 'X.head() — Iris 特徵欄位前五筆',
        'markdown': """X.head()

   sepal.length  sepal.width  petal.length  petal.width
0           5.1          3.5           1.4          0.2
1           4.9          3.0           1.4          0.2
2           4.7          3.2           1.3          0.2
3           4.6          3.1           1.5          0.2
4           5.0          3.6           1.4          0.2""",
    },
    '/pdf-assets/中級/mid_1151_s3/page_013/image_04_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Q45 交叉驗證可選程式碼',
        'markdown': """程式碼 A : cv = KFold(n_splits=5, shuffle=True)
程式碼 B : cv = StratifiedKFold(n_splits=5, shuffle=True)
程式碼 C : cv = 5
程式碼 D : cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=2)""",
    },
    '/pdf-assets/中級/mid_1151_s3/page_014/image_06_01.png': {
        'markdown_language': 'text',
        'markdown_title': 'y_train[0] 輸出',
        'markdown': """>>> y_train[0]
array([6], dtype=uint8)""",
    },
    '/pdf-assets/中級/mid_1151_s3/page_015/image_03_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'Keras CNN 模型定義（Q47）',
        'markdown': """model = models.Sequential([
    # 區塊 1
    layers.Input(shape=(32, 32, 3)),
    layers.Conv2D(32, kernel_size=(3,3), padding="same", activation="relu"),
    layers.BatchNormalization(),
    layers.Conv2D(32, (3,3), activation='relu', padding='same'),
    layers.BatchNormalization(),
    layers.MaxPooling2D((2,2)),
    layers.Dropout(0.25),

    # 區塊 2
    layers.Conv2D(64, (3,3), activation='relu', padding='same'),
    layers.BatchNormalization(),
    layers.Conv2D(64, (3,3), activation='relu', padding='same'),
    layers.BatchNormalization(),
    layers.MaxPooling2D((2,2)),
    layers.Dropout(0.25),

    # 區塊 3
    layers.Conv2D(128, (3,3), activation='relu', padding='same'),
    layers.BatchNormalization(),
    layers.Conv2D(128, (3,3), activation='relu', padding='same'),
    layers.BatchNormalization(),
    layers.MaxPooling2D((2,2)),
    layers.Dropout(0.25),

    # 區塊 4
    layers.Flatten(),
    layers.Dense(256, activation='relu'),
    layers.BatchNormalization(),
    layers.Dropout(0.5),
    layers.Dense(10, activation='softmax')
])""",
    },
    '/pdf-assets/中級/mid_1151_s3/page_017/image_02_01.png': {
        'markdown_language': 'python',
        'markdown_title': 'PyTorch 訓練迴圈（含填空）',
        'markdown': """for images, labels in train_loader:
    optimizer.zero_grad()          # 位置 1
    outputs = model(images)        # 位置 2
    loss = criterion(outputs, labels) # 位置 3
    loss.backward()                # 位置 4
    optimizer.step()               # 位置 5""",
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
    if question.get('id') not in {'mid_1141_s3_q42', 'mid_1141_s3_q43', 'mid_1141_s3_q44', 'mid_1141_s3_q45'}:
        question.pop('context_blocks', None)
        return False

    changed = False

    context = question.get('context')
    split = split_vgg16_context(context) if isinstance(context, str) else None

    if split:
        intro, _ = split
        if question.get('context') != intro:
            question['context'] = intro
            changed = True

    # The parser may emit only the shared-context introduction after a clean
    # rebuild. Keep the official summary here so q42-q45 never depend on an old
    # generated JSON file to retain the table needed to answer the questions.
    expected_context_blocks = [{
        'title': 'VGG16 模型摘要',
        'language': 'text',
        'markdown': VGG16_SUMMARY_MARKDOWN,
    }]
    if question.get('context_blocks') != expected_context_blocks:
        question['context_blocks'] = expected_context_blocks
        changed = True

    if question.get('id') == 'mid_1141_s3_q45':
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
            'alt': 'mid_1141_s3 第 11 頁 VGG16 載入程式碼',
            'page_index': 10,
            'page_number': 11,
            'bbox': [120.38, 541.33, 413.33, 581.33],
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
    if not isinstance(question_id, str) or not question_id.startswith('mid_1141_s2_q'):
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
            'mid_1141_s2 第 13 頁 vgsales 資料預覽',
            12,
            13,
            [118.15, 584.0, 480.4, 712.05],
        ), 0)

    if qnum == 43:
        changed |= add_unique_image(images, image_payload(
            GAME_YEAR_SRC,
            "mid_1141_s2 第 14 頁 data['Year'] 欄位輸出",
            13,
            14,
            [118.15, 132.15, 439.93, 295.7],
            'question',
        ), 0)

    if 48 <= qnum <= 50:
        changed |= add_unique_image(images, image_payload(
            MARKETING_LOAD_SRC,
            'mid_1141_s2 第 15 頁 marketing.csv 載入程式碼',
            14,
            15,
            [118.15, 639.43, 452.57, 699.03],
        ), 0)
        changed |= add_unique_image(images, image_payload(
            MARKETING_PREVIEW_SRC,
            'mid_1141_s2 第 16 頁 marketing.csv 資料預覽與描述統計',
            15,
            16,
            [118.15, 139.18, 487.07, 399.08],
        ), 1)

    return changed


MID_1151_S2_IRIS_CONTEXT_BLOCK: dict[str, str] = {
    'title': 'Iris 資料載入（第 48~50 題共用）',
    'language': 'python',
    'markdown': (
        'from sklearn.datasets import load_iris\n'
        'from sklearn.preprocessing import StandardScaler\n'
        'from sklearn.model_selection import train_test_split\n'
        'from sklearn.linear_model import LogisticRegression\n'
        'from sklearn.metrics import confusion_matrix, f1_score, classification_report\n\n'
        'iris = load_iris()\n'
        'X, y = iris.data, iris.target\n'
        'feature_names = iris.feature_names\n'
        "target_names = iris.target_names\n\n"
        '>>> print(X[0:5])\n'
        '[[5.1 3.5 1.4 0.2]\n'
        ' [4.9 3.  1.4 0.2]\n'
        ' [4.7 3.2 1.3 0.2]\n'
        ' [4.6 3.1 1.5 0.2]\n'
        ' [5.  3.6 1.4 0.2]]\n'
        '>>> print(y[0:5])\n'
        '[0 0 0 0 0]\n'
        '>>> print(feature_names)\n'
        "['sepal length (cm)', 'sepal width (cm)', 'petal length (cm)', 'petal width (cm)']\n"
        '>>> print(target_names)\n'
        "['setosa' 'versicolor' 'virginica']"
    ),
}

MID_1151_S2_Q41_CODE = (
    'import pandas as pd\n\n'
    "df = pd.read_csv('driver_daily_stats.csv')\n"
    "print(df['daily_earnings'].describe()[['mean', '50%', 'max']])"
)

MID_1151_S2_Q41_OUTPUT = (
    'mean    223.411306\n'
    '50%     128.552462\n'
    'max    4500.000000'
)

_Q41_TEXT_OLD = '（Pandas 2以上版本）： 輸出結果如下： ● mean：223.411306 ● 50%：128.552462 ● max：4500.000000 若'
_Q41_TEXT_NEW = '（Pandas 2以上版本，程式碼與輸出見下方）。若'


def annotate_mid1151s2_q41(question: dict[str, Any]) -> bool:
    if question.get('id') != 'mid_1151_s2_q41':
        return False
    changed = False

    q_text = question.get('question', '')
    if _Q41_TEXT_OLD in q_text:
        question['question'] = q_text.replace(_Q41_TEXT_OLD, _Q41_TEXT_NEW)
        changed = True

    expected_blocks = [
        {'title': 'Python 程式碼', 'language': 'python', 'markdown': MID_1151_S2_Q41_CODE},
        {'title': '執行結果', 'language': 'text', 'markdown': MID_1151_S2_Q41_OUTPUT},
    ]
    if question.get('context_blocks') != expected_blocks:
        question['context_blocks'] = expected_blocks
        changed = True

    images = question.setdefault('images', [])
    if isinstance(images, list):
        src = '/pdf-assets/中級/mid_1151_s2/page_012/image_02_01.png'
        if add_unique_image(images, image_payload(
            src, 'mid_1151_s2 第 13 頁 pandas describe 程式碼', 12, 13,
            [108.2, 444.28, 488.21, 523.73],
        ), 0):
            changed = True
    return changed


def annotate_mid1151s2_q43(question: dict[str, Any]) -> bool:
    if question.get('id') != 'mid_1151_s2_q43':
        return False
    images = question.setdefault('images', [])
    if not isinstance(images, list):
        return False
    src = '/pdf-assets/中級/mid_1151_s2/page_013/image_02_01.png'
    return add_unique_image(images, image_payload(
        src, 'mid_1151_s2 第 14 頁 分類報告', 13, 14,
        [108.2, 375.43, 347.45, 478.18],
    ), 0)


def annotate_mid1151s2_iris_group(question: dict[str, Any]) -> bool:
    """Add iris dataset loading context to Q48 and Q50 (Q49 handled separately)."""
    qid = question.get('id', '')
    if qid not in {'mid_1151_s2_q48', 'mid_1151_s2_q50'}:
        return False
    expected_blocks = [MID_1151_S2_IRIS_CONTEXT_BLOCK]
    if question.get('context_blocks') != expected_blocks:
        question['context_blocks'] = expected_blocks
        return True
    return False


MID_1151_S2_Q49_CODES = {
    'A': 'X_train, X_test, y_train, y_test = train_test_split(X_norm, y, train_size=0.2, random_state=123)\nlog_reg = LogisticRegression(solver="liblinear")\nlog_reg.fit(X_train, y_train)',
    'B': 'X_train, X_test, y_train, y_test = train_test_split(X_norm, y, train_size=0.2, random_state=123)\nlog_reg = LogisticRegression(solver="lbfgs")\nlog_reg.fit(X_train, y_train)',
    'C': 'X_train, X_test, y_train, y_test = train_test_split(y, X_norm, train_size=0.2, random_state=123)\nlog_reg = LogisticRegression(solver="liblinear")\nlog_reg.fit(X_train, y_train)',
    'D': 'X_train, X_test, y_train, y_test = train_test_split(y, X_norm, train_size=0.2, random_state=123)\nlog_reg = LogisticRegression(solver="lbfgs")\nlog_reg.fit(X_train, y_train)',
}


def annotate_mid1151s2_q49(question: dict[str, Any]) -> bool:
    """Q49 has 4 code-image options that PDF table parser cannot extract as text.
    Use context_blocks to display all 4 options as highlighted code above the question.
    """
    if question.get('id') != 'mid_1151_s2_q49':
        return False
    changed = False
    expected_options = {k: f'見下方選項 {k} 程式碼' for k in 'ABCD'}
    if question.get('options') != expected_options:
        question['options'] = expected_options
        changed = True
    expected_blocks = [MID_1151_S2_IRIS_CONTEXT_BLOCK] + [
        {'title': f'選項 {k} 程式碼', 'language': 'python', 'markdown': code}
        for k, code in MID_1151_S2_Q49_CODES.items()
    ]
    if question.get('context_blocks') != expected_blocks:
        question['context_blocks'] = expected_blocks
        changed = True
    # Remove stale option images (code shown via context_blocks)
    images = question.get('images')
    if isinstance(images, list):
        clean = [img for img in images if img.get('placement') != 'option']
        if clean != images:
            question['images'] = clean or None
            if not clean:
                question.pop('images', None)
            changed = True
    return changed


MID_1151_S3_Q50_SRC = '/pdf-assets/中級/mid_1151_s3/page_017/image_02_01.png'


def annotate_mid1151s3_transfer_group(question: dict[str, Any]) -> bool:
    """Repair the page-break association for the shared Q42-Q43 ResNet block."""
    question_id = question.get('id')

    if question_id == 'mid_1151_s3_q41':
        images = question.get('images')
        if not isinstance(images, list):
            return False
        kept = [image for image in images if image.get('src') != MID_1151_S3_TRANSFER_SRC]
        if kept == images:
            return False
        if kept:
            question['images'] = kept
        else:
            question.pop('images', None)
        return True

    if question_id not in {'mid_1151_s3_q42', 'mid_1151_s3_q43'}:
        return False

    changed = False
    if question.get('context') != MID_1151_S3_TRANSFER_CONTEXT:
        question['context'] = MID_1151_S3_TRANSFER_CONTEXT
        changed = True

    expected_images = [image_payload(
        MID_1151_S3_TRANSFER_SRC,
        'mid_1151_s3 第 12 頁第 42~43 題共用 ResNet 遷移學習程式碼',
        11,
        12,
        [115.35, 255.86, 531.85, 445.6],
        'context',
    )]
    if question.get('images') != expected_images:
        question['images'] = expected_images
        changed = True
    return changed


def annotate_mid1151s3_q50(question: dict[str, Any]) -> bool:
    if question.get('id') != 'mid_1151_s3_q50':
        return False
    images = question.setdefault('images', [])
    if not isinstance(images, list):
        return False
    return add_unique_image(images, image_payload(
        MID_1151_S3_Q50_SRC,
        'mid_1151_s3 第 18 頁 PyTorch 訓練迴圈程式碼',
        17,
        18,
        [369, 187, 477, 917],
        'context',
    ), 0)


def annotate_question_images(path: Path) -> int:
    data: dict[str, Any] = json.loads(path.read_text(encoding='utf-8'))
    changed = 0
    is_middle_exam2 = path.parts[-3:] == ('中級', 'questions', 'mock_mid_1141_s2.json')
    middle_exam2_sources = {GAME_PREVIEW_SRC, GAME_YEAR_SRC, MARKETING_LOAD_SRC, MARKETING_PREVIEW_SRC}
    for question in data.get('questions') or []:
        if annotate_context_blocks(question):
            changed += 1
        if is_middle_exam2 and annotate_exam2_group_images(question):
            changed += 1
        if annotate_mid1151s2_q41(question):
            changed += 1
        if annotate_mid1151s2_q43(question):
            changed += 1
        if annotate_mid1151s2_iris_group(question):
            changed += 1
        if annotate_mid1151s2_q49(question):
            changed += 1
        if annotate_mid1151s3_transfer_group(question):
            changed += 1
        if annotate_mid1151s3_q50(question):
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
        # 防護：資產改名/重抽後可能留下指向不存在檔案的圖片參照，
        # 前端會渲染成破圖，這裡一律清掉。
        if isinstance(question.get('images'), list):
            kept = [
                image for image in question['images']
                if (BASE / 'frontend' / 'public' / str(image.get('src', '')).lstrip('/')).exists()
            ]
            if len(kept) != len(question['images']):
                for image in question['images']:
                    if image not in kept:
                        print(f"  [DROP] {question.get('id')}: missing asset {image.get('src')}")
                question['images'] = kept
                changed += 1

        if question.get('images') == []:
            question.pop('images')
            changed += 1
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return changed


def annotation_exam_entries() -> list[dict[str, Any]]:
    """Return catalog exams owned by this post-processing layer.

    Middle-level exams use the curated code/image alternatives in this file;
    the junior sample keeps its historical cleanup pass. Junior official exams
    are intentionally outside this layer.
    """
    # This post-processing layer intentionally covers every middle-level exam
    # plus the junior sample. File names still come only from the catalog, so a
    # newly catalogued middle exam cannot be skipped by a stale local table.
    return [
        entry for entry in exam_entries()
        if entry['levelId'] == 'middle' or entry['kind'] == 'sample'
    ]


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--level', choices=['初級', '中級'])
    parser.add_argument('--key', action='append', dest='keys', help='只更新指定考卷 key（可重複）')
    args = parser.parse_args()

    entries = annotation_exam_entries()
    if args.level:
        entries = [
            entry for entry in entries
            if level_entry(level_id=entry['levelId'])['dataLevel'] == args.level
        ]
    if args.keys:
        selected_keys = set(args.keys)
        known = {entry['key'] for entry in entries}
        unknown = sorted(selected_keys - known)
        if unknown:
            parser.error(f'沒有圖片補強資料的考卷 key: {", ".join(unknown)}')
        entries = [entry for entry in entries if entry['key'] in selected_keys]

    total = 0
    for entry in entries:
        level = level_entry(level_id=entry['levelId'])['dataLevel']
        path = BASE / 'data' / level / 'questions' / entry['questionFile']
        changed = annotate_question_images(path)
        if changed:
            print(f'Annotated {path.relative_to(BASE)} ({changed} fields)')
            total += changed
    print(f'Done. annotated fields: {total}')


if __name__ == '__main__':
    main()
