# Problem statement 
# ------------------------------------
# Given a year, a number of paid-leave (PTO) days, optional public holidays,
# and company days off, find the best set of vacation breaks that maximizes
# total days off. Weekends and provided holidays/company days do not consume PTO.
#
# Input format (JSON on stdin, one object):
# {
#   "numberOfDays": 10,
#   "year": 2026,
#   "holidays": [{"date": "2026-01-26", "name": "Republic Day"}],
#   "companyDaysOff": [{"date": "2026-02-14", "name": "Company Retreat"}]
# }
#
# Sample run:
# echo '{ "numberOfDays": 5, "year": 2026, "holidays":[{"date":"2026-01-26","name":"Republic Day"}] }' | python vacation_optimizer.py
#
# OR (from repo root)
#
# python3 vacation_optimizer.py <<'EOF'
# { "numberOfDays": 5, "year": 2026, "holidays":[{"date":"2026-01-26","name":"Republic Day"}] }
# EOF
#
# Output: A text report listing breaks, paid leave used, and dates.

import json
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from typing import List, Dict, Tuple


# -----------------------------
# Data models
# -----------------------------
@dataclass
class Day:
    date: str
    is_weekend: bool
    is_public_holiday: bool
    is_company_day: bool
    is_pto: bool = False
    is_part_of_break: bool = False


@dataclass
class Break:
    start_date: str
    end_date: str
    total_days: int
    pto_days: int
    weekends: int
    public_holidays: int
    company_days: int
    days: List[Day]


@dataclass
class Stats:
    total_days_off: int
    total_paid_leave: int
    total_public_holidays: int
    total_weekends: int
    total_company_days: int


@dataclass
class Result:
    days: List[Day]
    breaks: List[Break]
    stats: Stats


# -----------------------------
# Helpers
# -----------------------------
def format_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def add_days(d: date, n: int) -> date:
    return d + timedelta(days=n)


def build_calendar(params: Dict) -> List[Day]:
    yr = params.get("year") or date.today().year
    today = date.today()
    start = today if yr == today.year else date(yr, 1, 1)
    end = date(yr, 12, 31)

    holidays = {h["date"] for h in params.get("holidays", [])}
    company = {c["date"] for c in params.get("companyDaysOff", [])}

    days: List[Day] = []
    d = start
    while d <= end:
        ds = format_date(d)
        is_weekend = d.weekday() >= 5
        days.append(
            Day(
                date=ds,
                is_weekend=is_weekend,
                is_public_holiday=ds in holidays,
                is_company_day=ds in company,
            )
        )
        d = add_days(d, 1)
    return days


def is_fixed_off(day: Day) -> bool:
    return day.is_weekend or day.is_public_holiday or day.is_company_day


def generate_candidates(cal: List[Day], min_len: int, max_len: int) -> List[Dict]:
    candidates = []
    n = len(cal)
    for i in range(n):
        for L in range(min_len, max_len + 1):
            if i + L > n:
                break
            seg = cal[i : i + L]
            pto_used = sum(1 for d in seg if not is_fixed_off(d))
            if pto_used == 0:
                continue
            candidates.append(
                {
                    "start_idx": i,
                    "end_idx": i + L - 1,
                    "total_days": L,
                    "pto_used": pto_used,
                    "eff": L / pto_used,
                    "segment": seg,
                }
            )
    return candidates


def prune_candidates(cands: List[Dict], max_pto: int) -> List[Dict]:
    # remove those exceeding PTO
    cands = [c for c in cands if c["pto_used"] <= max_pto]
    # dominance: same start, prefer longer/less pto
    by_start: Dict[int, List[Dict]] = {}
    for c in cands:
        by_start.setdefault(c["start_idx"], []).append(c)

    pruned: List[Dict] = []
    for start, items in by_start.items():
        items.sort(key=lambda x: (x["pto_used"], -x["total_days"]))
        best = []
        for cand in items:
            if any(
                b["end_idx"] >= cand["end_idx"]
                and b["pto_used"] <= cand["pto_used"]
                and b["total_days"] >= cand["total_days"]
                for b in best
            ):
                continue
            best.append(cand)
        pruned.extend(best)
    pruned.sort(key=lambda x: x["start_idx"])
    return pruned


