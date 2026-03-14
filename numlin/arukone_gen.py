"""
アルコネ（全マス使用ナンバーリンク）作問アルゴリズム - 完成版

アルゴリズムの概要：
1. 縦ストライプジグザグのハミルトンパスを切断して多数のパスに分割する
2. ArukoneCheckerで全マス使用の別解を検出
   StandardCheckerで空白マスを含む短絡解を検出
   どちらかが見つかればエッジを切断してペアを追加→唯一解に→繰り返す
3. 唯一解になったら、隣接パスを結合してみて「結合後も唯一解なら結合（ペア削減）」を繰り返す

SATモデルの設計：
ArukoneChecker:
  - 端点マス: 次数=1
  - 非端点マス: 次数=2 ← 全マス使用を保証
  → 全マス使用の別解のみを検出

StandardChecker:
  - 端点マス: 次数=1
  - 非端点マス: 次数=0または2 ← 空白マスを許容
  → 空白マスを含む短絡解も検出可能
"""

import numpy as np
import random
import time
from pysat.solvers import Glucose3
from pysat.card import CardEnc


# ==============================================================
# パート1: ハミルトンパス生成とパス分割
# ==============================================================

def _adjacent(a, b):
    return abs(a[0]-b[0]) + abs(a[1]-b[1]) == 1


import sys
sys.setrecursionlimit(20000)

def make_random_hamiltonian_path(h, w):
    """
    Warnsdorffのヒューリスティックを用いたランダム化DFSにより、
    入り組んだランダムなハミルトンパスを生成する。
    """
    grid = [[False] * w for _ in range(h)]
    path = []
    
    def dfs(r, c):
        grid[r][c] = True
        path.append((r, c))
        if len(path) == h * w:
            return True
            
        neighbors = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and not grid[nr][nc]:
                count = 0
                for ddr, ddc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nnr, nnc = nr + ddr, nc + ddc
                    if 0 <= nnr < h and 0 <= nnc < w and not grid[nnr][nnc]:
                        count += 1
                # ランダム性を加える
                neighbors.append((count, random.random(), (nr, nc)))
        
        # 訪問可能な隣接先が少ない順に探索（行き止まり回避）
        neighbors.sort()
        
        for _, _, nxt in neighbors:
            if dfs(*nxt):
                return True
                
        grid[r][c] = False
        path.pop()
        return False
        
    dfs(0, 0)
    return path


def split_path(path, n, h, w):
    """ハミルトンパスをランダムにn本に分割する（各パスは長さ>=3、エンドポイント隣接なし）"""
    total = len(path)
    if n * 3 > total:
        return None

    positions = list(range(1, total))
    
    def is_boundary(pos_idx):
        if pos_idx < 0 or pos_idx >= total: return False
        r, c = path[pos_idx]
        return r == 0 or r == h - 1 or c == 0 or c == w - 1

    def cut_score(p):
        return int(is_boundary(p-1)) + int(is_boundary(p))

    # まずランダムシャッフルし、その後に安定ソートでスコア順にする
    random.shuffle(positions)
    positions.sort(key=cut_score)

    cuts = []
    used = set()
    for p in positions:
        if p not in used:
            cuts.append(p)
            # 各セグメントの長さが必ず3以上になるよう、カット位置の前後2マス以内を禁止する
            for dp in [-2, -1, 0, 1, 2]:
                used.add(p + dp)
            if len(cuts) == n - 1:
                break

    if len(cuts) != n - 1:
        return None

    cuts = sorted(cuts)
    paths = []
    prev = 0
    for cut in cuts + [total]:
        seg = path[prev:cut]
        if len(seg) < 3 or _adjacent(seg[0], seg[-1]):
            return None
        paths.append(seg)
        prev = cut
    return paths


