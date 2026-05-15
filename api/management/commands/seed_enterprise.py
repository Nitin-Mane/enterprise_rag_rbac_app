import csv
import json
import sqlite3
import textwrap
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from api.models import DataSource, EnterpriseUser, QueryAudit
from api.services.ingestion import ingest_all_sources


USERS = [
    ("aisha", "Aisha Raman", "security", "Security Analyst", 3),
    ("marco", "Marco Singh", "finance", "Finance Manager", 3),
    ("elen", "Elen Carter", "operations", "Ops Lead", 2),
    ("nora", "Nora Li", "compliance", "Compliance Officer", 4),
    ("devon", "Devon Brooks", "engineering", "Platform Engineer", 2),
    ("sam", "Sam Rivera", "hr", "HR Partner", 1),
]


SOURCES = [
    {
        "source_id": "SEC-IR-2026-04",
        "title": "April Security Incident Review",
        "source_type": "pdf",
        "path": "enterprise_data/security/april_incident_review.pdf",
        "departments": ["security", "compliance"],
        "allowed_roles": ["Security Analyst", "Compliance Officer"],
        "min_clearance": 3,
        "sensitivity": "restricted",
        "description": "security incident audit alert token risk",
    },
    {
        "source_id": "FIN-VENDOR-Q1",
        "title": "Q1 Vendor Spend Register",
        "source_type": "csv",
        "path": "enterprise_data/finance/vendor_spend_q1.csv",
        "departments": ["finance", "compliance"],
        "allowed_roles": ["Finance Manager", "Compliance Officer"],
        "min_clearance": 3,
        "sensitivity": "confidential",
        "description": "finance revenue cost invoice vendor budget",
    },
    {
        "source_id": "OPS-SLA-BOARD",
        "title": "Operations SLA Board",
        "source_type": "json",
        "path": "enterprise_data/operations/sla_board.json",
        "departments": ["operations", "engineering"],
        "allowed_roles": ["Ops Lead", "Platform Engineer"],
        "min_clearance": 2,
        "sensitivity": "internal",
        "description": "operations sla ticket outage capacity latency",
    },
    {
        "source_id": "COMP-SOX-2026",
        "title": "SOX Control Evidence Notes",
        "source_type": "txt",
        "path": "enterprise_data/compliance/sox_control_notes.txt",
        "departments": ["compliance"],
        "allowed_roles": ["Compliance Officer"],
        "min_clearance": 4,
        "sensitivity": "restricted",
        "description": "compliance sox control retention finding audit",
    },
    {
        "source_id": "ENG-ARCH-LEDGER",
        "title": "Platform Architecture Ledger",
        "source_type": "pdf",
        "path": "enterprise_data/engineering/platform_architecture_ledger.pdf",
        "departments": ["engineering", "operations"],
        "allowed_roles": ["Platform Engineer", "Ops Lead"],
        "min_clearance": 2,
        "sensitivity": "internal",
        "description": "engineering api deployment schema database service",
    },
    {
        "source_id": "OPS-ASSET-SQL",
        "title": "Warehouse Asset SQLite Dump",
        "source_type": "sql",
        "path": "enterprise_data/operations/warehouse_assets.sqlite",
        "departments": ["operations", "finance"],
        "allowed_roles": ["Ops Lead", "Finance Manager"],
        "min_clearance": 2,
        "sensitivity": "internal",
        "description": "operations warehouse asset cost capacity database",
    },
]