def binary_search_next(cands: List[Dict], start_pos: int) -> int:
    lo, hi = 0, len(cands)
    while lo < hi:
        mid = (lo + hi) // 2
        if cands[mid]["start_idx"] < start_pos:
            lo = mid + 1
        else:
            hi = mid
    return lo


def dp_select(cands: List[Dict], max_pto: int, spacing: int) -> List[Dict]:
    if not cands or max_pto <= 0:
        return []

    # Precompute next indices for spacing jump
    next_indices = [
        binary_search_next(cands, c["end_idx"] + 1 + spacing) for c in cands
    ]

    n = len(cands)
    # dp[idx][p] = (best_days, choice_list_of_indices)
    dp: List[List[Tuple[int, List[int]]]] = [
        [(0, []) for _ in range(max_pto + 1)] for _ in range(n + 1)
    ]

    for idx in range(n - 1, -1, -1):
        cand = cands[idx]
        pto_cost = cand["pto_used"]
        total_days = cand["total_days"]
        jump = next_indices[idx]
        for p in range(max_pto + 1):
            # Option 1: skip
            best_days, best_choice = dp[idx + 1][p]
            # Option 2: take
            if pto_cost <= p:
                take_days = total_days + dp[jump][p - pto_cost][0]
                if take_days > best_days:
                    best_days = take_days
                    best_choice = [idx] + dp[jump][p - pto_cost][1]
            dp[idx][p] = (best_days, best_choice)

    _, choice = dp[0][max_pto]
    return [cands[i] for i in choice]


def force_extend(cal: List[Day], breaks: List[Break], remaining: int) -> int:
    if remaining <= 0:
        return remaining
    for br in breaks:
        end_date = date.fromisoformat(br.end_date)
        next_day = add_days(end_date, 1)
        idx = next((i for i, d in enumerate(cal) if d.date == format_date(next_day)), None)
        if idx is not None and remaining > 0 and not cal[idx].is_part_of_break and not is_fixed_off(cal[idx]):
            cal[idx].is_part_of_break = True
            cal[idx].is_pto = True
            br.days.append(cal[idx])
            br.end_date = cal[idx].date
            br.total_days += 1
            br.pto_days += 1
            remaining -= 1
    return remaining


def add_forced_segments(cal: List[Day], remaining: int) -> List[Break]:
    forced: List[Break] = []
    i = 0
    n = len(cal)
    while i < n and remaining > 0:
        if cal[i].is_part_of_break or is_fixed_off(cal[i]):
            i += 1
            continue
        seg: List[Day] = []
        while i < n and remaining > 0 and not cal[i].is_part_of_break and not is_fixed_off(cal[i]):
            cal[i].is_part_of_break = True
            cal[i].is_pto = True
            seg.append(cal[i])
            remaining -= 1
            i += 1
        if seg:
            forced.append(
                Break(
                    start_date=seg[0].date,
                    end_date=seg[-1].date,
                    total_days=len(seg),
                    pto_days=len(seg),
                    weekends=sum(d.is_weekend for d in seg),
                    public_holidays=sum(d.is_public_holiday for d in seg),
                    company_days=sum(d.is_company_day for d in seg),
                    days=seg,
                )
            )
        i += 1
    return forced


