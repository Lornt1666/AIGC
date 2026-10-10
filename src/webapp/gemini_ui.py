from __future__ import annotations


def render_surface_ui(surface: str) -> str:
    if surface == "judge":
        return _document(
            title="AIGC · Judge Evidence",
            description=(
                "Read-only, sanitized AIGC evidence for authorized reviewers."
            ),
            body=_JUDGE_BODY,
        )
    return _document(
        title="AIGC · Governed Opportunity Workspace",
        description=(
            "A governed opportunity assessment and human review workspace."
        ),
        body=_OPERATOR_BODY,
    )


def render_surface_styles() -> str:
    return _SURFACE_STYLES


def render_surface_script(surface: str) -> str:
    if surface == "judge":
        return _JUDGE_SCRIPT
    return _OPERATOR_SCRIPT


def _document(*, title: str, description: str, body: str) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" '
        'content="width=device-width, initial-scale=1">\n'
        f"  <title>{title}</title>\n"
        f'  <meta name="description" content="{description}">\n'
        '  <meta name="color-scheme" content="dark">\n'
        '  <link rel="stylesheet" href="/assets/aigc.css">\n'
        '  <script src="/assets/surface.js" defer></script>\n'
        "</head>\n"
        f"{body}\n"
        "</html>\n"
    )


