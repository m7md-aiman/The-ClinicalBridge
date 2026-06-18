"""Deterministic generator for the simulated ClinicalBridge dataset.

ALL DATA IS FICTIONAL AND MACHINE-GENERATED. No real patient information is used.

Produces 12 internally-consistent fictional patients, each with three components reflecting the
three data sources at the heart of the Clinical Context Gap:

- **EHR**  — document-oriented record (problems w/ ICD-10, meds, labs, notes, allergies)
- **RPM**  — numeric time-series of vitals with baselines + thresholds
- **Anamnesis** — narrative + semi-structured self-report (HPI, ROS, social/family hx, diary)

Patients PT-001..PT-005 are purpose-built to drive the five required clinical scenarios
(see Phase 5). PT-006..PT-012 add realistic breadth so the EHR retriever must discriminate
between patients.

Generation is seeded, so re-running yields byte-identical output (important for reproducible
evaluation). Time-series are anchored to a fixed "now" so scenario alerts line up with the data.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from clinicalbridge.config import settings

SEED = 20260513                     # project date → reproducible RNG
NOW = datetime(2026, 6, 1, 8, 0)    # anchor for RPM time-series and "current" alerts
DAYS = 30                            # days of daily RPM readings per vital


# ---------------------------------------------------------------------------
# Time-series helpers
# ---------------------------------------------------------------------------


def _series(
    rng: random.Random,
    n: int,
    base: float,
    noise: float,
    drift: float = 0.0,
    event_day: int | None = None,
    overrides: dict[int, float] | None = None,
    ndigits: int = 1,
) -> list[float]:
    """Generate ``n`` daily values around ``base`` with Gaussian ``noise``.

    ``drift`` is per-day; if ``event_day`` is set the drift only applies *after* that day
    (modelling a change such as stopping a medication). ``overrides`` force specific indices.
    """
    values: list[float] = []
    for i in range(n):
        elapsed = i if event_day is None else max(0, i - event_day)
        value = base + drift * elapsed + rng.gauss(0, noise)
        values.append(round(value, ndigits))
    for idx, val in (overrides or {}).items():
        values[idx] = val
    return values


def _build_rpm(profile: dict, rng: random.Random) -> dict:
    vitals_meta: list[dict] = []
    readings: list[dict] = []

    for v in profile["rpm"]:
        primary = _series(
            rng, DAYS, v["base"], v.get("noise", 2.0), v.get("drift", 0.0),
            v.get("event_day"), v.get("overrides"), v.get("ndigits", 1),
        )
        secondary = None
        if "base2" in v:
            secondary = _series(
                rng, DAYS, v["base2"], v.get("noise2", 2.0), v.get("drift2", 0.0),
                v.get("event_day"), v.get("overrides2"), v.get("ndigits", 1),
            )

        for i in range(DAYS):
            ts = NOW - timedelta(days=(DAYS - 1 - i))
            reading = {
                "timestamp": ts.isoformat(timespec="minutes"),
                "vital_type": v["vital_type"],
                "value": primary[i],
                "unit": v["unit"],
            }
            if secondary is not None:
                reading["value_secondary"] = secondary[i]
            readings.append(reading)

        vitals_meta.append({
            "vital_type": v["vital_type"],
            "unit": v["unit"],
            "device": v.get("device", "generic monitor"),
            "baseline": v.get("baseline", round(v["base"], 1)),
            "threshold_low": v.get("low"),
            "threshold_high": v.get("high"),
        })

    return {
        "patient_id": profile["id"],
        "monitoring_start": (NOW - timedelta(days=DAYS - 1)).date().isoformat(),
        "monitoring_end": NOW.date().isoformat(),
        "reading_frequency": "daily",
        "vitals": vitals_meta,
        "readings": readings,
    }


def _build_ehr(profile: dict) -> dict:
    e = profile["ehr"]
    return {
        "patient_id": profile["id"],
        "name": profile["name"],
        "date_of_birth": e["dob"],
        "age": e["age"],
        "sex": e["sex"],
        "mrn": f"MRN-{profile['id'][-3:]}",
        "problem_list": e.get("problems", []),
        "medications": e.get("medications", []),
        "allergies": e.get("allergies", []),
        "lab_results": e.get("labs", []),
        "visit_notes": e.get("notes", []),
        "record_completeness": e.get("completeness", "complete"),
    }


def _build_anamnesis(profile: dict) -> dict:
    a = profile["anamnesis"]
    return {
        "patient_id": profile["id"],
        "intake_date": a.get("intake_date", "2026-05-28"),
        "chief_complaint": a.get("chief_complaint", ""),
        "history_of_present_illness": a.get("hpi", ""),
        "review_of_systems": a.get("ros", {}),
        "social_history": a.get("social", {}),
        "family_history": a.get("family", []),
        "medication_adherence": a.get("adherence", []),
        "symptom_diary": a.get("diary", []),
        "patient_concerns": a.get("concerns", []),
        "sensitive_notes": a.get("sensitive", []),
    }


def build_patient(profile: dict, rng: random.Random) -> dict:
    return {
        "ehr": _build_ehr(profile),
        "rpm": _build_rpm(profile, rng),
        "anamnesis": _build_anamnesis(profile),
    }


def build_all() -> dict[str, dict]:
    """Build every patient deterministically. Returns ``{patient_id: {ehr, rpm, anamnesis}}``."""
    rng = random.Random(SEED)
    return {p["id"]: build_patient(p, rng) for p in CATALOG}


def manifest(dataset: dict[str, dict]) -> list[dict]:
    rows = []
    for pid, parts in dataset.items():
        ehr = parts["ehr"]
        rows.append({
            "patient_id": pid,
            "name": ehr["name"],
            "age": ehr["age"],
            "sex": ehr["sex"],
            "conditions": [p["condition"] for p in ehr["problem_list"]],
            "monitored_vitals": [v["vital_type"] for v in parts["rpm"]["vitals"]],
            "record_completeness": ehr["record_completeness"],
        })
    return rows


def write_dataset(out_root: Path | None = None) -> dict[str, int]:
    """Generate and write all files. Returns a small summary of counts."""
    root = out_root or settings.data_dir
    dataset = build_all()
    for sub in ("ehr", "rpm", "anamnesis"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    for pid, parts in dataset.items():
        (root / "ehr" / f"{pid}.json").write_text(
            json.dumps(parts["ehr"], indent=2), encoding="utf-8")
        (root / "rpm" / f"{pid}.json").write_text(
            json.dumps(parts["rpm"], indent=2), encoding="utf-8")
        (root / "anamnesis" / f"{pid}.json").write_text(
            json.dumps(parts["anamnesis"], indent=2), encoding="utf-8")

    (root / "patients.json").write_text(
        json.dumps(manifest(dataset), indent=2), encoding="utf-8")

    total_readings = sum(len(p["rpm"]["readings"]) for p in dataset.values())
    return {"patients": len(dataset), "rpm_readings": total_readings}


# ---------------------------------------------------------------------------
# Patient catalog (curated, clinically plausible, internally consistent)
# ---------------------------------------------------------------------------

CATALOG: list[dict] = [
    # ===================================================================
    # PT-001 — Scenario 1: "The Missed Medication"
    # Hypertensive who stopped his ACE inhibitor due to a cough → BP climbs.
    # ===================================================================
    {
        "id": "PT-001",
        "name": "Harold Whitfield",
        "ehr": {
            "dob": "1958-02-14", "age": 68, "sex": "male", "completeness": "complete",
            "problems": [
                {"condition": "Essential hypertension", "icd10": "I10",
                 "status": "active", "onset_date": "2016-04-10"},
                {"condition": "Hyperlipidemia", "icd10": "E78.5",
                 "status": "active", "onset_date": "2017-09-02"},
            ],
            "medications": [
                {"name": "Lisinopril", "dose": "10 mg", "frequency": "once daily",
                 "started": "2016-04-10", "status": "active"},
                {"name": "Atorvastatin", "dose": "20 mg", "frequency": "once daily at night",
                 "started": "2017-09-02", "status": "active"},
            ],
            "allergies": [{"substance": "Penicillin", "reaction": "rash", "severity": "moderate"}],
            "labs": [
                {"test": "Potassium", "value": "4.2", "unit": "mmol/L",
                 "reference_range": "3.5-5.1", "date": "2026-03-15", "flag": "normal"},
                {"test": "Creatinine", "value": "1.0", "unit": "mg/dL",
                 "reference_range": "0.7-1.3", "date": "2026-03-15", "flag": "normal"},
                {"test": "LDL cholesterol", "value": "98", "unit": "mg/dL",
                 "reference_range": "<100", "date": "2026-03-15", "flag": "normal"},
            ],
            "notes": [
                {"date": "2026-03-15", "author": "Dr. Patel", "specialty": "Primary Care",
                 "note": "68M with HTN and hyperlipidemia, well controlled on lisinopril 10mg "
                         "and atorvastatin. Home BP log averaging 126/80. Continue current "
                         "regimen. No complaints today. RTC 6 months."},
            ],
        },
        "rpm": [
            {"vital_type": "blood_pressure", "unit": "mmHg", "device": "Omron BP cuff",
             "base": 126, "noise": 4, "drift": 3.6, "event_day": 16, "baseline": 126, "high": 140, "low": 90,
             "base2": 80, "noise2": 3, "drift2": 1.7},
        ],
        "anamnesis": {
            "intake_date": "2026-05-30",
            "chief_complaint": "High blood pressure readings at home.",
            "hpi": "Mr. Whitfield reports his home blood pressure has been 'creeping up' over the "
                   "last two weeks. About two weeks ago he stopped taking his blood pressure pill "
                   "because he developed 'an annoying dry tickle in my throat' and a persistent "
                   "dry cough that kept him up at night. He read online that the cough could be "
                   "from the pill, so he quit it on his own and did not tell anyone. He continues "
                   "his cholesterol medication.",
            "ros": {"cardiovascular": "Denies chest pain, palpitations, leg swelling.",
                    "respiratory": "Persistent dry cough for ~3 weeks, no sputum, no fever.",
                    "neurological": "No headache, no vision changes, no weakness."},
            "social": {"smoking": "Former smoker, quit 2005", "alcohol": "1-2 beers/week",
                       "diet": "Adds salt to most meals", "exercise": "Walks dog 20 min/day",
                       "occupation": "Retired postal worker", "living_situation": "Lives with spouse"},
            "family": ["Father: stroke at 70", "Mother: hypertension"],
            "adherence": [
                {"medication": "Lisinopril", "reported_status": "non_adherent",
                 "detail": "Self-discontinued ~2 weeks ago due to dry cough."},
                {"medication": "Atorvastatin", "reported_status": "adherent",
                 "detail": "Takes nightly as prescribed."},
            ],
            "diary": [
                {"date": "2026-05-20", "entry": "That tickly cough is back again at night. Stopped the little white pill to see if it helps."},
                {"date": "2026-05-27", "entry": "Cough a bit better but my home monitor said 168 over 100. Felt fine though."},
                {"date": "2026-05-31", "entry": "Monitor read 176/103 this morning. No headache. Should I worry?"},
            ],
            "concerns": ["Worried the cough means something serious.",
                         "Wants to know if there is a BP medicine that won't cause a cough."],
        },
    },

    # ===================================================================
    # PT-002 — Scenario 2: "The False Alarm"
    # Diabetic glucose spike that is contextually benign (planned diet change + recent med change).
    # ===================================================================
    {
        "id": "PT-002",
        "name": "Maria Delgado",
        "ehr": {
            "dob": "1972-07-21", "age": 53, "sex": "female", "completeness": "complete",
            "problems": [
                {"condition": "Type 2 diabetes mellitus without complications", "icd10": "E11.9",
                 "status": "active", "onset_date": "2019-01-15"},
                {"condition": "Obesity", "icd10": "E66.9", "status": "active", "onset_date": "2018-06-01"},
            ],
            "medications": [
                {"name": "Metformin", "dose": "1000 mg", "frequency": "twice daily",
                 "started": "2019-01-15", "status": "active"},
                {"name": "Empagliflozin", "dose": "10 mg", "frequency": "once daily",
                 "started": "2026-05-12", "status": "active"},
            ],
            "allergies": [],
            "labs": [
                {"test": "Hemoglobin A1c", "value": "7.4", "unit": "%",
                 "reference_range": "<7.0", "date": "2026-05-10", "flag": "high"},
                {"test": "Hemoglobin A1c", "value": "7.9", "unit": "%",
                 "reference_range": "<7.0", "date": "2025-11-08", "flag": "high"},
                {"test": "Creatinine", "value": "0.8", "unit": "mg/dL",
                 "reference_range": "0.6-1.1", "date": "2026-05-10", "flag": "normal"},
            ],
            "notes": [
                {"date": "2026-05-12", "author": "Dr. Nguyen", "specialty": "Endocrinology",
                 "note": "53F with T2DM, A1c 7.4 improving. Added empagliflozin 10mg to metformin. "
                         "Counseled that glucose may fluctuate as body adjusts to new agent and to "
                         "any dietary changes. Patient motivated, starting a low-carb diet."},
            ],
        },
        "rpm": [
            {"vital_type": "blood_glucose", "unit": "mg/dL", "device": "Contour glucometer",
             "base": 138, "noise": 16, "baseline": 140, "high": 180, "low": 70,
             "overrides": {DAYS - 1: 247}},
        ],
        "anamnesis": {
            "intake_date": "2026-05-31",
            "chief_complaint": "One high sugar reading this morning.",
            "hpi": "Ms. Delgado got a fasting glucose of 247 this morning, higher than her usual "
                   "120-150. She notes she started a strict low-carb (keto) diet about a week ago "
                   "on her doctor's encouragement and yesterday was a celebration where she 'had a "
                   "big slice of birthday cake and some juice.' She also started a new diabetes "
                   "pill two weeks ago. She feels completely well, no symptoms.",
            "ros": {"constitutional": "Feels well, no excessive thirst or urination today.",
                    "endocrine": "Denies blurred vision, no recent infections."},
            "social": {"smoking": "Never", "alcohol": "Rare", "diet": "Started keto diet ~1 week ago",
                       "exercise": "Walks 30 min 4x/week", "occupation": "Schoolteacher",
                       "living_situation": "Lives with husband and two children"},
            "family": ["Mother: type 2 diabetes", "Father: hypertension"],
            "adherence": [
                {"medication": "Metformin", "reported_status": "adherent", "detail": "Takes twice daily."},
                {"medication": "Empagliflozin", "reported_status": "adherent",
                 "detail": "Started two weeks ago, taking as directed."},
            ],
            "diary": [
                {"date": "2026-05-25", "entry": "Started the new low-carb diet. Sugars have been great, mostly 110-130!"},
                {"date": "2026-05-30", "entry": "It was my niece's birthday — had cake and a glass of juice. Worth it!"},
                {"date": "2026-05-31", "entry": "Whoa, meter said 247 this morning. Must be the cake. Feel totally fine."},
            ],
            "concerns": ["Wonders if one high reading after a birthday means her diabetes is out of control."],
        },
    },

    # ===================================================================
    # PT-003 — Scenario 3: "The Silent Deterioration"
    # Heart failure; gradual weight gain within thresholds + reported ankle swelling.
    # ===================================================================
    {
        "id": "PT-003",
        "name": "Walter Brennan",
        "ehr": {
            "dob": "1953-11-03", "age": 72, "sex": "male", "completeness": "complete",
            "problems": [
                {"condition": "Heart failure with reduced ejection fraction", "icd10": "I50.22",
                 "status": "active", "onset_date": "2022-08-19"},
                {"condition": "Essential hypertension", "icd10": "I10", "status": "active", "onset_date": "2014-02-01"},
                {"condition": "Atrial fibrillation", "icd10": "I48.91", "status": "active", "onset_date": "2022-08-19"},
            ],
            "medications": [
                {"name": "Furosemide", "dose": "40 mg", "frequency": "once daily",
                 "started": "2022-08-19", "status": "active"},
                {"name": "Carvedilol", "dose": "12.5 mg", "frequency": "twice daily",
                 "started": "2022-08-19", "status": "active"},
                {"name": "Sacubitril-valsartan", "dose": "49-51 mg", "frequency": "twice daily",
                 "started": "2022-10-01", "status": "active"},
            ],
            "allergies": [],
            "labs": [
                {"test": "NT-proBNP", "value": "1450", "unit": "pg/mL",
                 "reference_range": "<300", "date": "2026-04-02", "flag": "high"},
                {"test": "Potassium", "value": "4.6", "unit": "mmol/L",
                 "reference_range": "3.5-5.1", "date": "2026-04-02", "flag": "normal"},
                {"test": "Creatinine", "value": "1.3", "unit": "mg/dL",
                 "reference_range": "0.7-1.3", "date": "2026-04-02", "flag": "normal"},
            ],
            "notes": [
                {"date": "2026-04-02", "author": "Dr. Okafor", "specialty": "Cardiology",
                 "note": "72M with HFrEF (EF 35%), AF on rate control. Euvolemic today, dry weight "
                         "81.5 kg. Educated on daily weights; instructed to report >2 kg gain in 3 "
                         "days or increasing edema. Continue GDMT."},
            ],
        },
        "rpm": [
            {"vital_type": "weight", "unit": "kg", "device": "Withings scale",
             "base": 81.6, "noise": 0.25, "drift": 0.27, "event_day": 13,
             "baseline": 81.5, "high": 88.0, "low": 70.0},
            {"vital_type": "heart_rate", "unit": "bpm", "device": "Withings scale",
             "base": 74, "noise": 5, "baseline": 74, "high": 110, "low": 50},
        ],
        "anamnesis": {
            "intake_date": "2026-05-31",
            "chief_complaint": "Shoes feel tight and a bit more short of breath.",
            "hpi": "Mr. Brennan reports that over the past 10-14 days his shoes and socks have felt "
                   "tighter and his ankles look 'puffy' by evening. He is sleeping on two pillows "
                   "now instead of one because he feels 'a little winded' lying flat. He has not "
                   "missed any medications. He thought it was just the warm weather.",
            "ros": {"cardiovascular": "Bilateral ankle swelling, worse in evening. No chest pain.",
                    "respiratory": "Mild exertional dyspnea, new two-pillow orthopnea.",
                    "constitutional": "Feels more fatigued than usual."},
            "social": {"smoking": "Former, quit 1998", "alcohol": "None", "diet": "Admits to "
                       "takeout/Chinese food twice this week (salty)", "exercise": "Limited by fatigue",
                       "occupation": "Retired teacher", "living_situation": "Lives alone, daughter nearby"},
            "family": ["Father: MI at 65"],
            "adherence": [
                {"medication": "Furosemide", "reported_status": "adherent", "detail": "Takes every morning."},
                {"medication": "Carvedilol", "reported_status": "adherent", "detail": "Twice daily."},
                {"medication": "Sacubitril-valsartan", "reported_status": "adherent", "detail": "Twice daily."},
            ],
            "diary": [
                {"date": "2026-05-22", "entry": "Ankles a little puffy tonight. Probably the heat."},
                {"date": "2026-05-27", "entry": "Had Chinese takeout. Socks left big marks on my legs."},
                {"date": "2026-05-31", "entry": "Using two pillows now to breathe easier. Scale keeps going up a little each day."},
            ],
            "concerns": ["Thinks it might just be the hot weather.",
                         "Does not want to go to the hospital."],
        },
    },

    # ===================================================================
    # PT-004 — Scenario 4: "The Incomplete Record"
    # New transfer; sparse EHR; system must lean on anamnesis and flag gaps.
    # ===================================================================
    {
        "id": "PT-004",
        "name": "Priya Anand",
        "ehr": {
            "dob": "1965-05-30", "age": 61, "sex": "female", "completeness": "sparse",
            "problems": [
                {"condition": "Hypertension (per patient report; records pending)", "icd10": "I10",
                 "status": "active", "onset_date": "unknown"},
            ],
            "medications": [],
            "allergies": [],
            "labs": [],
            "notes": [
                {"date": "2026-05-29", "author": "Intake Clerk", "specialty": "Administration",
                 "note": "New patient, transferred from out-of-state. Outside records requested "
                         "but not yet received. Medication list and labs unavailable in system."},
            ],
        },
        "rpm": [
            {"vital_type": "blood_pressure", "unit": "mmHg", "device": "loaner BP cuff",
             "base": 158, "noise": 6, "baseline": None, "high": 140, "low": 90,
             "base2": 96, "noise2": 4},
        ],
        "anamnesis": {
            "intake_date": "2026-05-29",
            "chief_complaint": "New patient establishing care; high blood pressure.",
            "hpi": "Ms. Anand recently moved and is establishing care. She says she has had high "
                   "blood pressure 'for years' and was on 'a water pill and another small white "
                   "tablet' but ran out during the move three weeks ago and hasn't refilled. She "
                   "is unsure of the exact names. No chest pain or headaches.",
            "ros": {"cardiovascular": "Denies chest pain, palpitations, swelling.",
                    "neurological": "Occasional mild headaches, no vision changes."},
            "social": {"smoking": "Never", "alcohol": "Occasional wine", "diet": "Vegetarian",
                       "exercise": "Yoga twice weekly", "occupation": "Accountant",
                       "living_situation": "Lives with spouse, recently relocated"},
            "family": ["Mother: hypertension, stroke", "Brother: type 2 diabetes"],
            "adherence": [
                {"medication": "unknown 'water pill'", "reported_status": "non_adherent",
                 "detail": "Ran out ~3 weeks ago during the move; names unknown."},
            ],
            "diary": [],
            "concerns": ["Wants to get back on her medications.",
                         "Worried because her mother had a stroke."],
        },
    },

    # ===================================================================
    # PT-005 — Scenario 5: "The Conflicting Data"
    # Reports full adherence, but lab drug-effect markers (INR) are sub-therapeutic.
    # ===================================================================
    {
        "id": "PT-005",
        "name": "Gerald Foster",
        "ehr": {
            "dob": "1960-09-12", "age": 65, "sex": "male", "completeness": "complete",
            "problems": [
                {"condition": "Atrial fibrillation", "icd10": "I48.91", "status": "active", "onset_date": "2021-03-04"},
                {"condition": "Essential hypertension", "icd10": "I10", "status": "active", "onset_date": "2015-11-20"},
            ],
            "medications": [
                {"name": "Warfarin", "dose": "5 mg", "frequency": "once daily",
                 "started": "2021-03-04", "status": "active"},
                {"name": "Metoprolol succinate", "dose": "50 mg", "frequency": "once daily",
                 "started": "2021-03-04", "status": "active"},
            ],
            "allergies": [],
            "labs": [
                {"test": "INR", "value": "1.3", "unit": "ratio",
                 "reference_range": "2.0-3.0 (target)", "date": "2026-05-28", "flag": "low"},
                {"test": "INR", "value": "1.5", "unit": "ratio",
                 "reference_range": "2.0-3.0 (target)", "date": "2026-05-14", "flag": "low"},
                {"test": "INR", "value": "1.4", "unit": "ratio",
                 "reference_range": "2.0-3.0 (target)", "date": "2026-04-30", "flag": "low"},
            ],
            "notes": [
                {"date": "2026-05-28", "author": "Anticoag Clinic", "specialty": "Pharmacy",
                 "note": "65M on warfarin for AF, INR persistently sub-therapeutic (1.3-1.5) over "
                         "the last month despite reported adherence. Patient counseled. Consider "
                         "adherence assessment, dietary vitamin K review, or therapy change."},
            ],
        },
        "rpm": [
            {"vital_type": "heart_rate", "unit": "bpm", "device": "Apple Watch",
             "base": 76, "noise": 6, "baseline": 76, "high": 110, "low": 50,
             "overrides": {DAYS - 2: 132, DAYS - 1: 124}},
        ],
        "anamnesis": {
            "intake_date": "2026-05-29",
            "chief_complaint": "Routine check; occasional fluttering.",
            "hpi": "Mr. Foster reports he takes his blood thinner 'every single day, never miss a "
                   "dose' and is confused why his levels are low. He mentions he recently started "
                   "eating a large kale-and-spinach salad daily for his health. He had a couple of "
                   "episodes of his heart 'racing and fluttering' over the last two days.",
            "ros": {"cardiovascular": "Two episodes of palpitations in 48h, brief. No chest pain, no syncope.",
                    "constitutional": "Feels well otherwise."},
            "social": {"smoking": "Never", "alcohol": "1 glass wine/day", "diet": "Recently started "
                       "large daily leafy-green salads", "exercise": "Golf weekly",
                       "occupation": "Retired engineer", "living_situation": "Lives with spouse"},
            "family": ["Father: atrial fibrillation"],
            "adherence": [
                {"medication": "Warfarin", "reported_status": "adherent",
                 "detail": "Patient insists he takes it daily without missing."},
                {"medication": "Metoprolol succinate", "reported_status": "adherent", "detail": "Daily."},
            ],
            "diary": [
                {"date": "2026-05-20", "entry": "Started having a big healthy salad every day — kale, spinach, the works."},
                {"date": "2026-05-30", "entry": "Heart did that fluttering thing again for a minute. Watch said 132."},
            ],
            "concerns": ["Frustrated and a little offended that the clinic keeps asking if he takes his pills.",
                         "Wants to know why his numbers are off if he's doing everything right."],
        },
    },

    # ===================================================================
    # PT-006..PT-012 — breadth patients (realistic, support RAG discrimination)
    # ===================================================================
    {
        "id": "PT-006",
        "name": "Eleanor Voss",
        "ehr": {
            "dob": "1949-12-19", "age": 76, "sex": "female", "completeness": "complete",
            "problems": [
                {"condition": "Chronic obstructive pulmonary disease", "icd10": "J44.9",
                 "status": "active", "onset_date": "2018-01-22"},
            ],
            "medications": [
                {"name": "Tiotropium", "dose": "18 mcg", "frequency": "once daily (inhaled)",
                 "started": "2018-01-22", "status": "active"},
                {"name": "Albuterol", "dose": "90 mcg", "frequency": "as needed (inhaled)",
                 "started": "2018-01-22", "status": "active"},
            ],
            "allergies": [{"substance": "Sulfa drugs", "reaction": "hives", "severity": "moderate"}],
            "labs": [
                {"test": "Hemoglobin", "value": "13.1", "unit": "g/dL",
                 "reference_range": "12.0-15.5", "date": "2026-02-11", "flag": "normal"},
            ],
            "notes": [
                {"date": "2026-02-11", "author": "Dr. Lindqvist", "specialty": "Pulmonology",
                 "note": "76F with moderate COPD, stable. Baseline SpO2 93-95% on room air. "
                         "Continue maintenance inhaler. Pulmonary rehab encouraged."},
            ],
        },
        "rpm": [
            {"vital_type": "spo2", "unit": "%", "device": "pulse oximeter",
             "base": 94, "noise": 1.2, "baseline": 94, "high": None, "low": 90, "ndigits": 0},
            {"vital_type": "heart_rate", "unit": "bpm", "device": "pulse oximeter",
             "base": 82, "noise": 5, "baseline": 82, "high": 110, "low": 50},
        ],
        "anamnesis": {
            "intake_date": "2026-05-20",
            "chief_complaint": "Routine COPD monitoring.",
            "hpi": "Ms. Voss reports stable breathing, uses rescue inhaler ~twice a week. No fevers "
                   "or change in sputum.",
            "ros": {"respiratory": "Chronic mild dyspnea on exertion, at baseline. No new cough."},
            "social": {"smoking": "Former, 40 pack-years, quit 2017", "alcohol": "None",
                       "diet": "Regular", "exercise": "Short walks", "occupation": "Retired",
                       "living_situation": "Lives with daughter"},
            "family": ["Mother: COPD"],
            "adherence": [{"medication": "Tiotropium", "reported_status": "adherent", "detail": "Daily."}],
            "diary": [],
            "concerns": ["Wants to avoid another winter hospitalization."],
        },
    },
    {
        "id": "PT-007",
        "name": "Jamal Carter",
        "ehr": {
            "dob": "1996-03-08", "age": 30, "sex": "male", "completeness": "complete",
            "problems": [
                {"condition": "Type 1 diabetes mellitus", "icd10": "E10.9",
                 "status": "active", "onset_date": "2008-06-15"},
            ],
            "medications": [
                {"name": "Insulin glargine", "dose": "22 units", "frequency": "once daily at bedtime",
                 "started": "2008-06-15", "status": "active"},
                {"name": "Insulin aspart", "dose": "sliding scale", "frequency": "with meals",
                 "started": "2008-06-15", "status": "active"},
            ],
            "allergies": [],
            "labs": [
                {"test": "Hemoglobin A1c", "value": "6.9", "unit": "%",
                 "reference_range": "<7.0", "date": "2026-04-19", "flag": "normal"},
            ],
            "notes": [
                {"date": "2026-04-19", "author": "Dr. Nguyen", "specialty": "Endocrinology",
                 "note": "30M T1DM on basal-bolus + CGM, A1c 6.9, good control. Occasional nocturnal "
                         "lows. Reviewed pump vs MDI."},
            ],
        },
        "rpm": [
            {"vital_type": "blood_glucose", "unit": "mg/dL", "device": "Dexcom CGM",
             "base": 128, "noise": 28, "baseline": 130, "high": 250, "low": 70},
        ],
        "anamnesis": {
            "intake_date": "2026-05-18",
            "chief_complaint": "CGM review.",
            "hpi": "Mr. Carter reports good control with occasional overnight lows after evening "
                   "workouts.",
            "ros": {"endocrine": "Rare hypoglycemia symptoms at night."},
            "social": {"smoking": "Never", "alcohol": "Socially", "diet": "Carb-counting",
                       "exercise": "Gym 5x/week", "occupation": "Software developer",
                       "living_situation": "Lives alone"},
            "family": ["Aunt: type 1 diabetes"],
            "adherence": [{"medication": "Insulin glargine", "reported_status": "adherent", "detail": "Nightly."}],
            "diary": [],
            "concerns": ["Wants help reducing nighttime lows."],
        },
    },
    {
        "id": "PT-008",
        "name": "Rosa Jimenez",
        "ehr": {
            "dob": "1951-08-25", "age": 74, "sex": "female", "completeness": "complete",
            "problems": [
                {"condition": "Chronic kidney disease, stage 3", "icd10": "N18.3",
                 "status": "active", "onset_date": "2020-05-10"},
                {"condition": "Essential hypertension", "icd10": "I10", "status": "active", "onset_date": "2010-03-01"},
            ],
            "medications": [
                {"name": "Amlodipine", "dose": "5 mg", "frequency": "once daily",
                 "started": "2010-03-01", "status": "active"},
                {"name": "Losartan", "dose": "50 mg", "frequency": "once daily",
                 "started": "2020-05-10", "status": "active"},
            ],
            "allergies": [],
            "labs": [
                {"test": "Creatinine", "value": "1.6", "unit": "mg/dL",
                 "reference_range": "0.6-1.1", "date": "2026-05-05", "flag": "high"},
                {"test": "eGFR", "value": "42", "unit": "mL/min/1.73m2",
                 "reference_range": ">60", "date": "2026-05-05", "flag": "low"},
                {"test": "Potassium", "value": "4.8", "unit": "mmol/L",
                 "reference_range": "3.5-5.1", "date": "2026-05-05", "flag": "normal"},
            ],
            "notes": [
                {"date": "2026-05-05", "author": "Dr. Okafor", "specialty": "Nephrology",
                 "note": "74F CKD3 (eGFR 42) and HTN. Stable renal function. BP goal <130/80. "
                         "Avoid NSAIDs. Continue losartan and amlodipine."},
            ],
        },
        "rpm": [
            {"vital_type": "blood_pressure", "unit": "mmHg", "device": "Omron BP cuff",
             "base": 134, "noise": 5, "baseline": 134, "high": 150, "low": 90,
             "base2": 82, "noise2": 4},
        ],
        "anamnesis": {
            "intake_date": "2026-05-15",
            "chief_complaint": "Kidney and blood pressure follow-up.",
            "hpi": "Ms. Jimenez feels well. No swelling, urinating normally.",
            "ros": {"genitourinary": "No dysuria, normal urine output.", "cardiovascular": "No edema."},
            "social": {"smoking": "Never", "alcohol": "None", "diet": "Low-sodium, renal diet",
                       "exercise": "Gardening", "occupation": "Retired seamstress",
                       "living_situation": "Lives with spouse"},
            "family": ["Mother: kidney disease"],
            "adherence": [{"medication": "Losartan", "reported_status": "adherent", "detail": "Daily."}],
            "diary": [],
            "concerns": ["Worried about needing dialysis someday."],
        },
    },
    {
        "id": "PT-009",
        "name": "Frank Mueller",
        "ehr": {
            "dob": "1955-06-30", "age": 70, "sex": "male", "completeness": "complete",
            "problems": [
                {"condition": "Coronary artery disease, status post MI", "icd10": "I25.2",
                 "status": "active", "onset_date": "2023-12-02"},
                {"condition": "Hyperlipidemia", "icd10": "E78.5", "status": "active", "onset_date": "2012-01-01"},
            ],
            "medications": [
                {"name": "Aspirin", "dose": "81 mg", "frequency": "once daily", "started": "2023-12-02", "status": "active"},
                {"name": "Atorvastatin", "dose": "80 mg", "frequency": "once daily", "started": "2023-12-02", "status": "active"},
                {"name": "Metoprolol succinate", "dose": "100 mg", "frequency": "once daily", "started": "2023-12-02", "status": "active"},
            ],
            "allergies": [],
            "labs": [
                {"test": "LDL cholesterol", "value": "62", "unit": "mg/dL",
                 "reference_range": "<70 (high risk)", "date": "2026-03-20", "flag": "normal"},
            ],
            "notes": [
                {"date": "2026-03-20", "author": "Dr. Okafor", "specialty": "Cardiology",
                 "note": "70M s/p MI 2023, on guideline-directed secondary prevention. LDL 62 at goal. "
                         "Asymptomatic, good functional capacity."},
            ],
        },
        "rpm": [
            {"vital_type": "heart_rate", "unit": "bpm", "device": "Fitbit",
             "base": 62, "noise": 4, "baseline": 62, "high": 100, "low": 45},
            {"vital_type": "blood_pressure", "unit": "mmHg", "device": "Omron BP cuff",
             "base": 122, "noise": 4, "baseline": 122, "high": 140, "low": 90,
             "base2": 74, "noise2": 3},
        ],
        "anamnesis": {
            "intake_date": "2026-05-12",
            "chief_complaint": "Cardiac follow-up.",
            "hpi": "Mr. Mueller is doing well, walking 2 miles daily without chest pain.",
            "ros": {"cardiovascular": "No chest pain, no dyspnea, no palpitations."},
            "social": {"smoking": "Former, quit after MI", "alcohol": "Rare", "diet": "Mediterranean",
                       "exercise": "Walks 2 miles/day", "occupation": "Retired engineer",
                       "living_situation": "Lives with spouse"},
            "family": ["Father: MI at 60"],
            "adherence": [{"medication": "Aspirin", "reported_status": "adherent", "detail": "Daily."}],
            "diary": [],
            "concerns": ["Wants to keep his heart healthy and avoid another heart attack."],
        },
    },
    {
        "id": "PT-010",
        "name": "Tina Robinson",
        "ehr": {
            "dob": "1978-04-17", "age": 48, "sex": "female", "completeness": "complete",
            "problems": [
                {"condition": "Type 2 diabetes mellitus without complications", "icd10": "E11.9",
                 "status": "active", "onset_date": "2021-09-09"},
                {"condition": "Obesity", "icd10": "E66.9", "status": "active", "onset_date": "2015-01-01"},
            ],
            "medications": [
                {"name": "Metformin", "dose": "500 mg", "frequency": "twice daily", "started": "2021-09-09", "status": "active"},
            ],
            "allergies": [],
            "labs": [
                {"test": "Hemoglobin A1c", "value": "8.1", "unit": "%",
                 "reference_range": "<7.0", "date": "2026-04-28", "flag": "high"},
            ],
            "notes": [
                {"date": "2026-04-28", "author": "Dr. Nguyen", "specialty": "Primary Care",
                 "note": "48F T2DM, A1c 8.1 above goal. Discussed intensifying therapy and lifestyle. "
                         "Patient hesitant to add medication."},
            ],
        },
        "rpm": [
            {"vital_type": "blood_glucose", "unit": "mg/dL", "device": "Contour glucometer",
             "base": 168, "noise": 22, "baseline": 165, "high": 200, "low": 70},
        ],
        "anamnesis": {
            "intake_date": "2026-05-10",
            "chief_complaint": "Diabetes follow-up.",
            "hpi": "Ms. Robinson reports inconsistent monitoring and frequent fast food during a busy "
                   "work period.",
            "ros": {"endocrine": "Occasional increased thirst."},
            "social": {"smoking": "Never", "alcohol": "Socially", "diet": "Frequent fast food",
                       "exercise": "Minimal", "occupation": "Nurse (night shift)",
                       "living_situation": "Single parent, two children"},
            "family": ["Mother: type 2 diabetes", "Sister: type 2 diabetes"],
            "adherence": [
                {"medication": "Metformin", "reported_status": "partial",
                 "detail": "Sometimes forgets the evening dose on night shifts."},
            ],
            "diary": [],
            "concerns": ["Struggling to find time for healthy habits with shift work."],
        },
    },
    {
        "id": "PT-011",
        "name": "Beatrice Lowe",
        "ehr": {
            "dob": "1945-10-02", "age": 80, "sex": "female", "completeness": "complete",
            "problems": [
                {"condition": "Heart failure with preserved ejection fraction", "icd10": "I50.32",
                 "status": "active", "onset_date": "2021-06-30"},
                {"condition": "Atrial fibrillation", "icd10": "I48.91", "status": "active", "onset_date": "2019-02-14"},
            ],
            "medications": [
                {"name": "Furosemide", "dose": "20 mg", "frequency": "once daily", "started": "2021-06-30", "status": "active"},
                {"name": "Apixaban", "dose": "5 mg", "frequency": "twice daily", "started": "2019-02-14", "status": "active"},
            ],
            "allergies": [],
            "labs": [
                {"test": "NT-proBNP", "value": "680", "unit": "pg/mL",
                 "reference_range": "<300", "date": "2026-03-12", "flag": "high"},
            ],
            "notes": [
                {"date": "2026-03-12", "author": "Dr. Okafor", "specialty": "Cardiology",
                 "note": "80F HFpEF and AF on apixaban. Compensated. Dry weight ~68 kg. Continue "
                         "low-dose diuretic and anticoagulation."},
            ],
        },
        "rpm": [
            {"vital_type": "weight", "unit": "kg", "device": "Withings scale",
             "base": 68.1, "noise": 0.3, "baseline": 68.0, "high": 73.0, "low": 60.0},
            {"vital_type": "blood_pressure", "unit": "mmHg", "device": "Omron BP cuff",
             "base": 128, "noise": 5, "baseline": 128, "high": 145, "low": 90,
             "base2": 72, "noise2": 4},
        ],
        "anamnesis": {
            "intake_date": "2026-05-08",
            "chief_complaint": "Heart failure check-in.",
            "hpi": "Ms. Lowe feels stable, weight steady, no increased swelling or breathlessness.",
            "ros": {"cardiovascular": "No edema, no orthopnea.", "respiratory": "No new dyspnea."},
            "social": {"smoking": "Never", "alcohol": "None", "diet": "Low-salt",
                       "exercise": "Walks indoors", "occupation": "Retired librarian",
                       "living_situation": "Assisted living"},
            "family": ["Sister: atrial fibrillation"],
            "adherence": [{"medication": "Apixaban", "reported_status": "adherent", "detail": "Twice daily."}],
            "diary": [],
            "concerns": ["Wants to stay independent."],
        },
    },
    {
        "id": "PT-012",
        "name": "Daniel Park",
        "ehr": {
            "dob": "1981-01-27", "age": 45, "sex": "male", "completeness": "complete",
            "problems": [
                {"condition": "Essential hypertension", "icd10": "I10", "status": "active", "onset_date": "2023-04-18"},
                {"condition": "Generalized anxiety disorder", "icd10": "F41.1", "status": "active", "onset_date": "2020-11-05"},
            ],
            "medications": [
                {"name": "Amlodipine", "dose": "5 mg", "frequency": "once daily", "started": "2023-04-18", "status": "active"},
                {"name": "Sertraline", "dose": "50 mg", "frequency": "once daily", "started": "2020-11-05", "status": "active"},
            ],
            "allergies": [],
            "labs": [
                {"test": "Potassium", "value": "4.0", "unit": "mmol/L",
                 "reference_range": "3.5-5.1", "date": "2026-02-22", "flag": "normal"},
            ],
            "notes": [
                {"date": "2026-02-22", "author": "Dr. Patel", "specialty": "Primary Care",
                 "note": "45M with HTN and GAD. BP improving on amlodipine. Anxiety stable on "
                         "sertraline; reports work stress. Home BP can spike with stress."},
            ],
        },
        "rpm": [
            {"vital_type": "blood_pressure", "unit": "mmHg", "device": "Omron BP cuff",
             "base": 132, "noise": 7, "baseline": 132, "high": 150, "low": 90,
             "base2": 84, "noise2": 5, "overrides": {DAYS - 1: 158}, "overrides2": {DAYS - 1: 98}},
        ],
        "anamnesis": {
            "intake_date": "2026-05-27",
            "chief_complaint": "Blood pressure and stress.",
            "hpi": "Mr. Park reports a stressful week at work with a deadline. He noticed a higher BP "
                   "reading after a tense meeting. He takes his medications regularly.",
            "ros": {"cardiovascular": "No chest pain.", "psychiatric": "Increased work-related anxiety this week."},
            "social": {"smoking": "Never", "alcohol": "1-2 drinks/week", "diet": "Skips meals when busy",
                       "exercise": "Sporadic", "occupation": "Project manager",
                       "living_situation": "Lives with partner"},
            "family": ["Father: hypertension"],
            "adherence": [
                {"medication": "Amlodipine", "reported_status": "adherent", "detail": "Daily."},
                {"medication": "Sertraline", "reported_status": "adherent", "detail": "Daily."},
            ],
            "diary": [
                {"date": "2026-05-31", "entry": "Rough day, big deadline. BP cuff read 158/98 after my 4pm meeting."},
            ],
            "concerns": ["Worried stress is affecting his heart."],
            "sensitive": ["Patient discusses anxiety/work stress; handle supportively and without judgment."],
        },
    },
]


if __name__ == "__main__":
    summary = write_dataset()
    print(f"Wrote {summary['patients']} patients, {summary['rpm_readings']} RPM readings "
          f"to {settings.data_dir}")