def optimize(params: Dict) -> Result:
    max_pto = int(params["numberOfDays"])
    # Single, simple configuration: allow breaks between 3 and 15 days, spacing 7.
    min_len, max_len, spacing = 4, 9, 21

    cal = build_calendar(params)
    candidates = generate_candidates(cal, min_len, max_len)
    candidates = prune_candidates(candidates, max_pto)

    chosen = dp_select(candidates, max_pto, spacing)

    breaks: List[Break] = []
    for seg in chosen:
        for idx in range(seg["start_idx"], seg["end_idx"] + 1):
            cal[idx].is_part_of_break = True
            if not is_fixed_off(cal[idx]):
                cal[idx].is_pto = True
        segment_days = seg["segment"]
        breaks.append(
            Break(
                start_date=segment_days[0].date,
                end_date=segment_days[-1].date,
                total_days=seg["total_days"],
                pto_days=seg["pto_used"],
                weekends=sum(d.is_weekend for d in segment_days),
                public_holidays=sum(d.is_public_holiday for d in segment_days),
                company_days=sum(d.is_company_day for d in segment_days),
                days=list(segment_days),
            )
        )

    used_pto = sum(b.pto_days for b in breaks)
    remaining = max_pto - used_pto
    prev_remaining = remaining + 1
    while remaining > 0 and remaining < prev_remaining:
        prev_remaining = remaining
        remaining = force_extend(cal, breaks, remaining)
        extra = add_forced_segments(cal, remaining)
        breaks.extend(extra)
        used_pto = sum(b.pto_days for b in breaks)
        remaining = max_pto - used_pto

    stats = Stats(
        total_days_off=sum(b.total_days for b in breaks),
        total_paid_leave=sum(b.pto_days for b in breaks),
        total_public_holidays=sum(b.public_holidays for b in breaks),
        total_weekends=sum(b.weekends for b in breaks),
        total_company_days=sum(b.company_days for b in breaks),
    )

    return Result(days=cal, breaks=breaks, stats=stats)


# -----------------------------
# Reporting
# -----------------------------
def format_report(res: Result, params: Dict) -> str:
    lines: List[str] = []
    lines.append("Holiday Optimizer Report (Python)")
    lines.append("===============================")
    lines.append(f"Year: {params.get('year') or date.today().year}")
    lines.append(f"Requested Paid Leave Days: {params.get('numberOfDays')}")
    lines.append("")

    lines.append("Summary")
    lines.append("-------")
    lines.append(f"Total Days Off: {res.stats.total_days_off}")
    lines.append(f"Total Paid Leave Used: {res.stats.total_paid_leave}")
    lines.append(f"Public Holidays in Breaks: {res.stats.total_public_holidays}")
    lines.append(f"Weekends in Breaks: {res.stats.total_weekends}")
    if res.stats.total_company_days > 0:
        lines.append(f"Company Days in Breaks: {res.stats.total_company_days}")
    lines.append("")

    lines.append("Breaks")
    lines.append("------")
    if not res.breaks:
        lines.append("No breaks were scheduled.")
    else:
        for idx, br in enumerate(res.breaks, 1):
            company_part = f" | Company {br.company_days}" if br.company_days else ""
            lines.append(f"Break {idx}: {br.start_date} → {br.end_date}")
            lines.append(
                f"  • Total {br.total_days} days | Paid Leave {br.pto_days} | "
                f"Weekends {br.weekends} | Public {br.public_holidays}{company_part}"
            )
            pto_dates = [d.date for d in br.days if d.is_pto]
            if pto_dates:
                lines.append(f"  • Paid leave dates: {', '.join(pto_dates)}")
            lines.append("")

    pto_flat = [d.date for d in res.days if d.is_pto]
    lines.append("Paid Leave Dates (all)")
    lines.append("----------------------")
    lines.append(", ".join(pto_flat) if pto_flat else "None")

    return "\n".join(lines)


# -----------------------------
# Main
# -----------------------------
def main() -> None:
    try:
        raw = input().strip()
    except EOFError:
        raw = ""

    if raw:
        params = json.loads(raw)
    else:
        # Fallback sample
        params = {
            "numberOfDays": 5,
            "year": date.today().year,
            "holidays": [],
            "companyDaysOff": [],
        }

    result = optimize(params)
    print(format_report(result, params))


if __name__ == "__main__":
    main()