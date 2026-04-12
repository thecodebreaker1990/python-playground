import sqlite3
import random
import pandas as pd
import base64
from datetime import date

from typing import Any, TypeAlias
from IPython.display import HTML, display

ContractorRow: TypeAlias = tuple[int, str, str, str]
ContractorList: TypeAlias = list[ContractorRow]


# ================================
# Contractor generation
# ================================

CONTRACTOR_NAMES = [
    "Acme Industrial Solutions", "Globex International", "Cyberdyne Systems",
    "Apex Heavy Industries", "Sinergy Managed Services", "Titan Engineering Group",
    "Vanguard Construction Co.", "Meridian Logistics", "Ironclad Safety Services",
    "Pinnacle Drilling Corp.", "Atlas Mechanical Works", "Horizon Energy Partners",
    "Redstone Infrastructure", "Summit Crane Services", "Northwind Fabrication",
    "Cobalt Mining Solutions", "Steelbridge Contractors", "Trident Marine Services",
    "Falcon Electrical Systems", "Keystone Pipeline Co.", "Orion Scaffolding Ltd.",
    "Blackrock Demolition", "Silverline Maintenance", "Centurion Fire Protection",
    "Quantum Environmental", "Patriot Welding Services", "Evergreen Remediation",
    "Nexus Industrial Cleaning", "Fortis Structural Engineering", "Omega Insulation Group",
    "Crestline Roofing Co.", "Bedrock Civil Works", "Sapphire HVAC Solutions",
    "Ironforge Heavy Lift", "Cascade Water Systems", "Vertex Telecom Installations",
    "Granite Paving Corp.", "Blueshift Automation", "Rampart Security Fencing",
    "Solaris Solar Installations",
]

SIZE_TIERS = ["small", "medium", "large"]
INDUSTRIES = [
    "construction", "mining", "oil_and_gas", "manufacturing",
    "logistics", "energy", "marine", "environmental",
]

# Hours-per-month baseline by size tier
_TIER_HOURS = {"small": (200, 600), "medium": (800, 1600), "large": (1800, 3000)}


def generate_contractors(
    n: int = 40, rng: random.Random | None = None
) -> ContractorList:
    """Return list of (id, name, size_tier, industry) tuples."""
    if rng is None:
        rng = random.Random(42)

    names = list(CONTRACTOR_NAMES)
    rng.shuffle(names)
    names = names[:n]

    catalog: ContractorList = []
    for cid, name in enumerate(names, start=1):
        tier = rng.choices(SIZE_TIERS, weights=[0.4, 0.35, 0.25], k=1)[0]
        industry = rng.choice(INDUSTRIES)
        catalog.append((cid, name, tier, industry))
    return catalog


# ================================
# Database creation
# ================================

def _generate_months(start: date, end: date) -> list[str]:
    """Return list of 'YYYY-MM' strings from start to end (inclusive of partial months)."""
    months: list[str] = []
    cur = start.replace(day=1)
    while cur <= end:
        months.append(cur.strftime("%Y-%m"))
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)
    return months