_SURFACE_STYLES = r"""
:root {
  color-scheme: dark;
  --ink-950: #05090e;
  --ink-900: #08111a;
  --ink-850: #0b1721;
  --ink-800: #10212d;
  --ink-700: #183442;
  --line: rgba(159, 210, 215, 0.18);
  --line-strong: rgba(159, 210, 215, 0.32);
  --text: #eef8f6;
  --muted: #9eb6b7;
  --teal: #62e4cf;
  --teal-dark: #123e3b;
  --gold: #f2c572;
  --violet: #a899ff;
  --success: #77e0a2;
  --warning: #ffd47f;
  --danger: #ff8e8e;
  --danger-dark: #4a2024;
  --shadow: 0 24px 80px rgba(0, 0, 0, 0.36);
  font-family:
    Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", sans-serif;
  font-synthesis: none;
}

* {
  box-sizing: border-box;
}

html {
  background: var(--ink-950);
  scroll-behavior: smooth;
}

body {
  min-width: 320px;
  min-height: 100vh;
  margin: 0;
  overflow-x: hidden;
  background:
    radial-gradient(circle at 8% 10%, rgba(98, 228, 207, 0.10), transparent 32rem),
    radial-gradient(circle at 92% 0%, rgba(168, 153, 255, 0.09), transparent 28rem),
    linear-gradient(145deg, var(--ink-950), var(--ink-900) 46%, #07141a);
  color: var(--text);
}

button,
input,
textarea,
select {
  font: inherit;
}

button,
input,
textarea,
select,
summary {
  min-height: 44px;
}

button {
  border: 0;
}

a {
  color: var(--teal);
}

[hidden] {
  display: none !important;
}

.skip-link {
  position: fixed;
  z-index: 100;
  top: 0.75rem;
  left: 0.75rem;
  padding: 0.75rem 1rem;
  transform: translateY(-180%);
  border-radius: 0.6rem;
  background: var(--teal);
  color: var(--ink-950);
  font-weight: 800;
}

.skip-link:focus {
  transform: translateY(0);
}

:focus-visible {
  outline: 3px solid var(--gold);
  outline-offset: 3px;
}

.topbar {
  position: sticky;
  z-index: 20;
  top: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 72px;
  padding: 0.75rem clamp(1rem, 3vw, 2.5rem);
  border-bottom: 1px solid var(--line);
  background: rgba(5, 9, 14, 0.88);
  backdrop-filter: blur(18px);
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.9rem;
}

.brand-mark {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border: 1px solid rgba(98, 228, 207, 0.42);
  border-radius: 13px;
  background: linear-gradient(145deg, #153b3c, #101d2c);
  color: var(--teal);
  box-shadow: inset 0 0 24px rgba(98, 228, 207, 0.10);
  font-family: Georgia, serif;
  font-size: 1.05rem;
  font-weight: 700;
}

.brand-copy strong,
.brand-copy span {
  display: block;
}

.brand-copy strong {
  letter-spacing: 0.08em;
}

.brand-copy span {
  margin-top: 0.12rem;
  color: var(--muted);
  font-size: 0.76rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.connection-state {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  min-height: 36px;
  padding: 0.45rem 0.75rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--muted);
  font-size: 0.82rem;
  font-weight: 700;
}

.connection-state::before {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #60737a;
  content: "";
}

.connection-state.is-connected::before {
  background: var(--success);
  box-shadow: 0 0 14px rgba(119, 224, 162, 0.7);
}

.shell {
  display: grid;
  grid-template-columns: minmax(220px, 270px) minmax(0, 1fr);
  max-width: 1500px;
  min-height: calc(100vh - 72px);
  margin: 0 auto;
}

.rail {
  position: sticky;
  top: 72px;
  align-self: start;
  min-height: calc(100vh - 72px);
  padding: 2rem 1.2rem 2rem clamp(1rem, 2.5vw, 2rem);
  border-right: 1px solid var(--line);
}

.rail-label,
.eyebrow {
  margin: 0;
  color: var(--teal);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.flow {
  margin: 1.4rem 0 0;
  padding: 0;
  list-style: none;
}

.flow li {
  position: relative;
  display: grid;
  grid-template-columns: 30px 1fr;
  gap: 0.7rem;
  min-height: 68px;
  color: #6f888b;
}

.flow li:not(:last-child)::after {
  position: absolute;
  top: 31px;
  bottom: 0;
  left: 14px;
  width: 1px;
  background: var(--line);
  content: "";
}

.flow-number {
  position: relative;
  z-index: 1;
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: 50%;
  background: var(--ink-900);
  font-size: 0.72rem;
  font-weight: 800;
}

.flow-copy strong,
.flow-copy span {
  display: block;
}

.flow-copy strong {
  margin-top: 0.2rem;
  color: inherit;
  font-size: 0.9rem;
}

.flow-copy span {
  margin-top: 0.2rem;
  font-size: 0.75rem;
  line-height: 1.4;
}

.flow li.is-active,
.flow li.is-complete {
  color: var(--text);
}

.flow li.is-active .flow-number {
  border-color: var(--teal);
  background: var(--teal);
  color: var(--ink-950);
  box-shadow: 0 0 20px rgba(98, 228, 207, 0.22);
}

.flow li.is-complete .flow-number {
  border-color: rgba(119, 224, 162, 0.55);
  color: var(--success);
}

.rail-lock {
  margin-top: 1.6rem;
  padding: 1rem;
  border: 1px solid rgba(242, 197, 114, 0.24);
  border-radius: 14px;
  background: rgba(242, 197, 114, 0.055);
}

.rail-lock strong {
  display: block;
  color: var(--gold);
  font-size: 0.78rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.rail-lock p {
  margin: 0.5rem 0 0;
  color: var(--muted);
  font-size: 0.78rem;
  line-height: 1.55;
}

.workspace {
  width: 100%;
  max-width: 1120px;
  padding: clamp(1.3rem, 4vw, 3.2rem);
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(260px, 0.8fr);
  gap: 1.3rem;
  align-items: stretch;
  margin-bottom: 1.3rem;
}

.hero-copy,
.connect-card,
.panel {
  border: 1px solid var(--line);
  border-radius: 22px;
  background: linear-gradient(
    150deg,
    rgba(16, 33, 45, 0.96),
    rgba(8, 20, 29, 0.96)
  );
  box-shadow: var(--shadow);
}

.hero-copy {
  padding: clamp(1.5rem, 4vw, 3rem);
}

.hero h1 {
  max-width: 760px;
  margin: 0.8rem 0 0;
  font-family: Georgia, "Times New Roman", serif;
  font-size: clamp(2.25rem, 5.5vw, 5rem);
  font-weight: 500;
  letter-spacing: -0.045em;
  line-height: 0.98;
}

.lede {
  max-width: 680px;
  margin: 1.25rem 0 0;
  color: #b9cdcc;
  font-size: clamp(1rem, 1.6vw, 1.13rem);
  line-height: 1.7;
}

.connect-card {
  padding: 1.4rem;
}

.connect-card h2,
.panel h2,
.panel h3 {
  margin-top: 0;
}

.connect-card h2,
.panel h2 {
  font-size: 1.05rem;
  letter-spacing: -0.01em;
}

.connect-card p {
  color: var(--muted);
  font-size: 0.82rem;
  line-height: 1.55;
}

.panel {
  margin-top: 1.3rem;
  padding: clamp(1.2rem, 3vw, 2rem);
}

.panel-header {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 1.35rem;
}

.panel-header p {
  max-width: 680px;
  margin: 0.35rem 0 0;
  color: var(--muted);
  line-height: 1.55;
}

.panel-index {
  flex: 0 0 auto;
  color: var(--teal);
  font-family: Georgia, serif;
  font-size: 1.35rem;
}

.system-banner {
  display: flex;
  gap: 0.8rem;
  align-items: flex-start;
  margin: 1.3rem 0;
  padding: 1rem 1.1rem;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: rgba(98, 228, 207, 0.045);
}

.system-banner.is-critical {
  border-color: rgba(255, 142, 142, 0.45);
  background: rgba(255, 142, 142, 0.08);
}

.system-banner strong {
  display: block;
  margin-bottom: 0.2rem;
}

.system-banner p {
  margin: 0;
  color: var(--muted);
  line-height: 1.5;
}

.status-grid,
.metrics-grid,
.receipt-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.8rem;
}

.status-card,
.metric,
.receipt-item {
  min-width: 0;
  padding: 1rem;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: rgba(5, 13, 20, 0.54);
}

.status-card span,
.metric span,
.receipt-item dt {
  display: block;
  color: var(--muted);
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.11em;
  text-transform: uppercase;
}

.status-card strong,
.metric strong,
.receipt-item dd {
  display: block;
  margin: 0.5rem 0 0;
  overflow-wrap: anywhere;
  color: var(--text);
  font-size: 0.94rem;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.field {
  min-width: 0;
}

.field-wide {
  grid-column: 1 / -1;
}

label,
legend {
  color: #d5e4e2;
  font-size: 0.83rem;
  font-weight: 750;
}

legend {
  padding: 0 0.3rem;
}

.field-hint,
.field-count {
  display: block;
  margin-top: 0.35rem;
  color: #789295;
  font-size: 0.72rem;
  line-height: 1.45;
}

input,
textarea,
select {
  width: 100%;
  margin-top: 0.45rem;
  padding: 0.78rem 0.9rem;
  border: 1px solid #2b4a57;
  border-radius: 11px;
  background: rgba(3, 10, 16, 0.72);
  color: var(--text);
  transition:
    border-color 140ms ease,
    box-shadow 140ms ease,
    background 140ms ease;
}

input::placeholder,
textarea::placeholder {
  color: #5f777b;
}

input:hover,
textarea:hover,
select:hover {
  border-color: #416773;
}

input:focus,
textarea:focus,
select:focus {
  border-color: var(--teal);
  background: rgba(4, 14, 20, 0.95);
  box-shadow: 0 0 0 4px rgba(98, 228, 207, 0.08);
}

textarea {
  min-height: 124px;
  resize: vertical;
}

.compact-textarea {
  min-height: 88px;
}

.check-row {
  display: flex;
  gap: 0.7rem;
  align-items: flex-start;
  min-height: 44px;
  margin-top: 0.2rem;
  padding: 0.7rem 0.8rem;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: rgba(5, 13, 20, 0.42);
  cursor: pointer;
}

.check-row input {
  flex: 0 0 auto;
  width: 18px;
  min-height: 18px;
  margin: 0.12rem 0 0;
  accent-color: var(--teal);
}

.check-copy {
  display: block;
}

.check-copy strong,
.check-copy small {
  display: block;
}

.check-copy small {
  margin-top: 0.2rem;
  color: var(--muted);
  font-weight: 450;
  line-height: 1.45;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
  margin-top: 1.15rem;
}

.button {
  display: inline-flex;
  width: auto;
  min-width: 150px;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.72rem 1rem;
  border-radius: 11px;
  background: var(--teal);
  color: #06110f;
  cursor: pointer;
  font-size: 0.84rem;
  font-weight: 850;
  letter-spacing: 0.015em;
  transition:
    transform 130ms ease,
    filter 130ms ease,
    opacity 130ms ease;
}

.button:hover:not(:disabled) {
  transform: translateY(-1px);
  filter: brightness(1.08);
}

.button:disabled {
  cursor: not-allowed;
  opacity: 0.42;
}

.button-secondary {
  border: 1px solid var(--line-strong);
  background: transparent;
  color: var(--text);
}

.button-quiet {
  min-width: auto;
  background: rgba(98, 228, 207, 0.08);
  color: var(--teal);
}

.button-danger {
  background: var(--danger);
  color: #27090c;
}

.button-link {
  min-width: auto;
  padding-inline: 0.5rem;
  background: transparent;
  color: var(--muted);
}

.inline-status {
  color: var(--muted);
  font-size: 0.8rem;
}

.error-summary {
  margin: 1rem 0 0;
  padding: 0.9rem 1rem;
  border: 1px solid rgba(255, 142, 142, 0.42);
  border-radius: 12px;
  background: rgba(255, 142, 142, 0.08);
  color: #ffd2d2;
  line-height: 1.5;
}

.review-hero {
  display: grid;
  grid-template-columns: minmax(190px, 0.42fr) minmax(0, 1fr);
  gap: 1.1rem;
  margin-bottom: 1rem;
}

.score-card,
.recommendation-card {
  padding: 1.2rem;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: rgba(5, 13, 20, 0.58);
}

.score-value {
  display: flex;
  align-items: baseline;
  gap: 0.2rem;
  margin-top: 0.5rem;
}

.score-value strong {
  font-family: Georgia, serif;
  font-size: 3rem;
  font-weight: 500;
  line-height: 1;
}

.score-value span {
  color: var(--muted);
}

meter {
  width: 100%;
  height: 12px;
  margin-top: 0.8rem;
  accent-color: var(--teal);
}

.recommendation {
  margin: 0.55rem 0;
  color: var(--teal);
  font-family: Georgia, serif;
  font-size: clamp(1.6rem, 3vw, 2.5rem);
  text-transform: capitalize;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.tag {
  display: inline-flex;
  min-height: 30px;
  align-items: center;
  padding: 0.35rem 0.62rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  color: #bad0cf;
  font-size: 0.72rem;
  font-weight: 750;
}

.tag-success {
  border-color: rgba(119, 224, 162, 0.32);
  color: var(--success);
}

.tag-warning {
  border-color: rgba(255, 212, 127, 0.34);
  color: var(--warning);
}

.review-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.85rem;
}

.review-block {
  min-width: 0;
  padding: 1rem;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: rgba(7, 18, 26, 0.6);
}

.review-block-wide {
  grid-column: 1 / -1;
}

.review-block h3 {
  margin-bottom: 0.75rem;
  font-size: 0.9rem;
}

.clean-list {
  margin: 0;
  padding-left: 1.15rem;
  color: #c7d9d7;
}

.clean-list li {
  margin: 0.45rem 0;
  line-height: 1.5;
}

.empty-copy {
  margin: 0;
  color: #698286;
  font-size: 0.82rem;
}

.evidence-list,
.risk-list {
  display: grid;
  gap: 0.65rem;
}

.evidence-item,
.risk-item {
  padding: 0.8rem;
  border-left: 3px solid var(--teal-dark);
  border-radius: 0 9px 9px 0;
  background: rgba(3, 10, 16, 0.52);
}

.evidence-item strong,
.risk-item strong {
  display: block;
  color: var(--teal);
  font-size: 0.74rem;
}

.evidence-item p,
.risk-item p {
  margin: 0.35rem 0 0;
  color: #c4d6d4;
  line-height: 1.5;
}

.risk-item {
  border-left-color: var(--warning);
}

.risk-item strong {
  color: var(--warning);
}

.decision-options {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
  margin: 0;
  padding: 0;
  border: 0;
}

.decision-option {
  position: relative;
  display: block;
}

.decision-option input {
  position: absolute;
  width: 1px;
  height: 1px;
  min-height: 1px;
  opacity: 0;
}

.decision-option-copy {
  display: block;
  min-height: 102px;
  padding: 0.9rem;
  border: 1px solid var(--line);
  border-radius: 13px;
  background: rgba(5, 13, 20, 0.48);
  cursor: pointer;
}

.decision-option-copy strong,
.decision-option-copy small {
  display: block;
}

.decision-option-copy small {
  margin-top: 0.35rem;
  color: var(--muted);
  font-weight: 450;
  line-height: 1.45;
}

.decision-option input:checked + .decision-option-copy {
  border-color: var(--teal);
  background: rgba(98, 228, 207, 0.08);
  box-shadow: 0 0 0 3px rgba(98, 228, 207, 0.07);
}

.decision-option input:disabled + .decision-option-copy {
  cursor: not-allowed;
  opacity: 0.38;
}

.decision-outcome {
  margin-top: 1rem;
  padding: 1rem;
  border: 1px solid rgba(119, 224, 162, 0.3);
  border-radius: 13px;
  background: rgba(119, 224, 162, 0.07);
}

.decision-outcome strong {
  color: var(--success);
}

.receipt-grid {
  margin: 0;
}

.receipt-item dd {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 0.76rem;
  line-height: 1.45;
}

details {
  margin-top: 1rem;
  border-top: 1px solid var(--line);
}

summary {
  display: flex;
  align-items: center;
  padding-top: 0.85rem;
  color: var(--muted);
  cursor: pointer;
  font-size: 0.8rem;
  font-weight: 750;
}

pre {
  max-height: 380px;
  margin: 0.6rem 0 0;
  overflow: auto;
  padding: 1rem;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: #03080c;
  color: #bcd0cf;
  font: 0.74rem/1.55 ui-monospace, SFMono-Regular, Consolas, monospace;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.safety-panel {
  border-color: rgba(255, 142, 142, 0.24);
}

.divider {
  height: 1px;
  margin: 1.2rem 0;
  background: var(--line);
}

.resume-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.7rem;
  align-items: end;
}

.resume-row .button {
  min-width: 130px;
}

.toast {
  position: fixed;
  z-index: 50;
  right: 1rem;
  bottom: 1rem;
  max-width: min(430px, calc(100vw - 2rem));
  padding: 0.85rem 1rem;
  border: 1px solid var(--line-strong);
  border-radius: 12px;
  background: #12232e;
  box-shadow: var(--shadow);
  color: var(--text);
}

.judge-shell {
  max-width: 1000px;
  margin: 0 auto;
  padding: clamp(1rem, 5vw, 4rem);
}

.judge-hero {
  margin: 1.5rem 0;
  padding: clamp(1.4rem, 5vw, 3rem);
  border: 1px solid var(--line);
  border-radius: 24px;
  background:
    linear-gradient(145deg, rgba(16, 33, 45, 0.96), rgba(6, 17, 24, 0.96));
  box-shadow: var(--shadow);
}

.judge-hero h1 {
  max-width: 760px;
  margin: 0.7rem 0 0;
  font-family: Georgia, serif;
  font-size: clamp(2.4rem, 7vw, 5.5rem);
  font-weight: 500;
  letter-spacing: -0.05em;
  line-height: 0.98;
}

@media (max-width: 980px) {
  .shell {
    grid-template-columns: 1fr;
  }

  .rail {
    position: static;
    min-height: 0;
    padding: 1rem;
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }

  .rail-label,
  .rail-lock {
    display: none;
  }

  .flow {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    margin: 0;
  }

  .flow li {
    display: flex;
    min-height: 0;
    align-items: center;
  }

  .flow li::after,
  .flow-copy span {
    display: none;
  }

  .flow-copy strong {
    font-size: 0.75rem;
  }

  .workspace {
    margin: 0 auto;
  }
}

@media (max-width: 760px) {
  .topbar {
    position: static;
  }

  .brand-copy span {
    display: none;
  }

  .connection-state {
    max-width: 42%;
  }

  .shell {
    min-height: auto;
  }

  .hero,
  .review-hero,
  .form-grid,
  .review-grid,
  .status-grid,
  .metrics-grid,
  .receipt-grid {
    grid-template-columns: 1fr;
  }

  .hero h1 {
    font-size: clamp(2.2rem, 12vw, 3.6rem);
  }

  .field-wide,
  .review-block-wide {
    grid-column: auto;
  }

  .decision-options {
    grid-template-columns: 1fr;
  }

  .decision-option-copy {
    min-height: 0;
  }
}

@media (max-width: 520px) {
  .flow-copy {
    display: none;
  }

  .flow li {
    justify-content: center;
  }

  .workspace {
    padding: 1rem;
  }

  .panel-header {
    display: block;
  }

  .panel-index {
    display: block;
    margin-bottom: 0.5rem;
  }

  .actions,
  .actions .button {
    width: 100%;
  }

  .resume-row {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  html {
    scroll-behavior: auto;
  }

  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
  }
}
"""