def generate_cover(h, w, n):
    """n本のパスで全マスを被覆する。ランダムなハミルトンパスを切断。"""
    for _ in range(100):
        base = make_random_hamiltonian_path(h, w)
        if base and check_corners([base], h, w):
            break
    else:
        # 見つからなかった場合は適当に生成（通常は数回で見つかる）
        base = make_random_hamiltonian_path(h, w)
    for _ in range(10000):
        result = split_path(base, n, h, w)
        if result is not None:
            return result
    return None


# ==============================================================
# パート2: SATチェッカー群
# ==============================================================

def _build_edge_vars(var_fn, add_fn, clauses, nv_ref, R, C, K, prefix):
    """エッジ変数と色変数を構築する共通処理"""
    pass


class ArukoneChecker:
    """
    全マス使用アルコネ専用SAT唯一解チェッカー。
    非端点マスは次数=2を強制することで、全マス使用の別解のみを検出する。
    """
    def __init__(self, rows, cols, max_colors):
        self.rows = rows
        self.cols = cols
        self.max_colors = max_colors
        self._nv = 1
        self._var = {}
        self._clauses = []
        self._build()
        self._solver = Glucose3()
        self._solver.append_formula(self._clauses)
        self._blk = 0

    def _v(self, name):
        if name not in self._var:
            self._var[name] = self._nv
            self._nv += 1
        return self._var[name]

    def _add(self, cls):
        if not cls:
            return
        if not isinstance(cls, list):
            cls = list(cls)
        self._clauses.extend(cls)
        if cls:
            m = max(abs(l) for c in cls for l in c)
            if m >= self._nv:
                self._nv = m + 1

    def _build(self):
        R, C, K = self.rows, self.cols, self.max_colors
        for r in range(R):
            for c in range(C):
                cv = [self._v(f'c{r}_{c}_{k}') for k in range(K)]
                self._add(list(CardEnc.equals(lits=cv, bound=1, top_id=self._nv - 1)))

                adj = []
                if c + 1 < C:
                    e = self._v(f'eh{r}_{c}')
                    adj.append(e)
                    for k in range(K):
                        u, w = self._v(f'c{r}_{c}_{k}'), self._v(f'c{r}_{c+1}_{k}')
                        self._clauses += [[-e, -u, w], [-e, u, -w]]
                    # エッジが立っているなら色は設定されているはず（ArukoneCheckerは全マス着色なので自動的にOK）
                if c > 0:
                    adj.append(self._v(f'eh{r}_{c-1}'))
                if r + 1 < R:
                    e = self._v(f'ev{r}_{c}')
                    adj.append(e)
                    for k in range(K):
                        u, w = self._v(f'c{r}_{c}_{k}'), self._v(f'c{r+1}_{c}_{k}')
                        self._clauses += [[-e, -u, w], [-e, u, -w]]
                if r > 0:
                    adj.append(self._v(f'ev{r-1}_{c}'))

                ie = self._v(f'ie{r}_{c}')

                # 端点 → 次数=1
                d1 = list(CardEnc.equals(lits=adj, bound=1, top_id=self._nv - 1))
                for cl in d1:
                    self._clauses.append([-ie] + cl)
                m = max((abs(l) for cl in d1 for l in cl), default=0)
                if m >= self._nv:
                    self._nv = m + 1

                # 非端点 → 次数=2 （全マス使用の核心！）
                d2 = list(CardEnc.equals(lits=adj, bound=2, top_id=self._nv - 1))
                for cl in d2:
                    self._clauses.append([ie] + cl)
                m = max((abs(l) for cl in d2 for l in cl), default=0)
                if m >= self._nv:
                    self._nv = m + 1

    def _ev(self, r1, c1, r2, c2):
        if r1 == r2:
            return self._v(f'eh{r1}_{min(c1,c2)}')
        return self._v(f'ev{min(r1,r2)}_{c1}')

    def _make_asm(self, grid):
        asm = []
        for r in range(self.rows):
            for c in range(self.cols):
                ie = self._v(f'ie{r}_{c}')
                g = grid[r][c]
                if g != -1:
                    asm += [ie, self._v(f'c{r}_{c}_{g-1}')]
                else:
                    asm.append(-ie)
        return asm

    def find_alt(self, grid, sol_edges):
        """別解（全マス使用）のエッジリストを返す。なければNone。"""
        asm = self._make_asm(grid)

        bv = self._v(f'blk{self._blk}')
        self._blk += 1
        blocking = [-bv]
        for (r1, c1), (r2, c2) in sol_edges:
            blocking.append(-self._ev(r1, c1, r2, c2))
        self._solver.add_clause(blocking)
        asm.append(bv)

        if not self._solver.solve(assumptions=asm):
            return None

        ms = set(self._solver.get_model())
        alt = []
        for r in range(self.rows):
            for c in range(self.cols):
                if c + 1 < self.cols and self._v(f'eh{r}_{c}') in ms:
                    alt.append(((r, c), (r, c+1)))
                if r + 1 < self.rows and self._v(f'ev{r}_{c}') in ms:
                    alt.append(((r, c), (r+1, c)))
        return alt


