from pysat.solvers import Glucose3
from pysat.card import CardEnc
from pysat.examples.rc2 import RC2
from pysat.formula import WCNF

class NumberLinkSolver:
    def __init__(self, grid):
        self.grid = grid
        self.rows = len(grid)
        self.cols = len(grid[0])
        self.colors = set(val for row in grid for val in row if val != 0)
        
        self.var_map = {}
        self.next_var = 1
        self.cnf = []

    def get_var(self, name):
        """変数名からIDを取得"""
        if name not in self.var_map:
            self.var_map[name] = self.next_var
            self.next_var += 1
        return self.var_map[name]

    def add_clauses(self, clauses):
        """
        生成された節(clauses)を登録し、
        内部で使用された補助変数のID分だけ next_var を更新する
        """
        if not clauses:
            return
        
        self.cnf.extend(clauses)
        
        # 節の中で使われている最大の変数IDを探す
        max_id = 0
        for clause in clauses:
            for lit in clause:
                max_id = max(max_id, abs(lit))
        
        # 次に使う変数は、これまで使われた最大ID + 1
        if max_id >= self.next_var:
            self.next_var = max_id + 1

    def solve(self, force_full_fill=False):
        """
        force_full_fill: Trueの場合、すべての空白マスをパスで埋めることを強制する
        """
        self.cnf = [] # リセット
        self._generate_constraints(force_full_fill)
        
        if force_full_fill:
            with Glucose3() as solver:
                solver.append_formula(self.cnf)
                if solver.solve():
                    model = solver.get_model()
                    return self._decode_model(model)
                else:
                    return None
        else:
            wcnf = WCNF()
            for clause in self.cnf:
                wcnf.append(clause)
            
            # 最短経路のみを線でつなぐため、エッジ変数をなるべくFalseにするというソフト制約を入れる
            for name, var_id in self.var_map.items():
                if name.startswith('H_') or name.startswith('V_'):
                    wcnf.append([-var_id], weight=1)
            
            with RC2(wcnf) as solver:
                model = solver.compute()
                if model is not None:
                    return self._decode_model(model)
                else:
                    return None

    def _generate_constraints(self, force_full_fill):
        for r in range(self.rows):
            for c in range(self.cols):
                # 1. 色の制約 (各セルは必ずどれか1色を持つ)
                color_vars = [self.get_var(f'C_{r}_{c}_{k}') for k in self.colors]
                self.add_clauses(CardEnc.equals(lits=color_vars, bound=1, top_id=self.next_var-1))
                
                # 数字マスの固定
                if self.grid[r][c] != 0:
                    k = self.grid[r][c]
                    self.cnf.append([self.get_var(f'C_{r}_{c}_{k}')])

                # エッジ変数の収集
                adj_edges = []
                
                # 右 (Horizontal)
                if c < self.cols - 1:
                    edge_h = self.get_var(f'H_{r}_{c}')
                    adj_edges.append(edge_h)
                    # 接続があれば同色制約
                    for k in self.colors:
                        u = self.get_var(f'C_{r}_{c}_{k}')
                        v = self.get_var(f'C_{r}_{c+1}_{k}')
                        self.cnf.append([-edge_h, -u, v])
                        self.cnf.append([-edge_h, u, -v])

                # 左
                if c > 0:
                    adj_edges.append(self.get_var(f'H_{r}_{c-1}'))
                
                # 下 (Vertical)
                if r < self.rows - 1:
                    edge_v = self.get_var(f'V_{r}_{c}')
                    adj_edges.append(edge_v)
                    # 接続があれば同色制約
                    for k in self.colors:
                        u = self.get_var(f'C_{r}_{c}_{k}')
                        v = self.get_var(f'C_{r+1}_{c}_{k}')
                        self.cnf.append([-edge_v, -u, v])
                        self.cnf.append([-edge_v, u, -v])

                # 上
                if r > 0:
                    adj_edges.append(self.get_var(f'V_{r-1}_{c}'))

                # 2. 次数制約
                if self.grid[r][c] != 0:
                    # 端点: 次数は必ず 1
                    self.add_clauses(CardEnc.equals(lits=adj_edges, bound=1, top_id=self.next_var-1))
                else:
                    # 空白マス
                    if force_full_fill:
                        # 全マス埋め問題の場合: 次数は必ず 2
                        self.add_clauses(CardEnc.equals(lits=adj_edges, bound=2, top_id=self.next_var-1))
                    else:
                        # 空白許容の場合: 次数は 0 または 2 (1は禁止、3以上も禁止)
                        
                        # (A) 次数は2以下
                        self.add_clauses(CardEnc.atmost(lits=adj_edges, bound=2, top_id=self.next_var-1))
                        
                        # (B) 次数は1ではない (入ってきたら必ず出る)
                        if len(adj_edges) > 0:
                            for i, e_target in enumerate(adj_edges):
                                others = adj_edges[:i] + adj_edges[i+1:]
                                if others:
                                    # e_target が True なら、others のどれかも True
                                    self.cnf.append([-e_target] + others)
                                else:
                                    # 隣接が1つしかない(角の)場合、そこだけONにはなれない(=孤立確定)
                                    self.cnf.append([-e_target])

    def _decode_model(self, model):
        result = [[0] * self.cols for _ in range(self.rows)]
        model_set = set(model)
        
        # 接続があるセルを特定
        connected_cells = set()
        for r in range(self.rows):
            for c in range(self.cols):
                is_connected = False
                # H, V 変数をチェック
                if c < self.cols - 1 and self.get_var(f'H_{r}_{c}') in model_set: is_connected = True
                if c > 0 and self.get_var(f'H_{r}_{c-1}') in model_set: is_connected = True
                if r < self.rows - 1 and self.get_var(f'V_{r}_{c}') in model_set: is_connected = True
                if r > 0 and self.get_var(f'V_{r-1}_{c}') in model_set: is_connected = True
                
                if self.grid[r][c] != 0 or is_connected:
                    connected_cells.add((r,c))

        for r in range(self.rows):
            for c in range(self.cols):
                if (r,c) in connected_cells:
                    for k in self.colors:
                        if self.get_var(f'C_{r}_{c}_{k}') in model_set:
                            result[r][c] = k
                            break
        return result
