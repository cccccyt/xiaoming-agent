"""从 PNG 交割单图片提取交易数据，生成适配 xiaoming-agent 的 CSV 文件。
基于 EasyOCR 文本识别 + 模式匹配解析。"""

import csv
import re
from pathlib import Path

import easyocr

PROJECT_DIR = Path(__file__).parent.parent
PIC_DIR = PROJECT_DIR / "pic"
OUTPUT_DIR = PROJECT_DIR / "data" / "input"

HEADER = [
    "成交日期", "成交时间", "证券代码", "证券名称",
    "买卖方向", "成交数量", "成交均价", "成交金额",
    "手续费", "印花税", "其他费", "发生金额",
]

NAME_FIXES = {
    "特娈电工": "特变电工",
}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")
CODE_RE = re.compile(r"^\d{6}$")
DIRECTION_RE = re.compile(r"^(证券买入|证券卖出)$")


def read_all_text(reader, pic_dir: Path) -> list[list[str]]:
    """从所有 PNG 读取 OCR 文本，每张图片独立聚类行"""
    all_rows = []
    for png_file in sorted(pic_dir.glob("*.png")):
        results = reader.readtext(str(png_file))
        items = []
        for bbox, text, conf in results:
            text = text.strip()
            if not text:
                continue
            if any(w in text for w in ["pin_memory", "dataloader", "UserWarning"]):
                continue
            y = (bbox[0][1] + bbox[2][1]) / 2
            x = (bbox[0][0] + bbox[2][0]) / 2
            items.append((y, x, text))

        if not items:
            continue

        items.sort(key=lambda t: (t[0], t[1]))

        # 聚合成行
        img_rows = []
        current = [items[0][2]]
        last_y = items[0][0]
        for y, x, text in items[1:]:
            if y - last_y > 20:
                img_rows.append(current)
                current = [text]
                last_y = y
            else:
                current.append(text)
        if current:
            img_rows.append(current)

        all_rows.extend(img_rows)

    return all_rows


def parse_row_by_pattern(row: list[str]) -> dict | None:
    """按字段模式匹配解析一行数据"""
    dates = []
    times = []
    codes = []
    names = []
    directions = []
    numbers = []

    for cell in row:
        cell = cell.strip()
        if DATE_RE.match(cell):
            dates.append(cell)
        elif TIME_RE.match(cell):
            times.append(cell)
        elif CODE_RE.match(cell):
            codes.append(cell)
        elif DIRECTION_RE.match(cell):
            directions.append(cell)
        elif re.match(r"^[一-鿿]+$", cell) and len(cell) >= 2:
            names.append(NAME_FIXES.get(cell, cell))
        elif re.match(r"^-?\d+\.?\d*$", cell) or re.match(r"^~-?\d+\.?\d*$", cell):
            numbers.append(cell.lstrip("~"))

    if not dates or not codes:
        return None

    # 通常有2个日期：发生日期、交收日期（可能其中之一缺失）
    # 取第二个或最后一个作为成交日期（发生日期通常是第二个）
    trade_date = dates[-1] if len(dates) >= 1 else dates[0]
    # 如果有2个，第二个是"发生日期"
    if len(dates) >= 2:
        trade_date = dates[1]  # 发生日期 通常在 交收日期 之后出现

    time_val = times[0] if times else ""
    code = codes[0]
    name = names[0] if names else ""
    direction_raw = directions[0] if directions else ""
    direction = "买入" if "买" in direction_raw else "卖出" if "卖" in direction_raw else ""

    if not direction:
        return None

    # 数值字段: 成交数量(int), 成交价格(float), 成交金额, 发生金额
    nums_float = []
    for n in numbers:
        try:
            nums_float.append(float(n))
        except ValueError:
            continue

    if len(nums_float) < 3:
        return None

    # 用乘积约束找 数量*价格≈金额
    # 候选整数 → 数量  (小整数: 100-50000)
    small_ints = [n for n in nums_float if n == int(n) and 10 <= n <= 50000]
    # 候选大数 → 金额
    big_nums = sorted([n for n in nums_float if abs(n) > 1000], key=lambda x: -abs(x))
    # 候选价格: 非整数的中等大小浮点数，或 1-2000 区间
    price_candidates = [n for n in nums_float if n not in small_ints and n not in big_nums]

    best_qty, best_price, best_amount, best_net = 0, 0.0, 0.0, 0.0
    best_err = float("inf")

    for q in small_ints:
        for p_cand in nums_float:
            if abs(p_cand - q) < 0.01 or p_cand < 0.01:
                continue
            expected = abs(q * p_cand)
            for b in big_nums:
                err = abs(abs(b) - expected) / expected if expected > 0 else 1
                if err < best_err and err < 0.1:  # 10% tolerance
                    best_err = err
                    best_qty = int(q)
                    best_price = abs(p_cand)
                    best_amount = abs(b)
                    # net 是另一个大数
                    for other in big_nums:
                        if abs(abs(other) - abs(b)) > 0.01:
                            best_net = other
                            break
                    else:
                        best_net = b

    if best_qty == 0:
        # fallback
        if small_ints:
            best_qty = int(small_ints[0])
        else:
            return None
        best_price = price_candidates[0] if price_candidates else abs(best_amount / best_qty)
        best_amount = big_nums[0] if big_nums else abs(best_qty * best_price)
        best_net = big_nums[-1] if len(big_nums) > 1 else best_amount

    qty = best_qty
    price = abs(best_price)
    amount = abs(best_amount)
    net = best_net

    # 买入净额应为负
    if direction == "买入" and net > 0:
        net = -net

    # 计算手续费
    if direction == "买入":
        commission = max(abs(abs(net) - amount), 0)
        stamp_tax = 0.0
    else:
        stamp_tax = round(amount * 0.001, 2)
        commission = max(amount - net - stamp_tax, 0)

    commission = round(min(commission, amount * 0.01), 2)

    return {
        "成交日期": trade_date,
        "成交时间": time_val,
        "证券代码": code.zfill(6),
        "证券名称": name,
        "买卖方向": direction,
        "成交数量": str(qty),
        "成交均价": f"{price:.3f}",
        "成交金额": f"{amount:.2f}",
        "手续费": f"{commission:.2f}",
        "印花税": f"{stamp_tax:.2f}",
        "其他费": "0.00",
        "发生金额": f"{net:.2f}",
    }


