def save_numlin_format(grid, filename):
    """
    ナンバーリンクのグリッドデータを指定のフォーマットでファイルに出力する。
    
    Args:
        grid (list of list of int): パズル盤面。数字は端点、0は空白を表す。
        filename (str): 出力するファイルのパス。
    """
    if not grid:
        return

    height = len(grid)
    width = len(grid[0])

    with open(filename, 'w', encoding='utf-8') as f:
        # 1. ヘッダー情報の書き込み
        f.write("pzprv3\nnumlin\n")
        f.write(f"{height}\n")
        f.write(f"{width}\n")

        # 2. 盤面データの書き込み
        # 数字はそのまま、0は '.' に変換してスペース区切りで出力
        for row in grid:
            line_parts = []
            for cell in row:
                if cell == 0:
                    line_parts.append(".")
                else:
                    line_parts.append(str(cell))
            f.write(" ".join(line_parts) + "\n")

        # 3. 解答/補助データ（0の羅列）の書き込み
        # ご提示の例に基づき、以下のブロックを出力します。
        # ブロック1: (高さ-1)行 × (幅-1)列 の0  (※ご提示例の9行9列に合わせた形)
        # ブロック2: (高さ-1)行 × 幅列 の0      (※ご提示例の9行10列に合わせた形)
        
        # ※多くのツールではここが「縦の境界線」「横の境界線」のデータになります。
        # ツールによっては行数が height と一致する必要がある場合もあります。
        # 読み込みエラーが出る場合は range(height - 1) を range(height) に調整してください。

        # ブロック1 (例: 10行 x 9列)
        for _ in range(height):
            zeros = ["0"] * (width - 1)
            f.write(" ".join(zeros) + "\n")

        # ブロック2 (例: 9行 x 10列)
        for _ in range(height - 1):
            zeros = ["0"] * width
            f.write(" ".join(zeros) + "\n")

    print(f"Exported to {filename}")