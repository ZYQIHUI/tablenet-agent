import argparse
import csv
import json
import math
from pathlib import Path


DIMENSIONS = ("structure", "topic", "semantic")


def calculate(rows):
    result = {"samples": len(rows), "dimensions": {}}
    for dimension in DIMENSIONS:
        human = [float(row[f"human_{dimension}"]) for row in rows]
        checker = [float(row[f"checker_{dimension}"]) for row in rows]
        result["dimensions"][dimension] = {
            "pearson": round(pearson(human, checker), 6),
            "spearman": round(pearson(rank(human), rank(checker)), 6),
            "kendall": round(kendall_tau_b(human, checker), 6),
        }
    return result


def pearson(left, right):
    if len(left) != len(right) or len(left) < 2:
        return 0.0
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    left_norm = math.sqrt(sum((a - left_mean) ** 2 for a in left))
    right_norm = math.sqrt(sum((b - right_mean) ** 2 for b in right))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


def rank(values):
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        average = (index + 1 + end) / 2
        for position in range(index, end):
            ranks[ordered[position][0]] = average
        index = end
    return ranks


def kendall_tau_b(left, right):
    concordant = discordant = ties_left = ties_right = 0
    for first in range(len(left)):
        for second in range(first + 1, len(left)):
            left_delta = left[first] - left[second]
            right_delta = right[first] - right[second]
            if left_delta == 0 and right_delta == 0:
                continue
            if left_delta == 0:
                ties_left += 1
            elif right_delta == 0:
                ties_right += 1
            elif left_delta * right_delta > 0:
                concordant += 1
            else:
                discordant += 1
    denominator = math.sqrt(
        (concordant + discordant + ties_left) *
        (concordant + discordant + ties_right)
    )
    return (concordant - discordant) / denominator if denominator else 0.0


def read_ratings(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as file_object:
        rows = list(csv.DictReader(file_object))
    required = {f"{source}_{dimension}" for source in ("human", "checker") for dimension in DIMENSIONS}
    if not rows:
        raise ValueError("ratings file is empty")
    missing = required - set(rows[0])
    if missing:
        raise ValueError("missing rating columns: " + ", ".join(sorted(missing)))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ratings", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = calculate(read_ratings(args.ratings))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
