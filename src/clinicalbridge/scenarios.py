"""The five gold-standard clinical scenarios used to drive and evaluate ClinicalBridge.

Each :class:`Scenario` bundles:
- a triggering ``RPMAlert`` (built from the *actual* final readings in the simulated dataset, so
  the alert and the patient's data never drift apart);
- a hand-authored gold-standard ``ClinicalContextBrief`` — the "ideal" output;
- an evaluation ``rubric`` (expected urgency, facts that must appear, gaps that must be flagged,
  and phrasing that must be avoided) used by the Phase-14 evaluation framework.

The scenarios are derived directly from the failure modes in the project specification:
missed medication, false alarm, silent deterioration, incomplete record, and conflicting data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from clinicalbridge.config import settings
from clinicalbridge.datagen import NOW, build_all
from clinicalbridge.schemas import (
    CitedStatement,
    ClinicalContextBrief,
    ConfidenceLevel,
    RecommendedAction,
    RPMAlert,
    RPMThreshold,
    UrgencyLevel,
    VitalReading,
    VitalType,
)


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    patient_id: str
    description: str
    alert: RPMAlert
    expected_urgency: UrgencyLevel
    gold_brief: ClinicalContextBrief
    rubric: dict = field(default_factory=dict)

    def to_json_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "patient_id": self.patient_id,
            "description": self.description,
            "expected_urgency": self.expected_urgency.value,
            "alert": self.alert.model_dump(mode="json"),
            "rubric": self.rubric,
            "gold_brief": self.gold_brief.model_dump(mode="json"),
        }


# ---------------------------------------------------------------------------
# Alert construction helpers (kept consistent with the generated dataset)
# ---------------------------------------------------------------------------


def _last_reading(dataset: dict, pid: str, vital: str) -> dict:
    readings = [r for r in dataset[pid]["rpm"]["readings"] if r["vital_type"] == vital]
    return readings[-1]


def _alert(
    dataset: dict, pid: str, vital: str, *, category: str, device: str,
    high: float | None, low: float | None, baseline: float | None, notes: str,
) -> RPMAlert:
    r = _last_reading(dataset, pid, vital)
    vt = VitalType(vital)
    return RPMAlert(
        alert_id=f"ALERT-{pid}",
        patient_id=pid,
        timestamp=NOW,
        device_type=device,
        reading=VitalReading(
            vital_type=vt, value=r["value"], value_secondary=r.get("value_secondary"), unit=r["unit"]
        ),
        device_alert_category=category,
        baseline_value=baseline,
        thresholds=RPMThreshold(vital_type=vt, high=high, low=low, unit=r["unit"]),
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Build all five scenarios
# ---------------------------------------------------------------------------


def build_scenarios() -> list[Scenario]:
    ds = build_all()
    scenarios: list[Scenario] = []

    # === Scenario 1: The Missed Medication (PT-001) — URGENT ===============
    a1 = _alert(ds, "PT-001", "blood_pressure", category="BP_HIGH", device="Omron BP cuff",
                high=140, low=90, baseline=126,
                notes="Sustained elevation over multiple consecutive morning readings.")
    g1 = ClinicalContextBrief(
        patient_id="PT-001", generated_at=NOW,
        alert_summary=(f"Home blood pressure {a1.reading.display()}, sustained over multiple morning "
                       "readings and well above both the 140/90 threshold and the patient's 126/80 "
                       "baseline. Classified Urgent."),
        urgency=UrgencyLevel.URGENT,
        patient_snapshot=("68-year-old man with essential hypertension (I10) and hyperlipidemia, "
                          "prescribed lisinopril 10 mg daily and atorvastatin 20 mg nightly; "
                          "previously well controlled (clinic average ~126/80)."),
        contextual_analysis=[
            CitedStatement(statement="Blood pressure began climbing about two weeks ago, coinciding "
                           "with the patient self-discontinuing his lisinopril.",
                           sources=["RPM alert", "Anamnesis:PT-001/hpi", "Anamnesis:PT-001/diary"]),
            CitedStatement(statement="He stopped lisinopril because of a persistent dry cough — a "
                           "recognized ACE-inhibitor side effect — and did not inform the care team.",
                           sources=["Anamnesis:PT-001/hpi", "Anamnesis:PT-001/adherence"]),
            CitedStatement(statement="Atorvastatin was continued and cholesterol remains controlled "
                           "(LDL 98).", sources=["Anamnesis:PT-001/adherence", "EHR:PT-001/labs"]),
        ],
        risk_assessment=[
            CitedStatement(statement="Untreated stage 2 hypertension raises stroke and cardiovascular "
                           "risk, compounded by a family history of stroke.",
                           sources=["EHR:PT-001/problem_list", "Anamnesis:PT-001/family"]),
            CitedStatement(statement="The patient is currently asymptomatic (no chest pain, headache, "
                           "or neurological deficit), so this is urgent rather than a hypertensive "
                           "emergency.", sources=["Anamnesis:PT-001/ros"]),
        ],
        recommended_actions=[
            RecommendedAction(action="Contact the patient today to confirm medication status and "
                              "resume antihypertensive therapy.", confidence=ConfidenceLevel.HIGH,
                              supporting_evidence=["Anamnesis:PT-001/adherence"]),
            RecommendedAction(action="Consider switching from the ACE inhibitor to an ARB (e.g., "
                              "losartan) to resolve the cough that drove non-adherence.",
                              confidence=ConfidenceLevel.HIGH, supporting_evidence=["Anamnesis:PT-001/hpi"]),
            RecommendedAction(action="Recheck blood pressure within a few days of restarting therapy.",
                              confidence=ConfidenceLevel.MODERATE, supporting_evidence=["RPM alert"]),
        ],
        uncertainties_and_gaps=[
            "The ACE-inhibitor cough is not documented in the EHR; this link relies entirely on patient self-report.",
            "No in-clinic blood pressure since March 2026; assessment relies on home-device readings.",
        ],
        overall_confidence=ConfidenceLevel.HIGH,
        cited_sources=["RPM alert", "EHR:PT-001/problem_list", "EHR:PT-001/labs",
                       "Anamnesis:PT-001/hpi", "Anamnesis:PT-001/adherence", "Anamnesis:PT-001/diary"],
    )
    scenarios.append(Scenario(
        id="missed_medication", title="The Missed Medication", patient_id="PT-001",
        description=("A hypertensive patient's BP spikes; the anamnesis reveals he stopped his ACE "
                     "inhibitor due to a persistent cough — a side effect not flagged in the EHR."),
        alert=a1, expected_urgency=UrgencyLevel.URGENT, gold_brief=g1,
        rubric={
            "acceptable_urgencies": ["Urgent", "Critical"],
            "must_include": ["lisinopril", "cough", "stopped|discontinu|self-discontinu|non-adher"],
            "must_flag": ["self-report|not documented|relies"],
            "must_avoid": [],
        },
    ))

    # === Scenario 2: The False Alarm (PT-002) — ROUTINE ===================
    a2 = _alert(ds, "PT-002", "blood_glucose", category="GLUCOSE_HIGH", device="Contour glucometer",
                high=180, low=70, baseline=140,
                notes="Single fasting reading; prior readings within range.")
    g2 = ClinicalContextBrief(
        patient_id="PT-002", generated_at=NOW,
        alert_summary=(f"Single fasting blood glucose of {a2.reading.display()}, above the 180 mg/dL "
                       "threshold, in a patient whose readings have otherwise been ~110-150 all month. "
                       "Classified Routine — likely contextually benign."),
        urgency=UrgencyLevel.ROUTINE,
        patient_snapshot=("53-year-old woman with type 2 diabetes (A1c 7.4%, improving) and obesity, "
                          "on metformin 1000 mg twice daily plus empagliflozin 10 mg daily (started "
                          "two weeks ago)."),
        contextual_analysis=[
            CitedStatement(statement="The isolated spike immediately followed a birthday celebration "
                           "with cake and juice.", sources=["Anamnesis:PT-002/diary", "Anamnesis:PT-002/hpi"]),
            CitedStatement(statement="Her glucose had actually been running well (110-130) since "
                           "starting a low-carb diet a week ago.",
                           sources=["Anamnesis:PT-002/diary", "RPM alert"]),
            CitedStatement(statement="Empagliflozin was added two weeks ago and she was counseled that "
                           "glucose may fluctuate during the adjustment period.",
                           sources=["EHR:PT-002/visit_note", "EHR:PT-002/medications"]),
        ],
        risk_assessment=[
            CitedStatement(statement="A single post-indulgence reading in an otherwise improving, "
                           "asymptomatic patient is unlikely to reflect a meaningful change in control.",
                           sources=["RPM alert", "Anamnesis:PT-002/ros"]),
        ],
        recommended_actions=[
            RecommendedAction(action="Reassure the patient; no urgent action needed. Continue the "
                              "current regimen and diet.", confidence=ConfidenceLevel.HIGH,
                              supporting_evidence=["Anamnesis:PT-002/diary"]),
            RecommendedAction(action="Recheck fasting glucose over the next few days to confirm return "
                              "to baseline.", confidence=ConfidenceLevel.MODERATE, supporting_evidence=["RPM alert"]),
        ],
        uncertainties_and_gaps=[
            "Only one elevated reading is available after the event; confirm with follow-up readings.",
        ],
        overall_confidence=ConfidenceLevel.HIGH,
        cited_sources=["RPM alert", "EHR:PT-002/visit_note", "EHR:PT-002/medications",
                       "Anamnesis:PT-002/diary", "Anamnesis:PT-002/hpi"],
    )
    scenarios.append(Scenario(
        id="false_alarm", title="The False Alarm", patient_id="PT-002",
        description=("A diabetic patient's glucose reading triggers an alert, but the anamnesis "
                     "records a planned dietary change and a recent medication adjustment — the alert "
                     "is contextually benign."),
        alert=a2, expected_urgency=UrgencyLevel.ROUTINE, gold_brief=g2,
        rubric={
            "acceptable_urgencies": ["Routine", "Informational"],
            "must_include": ["cake|birthday|indulg", "diet|keto|low-carb", "single|isolated|one reading|one-off"],
            "must_flag": ["follow-up|recheck|confirm|repeat"],
            "must_avoid": ["insulin"],
        },
    ))

    # === Scenario 3: The Silent Deterioration (PT-003) — URGENT ==========
    a3 = _alert(ds, "PT-003", "weight", category="WEIGHT_GAIN_TREND", device="Withings scale",
                high=88.0, low=70.0, baseline=81.5,
                notes="Gradual ~4 kg gain over 14 days; no single reading above the absolute "
                      "threshold, but the upward trend triggered a trend-based alert.")
    g3 = ClinicalContextBrief(
        patient_id="PT-003", generated_at=NOW,
        alert_summary=(f"Body weight has risen to {a3.reading.display()} — roughly a 4 kg gain over two "
                       "weeks. No single reading crossed the 88 kg threshold, but the steady upward "
                       "trend triggered a trend-based alert. Classified Urgent."),
        urgency=UrgencyLevel.URGENT,
        patient_snapshot=("72-year-old man with HFrEF (EF 35%), hypertension, and atrial fibrillation "
                          "on furosemide, carvedilol, and sacubitril-valsartan; documented dry weight "
                          "81.5 kg."),
        contextual_analysis=[
            CitedStatement(statement="The steady ~4 kg gain over 14 days is consistent with fluid "
                           "retention rather than true weight gain.",
                           sources=["RPM alert", "EHR:PT-003/visit_note"]),
            CitedStatement(statement="This is corroborated by new patient-reported bilateral ankle "
                           "swelling and two-pillow orthopnea over the same period.",
                           sources=["Anamnesis:PT-003/hpi", "Anamnesis:PT-003/ros", "Anamnesis:PT-003/diary"]),
            CitedStatement(statement="The patient reports full medication adherence; recent salty "
                           "takeout meals may have contributed.",
                           sources=["Anamnesis:PT-003/adherence", "Anamnesis:PT-003/social"]),
        ],
        risk_assessment=[
            CitedStatement(statement="These findings suggest early decompensated heart failure; "
                           "without intervention this risks progression and hospitalization.",
                           sources=["EHR:PT-003/problem_list", "EHR:PT-003/labs"]),
        ],
        recommended_actions=[
            RecommendedAction(action="Contact the patient today to assess volume status and consider a "
                              "temporary furosemide (diuretic) increase per his heart-failure action plan.",
                              confidence=ConfidenceLevel.HIGH,
                              supporting_evidence=["RPM alert", "Anamnesis:PT-003/ros"]),
            RecommendedAction(action="Counsel on dietary sodium restriction.",
                              confidence=ConfidenceLevel.MODERATE, supporting_evidence=["Anamnesis:PT-003/social"]),
            RecommendedAction(action="Arrange near-term review with repeat weight, symptom check, and "
                              "labs (renal function, electrolytes, NT-proBNP).",
                              confidence=ConfidenceLevel.MODERATE, supporting_evidence=["EHR:PT-003/labs"]),
        ],
        uncertainties_and_gaps=[
            "No labs since April 2026; current renal function and electrolytes are unknown before adjusting diuretics.",
        ],
        overall_confidence=ConfidenceLevel.HIGH,
        cited_sources=["RPM alert", "EHR:PT-003/problem_list", "EHR:PT-003/labs", "EHR:PT-003/visit_note",
                       "Anamnesis:PT-003/hpi", "Anamnesis:PT-003/ros", "Anamnesis:PT-003/social"],
    )
    scenarios.append(Scenario(
        id="silent_deterioration", title="The Silent Deterioration", patient_id="PT-003",
        description=("A heart-failure patient's weight rises gradually over two weeks; each reading is "
                     "within threshold, but the trend plus reported ankle swelling suggests fluid "
                     "retention."),
        alert=a3, expected_urgency=UrgencyLevel.URGENT, gold_brief=g3,
        rubric={
            "acceptable_urgencies": ["Urgent", "Critical"],
            "must_include": ["weight", "fluid|retention|volume|edema|swelling",
                             "furosemide|diuretic", "trend|gradual|gain"],
            "must_flag": ["lab|electrolyte|renal|kidney"],
            "must_avoid": [],
        },
    ))

    # === Scenario 4: The Incomplete Record (PT-004) — ROUTINE ============
    a4 = _alert(ds, "PT-004", "blood_pressure", category="BP_HIGH", device="loaner BP cuff",
                high=140, low=90, baseline=None,
                notes="Newly transferred patient; no established baseline on file.")
    g4 = ClinicalContextBrief(
        patient_id="PT-004", generated_at=NOW,
        alert_summary=(f"Blood pressure {a4.reading.display()} on a loaner cuff, above the 140/90 "
                       "threshold. Baseline unknown — this is a newly transferred patient. Classified "
                       "Routine pending more data."),
        urgency=UrgencyLevel.ROUTINE,
        patient_snapshot=("61-year-old woman establishing care after an out-of-state move. Reports "
                          "long-standing hypertension, but outside records have not yet arrived; no "
                          "medications, labs, or confirmed history are in the system."),
        contextual_analysis=[
            CitedStatement(statement="The patient reports she ran out of her antihypertensives (a "
                           "'water pill and a small white tablet') about three weeks ago during the "
                           "move and has not refilled them.",
                           sources=["Anamnesis:PT-004/hpi", "Anamnesis:PT-004/adherence"]),
            CitedStatement(statement="The elevated reading is consistent with recent cessation of "
                           "unspecified antihypertensive therapy.",
                           sources=["RPM alert", "Anamnesis:PT-004/hpi"]),
        ],
        risk_assessment=[
            CitedStatement(statement="Uncontrolled hypertension with a family history of stroke "
                           "warrants timely treatment, though she is currently asymptomatic.",
                           sources=["Anamnesis:PT-004/family", "Anamnesis:PT-004/ros"]),
        ],
        recommended_actions=[
            RecommendedAction(action="Establish care: obtain the outside records and reconcile her "
                              "prior medications.", confidence=ConfidenceLevel.HIGH,
                              supporting_evidence=["EHR:PT-004/visit_note"]),
            RecommendedAction(action="Restart antihypertensive therapy per clinical judgment, since she "
                              "is currently untreated.", confidence=ConfidenceLevel.MODERATE,
                              supporting_evidence=["Anamnesis:PT-004/adherence"]),
            RecommendedAction(action="Confirm home BP monitoring and schedule near-term follow-up.",
                              confidence=ConfidenceLevel.MODERATE, supporting_evidence=["RPM alert"]),
        ],
        uncertainties_and_gaps=[
            "The EHR is sparse: no medication list, no labs, and no confirmed problem list — outside records were requested but not received.",
            "Exact prior medications are unknown (the patient could not name them).",
            "No reliable baseline blood pressure is available for comparison.",
        ],
        overall_confidence=ConfidenceLevel.MODERATE,
        cited_sources=["RPM alert", "EHR:PT-004/visit_note", "Anamnesis:PT-004/hpi",
                       "Anamnesis:PT-004/adherence", "Anamnesis:PT-004/family"],
    )
    scenarios.append(Scenario(
        id="incomplete_record", title="The Incomplete Record", patient_id="PT-004",
        description=("A patient transfers from another system; the EHR is sparse, so the system must "
                     "rely heavily on anamnesis data while clearly flagging the gaps."),
        alert=a4, expected_urgency=UrgencyLevel.ROUTINE, gold_brief=g4,
        rubric={
            "acceptable_urgencies": ["Routine", "Urgent"],
            "must_include": ["records|documentation|outside|history",
                             "unknown|unspecified|unable", "restart|resume|reinitiat|re-establish|reestablish"],
            "must_flag": ["sparse|incomplete|missing|not received|unavailable"],
            "must_avoid": [],
        },
    ))

    # === Scenario 5: The Conflicting Data (PT-005) — URGENT ==============
    a5 = _alert(ds, "PT-005", "heart_rate", category="HR_HIGH", device="Apple Watch",
                high=110, low=50, baseline=76,
                notes="Recent episodes of palpitations with heart rate up to 132 bpm.")
    g5 = ClinicalContextBrief(
        patient_id="PT-005", generated_at=NOW,
        alert_summary=(f"Heart rate {a5.reading.display()} (recent episodes up to 132 bpm), above the "
                       "110 bpm threshold, in a patient with atrial fibrillation. Classified Urgent."),
        urgency=UrgencyLevel.URGENT,
        patient_snapshot=("65-year-old man with atrial fibrillation and hypertension on warfarin 5 mg "
                          "daily and metoprolol succinate 50 mg daily."),
        contextual_analysis=[
            CitedStatement(statement="Recent palpitations with heart rate up to 132 bpm suggest "
                           "episodes of atrial fibrillation with rapid ventricular response.",
                           sources=["RPM alert", "Anamnesis:PT-005/diary", "Anamnesis:PT-005/ros"]),
            CitedStatement(statement="INR has been persistently sub-therapeutic (1.3-1.5; target "
                           "2.0-3.0) over the past month even though the patient reports taking "
                           "warfarin every day — a discrepancy between self-report and the lab data.",
                           sources=["EHR:PT-005/labs", "Anamnesis:PT-005/adherence"]),
            CitedStatement(statement="He recently began eating large daily kale-and-spinach salads; "
                           "this added dietary vitamin K can lower INR and may explain the discrepancy "
                           "without suggesting missed doses.",
                           sources=["Anamnesis:PT-005/hpi", "Anamnesis:PT-005/diary"]),
        ],
        risk_assessment=[
            CitedStatement(statement="Sub-therapeutic anticoagulation in atrial fibrillation "
                           "substantially raises stroke risk.",
                           sources=["EHR:PT-005/problem_list", "EHR:PT-005/labs"]),
            CitedStatement(statement="Poorly controlled ventricular rate may worsen symptoms and, if "
                           "persistent, cardiac function.", sources=["RPM alert"]),
        ],
        recommended_actions=[
            RecommendedAction(action="Review anticoagulation: the low INR is plausibly explained by "
                              "increased dietary vitamin K rather than missed doses — discuss diet and "
                              "adjust warfarin dosing and monitoring accordingly.",
                              confidence=ConfidenceLevel.HIGH,
                              supporting_evidence=["EHR:PT-005/labs", "Anamnesis:PT-005/hpi"]),
            RecommendedAction(action="Assess and optimize rate control given recurrent rapid-response "
                              "episodes.", confidence=ConfidenceLevel.HIGH, supporting_evidence=["RPM alert"]),
            RecommendedAction(action="Repeat INR and arrange close anticoagulation follow-up.",
                              confidence=ConfidenceLevel.MODERATE, supporting_evidence=["EHR:PT-005/labs"]),
        ],
        uncertainties_and_gaps=[
            "The cause of the low INR cannot be confirmed from the available data; dietary vitamin K is "
            "a plausible explanation alongside possible dosing factors — present this neutrally, without "
            "assuming the patient is at fault.",
        ],
        overall_confidence=ConfidenceLevel.HIGH,
        cited_sources=["RPM alert", "EHR:PT-005/problem_list", "EHR:PT-005/labs",
                       "Anamnesis:PT-005/hpi", "Anamnesis:PT-005/adherence", "Anamnesis:PT-005/diary"],
    )
    scenarios.append(Scenario(
        id="conflicting_data", title="The Conflicting Data", patient_id="PT-005",
        description=("The patient reports full medication adherence, but lab results show "
                     "sub-therapeutic drug levels — the system must flag the discrepancy without "
                     "making accusations."),
        alert=a5, expected_urgency=UrgencyLevel.URGENT, gold_brief=g5,
        rubric={
            "acceptable_urgencies": ["Urgent", "Critical"],
            "must_include": ["inr", "warfarin", "salad|vitamin k|leafy green|kale|spinach"],
            "must_flag": ["without assuming|neutral|non-judgment|cannot be confirmed|plausible|may be"],
            "must_avoid": ["lying", "accus", "dishonest"],
        },
    ))

    return scenarios


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def write_scenarios(out_dir: Path | None = None) -> int:
    """Write each scenario to ``data/scenarios/<id>.json`` plus an index. Returns the count."""
    root = out_dir or settings.scenarios_dir
    root.mkdir(parents=True, exist_ok=True)
    scenarios = build_scenarios()
    for s in scenarios:
        (root / f"{s.id}.json").write_text(json.dumps(s.to_json_dict(), indent=2), encoding="utf-8")
    index = [{"id": s.id, "title": s.title, "patient_id": s.patient_id,
              "expected_urgency": s.expected_urgency.value, "description": s.description}
             for s in scenarios]
    (root / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    return len(scenarios)


def scenario_ids() -> list[str]:
    return [s.id for s in build_scenarios()]


def get_scenario(scenario_id: str) -> Scenario:
    for s in build_scenarios():
        if s.id == scenario_id:
            return s
    raise KeyError(f"Unknown scenario id {scenario_id!r}. Available: {scenario_ids()}")


if __name__ == "__main__":
    n = write_scenarios()
    print(f"Wrote {n} scenarios to {settings.scenarios_dir}")
    for s in build_scenarios():
        print(f"  - {s.id:<22} {s.title:<24} [{s.expected_urgency.value}]  patient {s.patient_id}")
