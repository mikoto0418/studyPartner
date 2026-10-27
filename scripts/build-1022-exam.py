"""Rebuild the reviewed exam data; expected outputs are checked against independent solvers."""
import itertools
import json
import random
import re
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from exam_1022_extra import extra_cases

ROOT = Path(__file__).resolve().parents[1]
rng = random.Random(1022)


def palindrome(start, end):
    found = []
    day = date.fromisoformat(f"{start[:4]}-{start[4:6]}-{start[6:]}")
    finish = date.fromisoformat(f"{end[:4]}-{end[4:6]}-{end[6:]}")
    while day <= finish:
        text = day.strftime("%Y%m%d")
        if text == text[::-1]:
            found.append(text)
        day += timedelta(days=1)
    return "\n".join(found) or "0"


def position(room):
    pair = (room + 1) // 2
    return pair - (11 if room <= 20 else 10)


def delivery(orders):
    extremes = {}
    farthest = 0
    for floor, room in orders:
        x = position(room)
        left, right = extremes.get(floor, (0, 0))
        extremes[floor] = (max(left, -x), max(right, x))
        farthest = max(farthest, 30 * (floor - 1) + 3 * abs(x))
    edges = 30 * (max(extremes) - 1) + 3 * sum(l + r for l, r in extremes.values())
    return 2 * edges - farthest


def delivery_bruteforce(orders):
    nodes = list(set((a, position(b)) for a, b in orders))
    def distance(a, b):
        if a[0] == b[0]:
            return 3 * abs(a[1] - b[1])
        return 3 * (abs(a[1]) + abs(b[1])) + 30 * abs(a[0] - b[0])
    return min(
        sum(distance(a, b) for a, b in zip([(1, 0)] + list(order), order))
        for order in itertools.permutations(nodes)
    )


def candy(values):
    dp = values[:]
    for length in range(2, len(values) + 1):
        for left in range(len(values) - length + 1):
            right = left + length - 1
            dp[left] = max(values[left] - dp[left + 1], values[right] - dp[left])
    return "A" if dp[0] > 0 else "B" if dp[0] < 0 else "F"


def candy_bruteforce(values):
    @lru_cache(None)
    def best(left, right, turn):
        if left > right:
            return 0
        if turn == 0:
            return max(values[left] + best(left + 1, right, 1), values[right] + best(left, right - 1, 1))
        return min(best(left + 1, right, 0) - values[left], best(left, right - 1, 0) - values[right])
    difference = best(0, len(values) - 1, 0)
    return "A" if difference > 0 else "B" if difference < 0 else "F"


def main():
    for _ in range(60):
        orders = [(rng.randint(1, 6), rng.randint(1, 40)) for _ in range(rng.randint(1, 6))]
        assert delivery(orders) == delivery_bruteforce(orders)
        values = [rng.randrange(1, 1000) for _ in range(rng.randint(1, 20))]
        assert candy(values) == candy_bruteforce(values)

    date_ranges = [
        ("20000101", "20101231"), ("20200101", "20211231"), ("20261001", "20261022"),
        ("20000101", "20261022"), ("20011002", "20011002"), ("20200202", "20200202"),
        ("20211202", "20211202"), ("20000228", "20000301"), ("20261022", "20261022"),
        ("20011001", "20011003"), ("20111101", "20111103"), ("20200203", "20211201"),
    ]
    orders_list = [
        [(3, 21), (1, 1), (2, 40), (1, 19), (3, 20)],
        [(6, 40), (2, 1), (6, 1), (1, 21)],
        [(2, 19), (1, 20), (2, 19), (1, 19)],
        [(1, 20)], [(6, 40)], [(1, 1), (1, 40)], [(4, 19), (4, 20)],
        [(6, 1)] * 1000,
        [(rng.randint(1, 6), rng.randint(1, 40)) for _ in range(1000)],
    ]
    orders_list += [[(rng.randint(1, 6), rng.randint(1, 40)) for _ in range(rng.randint(2, 80))] for _ in range(9)]
    candies = [[5], [4, 4], [1, 9, 2], [8, 15, 3, 7], [1, 1, 1], [1], [999],
               [999] * 20, [1] * 20, [1, 999, 1], list(range(1, 21)), list(range(20, 0, -1))]
    candies += [[rng.randrange(1, 1000) for _ in range(n)] for n in (3, 5, 7, 9, 10, 13, 17, 19, 20)]
    case_lists = [
        [{"input": f"{a} {b}\n", "expected_output": palindrome(a, b) + "\n"} for a, b in date_ranges],
        [{"input": str(len(items)) + "\n" + "".join(f"{a} {100*a+b}\n" for a, b in items),
          "expected_output": str(delivery(items)) + "\n"} for items in orders_list],
        [{"input": f"{len(values)}\n" + " ".join(map(str, values)) + "\n",
          "expected_output": candy(values) + "\n"} for values in candies],
    ]
    colors, cipher = extra_cases()
    case_lists = [case_lists[0], colors, cipher, case_lists[1], case_lists[2]]
    proposal = (ROOT / "docs/1022-exam-proposal.md").read_text(encoding="utf-8")
    sections = re.split(r"(?m)^## [1-5]\. ", proposal)[1:]
    assert len(sections) == 5
    questions = []
    for index, section in enumerate(sections):
        section = section.split("\n## 导入及验证计划")[0]
        stem = re.sub(r"(?m)^#{1,6} ", "", section).replace("```text\n", "").replace("```\n", "").replace("**", "")
        images = None
        if index == 3:
            stem = stem.replace("每层的门口位置如下。", "原文 4 楼示意图（其他楼层布局相同）：\n[[IMG:0]]\n\n每层的门口位置如下。")
            images = [{"index": 0, "url": "/exam-assets/1022-floor-plan.png"}]
        questions.append({
            "question_type": "code", "order_index": index, "stem": stem.strip(),
            "stem_images": images, "language": "multi", "test_cases": case_lists[index],
            "starter_code": None, "score": (20, 20, 20, 40, 40)[index],
            "analysis": (
                "枚举年份，将年份反转构成月日，再验证日期与区间。",
                "将每种油漆记为一位二进制位，按区间叠加。统计最终掩码，0 和 7 都计入白色；也可按区间端点分段计数。",
                "逐字符按原始大小写分类：小写转大写，大写循环右移一位。每个字符只转换一次。",
                "将对向门口合并为一个位置。所需路径是一棵树，答案为所需边权和的两倍减去起点到最远配送点的距离。",
                "区间 DP：dp[l][r] 表示当前行动者能领先对手的最大糖果数，取 max(a[l]-dp[l+1][r], a[r]-dp[l][r-1])。",
            )[index],
            "tags": ["1022二面"],
        })
    target = ROOT / "server/app/data/exam_1022.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"title": "1022二面", "questions": questions}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Verified and generated case counts:", [len(c) for c in case_lists])


if __name__ == "__main__":
    main()