_OPERATOR_BODY = r"""
<body>
  <a class="skip-link" href="#workspace">Skip to workspace</a>
  <header class="topbar">
    <div class="brand" aria-label="AIGC by RegenExcalibur">
      <span class="brand-mark" aria-hidden="true">ΩX</span>
      <span class="brand-copy">
        <strong>AIGC</strong>
        <span>RegenExcalibur · Governed intelligence</span>
      </span>
    </div>
    <span id="connection-state" class="connection-state">Not connected</span>
  </header>

  <div class="shell">
    <aside class="rail" aria-label="Assessment workflow">
      <p class="rail-label">Operator flow</p>
      <ol class="flow">
        <li class="is-active" data-flow-step="connect">
          <span class="flow-number">01</span>
          <span class="flow-copy">
            <strong>Connect</strong>
            <span>Authenticate without storing credentials</span>
          </span>
        </li>
        <li data-flow-step="intake">
          <span class="flow-number">02</span>
          <span class="flow-copy">
            <strong>Intake</strong>
            <span>Minimize and bound the opportunity</span>
          </span>
        </li>
        <li data-flow-step="review">
          <span class="flow-number">03</span>
          <span class="flow-copy">
            <strong>Review</strong>
            <span>Separate assessment, evidence, and policy</span>
          </span>
        </li>
        <li data-flow-step="decide">
          <span class="flow-number">04</span>
          <span class="flow-copy">
            <strong>Decide</strong>
            <span>Record one internal-use attestation</span>
          </span>
        </li>
      </ol>
      <div class="rail-lock">
        <strong>External actions locked</strong>
        <p>
          An approval here records internal review only. It cannot send,
          apply, publish, purchase, contract, deploy, or contact anyone.
        </p>
      </div>
    </aside>

    <main id="workspace" class="workspace" tabindex="-1">
      <section class="hero" aria-labelledby="workspace-title">
        <div class="hero-copy">
          <p class="eyebrow">Opportunity intelligence · Human authority</p>
          <h1 id="workspace-title">Turn an opportunity into an evidence-bound decision.</h1>
          <p class="lede">
            A private operator workspace for structured Gemini assessment,
            deterministic policy, accountable review, and receipt inspection.
            Model output is advisory. Authority remains human and bounded.
          </p>
        </div>

        <div class="connect-card">
          <h2>Unlock operator workspace</h2>
          <p>
            Credentials remain in memory for this page only. They are never
            written to browser storage, a cookie, or the assessment record.
          </p>
          <form id="connection-form">
            <div class="field">
              <label for="operator-label">Operator label</label>
              <input
                id="operator-label"
                name="operator_label"
                maxlength="100"
                autocomplete="username"
                placeholder="Accountable attestation label"
                required
              >
              <span class="field-hint">
                This label is an attestation, not verified legal identity.
              </span>
            </div>
            <div class="field">
              <label for="operator-token">Operator token</label>
              <input
                id="operator-token"
                name="operator_token"
                type="password"
                maxlength="4096"
                autocomplete="current-password"
                required
              >
            </div>
            <div class="actions">
              <button class="button" id="connect-button" type="submit">
                Connect securely
              </button>
              <button
                class="button button-link"
                id="disconnect-button"
                type="button"
                hidden
              >
                Disconnect
              </button>
            </div>
            <div
              id="connection-error"
              class="error-summary"
              role="alert"
              tabindex="-1"
              hidden
            ></div>
          </form>
        </div>
      </section>

      <div id="app-shell" hidden>
        <div id="system-banner" class="system-banner" role="status">
          <div>
            <strong id="system-banner-title">Checking governed runtime</strong>
            <p id="system-banner-copy">
              Configuration and observed readiness are separate signals.
            </p>
          </div>
        </div>

        <section class="panel" aria-labelledby="environment-heading">
          <div class="panel-header">
            <div>
              <h2 id="environment-heading">Environment posture</h2>
              <p>
                Current configuration, observed readiness, and durable stop
                state. No status check invokes the model.
              </p>
            </div>
            <span class="panel-index" aria-hidden="true">00</span>
          </div>
          <div class="status-grid">
            <div class="status-card">
              <span>Provider configuration</span>
              <strong id="provider-state">Checking…</strong>
            </div>
            <div class="status-card">
              <span>Observed readiness</span>
              <strong id="readiness-state">Checking…</strong>
            </div>
            <div class="status-card">
              <span>Emergency stop</span>
              <strong id="stop-state">Checking…</strong>
            </div>
          </div>
          <div class="metrics-grid">
            <div class="metric">
              <span>Model</span>
              <strong id="model-value">—</strong>
            </div>
            <div class="metric">
              <span>Processing endpoint</span>
              <strong id="location-value">—</strong>
            </div>
            <div class="metric">
              <span>Evidence backend</span>
              <strong id="evidence-value">—</strong>
            </div>
          </div>
        </section>

        <section class="panel" id="intake-panel" aria-labelledby="intake-heading">
          <div class="panel-header">
            <div>
              <h2 id="intake-heading">Opportunity intake</h2>
              <p>
                Submit only synthetic or authorized content. Remove
                credentials, unnecessary personal data, and private URL paths.
              </p>
            </div>
            <span class="panel-index" aria-hidden="true">01</span>
          </div>

          <form id="intake-form">
            <div class="form-grid">
              <div class="field">
                <label for="opportunity-title">Opportunity title</label>
                <input
                  id="opportunity-title"
                  name="title"
                  minlength="3"
                  maxlength="200"
                  placeholder="Governed product discovery engagement"
                  required
                >
              </div>
              <div class="field">
                <label for="source-url">HTTPS source URL</label>
                <input
                  id="source-url"
                  name="source_url"
                  type="url"
                  inputmode="url"
                  placeholder="https://example.com/opportunity"
                  pattern="https://.*"
                  required
                >
                <span class="field-hint">
                  The model receives the safe origin, not credentials or query data.
                </span>
              </div>
              <div class="field field-wide">
                <label for="opportunity-description">Description</label>
                <textarea
                  id="opportunity-description"
                  name="description"
                  minlength="20"
                  maxlength="12000"
                  aria-describedby="description-hint description-count"
                  placeholder="Describe the opportunity, expected outcome, and known boundaries."
                  required
                ></textarea>
                <span id="description-hint" class="field-hint">
                  Do not paste passwords, API keys, tokens, or private keys.
                </span>
                <span id="description-count" class="field-count">0 / 12,000</span>
              </div>
              <div class="field field-wide">
                <label for="constraints">Constraints</label>
                <textarea
                  id="constraints"
                  name="constraints"
                  class="compact-textarea"
                  maxlength="8000"
                  placeholder="One constraint per line&#10;No external business action&#10;Human review required"
                  aria-describedby="constraints-hint"
                ></textarea>
                <span id="constraints-hint" class="field-hint">
                  Up to 20 non-empty constraints; 400 characters each.
                </span>
              </div>
              <div class="field field-wide">
                <label class="check-row" for="ai-permitted">
                  <input
                    id="ai-permitted"
                    name="ai_assistance_permitted"
                    type="checkbox"
                    required
                  >
                  <span class="check-copy">
                    <strong>AI assistance is authorized for this intake</strong>
                    <small>
                      The assessment remains advisory and requires a separate
                      operator decision.
                    </small>
                  </span>
                </label>
              </div>
            </div>

            <div class="actions">
              <button class="button" id="assess-button" type="submit" disabled>
                Run governed assessment
              </button>
              <span id="assessment-status" class="inline-status" role="status">
                Connect and pass readiness checks to continue.
              </span>
            </div>
            <div
              id="assessment-error"
              class="error-summary"
              role="alert"
              tabindex="-1"
              hidden
            ></div>
          </form>

          <div class="divider"></div>

          <form id="resume-form">
            <div class="resume-row">
              <div class="field">
                <label for="resume-run-id">Open an exact existing run</label>
                <input
                  id="resume-run-id"
                  name="run_id"
                  maxlength="128"
                  pattern="AIGC-GEMINI-RUN-[A-Za-z0-9-]+"
                  placeholder="AIGC-GEMINI-RUN-…"
                  required
                >
              </div>
              <button class="button button-secondary" type="submit">
                Read run
              </button>
            </div>
            <span class="field-hint">
              This is a read operation. It never repeats a model call.
            </span>
          </form>
        </section>

        <section
          class="panel"
          id="review-panel"
          aria-labelledby="review-heading"
          tabindex="-1"
          hidden
        >
          <div class="panel-header">
            <div>
              <h2 id="review-heading">Assessment review</h2>
              <p id="review-boundary">
                Generated from supplied input only; not independently verified.
              </p>
            </div>
            <span class="panel-index" aria-hidden="true">02</span>
          </div>

          <div class="review-hero">
            <div class="score-card">
              <span class="eyebrow">Fit score</span>
              <div class="score-value">
                <strong id="fit-score">—</strong>
                <span>/ 100</span>
              </div>
              <meter id="fit-score-meter" min="0" max="100" value="0">
                0 out of 100
              </meter>
            </div>
            <div class="recommendation-card">
              <span class="eyebrow">Advisory recommendation</span>
              <div id="recommendation" class="recommendation">Awaiting result</div>
              <div class="tag-row">
                <span id="workflow-status-tag" class="tag">—</span>
                <span id="policy-outcome-tag" class="tag">Policy: —</span>
                <span id="model-call-tag" class="tag">Model call: —</span>
              </div>
            </div>
          </div>

          <div class="review-grid">
            <article class="review-block">
              <h3>Rationale</h3>
              <div id="rationale"></div>
            </article>
            <article class="review-block">
              <h3>Deterministic policy reasons</h3>
              <div id="policy-reasons"></div>
            </article>
            <article class="review-block review-block-wide">
              <h3>Evidence pointers</h3>
              <div id="evidence-basis" class="evidence-list"></div>
            </article>
            <article class="review-block">
              <h3>Risks and mitigations</h3>
              <div id="risk-list" class="risk-list"></div>
            </article>
            <article class="review-block">
              <h3>Assumptions</h3>
              <div id="assumptions"></div>
            </article>
            <article class="review-block">
              <h3>Clarifying questions</h3>
              <div id="clarifying-questions"></div>
            </article>
            <article class="review-block">
              <h3>Proposed internal scope</h3>
              <div id="proposed-scope"></div>
            </article>
            <article class="review-block review-block-wide">
              <h3>AI-use disclosure</h3>
              <p id="ai-disclosure" class="lede"></p>
            </article>
          </div>
        </section>

        <section
          class="panel"
          id="decision-panel"
          aria-labelledby="decision-heading"
          tabindex="-1"
          hidden
        >
          <div class="panel-header">
            <div>
              <h2 id="decision-heading">Accountable operator decision</h2>
              <p>
                One decision may be recorded. Approval means internal use only
                and never authorizes an external business action.
              </p>
            </div>
            <span class="panel-index" aria-hidden="true">03</span>
          </div>

          <form id="decision-form">
            <fieldset class="decision-options">
              <legend>Choose an allowed decision</legend>
              <label class="decision-option" for="decision-approve">
                <input
                  id="decision-approve"
                  name="decision"
                  type="radio"
                  value="approve"
                >
                <span class="decision-option-copy">
                  <strong>Approve internal use</strong>
                  <small>Accept this assessment as an internal draft only.</small>
                </span>
              </label>
              <label class="decision-option" for="decision-deny">
                <input
                  id="decision-deny"
                  name="decision"
                  type="radio"
                  value="deny"
                >
                <span class="decision-option-copy">
                  <strong>Deny</strong>
                  <small>Close this assessment without approving its use.</small>
                </span>
              </label>
              <label class="decision-option" for="decision-revise">
                <input
                  id="decision-revise"
                  name="decision"
                  type="radio"
                  value="revise"
                >
                <span class="decision-option-copy">
                  <strong>Request revision</strong>
                  <small>Record the exact clarification or change required.</small>
                </span>
              </label>
            </fieldset>

            <div class="form-grid">
              <div class="field field-wide">
                <label for="decision-reason">Decision reason</label>
                <textarea
                  id="decision-reason"
                  name="reason"
                  class="compact-textarea"
                  minlength="10"
                  maxlength="2000"
                  placeholder="Document why this decision is appropriate."
                  required
                ></textarea>
              </div>
              <div class="field field-wide" id="revision-field" hidden>
                <label for="revision-instructions">Revision instructions</label>
                <textarea
                  id="revision-instructions"
                  name="revision_instructions"
                  class="compact-textarea"
                  maxlength="4000"
                  placeholder="State the exact evidence or scope change required."
                ></textarea>
              </div>
            </div>

            <div class="actions">
              <button class="button" id="decision-button" type="submit">
                Record decision
              </button>
              <span id="decision-status" class="inline-status" role="status"></span>
            </div>
            <div
              id="decision-error"
              class="error-summary"
              role="alert"
              tabindex="-1"
              hidden
            ></div>
          </form>

          <div id="decision-outcome" class="decision-outcome" hidden>
            <strong id="decision-outcome-title">Decision recorded</strong>
            <p id="decision-outcome-copy"></p>
          </div>
        </section>

        <section
          class="panel"
          id="evidence-panel"
          aria-labelledby="evidence-heading"
          hidden
        >
          <div class="panel-header">
            <div>
              <h2 id="evidence-heading">Receipt and claim boundary</h2>
              <p>
                These identifiers bind repository and runtime evidence. A hash
                proves content integrity, not factual correctness.
              </p>
            </div>
            <span class="panel-index" aria-hidden="true">04</span>
          </div>
          <dl id="receipt-grid" class="receipt-grid"></dl>
          <details>
            <summary>Inspect sanitized response JSON</summary>
            <pre id="raw-response"></pre>
          </details>
        </section>

        <section
          class="panel safety-panel"
          id="safety-panel"
          aria-labelledby="safety-heading"
        >
          <div class="panel-header">
            <div>
              <h2 id="safety-heading">Durable emergency stop</h2>
              <p>
                Stop new Gemini execution when authority, data, cost, or
                provider state is uncertain. Clearing requires a separate
                runtime-administrator credential and is intentionally absent.
              </p>
            </div>
            <span class="panel-index" aria-hidden="true">STOP</span>
          </div>
          <form id="stop-form">
            <div class="field">
              <label for="stop-reason">Accountable stop reason</label>
              <textarea
                id="stop-reason"
                name="reason"
                class="compact-textarea"
                minlength="10"
                maxlength="2000"
                placeholder="Describe the exact condition requiring the stop."
                required
              ></textarea>
            </div>
            <label class="check-row" for="stop-confirm">
              <input id="stop-confirm" type="checkbox" required>
              <span class="check-copy">
                <strong>I understand this blocks new Gemini assessments</strong>
                <small>
                  This does not cancel or reverse a provider action whose
                  outcome is already uncertain.
                </small>
              </span>
            </label>
            <div class="actions">
              <button class="button button-danger" id="stop-button" type="submit">
                Activate emergency stop
              </button>
              <button
                class="button button-secondary"
                id="refresh-stop-button"
                type="button"
              >
                Refresh stop state
              </button>
            </div>
            <div
              id="stop-error"
              class="error-summary"
              role="alert"
              tabindex="-1"
              hidden
            ></div>
          </form>
        </section>
      </div>
    </main>
  </div>

  <div id="toast" class="toast" role="status" aria-live="polite" hidden></div>
</body>
"""


