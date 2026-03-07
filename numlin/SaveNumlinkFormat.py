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

def writeNumber16(qn):
    """マスの数字を文字列に変換する"""
    if qn == -2: # (-2は通常使わない特殊記号)
        return "."
    elif 0 <= qn < 16:
        return hex(qn)[2:]
    elif 16 <= qn < 256:
        return "-" + hex(qn)[2:]
    elif 256 <= qn < 4096:
        return "+" + hex(qn)[2:]
    elif 4096 <= qn < 8192:
        return "=" + hex(qn - 4096)[2:].zfill(3)
    elif 8192 <= qn < 12240:
        return "@" + hex(qn - 8192)[2:].zfill(3)
    elif 12240 <= qn < 77776:
        return "*" + hex(qn - 12240)[2:].zfill(4)
    elif qn >= 77776:
        return "$" + hex(qn - 77776)[2:].zfill(5)
    else:
        # 数字が無いマスは空文字を返す
        return ""

def base36encode(number):
    """数値を36進数(0-9a-z)に変換する"""
    alphabet = '0123456789abcdefghijklmnopqrstuvwxyz'
    base36 = ''
    while number:
        number, i = divmod(number, 36)
        base36 = alphabet[i] + base36
    return base36 or alphabet[0]

def encodeNumber16(grid):
    """盤面の1次元配列を受け取ってエンコード文字列を生成する"""
    count = 0
    cm = ""
    for qn in grid:
        pstr = writeNumber16(qn)
        if pstr == "":
            count += 1
        
        if count == 0:
            cm += pstr
        elif pstr or count == 20:
            # 連続する空きマス情報をエンコードして結合
            # (15 + count) の36進数表現（count=1 なら "g", count=20 なら "z"）
            cm += base36encode(15 + count) + pstr
            count = 0

    # 最後に残った空きマス数を出力
    if count > 0:
        cm += base36encode(15 + count)

    return cm

def generate_numlin_url(width, height, grid):
    """
    width: 盤面の幅
    height: 盤面の高さ
    grid: 盤面のマスの情報（横方向優先の1次元配列）
          数字のあるマスはその数字（例: 1, 2, 3...）
          空白マスは -1 を指定する
    """
    if len(grid) != width * height:
        raise ValueError("Grid size does not match width * height")
        
    encoded_body = encodeNumber16(grid)
    url = f"https://puzz.link/p?numlin/{width}/{height}/{encoded_body}"
    return url
