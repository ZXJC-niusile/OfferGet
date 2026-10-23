# Skill design rationale

The skill is a local workflow around OfferGet's existing CLI. It does not publish
an MCP plugin, upload resumes, or add an OpenAI API dependency.

## Official guidance applied

- [Plugin skills](https://developers.openai.com/plugins/build/skills): clear activation
  boundaries, required inputs, outputs, and selective supporting references. The
  entry point routes by the user's task instead of imposing unrelated stages.
- [API skills](https://developers.openai.com/api/docs/guides/tools-skills): local
  skill paths differ from hosted, versioned bundles. Installing this repository
  locally does not upload or register a hosted skill. If hosted execution is added
  later, make data handling and skill/version selection explicit.
- [Evaluating skills](https://developers.openai.com/blog/eval-skills): validate the
  result, process, style, and efficiency separately. Static contract checks protect
  links/entry-point structure; they do not measure actual agent activation or quality.
- [Rethinking skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra):
  keep broadly useful instructions short, load domain detail on demand, and specify
  success criteria rather than requiring ceremony on every task.

## OfferGet-specific decisions

- Keep the existing root `SKILL.md` so current local installations remain compatible.
- Use a single router with non-overlapping outcome routes instead of several skills
  that compete to activate on the same resume request.
- Select one explicit theme in recipes. The CLI defaults to `modern-navy`; use `all` only for an explicitly requested theme comparison.
- Retain the source-of-truth and proposal-approval boundaries. A formatting request
  does not authorize rewriting content or submitting the resume.
- Report dependency/rendering gaps honestly. Readability, factual preservation, and
  inspection matter more than an unconditional one-page or ATS-score claim.

The recipe commands can be checked without personal data. Repository examples are
demonstration/test inputs, never verified facts about the user. Model-driven evaluation should
record the exact repository revision, model, prompts, command trace, and artifacts;
compare equivalent runs rather than inferring efficiency from instruction length.
