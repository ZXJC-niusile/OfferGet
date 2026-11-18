"""
OfferGet Presentation Commands Package.
Central entry point for core resume Skill CLI command handlers.
"""

from presentation.commands.ats_cmd import (
    cmd_ats_audit,
    cmd_ats_ledger,
    cmd_ats_filter,
)
from presentation.commands.resume_cmd import (
    cmd_resume_build,
    cmd_resume_dispatch,
)
from presentation.commands.fact_cmd import (
    cmd_fact_verify,
    cmd_anon_mask,
    cmd_anon_unmask,
)
from presentation.commands.selftest_cmd import (
    cmd_selftest,
)
from presentation.commands.doctor_cmd import (
    cmd_doctor,
)
from presentation.commands.diff_cmd import (
    cmd_diff_audit,
)
from presentation.commands.profile_cmd import (
    cmd_profile_parse,
    cmd_profile_refs,
)

__all__ = [
    "cmd_ats_audit",
    "cmd_ats_ledger",
    "cmd_ats_filter",
    "cmd_resume_build",
    "cmd_resume_dispatch",
    "cmd_fact_verify",
    "cmd_anon_mask",
    "cmd_anon_unmask",
    "cmd_selftest",
    "cmd_doctor",
    "cmd_diff_audit",
    "cmd_profile_parse",
    "cmd_profile_refs",
]
