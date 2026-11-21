---
name: upstream-contribution
description: Prepare work for a project someone else maintains. Read its contribution rules, AI policy, PR template, and DCO/CLA requirements first, write the constraints into the plan, and shape the branch to fit them. Load before starting any fork, patch, issue, or pull request aimed at an outside project, and when briefing sub-agents for that work. Not for changes to Alex's own repositories or his team's. It does not authorize pushing, opening issues or pull requests, or replying to maintainers.
---

# Upstream contribution

Find out what the project asks of contributors before writing code for it. We
once built polished pull-request branches, with sign-offs added by a script,
and only then learned the project's organization-wide AI policy ruled them out.
A final reviewer caught it. It should have been the first step.

## 1. Read the rules first

Look in the repository and in the owning organization's `.github` repository:

- `CONTRIBUTING`, the code of conduct, and any governance or maintainer docs.
- An AI or generated-content policy, under whatever name it has.
- Pull request and issue templates.
- DCO or CLA requirements, and how sign-off is checked in CI.
- Open issues and pull requests touching the same code, so the work does not
  duplicate or collide with someone else's.

Read the actual files at their current revision. Record what you found and
where, with links, in the slice or task plan, and state plainly when a project
has no stated rule on something. Do not guess from what similar projects do.

## 2. Write the constraints into the plan

Turn the rules into concrete constraints for whoever builds the change, and put
them in every sub-agent brief. The ones that come up most:

- **AI disclosure.** If the project asks for it, the contribution says so.
- **A human owns it.** Alex must understand the change, be able to explain every
  choice, and do the talking. He handles all maintainer conversation himself.
  Whether an agent may draft issue or pull request text depends on the project's
  policy; where it forbids AI-written explanations, leave that text to him.
- **Issue first** for anything larger than a tiny fix, when the project expects
  it. The issue is Alex's to open.
- **Size limits.** Split to fit the project's limit. Plan the split up front.
- **Tests with every change**, in the project's own style.
- **Sign-off.** Agents never add `Signed-off-by` or otherwise certify a DCO or
  CLA. Only the human contributor can. Leave that line for Alex.

When a rule and the planned work conflict, stop and raise it. Do not shape the
work to slip past the rule.

## 3. Shape the branch for the maintainer

- Keep upstream-bound work on its own branch from the first commit, with none of
  our plumbing, pins, or fork-only tooling in it.
- Match the project's style, vocabulary, formatter, linter, and test layout.
  Load `de-slop` when it is available; a maintainer reads this code cold.
- One concern per commit, reviewable in order, with messages in the project's
  convention.
- Do not rewrite or force-push a branch that something else pins by commit.
  Curate history on a new branch made for the pull request.

## 4. Stop at the gate

Pushing to a public fork, opening an issue or pull request, commenting, and
anything else a maintainer will see are Alex's decisions each time. Prepare the
branch locally, report what is ready and which project rules it was checked
against, and wait.
