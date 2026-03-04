"""
NumberLinkGenerator.py

「解先行生成 (Solution-First Generation)」方式による
効率的なナンバーリンク作問モジュール。

アルゴリズム概要:
  1. グリッドを「最大長制限付きランダムウォーク」で複数のパスに完全分割する
  2. 各パスの両端点を数字として抽出 → 問題グリッドを生成
  3. (オプション) SATソルバーで唯一解チェック

現状の手法との違い:
  旧: ランダムに端点配置 → SATで解ける確率が低く最大100万回ループ
  新: 先に解を作るので SATは唯一解確認の1〜2回だけ呼べばよい
"""

import random
from NumberLinkSolver import NumberLinkSolver


class NumberLinkGenerator:
    """
    Parameters
    ----------
    rows : int
    cols : int
    num_colors : int | (int, int) | None
        生成するパス数。
        int   → ちょうどその数
        tuple → (lo, hi) の範囲内
        None  → 自動 (全マス数の 25〜40%)
    max_attempts : int
        グリッド分割の最大試行回数
    require_unique : bool
        True のとき唯一解のみを採用 (SATソルバーを使用)
    min_path_len : int
        各パスの最短マス数 (端点込み)
    max_path_len : int | None
        各パスの最長マス数。None なら全体の 60% を上限にする
    """

    def __init__(
        self,
        rows: int = 6,
        cols: int = 6,
        num_colors: int | tuple | None = None,
        max_attempts: int = 2000,
        require_unique: bool = True,
        min_path_len: int = 2,
        max_path_len: int | None = None,
        compress_trials: int = 3,
    ):
        self.rows = rows
        self.cols = cols
        self.max_attempts = max_attempts
        self.require_unique = require_unique
        self.min_path_len = min_path_len
        self.compress_trials = compress_trials

        total = rows * cols
        if max_path_len is None:
            self.max_path_len = max(3, int(total * 0.6))
        else:
            self.max_path_len = max_path_len

        if num_colors is None:
            lo = max(2, int(total * 0.25))
            hi = max(lo + 1, int(total * 0.40))
            self._num_colors_range = (lo, hi)
        elif isinstance(num_colors, tuple):
            self._num_colors_range = num_colors
        else:
            self._num_colors_range = (num_colors, num_colors)

    # ------------------------------------------------------------------
    # 公開API
    # ------------------------------------------------------------------

    def generate(self) -> dict | None:
        """
        パズルを生成して返す。

        Returns
        -------
        dict または None
          成功:
            puzzle   : List[List[int]]    問題グリッド (0=空白)
            solution : List[List[int]]    解グリッド
            paths    : List[List[tuple]]  各パス [(r,c), ...]
          失敗: None
        """
        for attempt in range(1, self.max_attempts + 1):
            result = self._try_generate()
            if result is not None:
                print(f"[Generator] OK: {attempt}回目で生成成功 (パス数={len(result['paths'])})")
                return result

        print(f"[Generator] {self.max_attempts}回試行したが生成失敗")
        return None

    # ------------------------------------------------------------------
    # 内部: 1回の試行
    # ------------------------------------------------------------------

    def _try_generate(self) -> dict | None:
        lo, hi = self._num_colors_range

        # フェーズ1: 多めの色数でグリッド分割
        # 目標より多いパスで分割する方が速く、成功率が高い
        gen_hi = min(self.rows * self.cols // 2, max(hi + 4, hi * 2))

        original_range = self._num_colors_range
        self._num_colors_range = (lo, gen_hi)
        base_paths = self._partition_grid()
        self._num_colors_range = original_range

        if base_paths is None:
            return None

        # フェーズ2: 同じ partition 結果から圧縮を複数回試す
        # 圧縮はランダム順なので毎回異なる結果になる。
        # partition(重い) を1回やるだけで compress(軽い) を複数試せる。
        needs_compress = len(base_paths) > hi
        trials = self.compress_trials if needs_compress else 1

        for _ in range(trials):
            paths = list(base_paths)  # コピー

            if needs_compress:
                target = random.randint(lo, hi)
                paths = self._compress_colors(paths, target)

            if not (lo <= len(paths) <= hi):
                continue

            if any(len(p) < self.min_path_len for p in paths):
                continue

            puzzle = self._build_puzzle(paths)
            solution = self._build_solution(paths)

            if not self._no_partial_solution(puzzle):
                continue

            if self.require_unique and not self._is_unique(puzzle):
                continue

            return {"puzzle": puzzle, "solution": solution, "paths": paths}

        return None

    # ------------------------------------------------------------------
    # 内部: グリッド分割
    # ------------------------------------------------------------------

    def _partition_grid(self) -> list[list[tuple]] | None:
        """
        全マスを互いに素なパスに分割する。

        戦略:
          - 未割当マスが残っている間、スタート地点を選んでウォーク
          - ウォークには最大長制限を設け、1本のパスが大きくなりすぎるのを防ぐ
          - ウォークで届かなかった孤立マスは次のパスのスタートになる
        """
        rows, cols = self.rows, self.cols
        unassigned = set((r, c) for r in range(rows) for c in range(cols))
        paths = []
        _, hi = self._num_colors_range

        while unassigned:
            if len(paths) >= hi:
                # 既定数に達しているのにまだ未割当マスが残っている → 失敗
                return None

            start = self._choose_start(unassigned)
            # 残りマス数から動的に最大長を計算
            remaining = len(unassigned)
            lo, _ = self._num_colors_range
            paths_needed = max(1, lo - len(paths))
            # 残りのパスに均等に振り分けるための目安
            ideal_len = remaining // paths_needed
            max_len = min(self.max_path_len, max(self.min_path_len, int(ideal_len * 1.5)))

            path = self._walk(start, unassigned, max_len)
            if path is None or len(path) < 2:
                return None

            for cell in path:
                unassigned.discard(cell)
            paths.append(path)

        return paths

    def _choose_start(self, unassigned: set) -> tuple:
        """
        未割当マスの中から、隣接する未割当マスが少ないセルを優先して選ぶ。
        (次数が低い = 行き詰まりやすい角/端のマスを先に処理する)
        """
        rows, cols = self.rows, self.cols
        sample_size = min(30, len(unassigned))
        candidates = random.sample(list(unassigned), sample_size)

        def degree(cell):
            r, c = cell
            return sum(
                1
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]
                if (r + dr, c + dc) in unassigned
            )

        # 次数が低い順にソートし、上位の中からランダムに選ぶ
        candidates.sort(key=degree)
        top_n = max(1, len(candidates) // 3)
        return random.choice(candidates[:top_n])

    def _walk(
        self, start: tuple, unassigned: set, max_len: int
    ) -> list[tuple] | None:
        """
        start から unassigned 内でランダムウォークしてパスを返す。
        max_len を超えたら打ち切る。
        """
        rows, cols = self.rows, self.cols
        path = [start]
        in_path = {start}

        while len(path) < max_len:
            r, c = path[-1]
            candidates = []
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if (
                    0 <= nr < rows
                    and 0 <= nc < cols
                    and (nr, nc) in unassigned
                    and (nr, nc) not in in_path
                ):
                    candidates.append((nr, nc))

            if not candidates:
                break

            # 次マス選択: 孤立を避けるヒューリスティック
            # 候補のうち、選択後に他のマスの次数が0にならないものを優先
            safe = [
                cand for cand in candidates
                if not self._creates_isolated(cand, unassigned, in_path)
            ]
            nxt = random.choice(safe if safe else candidates)
            path.append(nxt)
            in_path.add(nxt)

        return path

    def _creates_isolated(
        self, candidate: tuple, unassigned: set, in_path: set
    ) -> bool:
        """
        candidate を選んだとき、候補の隣接マスに「次数0になるもの(孤立)」が生じるか。
        """
        rows, cols = self.rows, self.cols
        blocked = in_path | {candidate}

        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = candidate[0] + dr, candidate[1] + dc
            if (nr, nc) not in unassigned or (nr, nc) in blocked:
                continue
            # (nr, nc) の隣接で未割当&未 in_path&非candidate なものが0個 → 孤立
            free = sum(
                1
                for dr2, dc2 in [(-1, 0), (1, 0), (0, -1), (0, 1)]
                if (
                    0 <= nr + dr2 < rows
                    and 0 <= nc + dc2 < cols
                    and (nr + dr2, nc + dc2) in unassigned
                    and (nr + dr2, nc + dc2) not in blocked
                    and (nr + dr2, nc + dc2) != (nr, nc)
                )
            )
            if free == 0:
                return True
        return False

    # ------------------------------------------------------------------
    # 内部: グリッド構築
    # ------------------------------------------------------------------

    def _build_puzzle(self, paths: list[list[tuple]]) -> list[list[int]]:
        grid = [[0] * self.cols for _ in range(self.rows)]
        for color, path in enumerate(paths, start=1):
            r0, c0 = path[0]
            r1, c1 = path[-1]
            grid[r0][c0] = color
            grid[r1][c1] = color
        return grid

    def _build_solution(self, paths: list[list[tuple]]) -> list[list[int]]:
        grid = [[0] * self.cols for _ in range(self.rows)]
        for color, path in enumerate(paths, start=1):
            for r, c in path:
                grid[r][c] = color
        return grid

    # ------------------------------------------------------------------
    # 内部: パス圧縮 (端点結合)
    # ------------------------------------------------------------------

    def _compress_colors(
        self, paths: list[list[tuple]], target_count: int
    ) -> list[list[tuple]]:
        """
        端点同士が隣接しているパスのペアを結合し、パス数を target_count まで減らす。

        ナンバーリンク規則上、パスの端点同士が隣接していれば
        2本のパスを1本に繋いでも有効な単純パスになる。
        (パス内部は互いに交差しないことが構造上保証済み)

        target_count 未満にできない場合は圧縮できる限り圧縮して返す。
        """
        paths = [list(p) for p in paths]  # コピー

        while len(paths) > target_count:
            # 結合可能なすべてのペアを探し、ヒューリスティクス（結合後の長さ）で評価
            possible_merges = []
            for i in range(len(paths)):
                for j in range(i + 1, len(paths)):
                    merged_path = self._try_merge(paths[i], paths[j])
                    if merged_path is not None:
                        # 評価値: 結合後のパス長（短いほど優先）
                        # ＋ 短いパス同士の結合を優先するため len(paths[i]) * len(paths[j]) などを加味しても良いが
                        # シンプルに len(merged_path) でソートする
                        score = len(merged_path)
                        # 少しランダム性を入れて多様性を保つ
                        score += random.uniform(0, 3.0)
                        possible_merges.append((score, i, j, merged_path))

            if not possible_merges:
                break  # これ以上結合できない

            # 最もスコアが良い(パスが短くなる)ペアを選ぶ
            possible_merges.sort(key=lambda x: x[0])
            _, best_i, best_j, best_merged = possible_merges[0]

            new_paths = [
                paths[k]
                for k in range(len(paths))
                if k != best_i and k != best_j
            ]
            new_paths.append(best_merged)
            paths = new_paths

        return paths

    def _try_merge(
        self, path_a: list[tuple], path_b: list[tuple]
    ) -> list[tuple] | None:
        """
        path_a と path_b の端点同士が隣接していれば結合パスを返す。
        隣接していなければ None を返す。

        結合方向の4パターン:
          path_a[-1] -- path_b[0] : merged = path_a + path_b
          path_a[-1] -- path_b[-1]: merged = path_a + reversed(path_b)
          path_a[0]  -- path_b[0] : merged = reversed(path_a) + path_b
          path_a[0]  -- path_b[-1]: merged = reversed(path_a) + reversed(path_b)
        """
        # (cell, path_a を逆順にするか)
        ends_a = [(path_a[-1], False), (path_a[0], True)]
        # (cell, path_b を逆順にするか)
        ends_b = [(path_b[0], False), (path_b[-1], True)]

        for cell_a, rev_a in ends_a:
            for cell_b, rev_b in ends_b:
                r1, c1 = cell_a
                r2, c2 = cell_b
                if abs(r1 - r2) + abs(c1 - c2) == 1:
                    oriented_a = list(reversed(path_a)) if rev_a else list(path_a)
                    oriented_b = list(reversed(path_b)) if rev_b else list(path_b)
                    return oriented_a + oriented_b
        return None

    # ------------------------------------------------------------------
    # 内部: 唯一解チェック (SAT)
    # ------------------------------------------------------------------

    def _is_unique(self, puzzle: list[list[int]]) -> bool:
        """
        force_full_fill=True で1回解いた後、
        その解を禁止する節を追加して再度解けるかで唯一性を判定する。

        2回とも同じ SAT インスタンスを使い回すことでオーバーヘッドを削減。
        """
        from pysat.solvers import Glucose3

        solver = NumberLinkSolver(puzzle)
        solver.cnf = []
        solver._generate_constraints(force_full_fill=True)
        cnf_snapshot = list(solver.cnf)

        # 1回目
        with Glucose3() as sat:
            sat.append_formula(cnf_snapshot)
            if not sat.solve():
                return False
            model1 = sat.get_model()

        sol1 = solver._decode_model(model1)
        blocking_clause = []
        for r in range(solver.rows):
            for c in range(solver.cols):
                k = sol1[r][c]
                if k != 0:
                    var = solver.get_var(f"C_{r}_{c}_{k}")
                    blocking_clause.append(-var)

        # 2回目
        with Glucose3() as sat2:
            sat2.append_formula(cnf_snapshot)
            sat2.add_clause(blocking_clause)
            if sat2.solve():
                return False  # 別解あり

        return True

    def _no_partial_solution(self, puzzle: list[list[int]]) -> bool:
        """
        「部分解(空白マスあり)が存在しない」ことをRC2ソルバーで確認する。

        RC2ソルバーは「エッジ変数をなるべく False にする(= パスを短くする)」
        というソフト制約で最適化する。
        → 部分解(エッジが少なくて済む)が有効なら、RC2は必ずそれを選ぶ。
        → RC2の結果が全埋め(空白なし)なら、部分解は存在しない。

        Returns
        -------
        True  : 部分解なし = 全埋め必須問題
        False : 部分解あり = 全埋めにならない問題
        """
        solver = NumberLinkSolver(puzzle)
        sol = solver.solve(force_full_fill=False)  # RC2(エッジ最小化)
        if sol is None:
            return False  # 解なし
        # RC2の最適解に空白マスがなければ、部分解は存在しない
        return not any(0 in row for row in sol)


# ------------------------------------------------------------------
# デバッグ・動作確認
# ------------------------------------------------------------------

if __name__ == "__main__":
    import time

    tests = [
        {"rows": 6, "cols": 6, "num_colors": 5},
        {"rows": 6, "cols": 6, "num_colors": None},
        {"rows": 8, "cols": 8, "num_colors": 7},
        {"rows": 8, "cols": 8, "num_colors": None},
    ]

    print("=== NumberLinkGenerator デモ ===\n")
    for cfg in tests:
        label = f"{cfg['rows']}x{cfg['cols']}, colors={cfg['num_colors']}"
        print(f"--- {label} ---")
        t0 = time.time()
        gen = NumberLinkGenerator(
            rows=cfg["rows"],
            cols=cfg["cols"],
            num_colors=cfg["num_colors"],
            max_attempts=500,
            require_unique=True,
            min_path_len=2,
        )
        result = gen.generate()
        elapsed = time.time() - t0

        if result:
            print(f"  生成時間: {elapsed:.2f}秒  パス数: {len(result['paths'])}  各長: {[len(p) for p in result['paths']]}")
            print("  問題:")
            for row in result["puzzle"]:
                print("  ", row)
            print("  解:")
            for row in result["solution"]:
                print("  ", row)
        else:
            print(f"  生成失敗 ({elapsed:.2f}秒)")
        print()
