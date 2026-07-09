# AIGC Chat-Log Scoped Observer Hardening

## Purpose

This specification defines how AIGC should prepare an invitation to a **specific approved chat-log packet** without exposing the whole conversation, the whole account, private system internals, secrets, hidden prompts, or backend access.

## Correct Security Model

AIGC cannot harden OpenAI or ChatGPT backend infrastructure.

AIGC can harden what it exports, shares, references, and invites counterparties to observe.

The safe pattern is:

```text
specific chat-log/task artifact -> redaction review -> scoped observer packet -> operator approval -> invite/share only selected packet
```

Not:

```text
raw ChatGPT conversation link -> broad access -> backend visibility -> uncontrolled sharing
```

## Required Controls

A chat-log observer invitation must be:

- specific to one approved chat-log artifact;
- exported as a controlled packet;
- redacted before external sharing;
- read-only;
- time-limited where supported;
- revocable by the operator;
- denied by default until operator approval;
- excluded from search engine/crawler indexing;
- separated from unrelated conversations and clients;
- separated from system/developer/private content;
- separated from secrets, credentials, private notes, and hidden prompts.

## Hard Blocks

AIGC must not:

- expose whole ChatGPT account access;
- expose backend access;
- expose whole conversation history by default;
- expose system messages;
- expose developer messages;
- expose hidden/private reasoning;
- expose credentials or raw secrets;
- expose unrelated clients or conversations;
- share raw ChatGPT links by default;
- make observer packets discoverable by search engines.

## Implemented Files

```text
config/chatlog_scoped_observer_access.json
schemas/chatlog_scoped_observer_access.schema.json
src/core/chatlog_scoped_observer_access.py
src/chatlog_scoped_observer_access_cli.py
tests/test_chatlog_scoped_observer_access.py
```

## Command

```powershell
python .\src\chatlog_scoped_observer_access_cli.py
```

Output:

```text
reports/artifacts/chatlog_observer_access/<packet_id>/chatlog_scoped_observer_access.json
reports/artifacts/chatlog_observer_access/<packet_id>/chatlog_scoped_observer_access.md
```

## Operator Notes

The invitation is not to the ChatGPT backend.

The invitation is to a redacted, exported, specific chat-log packet that the operator approves.

This keeps employer visibility useful without giving broad access to private AIGC operations.
