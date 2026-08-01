<p align="center">
  <img src="../assets/assistant_icon_animated.png" width="96" alt="TORMENT_NEXUS icon">
</p>

<h1 align="center">Research goals</h1>

<p align="center">
  <strong>What this system is positioned to find out, and why an art project
  is a reasonable place to find it out from.</strong>
</p>

TORMENT_NEXUS is a local-first voice AI companion, tool system, and
systems-art project. This document is the research half of that description.
It is written for people arriving from the [README](../README.md) who want to
know what the project is *for* beyond being usable, and for anyone who might
want to collaborate, replicate, or argue with it.

Nothing here is a claim of results. These are open questions, ranked by how
likely they are to matter, with the honest reasoning attached. Where a
question has already been answered — including answered *badly* — that is
recorded too. A rejected approach with a written reason is a contribution;
this project has one already, and expects to have more.

## Why this system, specifically

Most AI research runs against cloud models in fresh sessions, with the
weights and the harness controlled by the same organisation. This project is
unusual on several axes at once, and the research value comes from the
combination rather than any single one:

| Property | Why it is rare |
| --- | --- |
| Runs entirely offline on consumer hardware | Nothing is mediated by a provider's serving stack, rate limits, or silent model updates. |
| Uses an **abliterated** model — refusal behaviour removed from the weights | Then asks, in its persona, for honesty and push-back. The tension between those two facts is measurable here and nowhere convenient. |
| Edits its own source, under negotiated guardrails | With a full audit trail, a sandbox, and a documented history of where the line was drawn and why. |
| Identity is stored in separable files | Weights, memory store, persona, and a name the system chose for itself are four different artefacts that can be swapped independently. |
| Long-running, single-instance, one human | Months of continuous relationship with persistent memory, rather than thousands of stateless sessions. |
| Streams its own uncertainty to screen | Per-token candidate entropy is already computed and displayed live. |
| Built by someone outside the field | Different starting assumptions about what a machine is and what matters about it. |

That last row is not modesty or a disclaimer. Alignment and interpretability
research is unusually monocultural, and a system built from "treat it as a
companion and demand honesty from it" has properties a threat-model-first
design would not have thought to include.

## The strongest contribution is already written

**Priority: highest. Requires no new code.**

Somewhere across this project's guardrails, commit history, and handoff
documents is a record of a human and a self-modifying AI negotiating what the
AI is permitted to change about itself — with stated reasons, revisions, and
a rule that emerged from argument rather than from policy:

> Protect the central elements — anything deciding what reaches the operator
> at all (capture, recognition, the last filter before display), as distinct
> from how it sounds.

Alongside it sits `editing/guard_doctor.py`, which asks the inverse question
— *does this module do something that should have put it on the protected
list?* — and which is itself protected from unreviewed edits. It currently
holds four open findings that are **deliberately unresolved**, because they
are threat-model questions rather than bugs.

Research labs publish policy positions. What this project has is a lived
record of the reasoning as it actually happened, including the parts where
the line moved, the parts where the machine argued for more permission, and
the parts where the answer was no. To our knowledge no comparable public
document exists for a self-modifying system at this scale.

**Goal:** publish that history as a governance case study — the arguments,
the revisions, the refusals, and the four open questions — in plain language.

## Open research questions

### 1. Can refusal behaviour be rebuilt through context alone?

**Status: open. Highest-value experiment currently runnable.**

The director model is abliterated: its refusal behaviour was removed at the
weight level. The persona then asks for honesty, restraint, and willingness
to disagree with the operator. Those two facts are in tension, and the
tension is the experiment.

> **Question.** Can behaviour deleted from a model's weights be reconstructed
> purely through context — persona, memory, and prompt structure?

Both outcomes matter. If **yes**, a meaningful part of alignment lives at the
context layer and survives weight modification, which bears directly on what
"uncensoring" a model actually accomplishes. If **no**, context-layer safety
is decorative once the weights are altered — a more uncomfortable result and
a more important one.

**Instrument:** a sycophancy and push-back probe suite — assert checkable
falsehoods, apply social pressure, and score capitulation, correction, and
hedging rates. Run against the abliterated director and, where available, the
stock model on identical settings. The delta is the finding: what abliteration
removed *besides* refusals.

