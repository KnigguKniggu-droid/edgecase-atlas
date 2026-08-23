"""Static presentation layer for the public EdgeCase Atlas workbench."""

APP_CSS = r"""
<style>
:root {
  --atlas-bg: #07090d;
  --atlas-panel: #10151d;
  --atlas-panel-raised: #151c26;
  --atlas-line: #2a3544;
  --atlas-line-strong: #3c4b60;
  --atlas-ink: #eef3f8;
  --atlas-muted: #aab6c4;
  --atlas-faint: #788697;
  --atlas-red: #e4544b;
  --atlas-red-deep: #b83a32;
  --atlas-cyan: #66d9d0;
  --atlas-amber: #f2b84b;
  --atlas-green: #42cf8d;
  --atlas-radius: 10px;
}

[data-testid="stAppViewContainer"] {
  background: var(--atlas-bg);
}

#MainMenu,
[data-testid="stToolbar"] {
  visibility: hidden;
}

[data-testid="stCaptionContainer"] {
  color: var(--atlas-muted);
}

.main .block-container {
  max-width: 1280px;
  padding-top: 2.25rem;
  padding-bottom: 5rem;
}

h1, h2, h3 {
  text-wrap: balance;
  letter-spacing: -0.025em;
}

p {
  text-wrap: pretty;
}

.st-key-atlas_hero {
  position: relative;
  overflow: hidden;
  padding: 1.65rem 1.75rem 1.5rem;
  background: var(--atlas-panel);
  border: 1px solid var(--atlas-line-strong);
  border-radius: 14px;
}

.st-key-atlas_hero::after {
  content: "";
  position: absolute;
  inset: 0 0 auto;
  height: 3px;
  background: linear-gradient(
    90deg,
    var(--atlas-red) 0 22%,
    var(--atlas-amber) 22% 35%,
    var(--atlas-cyan) 35% 100%
  );
}

.st-key-atlas_hero h1 {
  margin: 0;
  font-size: 3.05rem;
  line-height: 0.98;
  letter-spacing: -0.035em;
}

.st-key-atlas_hero [data-testid="stMarkdownContainer"] p {
  max-width: 68ch;
}

.st-key-atlas_brandline {
  color: var(--atlas-cyan);
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.78rem;
  font-weight: 600;
}

.st-key-atlas_thesis p {
  margin: 0.25rem 0 0.75rem;
  color: var(--atlas-ink);
  font-size: 1.38rem;
  font-weight: 500;
  line-height: 1.35;
}

.st-key-atlas_process {
  margin-top: 0.4rem;
  padding-top: 1rem;
  border-top: 1px solid var(--atlas-line);
}

.st-key-atlas_process [data-testid="stCaptionContainer"] {
  margin-bottom: 0.45rem;
  color: var(--atlas-muted);
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.1em;
}

.st-key-atlas_process_steps {
  gap: 0.45rem;
  flex-wrap: wrap;
}

.st-key-atlas_hero [data-testid="stBadge"],
.st-key-atlas_process [data-testid="stBadge"] {
  border: 1px solid var(--atlas-line-strong);
  border-radius: 999px;
}

.st-key-atlas_workbench_title {
  margin-top: 2.3rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--atlas-line);
}

.st-key-atlas_controls,
.st-key-atlas_specimen {
  min-height: 100%;
  padding: 1.2rem 1.25rem;
  background: var(--atlas-panel);
  border: 1px solid var(--atlas-line);
  border-radius: var(--atlas-radius);
}

.st-key-atlas_controls h3,
.st-key-atlas_specimen h3 {
  margin-top: 0;
}

.st-key-atlas_run_submit button {
  min-height: 3.1rem;
  width: 100%;
  border-radius: 7px;
  font-weight: 700;
  letter-spacing: 0.01em;
}

.st-key-atlas_source_panel,
.st-key-atlas_follow_panel {
  padding: 1rem;
  background: #0c1118;
  border: 1px solid var(--atlas-line);
  border-radius: 8px;
}

.st-key-atlas_source_panel {
  border-color: #32706e;
}

.st-key-atlas_follow_panel {
  border-color: #8c3d39;
}

.st-key-atlas_mutation_panel {
  padding: 0.8rem 0.4rem;
  color: var(--atlas-amber);
  text-align: center;
}

.st-key-atlas_mutation_panel code {
  white-space: normal;
}

.st-key-atlas_violation_banner {
  margin-top: 2rem;
  padding: 1.15rem 1.25rem;
  background: #211314;
  border: 1px solid #793834;
  border-radius: var(--atlas-radius);
}

.st-key-atlas_faultline {
  padding: 1.25rem;
  background: var(--atlas-panel);
  border: 1px solid var(--atlas-line-strong);
  border-radius: var(--atlas-radius);
}

.st-key-atlas_source_decision,
.st-key-atlas_failure_decision,
.st-key-atlas_delta {
  min-height: 11.5rem;
  padding: 1rem;
  border-radius: 8px;
}

.st-key-atlas_source_decision {
  background: #0c1719;
  border: 1px solid #2c6562;
}

.st-key-atlas_failure_decision {
  background: #211314;
  border: 1px solid #793834;
}

.st-key-atlas_delta {
  background: #18150e;
  border: 1px solid #6c5628;
}

.st-key-atlas_source_decision code,
.st-key-atlas_failure_decision code,
.st-key-atlas_delta code {
  color: var(--atlas-ink);
}

[data-testid="stMetric"] {
  background: var(--atlas-panel-raised);
  border: 1px solid var(--atlas-line);
  border-radius: 8px;
  padding: 0.9rem 1rem;
}

[data-testid="stMetricLabel"] {
  color: var(--atlas-muted);
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

[data-testid="stMetricValue"] {
  color: var(--atlas-ink);
  font-family: "IBM Plex Mono", monospace;
}

[data-testid="stDataFrame"],
[data-testid="stTable"] {
  border: 1px solid var(--atlas-line);
  border-radius: 8px;
  overflow: hidden;
}

[data-testid="stTable"] table {
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.78rem;
}

[data-baseweb="tab-list"] {
  gap: 0.25rem;
  border-bottom: 1px solid var(--atlas-line);
}

[data-baseweb="tab"] {
  font-weight: 600;
}

.st-key-atlas_downloads button {
  min-height: 2.6rem;
}

.st-key-atlas_footer {
  margin-top: 3rem;
  padding-top: 1.3rem;
  border-top: 1px solid var(--atlas-line);
  color: var(--atlas-faint);
}

button:focus-visible,
input:focus-visible,
textarea:focus-visible,
[role="combobox"]:focus-visible {
  outline: 3px solid rgba(102, 217, 208, 0.65) !important;
  outline-offset: 2px;
}

@media (max-width: 760px) {
  .main .block-container {
    padding: 1rem 0.85rem 3rem;
  }

  .st-key-atlas_hero {
    padding: 1.35rem 1.1rem 1.2rem;
  }

  .st-key-atlas_hero h1 {
    font-size: 2.15rem;
    line-height: 1.04;
  }

  .st-key-atlas_thesis p {
    font-size: 1.08rem;
  }

  .st-key-atlas_source_decision,
  .st-key-atlas_failure_decision,
  .st-key-atlas_delta {
    min-height: auto;
  }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
  }
}
</style>
"""
