from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.phases.phase12_observability_dashboard import Phase12ObservabilityDashboard


def main() -> int:
    try:
        import streamlit as st  # type: ignore
    except ImportError:
        print("Streamlit is not installed. Run Phase 12 CLI instead: python .\\src\\phase12_observability_dashboard.py --export")
        return 1

    dashboard = Phase12ObservabilityDashboard(
        root=PROJECT_ROOT,
        config_path=PROJECT_ROOT / "config" / "phase12_observability_dashboard.json",
    )
    snapshot = dashboard.build_snapshot()
    st.set_page_config(page_title="AIGC Observability", layout="wide")
    st.title("AIGC Observability Dashboard")
    st.metric("System Health", snapshot.system_health)
    st.write("Generated at:", snapshot.generated_at)
    st.subheader("Health Reasons")
    st.write(snapshot.health_reasons)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("Pipeline")
        st.json(snapshot.pipeline_metrics)
    with col2:
        st.subheader("Approvals")
        st.json(snapshot.approval_metrics)
    with col3:
        st.subheader("Secrets / Privacy")
        st.json(snapshot.secrets_privacy)
    st.subheader("Phase Health")
    st.dataframe([item.__dict__ for item in snapshot.phase_health], use_container_width=True)
    st.subheader("Next Recommended Action")
    st.write(snapshot.next_recommended_action)
    st.download_button(
        "Download Snapshot JSON",
        json.dumps(snapshot.__dict__, default=lambda value: value.__dict__, indent=2),
        file_name="aigc_phase12_system_snapshot.json",
        mime="application/json",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