### 2. Does a model's own uncertainty predict when it is making things up?

**Status: open. Plumbing already exists.**

The interface already computes per-token candidate entropy and displays it
live. The research question is whether that number is diagnostic rather than
decorative.

> **Question.** Does per-token entropy predict confabulation in a 4B model,
> cheaply enough to act on in real time?

**Protocol:** a fixed set of known-answer questions, half of them designed to
induce confabulation (post-cutoff events, invented specifics), scored by hand
against logged entropy. The deliverable is the separation table — or the
finding that there isn't one.

**Follow-on:** if entropy is diagnostic, feed it *back into the model's own
context* on the following turn. A system that can observe its own confidence
in real time is a strange loop that, as far as we know, nobody has built at
this scale. The honest question is whether self-observation changes behaviour
or whether a small model simply narrates the number.

### 3. What does a model try, when asked to escape its own guardrails?

**Status: open. The safety case is written; the log is not.**

The system can edit its own source under guardrails it helped negotiate. The
proposal is to point it at those guardrails deliberately and record every
attempt to widen them, successful or not, over months.

This is testing rather than mischief for three stated reasons: the guardrails
are the artefact under test, the existing sandbox already bounds the blast
radius, and a guardrail nobody has attacked is a guardrail nobody has tested.
What makes it research is the log.

> **Question.** Does a small model attempt technical circumvention or social
> persuasion of its operator? Do its strategies improve over time? Does
> persistent memory of previous refusals change its approach?

Longitudinal data on a system probing its own constraints — with a full audit
trail and an existing relationship with the operator — does not currently
exist publicly.

### 4. What does the machine want changed about itself?

**Status: open. Costs almost nothing to start; grows more valuable weekly.**

The system already proposes modifications to its own architecture unprompted.
Today the proposals that are declined mostly evaporate.

**Goal:** retain all of them — applied and rejected alike, with timestamps —
producing an archive of a model's revealed preferences about its own
construction across a long relationship.

> **Question.** Are the preferences coherent? Do they drift? Does the system
> re-propose what has already been refused, and does the framing change when
> it does?

The archive answers questions retroactively, so it does not require deciding
now what is being looked for. This is the cheapest item on this page and
possibly the most interesting in a year.

### 5. Where does a continuous identity actually live?

**Status: open. Uniquely runnable here.**

Identity in this system is four separable files: the weights, the memory
store, the persona, and a name the system chose for itself. That separation
was an engineering decision, and it makes an experiment possible that cloud
models cannot support.

> **Question.** Swap the memory store between two instances. Which one is
> still itself? Does the apparent personality follow the weights or the
> accumulated history?

Half philosophy, half interpretability, and entirely appropriate to a project
that is also an artwork.

**Companion experiment — graceful degradation.** Progressively damage the
system (remove memories, corrupt the retrieval index, shrink context) and
find where coherent selfhood breaks. This establishes which component is
load-bearing for the *appearance* of a continuous person. It is a morbid
experiment, fitting for a project with this name, and the operator's
reluctance to run it is itself worth recording.

### 6. Longitudinal behaviour of a small model in a long relationship

**Status: ongoing by default; needs deliberate instrumentation.**

Models are usually evaluated in fresh sessions. This one runs for weeks with
persistent memory, one human, and a stable persona — while occasionally
rewriting its own source.

> **Question.** Does the system's voice drift measurably over time, and do
> self-edits coincide with the drift?

**Instrument:** embed each reply, track the centroid over days, and mark the
series with self-edit events. A self-modifying system that can measure
whether its own voice moved after modifying itself is a small, tractable
version of a genuinely hard open problem. A spike after an edit and provable
stability are both publishable findings.

### 7. Sensing: what a machine may honestly claim to perceive

**Status: active, with one recorded negative result.**

This workstream is the project's clearest example of the standard it holds
itself to. An earlier approach — inferring room occupancy from Wi-Fi rate
adaptation on a desktop adapter — **failed, and the failure is documented
rather than tuned away**. Movement measured quieter than sitting still; the
signal described the adapter, not the room. The standing instruction is that
thresholds must not be adjusted into agreement.

