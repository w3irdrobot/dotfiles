---
name: frontend-design
description: Design and implement polished frontend components, pages, and interfaces. Use for new web UI, landing pages, dashboards, or substantive visual styling. Respect the project's design system, accessibility needs, and technical constraints.
license: Complete terms in LICENSE.txt
---

# Frontend design

Adapted from the frontend-design skill in `~/.claude/skills/frontend-design`.
Modified 2026-10-07 for project continuity and accessibility.

Build working interfaces with an intentional visual direction and attention to
typography, layout, color, interaction, and detail. Avoid generic, context-free
styling; make choices that fit the audience and purpose.

## Establish the direction

- Read the requirements and inspect the existing UI, components, tokens, assets,
  framework, and styling tools. Existing design systems and explicit user choices
  take precedence over personal aesthetic preferences.
- For a new design, choose a coherent direction: editorial, restrained, playful,
  industrial, luxurious, or another approach suited to the context. Boldness is
  optional; deliberate restraint is equally valid.
- For an existing interface, extend its visual language unless a redesign is
  requested. Avoid introducing a new framework, component library, or font set
  just to make a small change look distinctive.

## Implement

- Use hierarchy, spacing, readable typography, and a considered palette. Favor
  consistent tokens and reusable components over one-off decorative rules.
- Choose fonts for readability and fit, not novelty alone. System fonts and
  established brand fonts are valid. Avoid imposing external font downloads when
  the existing stack or deployment constraints favor local assets.
- Make layouts responsive to real content. Include empty, loading, error, long
  text, and narrow-screen states where the feature needs them.
- Use semantic HTML, meaningful labels, keyboard interaction, visible focus,
  adequate contrast, and appropriate alternative text. Native controls are often
  preferable to custom interactions with incomplete accessibility.
- Use motion when it helps feedback or hierarchy. Respect
  `prefers-reduced-motion`; keep content usable without animation or hover.
- Match complexity to the design. Texture, asymmetry, and expressive effects can
  help a new concept, but should serve the interface rather than obscure it.
- Implement real functionality and integrate with the project's existing state,
  navigation, and data patterns. Clearly identify any placeholder content.

## Verify

Use available project checks and browser tools to verify important interactions,
keyboard/focus behavior, content states, and responsive layouts. Report what was
actually checked and any remaining limitation. Keep the delivery summary concise.
