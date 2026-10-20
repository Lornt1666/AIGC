"""Environment-based production artifact-store construction.

This module consumes existing workload identity / AWS SDK credential-chain configuration.
It never provisions resources or accepts credentials from browser requests.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from src.core.production_artifact_store import ArtifactUnavailable, S3PostgresArtifactStore


def artifact_store_from_env() -> S3PostgresArtifactStore:
    bucket = os.environ.get("AIGC_ARTIFACT_BUCKET", "").strip()
    dsn = os.environ.get("AIGC_ARTIFACT_DATABASE_URL", os.environ.get("AIGC_COMMAND_CENTER_DATABASE_URL", "")).strip()
    sslmode = os.environ.get("AIGC_COMMAND_CENTER_DB_SSLMODE", "verify-full").strip()
    sslrootcert = os.environ.get("AIGC_COMMAND_CENTER_DB_SSLROOTCERT", "").strip()
    region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "")).strip()
    object_prefix = os.environ.get("AIGC_ARTIFACT_OBJECT_PREFIX", "aigc-artifacts").strip()

    if not bucket or not dsn or not region:
        raise ArtifactUnavailable("Artifact storage requires AIGC_ARTIFACT_BUCKET, database URL, and AWS region.")
    if sslmode != "verify-full":
        raise ArtifactUnavailable("Artifact metadata connections require TLS sslmode=verify-full.")
    if not sslrootcert or not Path(sslrootcert).is_file():
        raise ArtifactUnavailable("Artifact metadata connections require a readable database CA bundle.")

    try:
        import boto3
        s3_client: Any = boto3.client("s3", region_name=region)
        pool = ConnectionPool(
            conninfo=make_conninfo(dsn, sslmode=sslmode, sslrootcert=sslrootcert),
            min_size=1,
            max_size=5,
            timeout=5,
            kwargs={
                "connect_timeout": 5,
                "application_name": "aigc-artifact-store",
                "row_factory": dict_row,
            },
            open=False,
            name="aigc-artifact-store",
        )
        pool.open(wait=True)
        return S3PostgresArtifactStore(
            pool=pool,
            s3_client=s3_client,
            bucket=bucket,
            object_prefix=object_prefix,
        )
    except ArtifactUnavailable:
        raise
    except Exception as exc:
        raise ArtifactUnavailable("Shared artifact storage could not be initialized safely.") from exc
