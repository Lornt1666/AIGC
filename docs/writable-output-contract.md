# Writable output contract

AIGC phase outputs must be declared before execution and preflighted under the
same UID used by the runtime. The helper in
src/core/writable_output_contract.py rejects absolute paths, parent traversal,
duplicate declarations, files where directories are expected, and directories
that cannot pass an actual create/delete probe.

## Example

    from src.core.writable_output_contract import OutputPath, validate_output_contract

    validate_output_contract(
        "/app/data",
        [
            OutputPath("phase12-snapshot", "phase12_observability", "ephemeral"),
            OutputPath("arena-evidence", "arena/evidence", "durable"),
        ],
    )

## Storage semantics

- ephemeral: scratch or recomputable output. A tmpfs mount is suitable only
  when loss on container replacement is acceptable.
- durable: authoritative records or artifacts that must survive process and
  container replacement. Route these through the configured durable database
  or artifact-store backend; do not treat a container-local directory as durable.

The preflight validator checks declared directories only. It does not detect
arbitrary undeclared writes and must be called by the phase scheduler/entrypoint
to enforce pre-execution behavior. It does not itself configure mounts or
guarantee persistence. The Compose tmpfs mounts remain bounded and are not a
substitute for durable storage. Runtime wiring and a full phase inventory remain
follow-up acceptance requirements.