_JUDGE_BODY = r"""
<body>
  <a class="skip-link" href="#judge-main">Skip to receipt lookup</a>
  <header class="topbar">
    <div class="brand" aria-label="AIGC by RegenExcalibur">
      <span class="brand-mark" aria-hidden="true">ΩX</span>
      <span class="brand-copy">
        <strong>AIGC</strong>
        <span>Provider-free evidence surface</span>
      </span>
    </div>
    <span class="connection-state">Read only</span>
  </header>

  <main id="judge-main" class="judge-shell" tabindex="-1">
    <section class="judge-hero" aria-labelledby="judge-title">
      <p class="eyebrow">Sanitized evidence · No provider authority</p>
      <h1 id="judge-title">Verify the receipt, not the rhetoric.</h1>
      <p class="lede">
        This isolated surface can read a published AIGC evidence receipt. It
        cannot invoke Gemini, inspect private opportunity content, approve
        work, change runtime controls, or perform an external action.
      </p>
    </section>

    <section class="panel" aria-labelledby="lookup-heading">
      <div class="panel-header">
        <div>
          <h2 id="lookup-heading">Receipt lookup</h2>
          <p>
            Enter the exact published receipt identifier and judge credential.
            The credential is held in page memory only for this lookup.
          </p>
        </div>
        <span class="panel-index" aria-hidden="true">READ</span>
      </div>

      <form id="judge-form">
        <div class="form-grid">
          <div class="field">
            <label for="judge-token">Judge access token</label>
            <input
              id="judge-token"
              name="judge_token"
              type="password"
              maxlength="4096"
              autocomplete="current-password"
              required
            >
          </div>
          <div class="field">
            <label for="receipt-id">Published receipt ID</label>
            <input
              id="receipt-id"
              name="receipt_id"
              maxlength="55"
              pattern="AIGC-JUDGE-RECEIPT-[A-Fa-f0-9-]+"
              placeholder="AIGC-JUDGE-RECEIPT-…"
              required
            >
          </div>
        </div>
        <div class="actions">
          <button class="button" id="load-receipt-button" type="submit">
            Load sanitized receipt
          </button>
          <button
            class="button button-link"
            id="clear-judge-button"
            type="button"
          >
            Clear credential
          </button>
        </div>
        <div
          id="judge-error"
          class="error-summary"
          role="alert"
          tabindex="-1"
          hidden
        ></div>
      </form>
    </section>

    <section
      class="panel"
      id="judge-result"
      aria-labelledby="judge-result-heading"
      tabindex="-1"
      hidden
    >
      <div class="panel-header">
        <div>
          <h2 id="judge-result-heading">Published evidence</h2>
          <p>
            A valid content binding does not independently prove every
            real-world claim. Review the declared evidence basis and limits.
          </p>
        </div>
        <span class="panel-index" aria-hidden="true">PROOF</span>
      </div>
      <dl id="judge-receipt-grid" class="receipt-grid"></dl>
      <details>
        <summary>Inspect complete sanitized receipt</summary>
        <pre id="judge-raw-response"></pre>
      </details>
    </section>
  </main>

  <div id="judge-toast" class="toast" role="status" aria-live="polite" hidden></div>
</body>
"""