def create_risk_db(
    db_name: str = "risk_operations.db",
    n_contractors: int = 40,
    start_date: date = date(2026, 1, 1),
    end_date: date = date(2026, 3, 15),
) -> None:
    """
    Create an SQLite DB with:
      - contractors  (master list)
      - monthly_reports (one row per contractor per month)
    """
    rng = random.Random(42)
    conn = sqlite3.connect(db_name)
    cur = conn.cursor()

    # Reset tables
    cur.execute("DROP TABLE IF EXISTS monthly_reports")
    cur.execute("DROP TABLE IF EXISTS contractors")

    cur.execute("""
    CREATE TABLE contractors (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        size_tier TEXT NOT NULL,      -- 'small' | 'medium' | 'large'
        industry TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE monthly_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contractor_id INTEGER NOT NULL,
        month TEXT NOT NULL,           -- 'YYYY-MM'
        hours INTEGER NOT NULL DEFAULT 0,
        operated INTEGER NOT NULL DEFAULT 0,   -- 1/0 flag
        recordables INTEGER NOT NULL DEFAULT 0,
        lti INTEGER NOT NULL DEFAULT 0,
        hipo INTEGER NOT NULL DEFAULT 0,
        actions_open INTEGER NOT NULL DEFAULT 0,
        actions_closed INTEGER NOT NULL DEFAULT 0,
        actions_overdue INTEGER NOT NULL DEFAULT 0,
        critical_overdue INTEGER NOT NULL DEFAULT 0,
        exec_walks INTEGER NOT NULL DEFAULT 0,
        exec_crit_findings INTEGER NOT NULL DEFAULT 0,
        monthly_close_submitted INTEGER NOT NULL DEFAULT 0,  -- 1/0
        rejected_reports INTEGER NOT NULL DEFAULT 0,
        docs_blocked INTEGER NOT NULL DEFAULT 0,
        docs_at_risk INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (contractor_id) REFERENCES contractors(id),
        UNIQUE(contractor_id, month)
    )
    """)

    # Insert contractors
    contractors = generate_contractors(n=n_contractors, rng=rng)
    cur.executemany(
        "INSERT INTO contractors (id, name, size_tier, industry) VALUES (?, ?, ?, ?)",
        contractors,
    )
    print(f"Inserted {len(contractors)} contractors.")

    # Generate monthly reports
    months = _generate_months(start_date, end_date)
    row_count = 0

    for cid, name, tier, industry in contractors:
        lo, hi = _TIER_HOURS[tier]

        for month_str in months:
            # ~5% chance a small contractor didn't operate that month
            not_operated = tier == "small" and rng.random() < 0.05
            if not_operated:
                hours = 0
                operated = 0
            else:
                hours = rng.randint(lo, hi)
                operated = 1

            # Safety incidents scale with hours
            hour_factor = hours / 2000 if hours else 0
            recordables = _poisson(rng, 0.3 * hour_factor)
            lti = _poisson(rng, 0.1 * hour_factor) if recordables else 0
            hipo = _poisson(rng, 0.15 * hour_factor)

            # Actions
            actions_open = rng.randint(4, int(10 + 20 * hour_factor))
            actions_closed = rng.randint(
                max(0, actions_open - rng.randint(2, 8)), actions_open
            )
            actions_overdue = rng.randint(0, max(1, actions_open - actions_closed + 2))
            critical_overdue = rng.randint(0, max(0, actions_overdue))

            # Executive walks & findings
            exec_walks = rng.randint(0, 3) if operated else 0
            exec_crit_findings = rng.randint(0, min(3, exec_walks + 1)) if exec_walks else 0

            # Compliance
            monthly_close_submitted = 1 if rng.random() > 0.08 else 0
            rejected_reports = rng.randint(0, 2) if monthly_close_submitted else 0
            docs_blocked = 1 if rng.random() < 0.10 else 0
            docs_at_risk = 1 if rng.random() < 0.15 else 0

            cur.execute(
                """INSERT INTO monthly_reports (
                    contractor_id, month, hours, operated,
                    recordables, lti, hipo,
                    actions_open, actions_closed, actions_overdue, critical_overdue,
                    exec_walks, exec_crit_findings,
                    monthly_close_submitted, rejected_reports,
                    docs_blocked, docs_at_risk
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    cid, month_str, hours, operated,
                    recordables, lti, hipo,
                    actions_open, actions_closed, actions_overdue, critical_overdue,
                    exec_walks, exec_crit_findings,
                    monthly_close_submitted, rejected_reports,
                    docs_blocked, docs_at_risk,
                ),
            )
            row_count += 1

    conn.commit()
    conn.close()
    print(f"Created '{db_name}' with {row_count} monthly report rows across {len(months)} months.")


def _poisson(rng: random.Random, lam: float) -> int:
    """Simple Poisson-ish draw using the inverse-transform method."""
    import math
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p < L:
            return k - 1


# ================================
# Query helpers
# ================================

def get_schema(db_path: str = "risk_operations.db") -> str:
    """Return the schema of both tables for agent/LLM consumption."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    lines = []
    for table in ("contractors", "monthly_reports"):
        cur.execute(f"PRAGMA table_info({table})")
        rows = cur.fetchall()
        lines.append(f"table: {table}")
        lines.extend(f"  {r[1]} ({r[2]})" for r in rows)
        lines.append("")
    conn.close()
    return "\n".join(lines)


def execute_sql(query: str, db_path: str = "risk_operations.db") -> pd.DataFrame:
    """Execute a SELECT query and return a DataFrame."""
    q = query.strip().removeprefix("```sql").removesuffix("```").strip()
    conn = sqlite3.connect(db_path)
    try:
        return pd.read_sql_query(q, conn)
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})
    finally:
        conn.close()


