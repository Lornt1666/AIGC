# AIGC Post-Quantum Onion Layering

## Purpose

AIGC uses post-quantum onion layering as a cryptographic governance plan for future live connectors, release archives, permit packets, and handoff receipts.

This is not a claim of literal quantum encryption. This is not quantum key distribution. This repository does not include secret material and does not implement live cryptographic exchange.

## Current Boundary

The current implementation creates a metadata envelope that:

- canonicalizes the payload
- records a SHA3-256 payload digest
- excludes payload bytes from the envelope
- excludes secret material
- describes layered controls
- references approved post-quantum migration targets
- requires human review before external exchange
- records `external_action_performed: false`

## Onion Layers

1. Canonical payload digest
2. Symmetric content-encryption boundary through a vetted provider
3. Secret-manager or KMS key boundary
4. Post-quantum key-establishment readiness
5. Post-quantum signature readiness
6. Audit hash-chain linkage
7. Human approval gate

## Post-Quantum Migration Targets

The migration targets are:

- NIST FIPS 203 ML-KEM for key establishment
- NIST FIPS 204 ML-DSA for digital signatures
- NIST FIPS 205 SLH-DSA for digital signatures

Actual production encryption, signing, and key encapsulation must use vetted cryptographic libraries or managed KMS/HSM services. Do not invent cryptography in application code.

## Claims That Must Stay False

The envelope records these claims as false:

- literal quantum encryption claim
- real encryption performed
- quantum key distribution claim
- payload included
- secret material included
- external action performed

## Allowed Uses

The envelope may be used to:

- bind a governed artifact to a stable digest
- plan post-quantum crypto migration
- attach audit metadata to future permit packets
- describe encryption controls required before live connector expansion
- prove that no payload or secret material entered the planning envelope

## Forbidden Uses

The envelope must not be used to:

- claim unbreakable security
- hide payloads without real encryption
- store keys in Git
- log secret values
- perform external exchange without approval
- bypass human review
- bypass platform policy or legal review

## File Map

- `src/security/post_quantum_onion.py`
- `schemas/post_quantum_onion_envelope.schema.json`
- `tests/test_post_quantum_onion_layering.py`