_OPERATOR_SCRIPT = r"""
"use strict";

const byId = (id) => document.getElementById(id);

const state = {
  token: "",
  label: "",
  connected: false,
  configured: false,
  ready: false,
  stopActive: false,
  currentRunId: "",
  currentWorkflow: null,
  idempotencyKey: "",
};

const receiptFields = [
  ["run_id", "Run ID"],
  ["event_id", "Event ID"],
  ["record_sha256", "Record SHA-256"],
  ["state", "Runtime state"],
  ["stop_epoch", "Stop epoch"],
  ["reserved_tokens", "Reserved tokens"],
  ["actual_tokens", "Actual tokens"],
  ["model", "Resolved model"],
  ["source_revision", "Source revision"],
  ["runtime_revision", "Runtime revision"],
  ["image_digest", "Image digest"],
  ["execution_event_id", "Execution event"],
  ["evidence_object_uri", "Evidence object"],
  ["evidence_generation", "Evidence generation"],
  ["decision_event_id", "Decision event"],
  ["decision_generation", "Decision generation"],
];

function authHeaders(jsonBody = false) {
  const headers = {
    "X-AIGC-Operator-Token": state.token,
    "X-AIGC-Operator-Label": state.label,
  };
  if (jsonBody) {
    headers["Content-Type"] = "application/json";
  }
  return headers;
}

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return {detail: "The service returned an unexpected response."};
}

async function apiRequest(path, options = {}) {
  const response = await fetch(path, options);
  const body = await parseResponse(response);
  if (!response.ok) {
    const error = new Error(errorMessage(body, response.status));
    error.status = response.status;
    error.body = body;
    throw error;
  }
  return {status: response.status, body};
}

function errorMessage(body, status) {
  const detail = body && body.detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      const location = Array.isArray(item.loc)
        ? item.loc.filter((part) => part !== "body").join(" → ")
        : "request";
      return location + ": " + String(item.msg || "Invalid value");
    }).join(" · ");
  }
  if (detail && typeof detail === "object") {
    return String(detail.message || detail.status || "Request failed");
  }
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  return "Request failed with status " + String(status) + ".";
}

function setText(id, value, fallback = "—") {
  byId(id).textContent = value === null || value === undefined || value === ""
    ? fallback
    : String(value);
}

function setError(id, message) {
  const node = byId(id);
  node.textContent = message || "";
  node.hidden = !message;
  if (message) {
    node.focus();
  }
}

function setBusy(button, busy, busyLabel) {
  if (!button.dataset.defaultLabel) {
    button.dataset.defaultLabel = button.textContent.trim();
  }
  button.disabled = busy;
  button.textContent = busy
    ? busyLabel
    : button.dataset.defaultLabel;
}

let toastTimer = null;
function showToast(message) {
  const toast = byId("toast");
  toast.textContent = message;
  toast.hidden = false;
  if (toastTimer) {
    window.clearTimeout(toastTimer);
  }
  toastTimer = window.setTimeout(() => {
    toast.hidden = true;
  }, 5000);
}

function updateFlow(activeStep) {
  const order = ["connect", "intake", "review", "decide"];
  const activeIndex = order.indexOf(activeStep);
  document.querySelectorAll("[data-flow-step]").forEach((item) => {
    const index = order.indexOf(item.dataset.flowStep);
    item.classList.toggle("is-active", index === activeIndex);
    item.classList.toggle(
      "is-complete",
      activeIndex >= 0 && index < activeIndex,
    );
  });
}

function setConnected(connected) {
  state.connected = connected;
  byId("app-shell").hidden = !connected;
  byId("disconnect-button").hidden = !connected;
  byId("connect-button").hidden = connected;
  const indicator = byId("connection-state");
  indicator.textContent = connected
    ? "Operator credential active"
    : "Not connected";
  indicator.classList.toggle("is-connected", connected);
  updateFlow(connected ? "intake" : "connect");
}

function resetCredential() {
  state.token = "";
  state.label = "";
  state.connected = false;
  state.currentRunId = "";
  state.currentWorkflow = null;
  state.idempotencyKey = "";
  byId("operator-token").value = "";
  byId("operator-label").value = "";
  setConnected(false);
}

async function checkReadiness() {
  try {
    const response = await fetch("/readyz");
    const body = await parseResponse(response);
    return {ok: response.ok, body};
  } catch (_error) {
    return {ok: false, body: null};
  }
}

async function refreshEmergencyState() {
  try {
    const result = await apiRequest(
      "/api/gemini/runtime/emergency-stop",
      {headers: authHeaders()},
    );
    state.stopActive = Boolean(result.body.active);
    setText(
      "stop-state",
      state.stopActive
        ? "ACTIVE · epoch " + String(result.body.stop_epoch)
        : "Inactive · epoch " + String(result.body.stop_epoch),
    );
    refreshRuntimeGate();
    return result.body;
  } catch (error) {
    state.stopActive = true;
    setText("stop-state", "Control unavailable");
    refreshRuntimeGate();
    throw error;
  }
}

function refreshRuntimeGate() {
  const assessmentAllowed = (
    state.connected
    && state.configured
    && state.ready
    && !state.stopActive
  );
  byId("assess-button").disabled = !assessmentAllowed;
  if (state.stopActive) {
    byId("system-banner").classList.add("is-critical");
    setText("system-banner-title", "Emergency stop is active");
    setText(
      "system-banner-copy",
      "New Gemini assessments are blocked until a separately authenticated runtime administrator clears the stop.",
    );
    setText("assessment-status", "Assessment submission is blocked.");
  } else if (!state.configured) {
    byId("system-banner").classList.remove("is-critical");
    setText("system-banner-title", "Provider configuration is incomplete");
    setText(
      "system-banner-copy",
      "The workspace is available for inspection, but no model call can run until the approved configuration is complete.",
    );
    setText("assessment-status", "Gemini workflow is disabled.");
  } else if (!state.ready) {
    byId("system-banner").classList.remove("is-critical");
    setText("system-banner-title", "Observed readiness has not passed");
    setText(
      "system-banner-copy",
      "Configured does not mean ready. Resolve the reported dependency gate before execution.",
    );
    setText("assessment-status", "Waiting for observed readiness.");
  } else {
    byId("system-banner").classList.remove("is-critical");
    setText("system-banner-title", "Governed runtime ready");
    setText(
      "system-banner-copy",
      "Submission is enabled. Human review and the external-action lock remain mandatory.",
    );
    setText("assessment-status", "Ready for one governed assessment.");
  }
}

async function connectOperator(event) {
  event.preventDefault();
  setError("connection-error", "");
  const token = byId("operator-token").value;
  const label = byId("operator-label").value.trim();
  if (!token || !label) {
    setError(
      "connection-error",
      "Enter both the operator label and approved credential.",
    );
    return;
  }

  state.token = token;
  state.label = label;
  byId("operator-token").value = "";
  const button = byId("connect-button");
  setBusy(button, true, "Checking access…");

  try {
    const statusResult = await apiRequest(
      "/api/gemini/status",
      {headers: authHeaders()},
    );
    const status = statusResult.body;
    state.configured = Boolean(status.configured);
    setText(
      "provider-state",
      state.configured ? "Configured" : "Disabled / incomplete",
    );
    setText("model-value", status.model);
    setText("location-value", status.location);
    setText("evidence-value", status.evidence_backend);
    setConnected(true);

    const readiness = await checkReadiness();
    state.ready = Boolean(
      readiness.ok && readiness.body && readiness.body.ready,
    );
    setText(
      "readiness-state",
      state.ready ? "Observed ready" : "Not ready",
    );
    try {
      await refreshEmergencyState();
    } catch (_error) {
      showToast("Runtime-control state could not be read.");
    }
    refreshRuntimeGate();
    byId("intake-panel").focus();
  } catch (error) {
    resetCredential();
    setError(
      "connection-error",
      error.status === 401
        ? "Authentication failed. Check the approved operator credential."
        : error.message,
    );
  } finally {
    setBusy(button, false, "");
  }
}

function currentConstraints() {
  return byId("constraints").value
    .split("\n")
    .map((value) => value.trim())
    .filter(Boolean);
}

function createIdempotencyKey() {
  if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") {
    return "operator-ui-" + globalThis.crypto.randomUUID();
  }
  const values = new Uint32Array(4);
  globalThis.crypto.getRandomValues(values);
  return "operator-ui-" + Array.from(values, (value) => (
    value.toString(16).padStart(8, "0")
  )).join("");
}

function classifyExecutionError(error) {
  if (error.status === 409) {
    return "The workflow state or idempotency binding conflicts with this request. Do not alter and resend blindly; inspect the exact run.";
  }
  if (error.status === 429) {
    return "The governed quota was reached. Wait for the reported window; do not bypass the limit.";
  }
  if (error.status === 502) {
    return "The provider failed or its outcome may be uncertain. Do not automatically retry. Reconciliation is required.";
  }
  if (error.status === 503) {
    return "A runtime control, evidence store, or approved configuration is unavailable. No success is claimed.";
  }
  if (!error.status) {
    return "The network outcome is unknown. Do not automatically retry the model call.";
  }
  return error.message;
}

async function submitAssessment(event) {
  event.preventDefault();
  setError("assessment-error", "");
  const form = byId("intake-form");
  if (!form.reportValidity()) {
    return;
  }
  const constraints = currentConstraints();
  if (constraints.length > 20) {
    setError(
      "assessment-error",
      "Use no more than 20 non-empty constraints.",
    );
    return;
  }
  const longConstraint = constraints.find((value) => value.length > 400);
  if (longConstraint) {
    setError(
      "assessment-error",
      "Each constraint must contain 400 characters or fewer.",
    );
    return;
  }

  const payload = {
    title: byId("opportunity-title").value.trim(),
    source_url: byId("source-url").value.trim(),
    description: byId("opportunity-description").value.trim(),
    constraints,
    ai_assistance_permitted: byId("ai-permitted").checked,
    ai_disclosure_required: true,
  };
  state.idempotencyKey = createIdempotencyKey();
  const button = byId("assess-button");
  setBusy(button, true, "Assessing once…");
  setText("assessment-status", "Submitting one idempotent request…");

  try {
    const result = await apiRequest(
      "/api/gemini/workflows",
      {
        method: "POST",
        headers: {
          ...authHeaders(true),
          "Idempotency-Key": state.idempotencyKey,
        },
        body: JSON.stringify(payload),
      },
    );
    state.currentRunId = result.body.run_id || "";
    byId("resume-run-id").value = state.currentRunId;
    if (result.status === 202) {
      setText(
        "assessment-status",
        "An identical request is already executing. The POST was not repeated.",
      );
      showToast("Execution is in progress; use Read run to reconcile.");
      return;
    }
    state.currentWorkflow = result.body;
    renderWorkflow(result.body);
    setText("assessment-status", "Assessment recorded for human review.");
    updateFlow("review");
    byId("review-panel").focus();
  } catch (error) {
    setText("assessment-status", "Assessment not confirmed.");
    setError("assessment-error", classifyExecutionError(error));
  } finally {
    setBusy(button, false, "");
    refreshRuntimeGate();
  }
}

function clearNode(node) {
  node.replaceChildren();
}

function renderList(id, values, emptyText) {
  const root = byId(id);
  clearNode(root);
  if (!Array.isArray(values) || values.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-copy";
    empty.textContent = emptyText;
    root.appendChild(empty);
    return;
  }
  const list = document.createElement("ul");
  list.className = "clean-list";
  values.forEach((value) => {
    const item = document.createElement("li");
    item.textContent = String(value);
    list.appendChild(item);
  });
  root.appendChild(list);
}

function renderEvidence(values) {
  const root = byId("evidence-basis");
  clearNode(root);
  if (!Array.isArray(values) || values.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-copy";
    empty.textContent = "No evidence pointers were returned.";
    root.appendChild(empty);
    return;
  }
  values.forEach((value) => {
    const item = document.createElement("article");
    item.className = "evidence-item";
    const pointer = document.createElement("strong");
    pointer.textContent = (
      String(value.input_pointer || "input")
      + " · "
      + String(value.impact || "neutral")
    );
    const observation = document.createElement("p");
    observation.textContent = String(value.observation || "");
    item.append(pointer, observation);
    root.appendChild(item);
  });
}

function renderRisks(values) {
  const root = byId("risk-list");
  clearNode(root);
  if (!Array.isArray(values) || values.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-copy";
    empty.textContent = "No explicit risk item was returned.";
    root.appendChild(empty);
    return;
  }
  values.forEach((value) => {
    const item = document.createElement("article");
    item.className = "risk-item";
    const heading = document.createElement("strong");
    heading.textContent = (
      String(value.severity || "unknown").toUpperCase()
      + " · "
      + String(value.category || "risk")
    );
    const description = document.createElement("p");
    description.textContent = String(value.description || "");
    const mitigation = document.createElement("p");
    mitigation.textContent = "Mitigation: " + String(value.mitigation || "—");
    item.append(heading, description, mitigation);
    root.appendChild(item);
  });
}

function allowedDecisions(data) {
  const controls = data && data.controls;
  return controls && Array.isArray(controls.allowed_decisions)
    ? controls.allowed_decisions
    : [];
}

function configureDecisionPanel(data) {
  const allowed = new Set(allowedDecisions(data));
  const decisionInputs = Array.from(
    document.querySelectorAll('input[name="decision"]'),
  );
  decisionInputs.forEach((input) => {
    input.disabled = !allowed.has(input.value);
    input.checked = false;
  });
  const firstAllowed = decisionInputs.find((input) => !input.disabled);
  if (firstAllowed) {
    firstAllowed.checked = true;
  }
  byId("revision-field").hidden = (
    !firstAllowed || firstAllowed.value !== "revise"
  );
  byId("decision-panel").hidden = allowed.size === 0;
  byId("decision-outcome").hidden = true;
}

function renderWorkflow(data) {
  const payload = data.payload || {};
  const assessment = payload.assessment || {};
  const policy = payload.policy || {};
  const score = Number.isFinite(Number(assessment.fit_score))
    ? Number(assessment.fit_score)
    : 0;
  byId("review-panel").hidden = false;
  byId("evidence-panel").hidden = false;
  setText("fit-score", score);
  byId("fit-score-meter").value = score;
  byId("fit-score-meter").textContent = String(score) + " out of 100";
  setText("recommendation", assessment.recommendation, "Unavailable");
  setText("workflow-status-tag", data.status);
  setText("policy-outcome-tag", "Policy: " + String(policy.outcome || "—"));
  setText(
    "model-call-tag",
    data.model_api_call_performed
      ? "Model call: confirmed"
      : "Model call: not performed",
  );
  setText(
    "review-boundary",
    payload.assessment_grounding === "supplied_input_only_not_externally_verified"
      ? "Generated from supplied input only; claims are not independently verified."
      : "Review the exact evidence and grounding boundary.",
  );
  renderList("rationale", assessment.rationale, "No rationale returned.");
  renderList(
    "policy-reasons",
    policy.reasons,
    "No deterministic policy reason returned.",
  );
  renderEvidence(assessment.evidence_basis);
  renderRisks(assessment.risks);
  renderList("assumptions", assessment.assumptions, "No assumptions listed.");
  renderList(
    "clarifying-questions",
    assessment.clarifying_questions,
    "No clarifying question listed.",
  );
  renderList(
    "proposed-scope",
    assessment.proposed_scope,
    "No internal scope proposed.",
  );
  setText("ai-disclosure", assessment.ai_use_disclosure);
  configureDecisionPanel(data);
  renderReceipt(data, data.runtime_receipt || {});
}

function renderReceipt(record, receipt) {
  const root = byId("receipt-grid");
  clearNode(root);
  const merged = {...record, ...receipt};
  receiptFields.forEach(([key, label]) => {
    if (
      merged[key] === null
      || merged[key] === undefined
      || merged[key] === ""
    ) {
      return;
    }
    const wrapper = document.createElement("div");
    wrapper.className = "receipt-item";
    const term = document.createElement("dt");
    term.textContent = label;
    const value = document.createElement("dd");
    value.textContent = String(merged[key]);
    wrapper.append(term, value);
    root.appendChild(wrapper);
  });
  byId("raw-response").textContent = JSON.stringify(
    state.currentWorkflow || record,
    null,
    2,
  );
}

function selectedDecision() {
  const checked = document.querySelector(
    'input[name="decision"]:checked',
  );
  return checked ? checked.value : "";
}

function syncRevisionRequirement() {
  const revise = selectedDecision() === "revise";
  byId("revision-field").hidden = !revise;
  byId("revision-instructions").required = revise;
}

async function submitDecision(event) {
  event.preventDefault();
  setError("decision-error", "");
  if (!state.currentRunId) {
    setError("decision-error", "No exact workflow run is selected.");
    return;
  }
  const decision = selectedDecision();
  const allowed = new Set(allowedDecisions(state.currentWorkflow));
  if (!allowed.has(decision)) {
    setError(
      "decision-error",
      "The server did not admit this decision for the current workflow state.",
    );
    return;
  }
  syncRevisionRequirement();
  const form = byId("decision-form");
  if (!form.reportValidity()) {
    return;
  }

  const button = byId("decision-button");
  setBusy(button, true, "Recording once…");
  setText("decision-status", "Creating one append-only attestation…");
  try {
    const result = await apiRequest(
      "/api/gemini/workflows/"
        + encodeURIComponent(state.currentRunId)
        + "/decision",
      {
        method: "POST",
        headers: authHeaders(true),
        body: JSON.stringify({
          decision,
          reason: byId("decision-reason").value.trim(),
          revision_instructions: byId("revision-instructions").value.trim(),
        }),
      },
    );
    const prior = state.currentWorkflow || {};
    state.currentWorkflow = {
      ...prior,
      decision: result.body,
      controls: result.body.controls,
    };
    renderDecision(result.body);
    renderReceipt(result.body, result.body.decision_receipt || {});
    setText("decision-status", "Decision receipt recorded.");
    updateFlow("decide");
    showToast("Internal-use decision recorded. External actions remain locked.");
  } catch (error) {
    setText("decision-status", "Decision not confirmed.");
    setError("decision-error", error.message);
    if (error.status === 409) {
      try {
        await readRun(state.currentRunId, false);
      } catch (_readError) {
        showToast("Conflict detected; exact run could not be reconciled.");
      }
    }
  } finally {
    setBusy(button, false, "");
  }
}

function renderDecision(record) {
  byId("decision-panel").hidden = false;
  byId("decision-form").hidden = true;
  byId("decision-outcome").hidden = false;
  const payload = record.payload || {};
  setText(
    "decision-outcome-title",
    "Recorded: " + String(payload.decision || record.status || "decision"),
  );
  setText(
    "decision-outcome-copy",
    String(payload.reason || "")
      + " External action allowed: false. Identity claim: "
      + String(payload.identity_claim_scope || "operator attestation"),
  );
}

async function readRun(runId, focusResult = true) {
  const result = await apiRequest(
    "/api/gemini/workflows/" + encodeURIComponent(runId),
    {headers: authHeaders()},
  );
  const events = Array.isArray(result.body.events) ? result.body.events : [];
  const execution = events.find(
    (item) => item.event_type === "gemini_execution",
  );
  const decision = events.find(
    (item) => item.event_type === "operator_decision",
  );
  state.currentRunId = runId;
  byId("resume-run-id").value = runId;
  if (!execution) {
    setText(
      "assessment-status",
      "Run state: " + String(result.body.current_status || "unknown"),
    );
    showToast("No receipt-bound assessment is available for this run.");
    return result.body;
  }
  const projected = {
    ...execution,
    controls: result.body.controls,
    runtime_receipt: result.body.runtime_receipt,
  };
  state.currentWorkflow = projected;
  renderWorkflow(projected);
  if (decision) {
    state.currentWorkflow = {
      ...projected,
      decision,
    };
    renderDecision(decision);
    renderReceipt(decision, result.body.runtime_receipt || {});
  }
  updateFlow(decision ? "decide" : "review");
  if (focusResult) {
    byId("review-panel").focus();
  }
  return result.body;
}

async function submitResume(event) {
  event.preventDefault();
  setError("assessment-error", "");
  const form = byId("resume-form");
  if (!form.reportValidity()) {
    return;
  }
  try {
    await readRun(byId("resume-run-id").value.trim());
  } catch (error) {
    setError("assessment-error", error.message);
  }
}

async function activateStop(event) {
  event.preventDefault();
  setError("stop-error", "");
  const form = byId("stop-form");
  if (!form.reportValidity()) {
    return;
  }
  const button = byId("stop-button");
  setBusy(button, true, "Activating stop…");
  try {
    const result = await apiRequest(
      "/api/gemini/runtime/emergency-stop",
      {
        method: "POST",
        headers: authHeaders(true),
        body: JSON.stringify({
          reason: byId("stop-reason").value.trim(),
        }),
      },
    );
    state.stopActive = Boolean(result.body.active);
    setText(
      "stop-state",
      "ACTIVE · epoch " + String(result.body.stop_epoch),
    );
    refreshRuntimeGate();
    showToast("Durable emergency stop activated.");
  } catch (error) {
    setError("stop-error", error.message);
  } finally {
    setBusy(button, false, "");
  }
}

byId("connection-form").addEventListener("submit", connectOperator);
byId("disconnect-button").addEventListener("click", resetCredential);
byId("intake-form").addEventListener("submit", submitAssessment);
byId("resume-form").addEventListener("submit", submitResume);
byId("decision-form").addEventListener("submit", submitDecision);
byId("stop-form").addEventListener("submit", activateStop);
byId("refresh-stop-button").addEventListener("click", async () => {
  setError("stop-error", "");
  try {
    await refreshEmergencyState();
    showToast("Emergency-stop state refreshed.");
  } catch (error) {
    setError("stop-error", error.message);
  }
});
byId("opportunity-description").addEventListener("input", (event) => {
  setText(
    "description-count",
    event.target.value.length.toLocaleString() + " / 12,000",
  );
});
document.querySelectorAll('input[name="decision"]').forEach((input) => {
  input.addEventListener("change", syncRevisionRequirement);
});

setConnected(false);
"""