class StandardChecker:
    """
    通常のナンバーリンク唯一解チェッカー。
    空白マス（次数0）を許容する。
    これにより「短絡解（一部のマスを通らない解）」も別解として検出できる。
    """
    def __init__(self, rows, cols, max_colors):
        self.rows = rows
        self.cols = cols
        self.max_colors = max_colors
        self._nv = 1
        self._var = {}
        self._clauses = []
        self._build()
        self._solver = Glucose3()
        self._solver.append_formula(self._clauses)
        self._blk = 0

    def _v(self, name):
        if name not in self._var:
            self._var[name] = self._nv
            self._nv += 1
        return self._var[name]

    def _add(self, cls):
        if not cls:
            return
        if not isinstance(cls, list):
            cls = list(cls)
        self._clauses.extend(cls)
        if cls:
            m = max(abs(l) for c in cls for l in c)
            if m >= self._nv:
                self._nv = m + 1

    def _build(self):
        R, C, K = self.rows, self.cols, self.max_colors
        for r in range(R):
            for c in range(C):
                cv = [self._v(f'sc{r}_{c}_{k}') for k in range(K)]
                # 空白マスを許容: 色なし(全部False)もOKなので atmost 1
                self._add(list(CardEnc.atmost(lits=cv, bound=1, top_id=self._nv - 1)))

                adj = []
                if c + 1 < C:
                    e = self._v(f'seh{r}_{c}')
                    adj.append(e)
                    # エッジが立っていれば両端は同色
                    for k in range(K):
                        u, w = self._v(f'sc{r}_{c}_{k}'), self._v(f'sc{r}_{c+1}_{k}')
                        self._clauses += [[-e, -u, w], [-e, u, -w]]
                    # エッジが立っていれば端点は着色されている
                    u_colors = [self._v(f'sc{r}_{c}_{k}') for k in range(K)]
                    self._clauses.append([-e] + u_colors)
                if c > 0:
                    adj.append(self._v(f'seh{r}_{c-1}'))
                if r + 1 < R:
                    e = self._v(f'sev{r}_{c}')
                    adj.append(e)
                    for k in range(K):
                        u, w = self._v(f'sc{r}_{c}_{k}'), self._v(f'sc{r+1}_{c}_{k}')
                        self._clauses += [[-e, -u, w], [-e, u, -w]]
                    u_colors = [self._v(f'sc{r}_{c}_{k}') for k in range(K)]
                    self._clauses.append([-e] + u_colors)
                if r > 0:
                    adj.append(self._v(f'sev{r-1}_{c}'))

                ie = self._v(f'sie{r}_{c}')

                # 端点マス → 次数=1
                d1 = list(CardEnc.equals(lits=adj, bound=1, top_id=self._nv - 1))
                for cl in d1:
                    self._clauses.append([-ie] + cl)
                m = max((abs(l) for cl in d1 for l in cl), default=0)
                if m >= self._nv:
                    self._nv = m + 1

                # 非端点マス → 次数=0または2
                # 1. 次数は最大2
                d_atmost2 = list(CardEnc.atmost(lits=adj, bound=2, top_id=self._nv - 1))
                for cl in d_atmost2:
                    self._clauses.append([ie] + cl)
                m = max((abs(l) for cl in d_atmost2 for l in cl), default=0)
                if m >= self._nv:
                    self._nv = m + 1

                # 2. 次数は1ではない (e => exists other)
                if adj:
                    for ii, edge in enumerate(adj):
                        others = adj[:ii] + adj[ii+1:]
                        if others:
                            self._clauses.append([-edge] + others + [ie])
                        else:
                            self._clauses.append([-edge, ie])

    def _ev(self, r1, c1, r2, c2):
        if r1 == r2:
            return self._v(f'seh{r1}_{min(c1,c2)}')
        return self._v(f'sev{min(r1,r2)}_{c1}')

    def _make_asm(self, grid):
        asm = []
        for r in range(self.rows):
            for c in range(self.cols):
                ie = self._v(f'sie{r}_{c}')
                g = grid[r][c]
                if g != -1:
                    asm += [ie, self._v(f'sc{r}_{c}_{g-1}')]
                else:
                    asm.append(-ie)
        return asm

    def find_alt(self, grid, sol_edges):
        """
        sol_edgesと異なる有効な解（空白マスあり・なし問わず）のエッジリストを返す。
        なければNone。
        """
        asm = self._make_asm(grid)

        bv = self._v(f'sblk{self._blk}')
        self._blk += 1
        blocking = [-bv]
        for (r1, c1), (r2, c2) in sol_edges:
            blocking.append(-self._ev(r1, c1, r2, c2))
        self._solver.add_clause(blocking)
        asm.append(bv)

        if not self._solver.solve(assumptions=asm):
            return None

        ms = set(self._solver.get_model())
        alt = []
        for r in range(self.rows):
            for c in range(self.cols):
                if c + 1 < self.cols and self._v(f'seh{r}_{c}') in ms:
                    alt.append(((r, c), (r, c+1)))
                if r + 1 < self.rows and self._v(f'sev{r}_{c}') in ms:
                    alt.append(((r, c), (r+1, c)))
        return alt