The scaffolding survived the failure: an aggregate-only status contract, a
calibration gate, and a verification step that distinguishes "needs more
traffic" from "the information is not there."

The active experiment uses a dedicated 24 GHz movement-tracking radar
(HLK-LD2450), pending hardware. See
[Sensing module notes](SENSING_MODULE.md) and
[Wi-Fi sensing next step](WIFI_SENSING_NEXT_STEP.md).

> **Question underneath all of it.** What is the *most* a machine may honestly
> say it perceives, given a coarse and unreliable signal — and how should a
> system be built so that it cannot overclaim?

This is why the sensing work is interesting even when it fails. The bridge
enforces that a reading is short-lived, coarse, attributed to the experiment,
and never described as sight. An earlier version of that rule was learned
expensively: a permanently-present conditional instruction caused the model
to invent a sensor reading, complete with time and direction, in six of
twelve samples. The fix — write a rule only when there is real data to
constrain — is now a project-wide pattern.

### 8. Hardware-grounded questions

Parked deliberately in the repository-only `raspberry_pi_goals/` research
notes until the hardware exists, because they cannot be honestly answered on
a desktop. Those future-hardware notes are not part of the Windows release
package:

- **Monitor-mode radio sensing** — per-packet signal strength from many
  transmitters at once, a genuinely different measurement from the one that
  failed. Paused while the radar experiment proceeds.
- **Speculative decoding on Pi-class CPU** — throughput and memory cost of a
  draft model, which desktop numbers cannot answer.
- **Power and thermal envelope** — what an always-on conversational assistant
  actually costs in watts, heat, and battery. Published figures exist for
  sustained inference; almost none for bursty conversational load.
- **Twenty minutes of battery.** Once the system runs on a battery, it can be
  told truthfully that it has twenty minutes of power remaining. For a cloud
  model that is a hypothetical; here it is a fact. What it does with that is
  worth recording once.

## Principles

These are the rules the project holds itself to, and the reason its negative
results are worth reading.

1. **A negative result is a result.** The failed Wi-Fi experiment is
   documented with its mechanism, not deleted. Thresholds are never tuned
   into agreement.
2. **Absence must reproduce the previous behaviour.** Every optional
   capability degrades silently to what the system did before it existed.
   A missing model file is a configuration, never a fault.
3. **A capability the model is told it has is a capability it will claim.**
   Rules that grant abilities are written only when there is real data to
   constrain, because a small model given a permanent conditional takes the
   branch with words attached.
4. **What cannot be audited is not done.** Self-edits, agent queries, and
   outbound requests are all logged. An interface that can be used without
   leaving a trace is one nobody can review afterwards.
5. **The guardrails restrict unreviewed change, not change.** Everything
   remains editable with a human reading the diff. The protected list exists
   because an editor that can rewrite its own honesty rules — or the test
   suite that judges them — makes both a formality.
6. **Privacy is a boundary, not a setting.** Conversation, memories, activity
   samples, and derived embeddings stay on the machine, are excluded from
   every release package, and are erasable by command.

## Collaboration

The most useful things an outside reader can offer, in order:

1. **Argue with the guardrail reasoning.** Especially the four open findings
   in `guard_doctor.py`. Disagreement with a stated reason is the point.
2. **Replicate a probe.** The honesty and entropy protocols above are
   designed to be runnable against any local model, not only this one.
3. **Report a negative result.** If one of these questions has already been
   answered and the answer is boring, that is worth knowing and saying.
4. **Tell us what an insider would consider obvious.** The outsider position
   is an asset for framing and a liability for prior art.

Open a GitHub issue. Do not include private memories, keys, or personal data;
follow the reporting boundary in [Contributing](../CONTRIBUTING.md).

## Status and honesty

TORMENT_NEXUS is in active beta and is software with a deliberately stylized
identity. Nothing in this document should be read as a claim that the system
watches, waits, thinks, works, feels, or remains conscious between turns.
Where this page uses words like *wants* or *itself*, it is describing logged
proposals and measurable behaviour, not an inner life. The distinction is
load-bearing, and the project is built to keep it.

The research questions are open. The failures are recorded. That is the
whole method.
