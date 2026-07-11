# AIGC Review Packet Generator v1 Standard

## Purpose

Generate complete, exact-head, evidence-backed review packets so reviewers do not have to reverse-engineer a pull request.

## Required sections

Executive Summary; Scope and Intent; Constitutional Traceability; Architecture Diff; Contract Diff; Schema Diff; Testing and Regression; Security Diff; Privacy Diff; Accessibility Diff; Readiness Impact; Rollback Plan; Reviewer Questions; Reviewer Decision Sheet; Evidence Appendix.

## Required shared contracts

Every evidence item must be an EIAP `EvidenceReference`. Every gate result must be an EIAP `GateReceipt`. Both must match the packet revision.

## Fail-closed rules

A packet is invalid when any required section is absent, the revision is invalid, evidence or gate receipts are missing, any reference is stale, or review time is non-positive.

## Authority boundary

The generator prepares advisory material only. It cannot approve, request changes, merge, deploy, publish externally, or claim independent human review.

## v1 outputs

- in-memory machine-readable packet;
- deterministic Markdown renderer;
- exact-head staleness checks;
- positive and negative tests.

DOCX, PDF, HTML, diagrams, external publication, and council workspace integration remain deferred.