def main():
    print("正在加载 OCR 模型...")
    reader = easyocr.Reader(["ch_sim", "en"], gpu=False)
    print("正在识别图片文字...")

    rows = read_all_text(reader, PIC_DIR)
    print(f"识别到 {len(rows)} 行文本")

    records = []
    for row in rows:
        parsed = parse_row_by_pattern(row)
        if parsed:
            records.append(parsed)
            print(f"  {parsed['成交日期']} {parsed['买卖方向']} {parsed['证券名称']}({parsed['证券代码']}) "
                  f"{parsed['成交数量']}股 × {parsed['成交均价']}")

    if not records:
        print("\n错误: 未提取到有效交易记录。原始行如下:")
        for row in rows:
            print(f"  {row}")
        return

    # 去重 + 排序
    seen = set()
    unique = []
    for r in records:
        key = (r["成交日期"], r["成交时间"], r["证券代码"], r["买卖方向"], r["成交数量"])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    unique.sort(key=lambda r: (r["成交日期"], r["成交时间"]))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / "历史成交_2026.csv"

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(unique)

    print(f"\n✅ 已生成: {csv_path}")
    print(f"共 {len(unique)} 条交易记录")

    # 也清理旧的测试数据
    old_csv = OUTPUT_DIR / "历史成交_2024.csv"
    if old_csv.exists():
        old_csv.unlink()

    # 验证 CSV 可以被 xiaoming-agent 读取
    print("\n--- 验证 ---")
    import sys
    sys.path.insert(0, str(PROJECT_DIR))
    from src.data_ingestion.trade_history import parse_trade_history
    from src.data_ingestion.csv_reader import find_columns_in_files

    files = find_columns_in_files(OUTPUT_DIR)
    trade_files = files.get("trade_history", [])
    if trade_files:
        trades = parse_trade_history(trade_files[0])
        print(f"xiaoming-agent 解析通过: {len(trades)} 条记录")
        from collections import Counter
        months = Counter(t.trade_date.strftime("%Y-%m") for t in trades)
        for m, c in sorted(months.items()):
            print(f"  {m}: {c} 笔")


if __name__ == "__main__":
    main()
