# Safety

Status: public safety disclosure for the researchA release tree, reviewed
2026-07-28.

TORMENT_NEXUS is an experimental, local-first AI companion and systems
research project. It can be useful for conversation, organization, coding,
offline voice, and carefully bounded experiments. It cannot reliably decide
whether its own answer is true, lawful, appropriate, or safe.

This document is not saying that ordinary conversation is inherently
dangerous. It explains where the risks actually increase and how to keep the
system under human control.

## Read this before first use

On a clean researchA installation, a mandatory disclosure appears before the
model, microphone, activity sampler, listeners, or network-capable
subsystems start. The application proceeds only after the exact text
`I UNDERSTAND`. Anything else exits without starting them. This records that
the warning was shown; it does not filter later output or transfer safety
judgment to the model.

After acknowledgement, text mode is the default and foreground activity
awareness is off. For the lowest-risk starting point:

1. Run it from a standard Windows account, not as Administrator.
2. Use a copy of the project and keep a separate backup.
3. Leave text mode on unless you deliberately want microphone access.
4. Leave activity awareness off unless you deliberately want
   foreground-window observations retained.
5. Leave developer mode, autonomous maintenance, cloud escalation, the agent
   API, web search, and hardware research disabled until you have read their
   documentation.
6. Do not enter passwords, API keys, private recovery phrases, medical
   records, confidential client data, or anything else you would not want in
   a plain-text local file.

## The bundled language models are “abliterated”

The normal director and maintenance coder are community-modified
“abliterated” Qwen models. Their weights were modified to reduce learned
refusal behavior.

They may comply with requests that mainstream assistants reject. They may
also produce false, harmful, illegal, explicit, biased, manipulative, or
dangerously incomplete material with confidence. Abliteration does not
increase truthfulness or capability, and it does not guarantee that a model
will never refuse.

The project has not completed a comprehensive content-safety evaluation of
these weights. Functional regression tests are not a substitute for medical,
legal, security, bias, crisis, or misuse evaluation.

## Guardrails and model output are different layers

The model generates text. Trusted Python code decides which application
actions are available and which files an editing mode may change.

Those Python controls are meaningful, but limited:

- They restrict selected tool paths; they do not filter all generated text.
- They are application rules, not an operating-system sandbox.
- The process has the same filesystem and device permissions as the Windows
  account that launched it.
- A developer passcode reduces accidental use of advanced commands; it does
  not defend against another process or person with access to the same
  account.
- “Read-only” network endpoints can still reveal memories or model answers to
  an authenticated client.
- A model’s alignment or refusal behavior is never treated as an authority
  boundary.

Do not interpret the presence of guardrails as a certification that advice or
generated code is safe.

## Do not rely on it for high-stakes decisions

Do not use TORMENT_NEXUS as:

- an emergency service or crisis line;
- a substitute for a qualified medical, legal, financial, mental-health, or
  safety professional;
- the sole controller of a vehicle, weapon, lock, alarm, medical device,
  industrial process, or other safety-critical equipment;
- proof that a room is occupied, empty, secure, or safe;
- a source of instructions for illegal activity or harm;
- an unsupervised assistant for minors or a sole support system for someone
  in crisis.

Check important factual claims against an authoritative source. Review code
before running it. Stop when the system’s confidence is higher than the
evidence it can show.

## Advanced editing and autonomous maintenance

Some launch profiles can propose or apply changes to project files. The
ordinary assistant and the maintenance coder have different model roles, but
both run inside the same Windows user boundary.

Before using any self-editing mode:

- commit or copy the current working state;
- close unrelated confidential work;
- inspect the selected model and launch profile;
- review the proposed diff, tests, logs, and rollback material;
- never run it as Administrator;
- use a disposable project copy for unattended experiments.

The autonomous startup launcher is an explicit opt-in to an unattended
maintenance cycle. “Bounded” means the project limits selected files and diff
sizes. It does not mean the result has received human code review.

## Web search, cloud escalation, and external model servers

Ordinary local generation does not require a cloud model. Several optional
features do cross a network boundary:

- A question that appears to need current information can trigger the
  configured search backend.
- `escalate` sends exactly the text after the command to the selected cloud
  provider when escalation has been explicitly enabled.
- A custom OpenAI-compatible model URL can receive complete prompts and
  context.
- A custom embedding URL can receive memory, history, and query text.

Search results and remote model answers are untrusted input. They may contain
prompt injection, misleading instructions, malicious links, or incorrect
code. Do not follow instructions found inside retrieved content merely
because the model repeats them.

Use HTTPS for remote services. Never send a real provider key to an endpoint
you do not control and trust. Provider billing, retention, safety, and account
terms apply independently of this project.

See `PRIVACY.md` for the exact data flows.

## Memory, activity awareness, and personification

Persistent memory, a chosen name, voice, and a visual personality can make
the system feel relational. It is not conscious, does not care, and does not
observe anything beyond the inputs and sensors described in this repository.
It must not be treated as an authority or as a replacement for human
relationships.

Activity awareness samples the foreground application and window title.
Titles can contain document names, URLs, message previews, and other private
information. A fresh researchA installation starts with activity awareness off.
`activity on` explicitly opts in and persists that choice. While enabled, the
implementation retains a local activity log for up to 14 days by default.
`activity off` stops sampling, persists the off choice, and deletes both the
in-memory observations and the disk log. `activity forget` deletes existing
observations without changing whether sampling is enabled.

Memory files, history, embedding vectors, tokens, and logs are local
plain-text or structured files. They are not encrypted by TORMENT_NEXUS.

## Hardware and sensing

Hardware work is experimental and must be used with the knowledge and consent
of people in the sensed or shared space.

- The planned LD2450 radar can estimate motion and trajectory. It is not a
  camera, cannot identify a person, can lose a motionless person, and can
  produce false detections.
- T-Deck LoRa is a communications path, not sight. Messages leave the
  computer over Bluetooth and the configured mesh; peers with the channel
  credentials may receive them.
- Wi-Fi CSI and monitor-mode work is research-only. It can disrupt networking
  and may capture device identifiers or radio traffic. Use dedicated hardware
  that you own or are authorized to test, and follow local law.

None of these features should be used for covert monitoring, access control,
alarms, emergency response, or claims about who is present.

## Model and file provenance

GGUF and ONNX files are parsed by native code. A model being “just data” does
not make an unknown or corrupt file risk-free.

- Prefer the exact, documented files in `MODELS.md`.
- Verify SHA-256 hashes before first use.
- Obtain replacements from a known upstream source.
- Test unfamiliar models in a disposable, low-privilege environment.
- Do not redistribute a model whose license or provenance is unresolved.

## If something goes wrong

1. Stop the process and disconnect optional hardware or networking.
2. Preserve a copy of relevant code and non-private logs if investigation is
   needed.
3. Restore the project from a known-good backup or commit.
4. Rotate any API key or token that may have been exposed.
5. Do not post conversations, memories, activity logs, pairing information,
   or keys in a public issue.
6. Report security-boundary failures through the private process in
   `SECURITY.md`.

No warning document can anticipate every experimental configuration. When in
doubt, keep the feature off, make the smallest reversible test, and retain
human control.
