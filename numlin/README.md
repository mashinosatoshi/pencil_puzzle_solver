# Numberlink / Arukone Solver and Generator

SATソルバー（`python-sat`）を用いて、ナンバーリンクおよびアルコネ（全マス使用ナンバーリンク）パズルの解答探索、および問題の自動生成を行うPythonプログラム群。

## 概要

SATソルバーを用いて以下の機能を提供する。
- **解答機能**: 盤面の状態を受け取り、各マスの接続情報や色の制約を論理変数に変換（CNF変換）した上で、SATソルバーから経路を出力する
- **生成機能**: ハミルトンパスのランダム生成、切断・結合アルゴリズムと、SATチェッカーによる唯一解判定・全マス使用判定を組み合わせて、良質なパズルを自動生成する
- **エクスポート機能**: 生成した盤面をファイル形式（pzprv3形式）で保存したり、puzz.link上で直接遊べるURLを生成する

## ファイル構成

- `NumberLinkSolver.py`
  パズルを解くためのコアクラス。マスごとの色・エッジの制約を論理式として生成し、`python-sat` (Glucose3/RC2) を用いて解を探索する。
- `arukone_gen.py`
  全マス使用・唯一解のパズル（アルコネ）を生成するコアモジュール。ハミルトンパスの生成、パスの分割・結合、ならびに唯一解や別解を判定するSATチェッカー群（`ArukoneChecker`, `StandardChecker`）を含む。
- `SaveNumlinkFormat.py`
  パズル情報の保存ならびにURL生成ユーティリティモジュール。テキストデータのファイルエクスポート機能と、puzz.linkでプレイ可能なURL生成機能（36進数エンコード処理）を含む。
- `jn_make_random_numlink.ipynb`
  アルコネの自動生成を実行するためのJupyter Notebook。パラメータ（縦横サイズなど）を指定して問題を生成し、出力URLを生成する流れを確認できる。
- `jn_solveNumlink.ipynb`
  ソルバーの実行例を示すJupyter Notebook。テキスト形式の盤面データをパースし、`NumberLinkSolver`を用いて解を出力する手順を網羅している。

## インストール

依存ライブラリ（`python-sat`等）をインストールする。

```bash
pip install -r requirement.txt
```

## 使い方

Jupyter Notebook経由での利用を推奨する。

### 問題を解く場合
`jn_solveNumlink.ipynb` を参照のこと。盤面を表す2次元配列（0が空白、数字が端点）を `NumberLinkSolver` に渡し、`solve()` メソッドを実行する。
ルールとして全マスを埋める必要がある場合は `solve(force_full_fill=True)` を指定する。

### 問題を生成する場合
`jn_make_random_numlink.ipynb` を参照のこと。`arukone_gen.py` の生成アルゴリズムを利用して全マス使用・一意解の盤面を作り出し、`SaveNumlinkFormat.py` を経由してWebブラウザで遊べるURLを出力できる。
