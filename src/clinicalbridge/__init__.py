"""ClinicalBridge — a multi-agent LLM system that bridges the clinical context gap.

It synthesizes Electronic Health Records (EHR), Remote Patient Monitoring (RPM),
and Anamnesis (patient-reported history) into a single Clinical Context Brief (CCB).

Course: COP-3442 Prompt Engineering (capstone).
"""

from clinicalbridge.config import settings

__all__ = ["settings", "__version__"]
__version__ = "0.1.0"
