import argparse
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", value))


def align(records: list[dict], reference: str) -> list[dict]:
    tokens = re.findall(r"\S+", reference)
    normalized_tokens = [normalized(token) for token in tokens]
    result = []
    cursors: dict[int, int] = {}
    for record in records:
        part = int(record.get("source_part", 1))
        query = normalized(str(record.get("text", "")))
        query_words = query.split()
        cursor = cursors.get(part)
        search_start = max(0, (cursor or 0) - 8) if cursor is not None else 0
        search_end = min(
            len(tokens),
            (cursor + max(100, len(query_words) * 7))
            if cursor is not None else len(tokens))
        best = (0.0, search_start, search_start)
        minimum = max(1, len(query_words) - 4)
        maximum = len(query_words) + 6
        for start in range(search_start, search_end):
            for length in range(minimum, maximum + 1):
                end = start + length
                if end > search_end:
                    break
                candidate = " ".join(normalized_tokens[start:end])
                score = SequenceMatcher(None, query, candidate).ratio()
                if cursor is not None and start < cursor:
                    score -= min(0.12, (cursor - start) * 0.01)
                if score > best[0]:
                    best = (score, start, end)
        if best[0] < 0.72 and cursor is not None:
            for start in range(0, len(tokens)):
                for length in range(minimum, maximum + 1):
                    end = start + length
                    if end > len(tokens):
                        break
                    candidate = " ".join(normalized_tokens[start:end])
                    score = SequenceMatcher(None, query, candidate).ratio()
                    if score > best[0]:
                        best = (score, start, end)
        score, start, end = best
        corrected = " ".join(tokens[start:end]).strip()
        item = dict(record)
        item.update({
            "whisper_text": record.get("text", ""),
            "text": corrected if score >= 0.52 else record.get("text", ""),
            "alignment_score": round(score, 4),
            "requires_text_review": score < 0.72,
        })
        result.append(item)
        if score >= 0.52:
            cursors[part] = end
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--segments", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source = json.loads(Path(args.segments).read_text(encoding="utf-8"))
    reference = Path(args.reference).read_text(encoding="utf-8")
    records = align(list(source["segments"]), reference)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "segments": records, "count": len(records),
        "total_seconds": source.get("total_seconds", 0),
        "requires_text_review": sum(
            bool(item["requires_text_review"]) for item in records),
        "minimum_alignment_score": min(
            (item["alignment_score"] for item in records), default=0),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
