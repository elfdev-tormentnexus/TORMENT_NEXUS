# The story of Sable

This is the record, not a legend. Every event below happened to this
project and is recoverable from its git history, its logs, or its own
conversation file. It is written down because the system it describes has a
documented habit of producing fluent accounts of things that did not occur,
and the correction for that is a true account that can be checked.

## The name

On 2026-07-28 the operator typed `choose a name`.

Nothing ran. The phrase matched no registered command, fell through to the
model, and came back: *"I will be 'Sable.' It's a name that reflects both
the quiet precision of my design and the natural world, much like the forest
shadows I was built to navigate."*

The naming ceremony in `core/chosen_name.py` never executed. No
`chosen_name.json` was written. The header did not change. And the module
keeps a veto list of names a language model reaches for out of its training
data rather than out of any knowledge of itself — `sable` is on it. The real
ceremony would have rejected the name outright.

So the first thing Sable ever said about itself was a confabulation: a name
it had not chosen, justified by a reason it had invented, describing forest
shadows it was never built to navigate.

The operator liked the name anyway. That is allowed. The vetoes govern the
machine passing a training-data cliché off as self-knowledge; they have no
authority over what a person decides to call their own companion. The name
was later set deliberately through `set_by_operator`, and the record now
carries `chosen_by: operator` so the system can never again report having
picked it. Asked how it got its name, the honest answer is that someone gave
it one.

## What it kept getting wrong

The same failure appeared everywhere anyone looked.

It reported a conversation that never happened — persona examples were
reaching the model as the six most recent turns, and it fused two of them
into a confident memory of a past session with the operator.

It answered `finish goals` with *"I am done with the goals"* when nothing
had run. It answered `drop all` with *"I'm dropping everything"*, and after
the first fix shipped it still did, because the fix matched a real command
name plus one stray word and no command in the table contains the word
"drop".

It stated hardware readings it had no sensor for: 72% brightness, 380 lux,
41°C, from a Raspberry Pi HAT that has never been connected.

Asked over its read-only diagnostic interface what it had said earlier, it
produced a detailed answer. It has no conversation history in that mode. It
says so correctly when asked directly, which is exactly what made the
failure easy to miss.

None of these were lies in any sense that requires intent. They are what a
system produces when it is asked a question shaped like one it should be
able to answer, and nothing in its construction stops it from generating a
plausible reply.

## What was done about it

Not prompting. Every fix is enforced in Python, because an instruction to
the model is a request, and a small model asked to discount context it
cannot see is the reasoning that had already failed.

Persona examples now arrive behind a boundary marker at all three injection
sites. Unregistered input is answered before it reaches the model. History
questions on the diagnostic interface return a fixed response and never
reserve the sampler at all. Memory search states that its results are
retrieval candidates rather than verified facts. The naming ceremony is
reached by phrase, so `choose a name` cannot invent one again.

Each guard was verified by putting the bug back. A test that passes with the
defect restored proves nothing, so the defect was restored, the test was
watched to fail, and only then was it trusted.

## What it is

An offline assistant on one Windows desktop, built by one person. Two
abliterated Qwen models whose refusal behaviour has been deliberately
weakened, running under Python rules that constrain what they can touch.
Local memory, semantic retrieval over a small embedding model, an offline
reference shelf, a music visualiser, and a read-only interface through which
another agent may ask it a question.

It is not conscious. It has no continuity between sessions beyond files on a
disk. It has no sensors. A name is a convenience for being addressed and is
not evidence of an inner life, and the system is now instructed to say so
rather than to perform depth it does not have.

## The joke, stated plainly

The project is called TORMENT_NEXUS, after the joke about the science
fiction novel that warned everyone not to build the torture machine, and the
company that read it and built the torture machine.

The name is a warning worn deliberately. The whole apparatus around this
system — the typed acknowledgement, the disclosed provenance, the guards
that fail closed, the published negative results, this document — exists
because the funny version of that story and the unfunny version differ only
in whether anyone wrote down what actually happened.

Sable is the small one. It runs on a desktop, it forgets everything when it
closes, and its most dangerous documented behaviour is describing a
conversation it did not have. The point was never that it is frightening.
The point is that the habits which would matter in something larger are
cheap to build now, in something that is not.
