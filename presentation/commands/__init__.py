"""
OfferGet Presentation Commands Package.
Central entry point for all CLI command handlers.
"""

from presentation.commands.jd_cmd import (
    cmd_jd_decode,
    cmd_jd_match,
    cmd_jd_report,
)
from presentation.commands.ats_cmd import (
    cmd_ats_audit,
    cmd_ats_ledger,
    cmd_ats_filter,
)
from presentation.commands.gap_cmd import (
    cmd_gap_roi,
)
from presentation.commands.offer_cmd import (
    cmd_offer_eval,
    cmd_offer_evaluate,
    cmd_offer_counter,
)
from presentation.commands.review_cmd import (
    cmd_career_review,
)
from presentation.commands.resume_cmd import (
    cmd_resume_build,
    cmd_resume_passthrough,
)
from presentation.commands.academic_cmd import (
    cmd_baoyan_audit,
    cmd_baoyan_compress,
    cmd_baoyan_advisor,
    cmd_advisor_match,
    cmd_baoyan_checklist,
    cmd_defense_simulate,
)
from presentation.commands.fact_cmd import (
    cmd_fact_verify,
    cmd_anon_mask,
    cmd_anon_unmask,
    cmd_anon_profile,
)
from presentation.commands.selftest_cmd import (
    cmd_selftest,
)

__all__ = [
    "cmd_jd_decode",
    "cmd_jd_match",
    "cmd_jd_report",
    "cmd_ats_audit",
    "cmd_ats_ledger",
    "cmd_ats_filter",
    "cmd_gap_roi",
    "cmd_offer_eval",
    "cmd_offer_evaluate",
    "cmd_offer_counter",
    "cmd_career_review",
    "cmd_resume_build",
    "cmd_resume_passthrough",
    "cmd_baoyan_audit",
    "cmd_baoyan_compress",
    "cmd_baoyan_advisor",
    "cmd_advisor_match",
    "cmd_baoyan_checklist",
    "cmd_defense_simulate",
    "cmd_fact_verify",
    "cmd_anon_mask",
    "cmd_anon_unmask",
    "cmd_anon_profile",
    "cmd_selftest",
]