# ==============================================================
# パート3: ユーティリティ関数
# ==============================================================

def paths_to_edges(paths):
    edges = []
    for p in paths:
        for i in range(len(p) - 1):
            edges.append((p[i], p[i+1]))
    return edges


def check_corners(paths, h, w):
    """すべての行と列に、必ず直角になる箇所（コーナー）または数字（端点）が1か所以上あるか判定する"""
    row_condition = [False] * h
    col_condition = [False] * w
    
    for p in paths:
        # 端点（数字）の条件をチェック
        r_start, c_start = p[0]
        row_condition[r_start] = True
        col_condition[c_start] = True
        
        r_end, c_end = p[-1]
        row_condition[r_end] = True
        col_condition[c_end] = True

        for i in range(1, len(p) - 1):
            r1, c1 = p[i-1]
            r2, c2 = p[i]
            r3, c3 = p[i+1]
            
            # 進行方向が変わる（直角・コーナー）場合
            if r1 != r3 and c1 != c3:
                row_condition[r2] = True
                col_condition[c2] = True
                
    return all(row_condition) and all(col_condition)


def paths_to_grid(paths, h, w):
    grid = [[-1] * w for _ in range(h)]
    for k, p in enumerate(paths, 1):
        r1, c1 = p[0]
        r2, c2 = p[-1]
        if grid[r1][c1] != -1 or grid[r2][c2] != -1:
            return None  # 端点重複
        grid[r1][c1] = k
        grid[r2][c2] = k
    return grid


