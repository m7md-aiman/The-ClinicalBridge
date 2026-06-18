"""CLI: generate the simulated ClinicalBridge dataset.

Usage:
    python scripts/generate_dataset.py            # writes to ./data
    python scripts/generate_dataset.py --summary  # also print a patient summary table

All data is fictional and machine-generated. Re-running overwrites with identical content.
"""

from __future__ import annotations

import argparse

from clinicalbridge.config import settings
from clinicalbridge.datagen import build_all, manifest, write_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the simulated dataset.")
    parser.add_argument("--summary", action="store_true", help="Print a patient summary table.")
    args = parser.parse_args()

    result = write_dataset()
    print(f"[OK] Wrote {result['patients']} patients and {result['rpm_readings']} RPM readings "
          f"to {settings.data_dir}")
    print(f"     EHR:       {settings.ehr_dir}")
    print(f"     RPM:       {settings.rpm_dir}")
    print(f"     Anamnesis: {settings.anamnesis_dir}")
    print(f"     Manifest:  {settings.data_dir / 'patients.json'}")

    if args.summary:
        rows = manifest(build_all())
        print("\nPatient summary")
        print("-" * 78)
        print(f"{'ID':<8}{'Name':<20}{'Age':<5}{'Sex':<8}Conditions")
        print("-" * 78)
        for r in rows:
            conds = ", ".join(c.split(" (")[0] for c in r["conditions"]) or "(none recorded)"
            print(f"{r['patient_id']:<8}{r['name']:<20}{r['age']:<5}{r['sex']:<8}{conds}")


if __name__ == "__main__":
    main()
