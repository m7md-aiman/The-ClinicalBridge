"""CLI: write the five clinical scenarios (alert + gold-standard CCB + rubric) to data/scenarios/.

Usage:
    python scripts/generate_scenarios.py
"""

from __future__ import annotations

from clinicalbridge.config import settings
from clinicalbridge.scenarios import build_scenarios, write_scenarios


def main() -> None:
    count = write_scenarios()
    print(f"[OK] Wrote {count} scenarios to {settings.scenarios_dir}")
    for s in build_scenarios():
        print(f"     - {s.id:<22} {s.title:<24} [{s.expected_urgency.value:<13}] patient {s.patient_id}")


if __name__ == "__main__":
    main()