def try_split(paths, sol_edges, edge_key):
    """edge_keyでパスを分割する（同じ数字が隣接する場合はNone）"""
    for pi, p in enumerate(paths):
        for si in range(len(p) - 1):
            key = tuple(sorted((p[si], p[si+1])))
            if key == edge_key:
                left_len = si + 1
                right_len = len(p) - (si + 1)
                if left_len < 3 or right_len < 3:
                    return None
                left = p[:si + 1]
                right = p[si + 1:]
                if _adjacent(left[0], left[-1]) or _adjacent(right[0], right[-1]):
                    return None
                new_paths = paths[:pi] + [left, right] + paths[pi+1:]
                new_edges = paths_to_edges(new_paths)
                return new_paths, new_edges
    return None


def try_merge(paths, i, j):
    """paths[i]とpaths[j]を結合する（隣接していれば）"""
    pi = paths[i]
    pj = paths[j]

    if _adjacent(pi[-1], pj[0]):
        merged = pi + pj
    elif _adjacent(pi[-1], pj[-1]):
        merged = pi + list(reversed(pj))
    elif _adjacent(pi[0], pj[0]):
        merged = list(reversed(pi)) + pj
    elif _adjacent(pi[0], pj[-1]):
        merged = pj + pi
    else:
        return None

    if _adjacent(merged[0], merged[-1]):
        return None

    return merged


def fix_alt(paths, sol_edges, alt_edges, h, w):
    """
    別解（alt_edges）を踏まえて、正解と別解の差分エッジを切断してペア数を増やす。
    """
    sol_set = {tuple(sorted((a, b))) for a, b in sol_edges}
    alt_set = {tuple(sorted((a, b))) for a, b in alt_edges}
    diff = list(sol_set - alt_set)
    
    def edge_score(edge_key):
        (r1, c1), (r2, c2) = edge_key
        b1 = (r1 == 0 or r1 == h - 1 or c1 == 0 or c1 == w - 1)
        b2 = (r2 == 0 or r2 == h - 1 or c2 == 0 or c2 == w - 1)
        return int(b1) + int(b2)
        
    # 端点が外周に配置されるのを避けるため、外周辺を含まないエッジの切断を優先
    diff.sort(key=lambda e: (edge_score(e), random.random()))

    for edge_key in diff:
        result = try_split(paths, sol_edges, edge_key)
        if result is not None:
            return result
    return None


# ==============================================================
# パート4: 作問メインロジック
# ==============================================================