def build_contractors_monthly_left_join_query() -> str:
    """
    Return the default LEFT JOIN used to orchestrate notebook scoring input.

    The shape intentionally mirrors the CSV input fields expected by the
    HSE scoring pipeline, while preserving contractor master data as extras.
    """
    return """
    SELECT
        c.id AS contractor_id,
        c.name AS contractor,
        c.size_tier,
        c.industry,
        COALESCE(mr.month, '') AS month,
        COALESCE(mr.hours, 0) AS hours,
        COALESCE(mr.operated, 0) AS operated,
        COALESCE(mr.recordables, 0) AS recordables,
        COALESCE(mr.lti, 0) AS lti,
        COALESCE(mr.hipo, 0) AS hipo,
        COALESCE(mr.actions_open, 0) AS actions_open,
        COALESCE(mr.actions_closed, 0) AS actions_closed,
        COALESCE(mr.actions_overdue, 0) AS actions_overdue,
        COALESCE(mr.critical_overdue, 0) AS critical_overdue,
        COALESCE(mr.exec_walks, 0) AS exec_walks,
        COALESCE(mr.exec_crit_findings, 0) AS exec_crit_findings,
        COALESCE(mr.monthly_close_submitted, 0) AS monthly_close_submitted,
        COALESCE(mr.rejected_reports, 0) AS rejected_reports,
        COALESCE(mr.docs_blocked, 0) AS docs_blocked,
        COALESCE(mr.docs_at_risk, 0) AS docs_at_risk
    FROM contractors AS c
    LEFT JOIN monthly_reports AS mr
        ON mr.contractor_id = c.id
    ORDER BY c.name, mr.month
    """


def fetch_csv_like_monthly_rows(
    db_path: str = "risk_operations.db",
    query: str | None = None,
) -> list[dict[str, Any]]:
    """
    Return left-joined contractor/monthly-report rows as CSV-like dictionaries.

    This is the notebook-friendly structure to pass into `rows_from_dicts()`.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(query or build_contractors_monthly_left_join_query())
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


# ================================
# Utility function
# ================================
def print_html(content: Any, title: str | None = None, is_image: bool = False):
    """
    Pretty-print inside a styled card.
    - If is_image=True and content is a string: treat as image path/URL and render <img>.
    - If content is a pandas DataFrame/Series: render as an HTML table.
    - Otherwise (strings/otros): show as code/text in <pre><code>.
    """
    try:
        from html import escape as _escape
    except ImportError:
        _escape = lambda x: x

    def image_to_base64(image_path: str) -> str:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")

    # Render content
    if is_image and isinstance(content, str):
        b64 = image_to_base64(content)
        rendered = f'<img src="data:image/png;base64,{b64}" alt="Image" style="max-width:100%; height:auto; border-radius:8px;">'
    elif isinstance(content, pd.DataFrame):
        rendered = content.to_html(classes="pretty-table", index=False, border=0, escape=False)
    elif isinstance(content, pd.Series):
        rendered = content.to_frame().to_html(classes="pretty-table", border=0, escape=False)
    elif isinstance(content, str):
        rendered = f"<pre><code>{_escape(content)}</code></pre>"
    else:
        rendered = f"<pre><code>{_escape(str(content))}</code></pre>"

    css = """
    <style>
    .pretty-card{
      font-family: ui-sans-serif, system-ui;
      border: 2px solid transparent;
      border-radius: 14px;
      padding: 14px 16px;
      margin: 10px 0;
      background: linear-gradient(#fff, #fff) padding-box,
                  linear-gradient(135deg, #3b82f6, #9333ea) border-box;
      color: #111;
      box-shadow: 0 4px 12px rgba(0,0,0,.08);
    }
    .pretty-title{
      font-weight:700;
      margin-bottom:8px;
      font-size:14px;
      color:#111;
    }
    .pretty-card pre, 
    .pretty-card code {
      background: #f3f4f6;
      color: #111;
      padding: 8px;
      border-radius: 8px;
      display: block;
      overflow-x: auto;
      font-size: 13px;
      white-space: pre-wrap;
    }
    .pretty-card img { max-width: 100%; height: auto; border-radius: 8px; }
    .pretty-card table.pretty-table {
      border-collapse: collapse;
      width: 100%;
      font-size: 13px;
      color: #111;
    }
    .pretty-card table.pretty-table th, 
    .pretty-card table.pretty-table td {
      border: 1px solid #e5e7eb;
      padding: 6px 8px;
      text-align: left;
    }
    .pretty-card table.pretty-table th { background: #f9fafb; font-weight: 600; }
    </style>
    """

    title_html = f'<div class="pretty-title">{title}</div>' if title else ""
    card = f'<div class="pretty-card">{title_html}{rendered}</div>'
    display(HTML(css + card))
