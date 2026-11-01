# Writing designs Alex wants to read

Write developer-to-developer: conversational, concrete, and technically precise.
The reader should understand what we are building and why before encountering a
catalogue of constraints. Avoid corporate language, RFC cosplay, and tutorial
explanations of concepts the intended reader already knows.

## Tell the story

Start with the problem and an example of the intended experience. Explain the
shape of the solution, who owns which responsibilities, and the important flows.
Then cover tradeoffs and open questions. A library design benefits from a small
consumer-facing API example; a service might benefit from a request flow. Use
diagrams where they clarify relationships, not as mandatory decoration.

Prefer short paragraphs. Use lists for genuinely list-shaped information and
tables for comparisons or structured data, not to squeeze every thought into a
cell. Headings describe the subject; avoid numbered sections by default unless
the existing project needs stable numbered references. Do not impose page limits
or word quotas: enough detail to explain the design, without repeating it.

## Explain instead of repeatedly warning

Lead with positive responsibility and behavior. State important constraints once,
close to the relevant design. Include the reason when it helps the reader judge
the tradeoff. Avoid repeated "not a", "never", "no framework", "deferred", and
"not yet verified" reminders throughout otherwise unrelated sections.

For example:

> Applications own their entry point, routes, and caller authorization. Saferoom
> supplies the encrypted connection and serving APIs, so it can fit into an
> existing tower application without taking over its runtime.

Rather than:

> Saferoom is not a standalone server. No library-owned routes, application main,
> business logic, or authorization framework. Examples are not a second server.

This is a change in presentation, not permission to weaken requirements. A
security invariant such as "Secrets crossing vsock must be encrypted" should
remain explicit. Exact wire formats, bounds, and failure semantics belong in
linked specs when they would overwhelm the design story. Do not replace precise
requirements with reassuring but vague prose.

## Be opinionated and honest

Describe the proposed choice and why it fits, including the cost we accept. Avoid
listing every possible option without a recommendation. Do not manufacture
certainty, benchmarks, dependency support, historical decisions, or user agreement.
Label pseudocode and proposed APIs. Distinguish design intent from implemented
behavior and validation evidence with concise status notes in the right places.

Keep open questions actionable: what needs deciding, why it matters, and which
work it blocks. Cite primary sources near claims when useful; do not let a giant
research dump substitute for reasoning. Keep deep research in supporting docs
only when there is enough value to retain it.

## Final prose review

- Can a reader explain the problem, proposed experience, and approach after the
  first few sections?
- Does each section add information rather than restate a warning?
- Are dense contracts separated without making the main document incomprehensible?
- Are accepted decisions, proposals, implementation status, and evidence distinct?
- Does the language sound like a thoughtful developer, not a compliance checklist?