_JUDGE_SCRIPT = r"""
"use strict";

const byId = (id) => document.getElementById(id);
const judgeState = {token: ""};
let judgeToastTimer = null;

function judgeErrorMessage(body, status) {
  if (body && typeof body.detail === "string") {
    return body.detail;
  }
  return "Receipt lookup failed with status " + String(status) + ".";
}

function setJudgeError(message) {
  const node = byId("judge-error");
  node.textContent = message || "";
  node.hidden = !message;
  if (message) {
    node.focus();
  }
}

function showJudgeToast(message) {
  const toast = byId("judge-toast");
  toast.textContent = message;
  toast.hidden = false;
  if (judgeToastTimer) {
    window.clearTimeout(judgeToastTimer);
  }
  judgeToastTimer = window.setTimeout(() => {
    toast.hidden = true;
  }, 5000);
}

function appendJudgeField(root, label, value) {
  if (value === null || value === undefined || value === "") {
    return;
  }
  const wrapper = document.createElement("div");
  wrapper.className = "receipt-item";
  const term = document.createElement("dt");
  term.textContent = label;
  const description = document.createElement("dd");
  description.textContent = String(value);
  wrapper.append(term, description);
  root.appendChild(wrapper);
}

function renderJudgeReceipt(receipt) {
  const root = byId("judge-receipt-grid");
  root.replaceChildren();
  const claim = receipt.claim || {};
  [
    ["Receipt ID", receipt.receipt_id],
    ["Publication state", receipt.publication_state],
    ["Published at", receipt.published_at],
    ["Project", claim.project_slug],
    ["Business identity", claim.business_identity],
    ["Capability", claim.capability],
    ["Evidence basis", claim.evidence_basis],
    ["Workflow run", claim.workflow_run_id],
    ["Source revision", claim.source_revision],
    ["Runtime revision", claim.runtime_revision],
    ["Evidence SHA-256", claim.evidence_record_sha256],
    ["Evidence generation", claim.evidence_generation],
    ["Model call status", claim.model_api_call_status],
    ["Human review state", claim.human_review_state],
    ["External action performed", claim.external_action_performed],
    ["Receipt SHA-256", receipt.receipt_sha256],
  ].forEach(([label, value]) => appendJudgeField(root, label, value));
  byId("judge-raw-response").textContent = JSON.stringify(receipt, null, 2);
  byId("judge-result").hidden = false;
  byId("judge-result").focus();
}

async function loadJudgeReceipt(event) {
  event.preventDefault();
  setJudgeError("");
  const form = byId("judge-form");
  if (!form.reportValidity()) {
    return;
  }
  const suppliedToken = byId("judge-token").value;
  if (suppliedToken) {
    judgeState.token = suppliedToken;
    byId("judge-token").value = "";
  }
  if (!judgeState.token) {
    setJudgeError("Enter the approved judge credential.");
    return;
  }
  const button = byId("load-receipt-button");
  button.disabled = true;
  const defaultLabel = button.textContent;
  button.textContent = "Reading receipt…";
  try {
    const receiptId = byId("receipt-id").value.trim();
    const response = await fetch(
      "/api/judge/receipts/" + encodeURIComponent(receiptId),
      {headers: {"X-AIGC-Judge-Token": judgeState.token}},
    );
    const body = await response.json();
    if (!response.ok) {
      throw new Error(judgeErrorMessage(body, response.status));
    }
    renderJudgeReceipt(body);
    showJudgeToast("Sanitized receipt loaded. No provider call was made.");
  } catch (error) {
    setJudgeError(error.message);
  } finally {
    button.disabled = false;
    button.textContent = defaultLabel;
  }
}

function clearJudgeCredential() {
  judgeState.token = "";
  byId("judge-token").value = "";
  byId("judge-result").hidden = true;
  setJudgeError("");
  showJudgeToast("Judge credential cleared from page memory.");
}

byId("judge-form").addEventListener("submit", loadJudgeReceipt);
byId("clear-judge-button").addEventListener("click", clearJudgeCredential);
"""