def build_arukone(h, w, target_max_n=10, verbose=False):
    """
    target_max_n 以下のペア数で全マス使用の唯一解アルコネパズルを生成する。

    フェーズ1: 多ペア数の唯一解を高速生成
      - ArukoneCheckerで全マス使用の別解を潰す
      - StandardCheckerで短絡解（空白マス含む別解）も潰す
    フェーズ2: 隣接パスを結合してペア数を最小化
      - 両チェッカーで唯一性を確認してから結合する
    """
    max_init_n = h * w // 5  # 最初は5マスに1ペア程度
    aru_checker = ArukoneChecker(h, w, max_init_n + 2)
    std_checker = StandardChecker(h, w, max_init_n + 2)

    t0 = time.time()
    trial = 0

    while True:
        trial += 1
        if verbose and trial % 20 == 0:
            print(f"  {trial}試行目... ({time.time()-t0:.1f}秒)")

        # ─── フェーズ1: 唯一解の初期パスを生成 ───
        start_n = max_init_n
        paths = generate_cover(h, w, start_n)
        if paths is None:
            continue

        grid = paths_to_grid(paths, h, w)
        if grid is None:
            continue

        current_n = start_n
        sol_edges = paths_to_edges(paths)

        # 別解（全マス・短絡共に）がなくなるまで分割を繰り返す
        ok = False
        for _ in range(current_n * 3):
            grid = paths_to_grid(paths, h, w)
            if grid is None:
                break

            # まず全マス使用の別解をチェック（速い）
            alt = aru_checker.find_alt(grid, sol_edges)
            if alt is None:
                # 次に短絡解をチェック（一般ナンバーリンクの別解）
                alt = std_checker.find_alt(grid, sol_edges)
                if alt is None:
                    # どちらの別解もない → 真の唯一解
                    ok = True
                    break

            # 別解のエッジと正解のエッジの差分を切断してペアを追加
            result = fix_alt(paths, sol_edges, alt, h, w)
            if result is None:
                break
            paths, sol_edges = result
            current_n += 1

        if not ok:
            continue

        if verbose:
            print(f"  フェーズ1完了: {len(paths)}ペアの唯一解 ({time.time()-t0:.1f}秒)")

        # ─── フェーズ2: 隣接パスを結合してペア数を最小化 ───
        improved = True
        while improved and len(paths) > target_max_n:
            improved = False
            indices = list(range(len(paths)))
            
            def boundary_count(pi):
                c = 0
                for r, c_idx in [paths[pi][0], paths[pi][-1]]:
                    if r == 0 or r == h - 1 or c_idx == 0 or c_idx == w - 1:
                        c += 1
                return c
            
            # 外周に端点を持つパスから優先的に結合を試みることで、外周の端点を減らす
            indices.sort(key=lambda i: (-boundary_count(i), random.random()))

            found = False
            for i in indices:
                if found:
                    break
                for j in indices:
                    if j == i or found:
                        continue

                    merged = try_merge(paths, i, j)
                    if merged is None:
                        continue

                    new_paths = [paths[k] for k in range(len(paths)) if k != i and k != j]
                    new_paths.append(merged)

                    new_grid = paths_to_grid(new_paths, h, w)
                    if new_grid is None:
                        continue

                    new_edges = paths_to_edges(new_paths)

                    # 全マス使用の別解チェック
                    alt = aru_checker.find_alt(new_grid, new_edges)
                    # 短絡解チェック（全マス使用の別解がない場合のみ）
                    if alt is None:
                        alt = std_checker.find_alt(new_grid, new_edges)

                    if alt is None:
                        # 両チェッカーとも別解なし → 唯一解のまま結合できた！
                        paths = new_paths
                        sol_edges = new_edges
                        if verbose:
                            print(f"  {len(paths)+1} -> {len(paths)} ペア ({time.time()-t0:.1f}秒)")
                        improved = True
                        found = True

        if not check_corners(paths, h, w):
            if verbose:
                print(f"  直角・数字条件（各行列に1つ以上）未達のためリトライします。")
            continue

        boundary_endpoints = 0
        for p in paths:
            for r, c in [p[0], p[-1]]:
                if r == 0 or r == h - 1 or c == 0 or c == w - 1:
                    boundary_endpoints += 1
        
        if boundary_endpoints > 2:
            if verbose:
                print(f"  外縁の端点が多い({boundary_endpoints}個)ためリトライします。")
            continue

        grid = paths_to_grid(paths, h, w)
        n = len(paths)

        if verbose:
            print(f"  ✓ 完成 n={n} ({time.time()-t0:.2f}秒)")

        return grid, paths


# ==============================================================
# メイン実行
# ==============================================================

if __name__ == '__main__':
    h, w = 10, 10
    max_n = 10
    print(f"--- {h}x{w} 全マス使用アルコネ 最大{max_n}ペア で作問中 ---")
    t0 = time.time()
    grid, paths = build_arukone(h, w, max_n, verbose=True)
    elapsed = time.time() - t0
    n = len(paths)
    print(f"\n★ 完成！ ペア数={n}  ({elapsed:.2f}秒)")
    print(np.array(grid))

    # 検証
    used_cells = sum(len(p) for p in paths)
    print(f"\n検証: 利用セル数={used_cells}, 全セル数={h*w}")
    assert used_cells == h * w, "ERROR: 全マス使用されていない！"
    print("OK: 全マス使用確認済み")
