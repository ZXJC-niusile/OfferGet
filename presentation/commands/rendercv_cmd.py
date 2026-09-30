"""RenderCV JSON import/export interoperability commands."""

from __future__ import annotations

from pathlib import Path

from core.cli_helpers import emit_json, fail_cli, load_json, write_json
from core.rendercv_adapter import export_rendercv, import_rendercv


def cmd_rendercv_import(args) -> None:
    try:
        result = import_rendercv(args.input)
    except (OSError, ValueError, TypeError) as exc:
        fail_cli(args, "rendercv_import_error", str(exc))
    output = write_json(result.profile, args.output)
    payload = {
        "output": output,
        "warnings": result.warnings,
        "unsupported_sections": sorted(result.unsupported_sections),
    }
    emit_json(payload) if args.json else print(f"OfferGet profile written: {output}; warnings: {len(result.warnings)}")


def cmd_rendercv_export(args) -> None:
    profile_path = Path(args.profile)
    if not profile_path.is_file():
        fail_cli(args, "profile_not_found", f"Profile not found: {profile_path}")
    try:
        document = export_rendercv(load_json(str(profile_path)))
        output = write_json(document, args.output)
    except (OSError, ValueError, TypeError) as exc:
        fail_cli(args, "rendercv_export_error", str(exc))
    payload = {"output": output, "sections": sorted(document["cv"]["sections"])}
    emit_json(payload) if args.json else print(f"RenderCV JSON written: {output}")
