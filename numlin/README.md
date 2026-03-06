# Pencil Puzzle Solver (Numberlink)

SATソルバーを用いてナンバーリンク（Numberlink）パズルを解くPythonプログラム群。

## 概要

盤面の状態を受け取り、各マスの接続情報や色の制約を論理式変数に変換（CNF変換）した上で、SATソルバーから解（経路）を得るアプローチをとっている。

## ファイル構成

- `NumberLinkSolver.py`
  パズルを解くためのコアクラス。マスごとの色・エッジの制約を生成し、`python-sat` (Glucose3) を用いて解を求める。
- `numlink.ipynb`
  ソルバーの実行例を示すJupyter Notebook。テキスト形式の盤面データ（`.`が空白、数字が端点）をパースし、ソルバーに入力して結果を出力する流れを確認できる。
- `requirement.txt`
  実行に必要なPythonパッケージのリスト（`python-sat`）。

## インストール

実行環境に依存ライブラリをインストールする。

```bash
pip install -r requirement.txt
```

## 使い方

`numlink.ipynb` の内容に沿って、基本的には以下のように実行する。

```python
from NumberLinkSolver import NumberLinkSolver

# 0: 空白, 数字: つなぐべき端点
grid = [
    [0, 0, 4, 0, 0, 0],
    [0, 0, 0, 0, 2, 0],
    [0, 3, 0, 0, 0, 3],
    [0, 1, 2, 4, 0, 0],
    [0, 0, 0, 0, 1, 0],
    [0, 0, 0, 0, 0, 0]
]

solver = NumberLinkSolver(grid)
# パスですべてのマスを埋めるルールにする場合は force_full_fill=True を指定
solution = solver.solve()

if solution:
    for row in solution:
        print(row)
else:
    print("解が見つからない")
```