def write_pdf(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    y = height - 72
    doc.setFont("Helvetica-Bold", 14)
    doc.drawString(72, y, lines[0])
    y -= 32
    doc.setFont("Helvetica", 10)
    for line in lines[1:]:
        wrapped_lines = textwrap.wrap(line, width=96) or [""]
        for wrapped_line in wrapped_lines:
            if y < 72:
                doc.showPage()
                doc.setFont("Helvetica", 10)
                y = height - 72
            doc.drawString(72, y, wrapped_line)
            y -= 18
        y -= 4
    doc.save()


def create_files(base):
    write_pdf(
        base / "security/april_incident_review.pdf",
        [
            "April Security Incident Review",
            "Incident SEC-447 involved anomalous API token reuse from a decommissioned integration host.",
            "The event began at 02:14 UTC and was contained by rotating service tokens and disabling legacy VPN ingress.",
            "Root cause: stale automation credential retained after vendor offboarding.",
            "Customer data exposure was not observed. Evidence came from IAM logs, WAF telemetry, and SIEM correlation rules.",
            "Corrective actions: enforce 30 day credential attestations, block unmanaged service principals, and add token age alerts.",
        ],
    )
    write_pdf(
        base / "engineering/platform_architecture_ledger.pdf",
        [
            "Platform Architecture Ledger",
            "The customer intelligence API uses read replicas for analytics queries and isolates write paths behind queue workers.",
            "Deployment policy requires canary release, schema compatibility checks, and rollback verification before promotion.",
            "Known risk: the reporting service still depends on a shared Redis namespace used by the operations dashboard.",
            "Recommended fix: split cache namespaces and add contract tests for report export jobs.",
        ],
    )

    finance_dir = base / "finance"
    finance_dir.mkdir(parents=True, exist_ok=True)
    with open(finance_dir / "vendor_spend_q1.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["vendor", "category", "quarter", "spend_usd", "owner", "risk"])
        writer.writeheader()
        writer.writerows(
            [
                {"vendor": "Northstar Cloud", "category": "compute", "quarter": "Q1", "spend_usd": "184200", "owner": "Platform", "risk": "medium"},
                {"vendor": "BluePeak Advisory", "category": "audit", "quarter": "Q1", "spend_usd": "47200", "owner": "Compliance", "risk": "low"},
                {"vendor": "VectorGrid Logistics", "category": "warehouse", "quarter": "Q1", "spend_usd": "98100", "owner": "Operations", "risk": "high"},
            ]
        )

    operations_dir = base / "operations"
    operations_dir.mkdir(parents=True, exist_ok=True)
    (operations_dir / "sla_board.json").write_text(
        json.dumps(
            [
                {"service": "Order Gateway", "sla": "99.95", "current": "99.91", "status": "watch", "reason": "two regional latency spikes"},
                {"service": "Inventory Sync", "sla": "99.50", "current": "99.72", "status": "green", "reason": "queue depth normalized"},
                {"service": "Returns Portal", "sla": "99.70", "current": "99.61", "status": "breach-risk", "reason": "database lock contention"},
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    compliance_dir = base / "compliance"
    compliance_dir.mkdir(parents=True, exist_ok=True)
    (compliance_dir / "sox_control_notes.txt").write_text(
        "SOX Control Evidence Notes\n"
        "Control FIN-17 requires monthly reconciliation between procurement approvals and payment release logs.\n"
        "March evidence passed with one management review delay. April evidence is pending two approvals.\n"
        "Retention policy requires seven years for signed control evidence and immutable audit trail exports.\n"
        "Open finding: approval delegation was not consistently recorded for emergency vendor onboarding.\n",
        encoding="utf-8",
    )

    sqlite_path = operations_dir / "warehouse_assets.sqlite"
    if sqlite_path.exists():
        sqlite_path.unlink()
    connection = sqlite3.connect(sqlite_path)
    try:
        cursor = connection.cursor()
        cursor.execute("CREATE TABLE assets (asset_id TEXT, site TEXT, owner TEXT, status TEXT, annual_cost INTEGER)")
        cursor.executemany(
            "INSERT INTO assets VALUES (?, ?, ?, ?, ?)",
            [
                ("FLT-103", "Dallas", "Operations", "maintenance due", 12400),
                ("RBT-221", "Phoenix", "Operations", "active", 38200),
                ("SEN-884", "Reno", "Facilities", "retire", 2200),
            ],
        )
        connection.commit()
    finally:
        connection.close()


class Command(BaseCommand):
    help = "Create synthetic enterprise data, RBAC metadata, and searchable chunks."

    def handle(self, *args, **options):
        data_root = Path(settings.RAG_DATA_PATH)
        create_files(data_root)

        QueryAudit.objects.all().delete()
        EnterpriseUser.objects.all().delete()
        for username, display_name, department, role, clearance in USERS:
            EnterpriseUser.objects.create(
                username=username,
                display_name=display_name,
                department=department,
                role=role,
                clearance=clearance,
            )

        DataSource.objects.all().delete()
        for source in SOURCES:
            DataSource.objects.create(**source)

        chunks = ingest_all_sources()
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(USERS)} users, {len(SOURCES)} sources, and {chunks} chunks."))
