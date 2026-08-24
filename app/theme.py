"""Forensic product design system for the public EdgeCase Atlas surface."""

APP_CSS = r"""
<style>
:root {
  /* Semantic Color Tokens */
  --atlas-bg: #060d14;
  --atlas-surface: #0a131d;
  --atlas-panel: #0e1a26;
  --atlas-raised: #132331;
  --atlas-border: #26394a;
  --atlas-border-hot: #496176;
  --atlas-text-main: #f4f7f9;
  --atlas-text-muted: #a7b7c5;
  --atlas-text-faint: #748698;
  --atlas-accent: #58d6c8;
  --atlas-error: #ff625b;
  --atlas-error-deep: #9f302f;
  --atlas-warn: #f5bd58;
  --atlas-success: #4cda91;
  --atlas-brand-blue: #73a7ff;
  
  /* Typography Tokens */
  --atlas-font-sans: "Inter", system-ui, sans-serif;
  --atlas-font-mono: "IBM Plex Mono", monospace;
  
  /* Spacing Scale (4pt basis) */
  --atlas-space-1: 0.25rem;
  --atlas-space-2: 0.5rem;
  --atlas-space-3: 0.75rem;
  --atlas-space-4: 1rem;
  --atlas-space-6: 1.5rem;
  --atlas-space-8: 2rem;
}

[data-testid="stAppViewContainer"] {
  background-color: var(--atlas-bg);
  background-image:
    linear-gradient(rgba(88, 214, 200, 0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(88, 214, 200, 0.025) 1px, transparent 1px);
  background-size: 44px 44px;
}

[data-testid="stAppViewBlockContainer"] {
  max-width: 1320px;
  padding-top: var(--atlas-space-6);
  padding-bottom: 20px; /* Reduced from 5rem for better density */
}
/* ... rest of theme styles would be updated to use these tokens ... */


#MainMenu,
[data-testid="stStatusWidget"],
[data-testid="stAppDeployButton"] {
  visibility: hidden;
}

[data-testid="stToolbar"] {
  background: transparent;
}

h1, h2, h3 {
  color: var(--atlas-ink);
  text-wrap: balance;
  letter-spacing: -0.032em;
}

h1 { line-height: 1.02; }
h2 { margin-top: 2.15rem; }
p { text-wrap: pretty; }

[data-testid="stCaptionContainer"] {
  color: var(--atlas-muted);
}

.st-key-atlas_shell_brand {
  position: relative;
  min-height: 3.3rem;
  align-items: center;
  margin-bottom: 0.15rem;
  padding: 0.55rem 0.95rem 0.55rem 1.15rem;
  background: rgba(10, 19, 29, 0.94);
  border: 1px solid var(--atlas-line);
  border-radius: 11px 11px 0 0;
}

.st-key-atlas_shell_brand::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 5px;
  background: var(--atlas-red);
  border-radius: 10px 0 0 0;
}

.st-key-atlas_shell_brand p {
  margin: 0;
  font-family: var(--atlas-mono);
  letter-spacing: 0.12em;
}

.st-key-atlas_shell_brand strong {
  color: var(--atlas-ink);
  font-size: 0.87rem;
}

.st-key-atlas_shell_brand [data-testid="stCaptionContainer"] {
  font-family: var(--atlas-mono);
  font-size: 0.68rem;
  letter-spacing: 0.08em;
}

.st-key-atlas_shell_nav {
  gap: 0.35rem;
  align-items: center;
  margin-bottom: 1.2rem;
  padding: 0.32rem 0.45rem;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  background: rgba(10, 19, 29, 0.94);
  border: 1px solid var(--atlas-line);
  border-top: 0;
  border-radius: 0 0 11px 11px;
  scrollbar-width: thin;
}

.st-key-atlas_shell_nav [data-testid="stPageLink"] {
  flex: 1 0 auto;
}

.st-key-atlas_shell_nav [data-testid="stPageLink"] a {
  justify-content: center;
  min-height: 2.55rem;
  padding: 0.55rem 0.85rem;
  border-radius: 7px;
  color: var(--atlas-muted);
  font-family: var(--atlas-mono);
  font-size: 0.75rem;
  font-weight: 600;
  white-space: nowrap;
}

.st-key-atlas_shell_nav [data-testid="stPageLink"] a:hover,
.st-key-atlas_shell_nav [data-testid="stPageLink"] a[aria-current="page"] {
  color: var(--atlas-ink);
  background: var(--atlas-raised);
  box-shadow: inset 0 -2px 0 var(--atlas-cyan);
}

[data-testid="stNavigation"] {
  margin-bottom: 1.2rem;
  padding: 0.25rem 0.35rem;
  background: rgba(10, 19, 29, 0.94);
  border: 1px solid var(--atlas-line);
  border-top: 0;
  border-radius: 0 0 11px 11px;
}

[data-testid="stNavigation"] a {
  border-radius: 7px;
  font-weight: 600;
}

[data-testid="stNavigation"] a[aria-current="page"] {
  color: var(--atlas-ink);
  background: var(--atlas-raised);
  box-shadow: inset 0 -2px 0 var(--atlas-cyan);
}

[class*="st-key-atlas_"][class*="_intro"] {
  position: relative;
  overflow: hidden;
  margin-bottom: 1.4rem;
  padding: 2rem 2.1rem 1.8rem;
  background: var(--atlas-asphalt);
  border: 1px solid var(--atlas-line-hot);
  border-radius: 14px;
}

[class*="st-key-atlas_"][class*="_intro"]::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 5px;
  background: var(--atlas-cyan);
}

[class*="st-key-atlas_"][class*="_intro"] h1 {
  max-width: 21ch;
  margin: 0.25rem 0 0.7rem;
  font-size: clamp(2.25rem, 5vw, 4.4rem);
  letter-spacing: -0.055em;
}

[class*="st-key-atlas_"][class*="_intro"] [data-testid="stCaptionContainer"],
.st-key-atlas_home_hero [data-testid="stCaptionContainer"] {
  color: var(--atlas-cyan);
  font-family: var(--atlas-mono);
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.12em;
}

[class*="st-key-atlas_"][class*="_intro"] [data-testid="stMarkdownContainer"] p {
  max-width: 68ch;
  color: var(--atlas-muted);
  font-size: 1.08rem;
}

.st-key-atlas_home_chain {
  margin: 1.2rem 0;
  padding: 0.9rem 1.1rem;
  background: rgba(14, 26, 38, 0.75);
  border: 1px solid var(--atlas-line);
  border-left: 3px solid var(--atlas-cyan);
  border-radius: 9px;
}

.st-key-atlas_home_chain [data-testid="stCaptionContainer"] {
  color: var(--atlas-cyan);
  font-family: var(--atlas-mono);
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.12em;
}

.st-key-atlas_home_chain [data-testid="stMarkdownContainer"] p {
  margin: 0.2rem 0 0;
  color: var(--atlas-ink);
  font-size: 0.88rem;
  line-height: 1.5;
}

.st-key-atlas_home_hero {
  position: relative;
  overflow: hidden;
  min-height: 25rem;
  padding: clamp(2rem, 5vw, 4.8rem);
  background: var(--atlas-asphalt);
  border: 1px solid var(--atlas-line-hot);
  border-radius: 16px;
}

.st-key-atlas_home_hero::before {
  content: "";
  position: absolute;
  top: -30%;
  right: 9%;
  width: 1px;
  height: 165%;
  background: var(--atlas-red);
  box-shadow: 18px 0 0 rgba(255,98,91,.18), 36px 0 0 rgba(255,98,91,.08);
  transform: rotate(17deg);
}

.st-key-atlas_home_hero::after {
  content: "CONTROL / MUTATE / REPRODUCE / REDUCE / REPLAY";
  position: absolute;
  right: -9.4rem;
  bottom: 11rem;
  color: rgba(244,247,249,.19);
  font-family: var(--atlas-mono);
  font-size: 0.64rem;
  font-weight: 600;
  letter-spacing: .16em;
  transform: rotate(90deg);
}

.st-key-atlas_home_hero h2 {
  position: relative;
  z-index: 1;
  max-width: 16ch;
  margin: 0.4rem 0 1rem;
  font-size: clamp(2.65rem, 6vw, 5.5rem);
  line-height: 0.94;
  letter-spacing: -0.067em;
}

.st-key-atlas_home_hero [data-testid="stMarkdownContainer"] p {
  position: relative;
  z-index: 1;
  max-width: 59ch;
  color: var(--atlas-muted);
  font-size: 1.13rem;
  line-height: 1.62;
}

.st-key-atlas_home_trust {
  position: relative;
  z-index: 1;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 1rem;
}

[class*="st-key-atlas_"][class*="_faultline"] {
  position: relative;
  margin: 2rem 0;
  padding: 1.4rem;
  background: rgba(10, 19, 29, 0.94);
  border: 1px solid rgba(255, 98, 91, 0.45);
  border-radius: 14px;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.32), 0 0 24px rgba(255, 98, 91, 0.06);
}

[class*="st-key-atlas_"][class*="_faultline"]::before {
  content: "";
  position: absolute;
  top: 5.4rem;
  bottom: 1.3rem;
  left: 50%;
  width: 1px;
  background: var(--atlas-red);
  opacity: 0.6;
  pointer-events: none;
}

[class*="st-key-atlas_"][class*="_sequence"] {
  gap: 0.75rem;
  align-items: stretch;
}

[data-testid="stVerticalBlockBorderWrapper"] {
  background: rgba(14, 26, 38, 0.9);
  border-color: var(--atlas-line) !important;
  border-radius: 11px !important;
  box-shadow: 0 12px 34px rgba(0,0,0,.16);
}

[class*="st-key-atlas_"][class*="_mutation"] [data-testid="stVerticalBlockBorderWrapper"] {
  background: #19170f;
  border-color: #6b572d !important;
}

[class*="st-key-atlas_"][class*="_stage_3"] [data-testid="stVerticalBlockBorderWrapper"],
[class*="st-key-atlas_"][class*="_certificate"] > [data-testid="stVerticalBlockBorderWrapper"],
[class*="st-key-atlas_"][class*="_result"] > [data-testid="stVerticalBlockBorderWrapper"] {
  border-color: rgba(255, 98, 91, 0.55) !important;
}

[class*="st-key-atlas_"][class*="_pipeline"] {
  margin: 2rem 0;
  padding: 1.25rem;
  background: rgba(10, 19, 29, 0.74);
  border: 1px solid var(--atlas-line);
  border-radius: 13px;
}

[class*="st-key-atlas_"][class*="_stages"] {
  gap: 0.6rem;
  align-items: stretch;
}

[data-testid="stMetric"] {
  min-height: 6.2rem;
  padding: 0.95rem 1rem;
  background: var(--atlas-raised);
  border: 1px solid var(--atlas-line) !important;
  border-radius: 9px !important;
}

[data-testid="stMetricLabel"] {
  color: var(--atlas-muted);
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.085em;
  text-transform: uppercase;
}

[data-testid="stMetricValue"] {
  color: var(--atlas-ink);
  font-family: var(--atlas-mono);
  letter-spacing: -0.035em;
}

[data-testid="stForm"] {
  margin-bottom: 1.5rem;
  padding: 1.4rem;
  background: rgba(10, 19, 29, 0.86);
  border: 1px solid var(--atlas-line) !important;
  border-radius: 13px;
}

[data-testid="stFileUploader"] section {
  min-height: 9rem;
  background: var(--atlas-asphalt);
  border: 1px dashed var(--atlas-line-hot);
  border-radius: 10px;
}

/* White on the deep emerald, which is 5.47 against white. The previous rule painted near-black
   text over a colour variable, so wherever that variable did not resolve the label vanished
   into the background. Red is reserved for failure meaning, so the run button should not be red. */
button[kind="primary"] {
  min-height: 2.9rem;
  padding-inline: 1.25rem;
  color: #ffffff !important;
  background: #0f766e !important;
  border: 1px solid #14a08f !important;
  border-radius: 8px !important;
  box-shadow: 0 8px 26px rgba(15, 118, 110, 0.28);
  font-weight: 700 !important;
}

button[kind="primary"]:hover {
  background: #14907f !important;
  color: #ffffff !important;
  transform: translateY(-1px);
}

button[kind="secondary"] {
  min-height: 2.7rem;
  border-color: var(--atlas-line-hot) !important;
  border-radius: 8px !important;
}

[data-testid="stDownloadButton"] button {
  border-color: #3c6f73 !important;
  color: var(--atlas-cyan) !important;
}

[data-testid="stAlert"] {
  border-radius: 9px;
}

[data-testid="stCode"] {
  border: 1px solid var(--atlas-line);
  border-radius: 8px;
}

[data-baseweb="select"] > div,
[data-baseweb="input"] > div,
textarea {
  background: var(--atlas-asphalt) !important;
  border-color: var(--atlas-line) !important;
}

[role="radiogroup"],
[data-testid="stPills"] {
  gap: 0.35rem;
}

.st-key-atlas_gallery_replay {
  margin: 1.5rem 0 2rem;
  padding: 1.3rem 1.5rem;
  background: rgba(14, 26, 38, 0.96);
  border: 1px solid rgba(88, 214, 200, 0.35);
  border-left: 5px solid var(--atlas-cyan);
  border-radius: 13px;
  box-shadow: 0 14px 38px rgba(0, 0, 0, 0.28), 0 0 20px rgba(88, 214, 200, 0.08);
}

.st-key-atlas_gallery_replay [data-testid="stCaptionContainer"] {
  color: var(--atlas-cyan);
  font-family: var(--atlas-mono);
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.st-key-atlas_lab_status {
  margin: 1.2rem 0;
}

.st-key-atlas_lab_status [data-testid="stStatusWidget"] {
  background: rgba(14, 26, 38, 0.85);
  border: 1px solid var(--atlas-line);
  border-radius: 11px;
}

.st-key-atlas_home_action {
  justify-content: center;
  gap: 1rem;
  margin: 1rem 0 2.4rem;
  padding: 1rem;
  background: rgba(14, 26, 38, 0.72);
  border: 1px solid var(--atlas-line);
  border-radius: 11px;
}

[class*="st-key-atlas_ledger_row_"] {
  border-bottom: 1px solid var(--atlas-line);
}

[class*="st-key-atlas_ledger_row_"]:last-child {
  border-bottom: none;
}

.st-key-atlas_research_ledger [data-testid="stHorizontalBlock"] {
  padding: 0.65rem 0.8rem;
}

.st-key-atlas_lab_onboarding_section,
.st-key-atlas_home_proof,
.st-key-atlas_home_value,
.st-key-atlas_research_method,
.st-key-atlas_research_next {
  margin-top: 2rem;
}

[class*="st-key-atlas_"][class*="_footer"] {
  margin-top: 3.5rem;
  padding: 1.2rem 0;
  border-top: 1px solid var(--atlas-line);
}

[class*="st-key-atlas_"][class*="_footer"] [data-testid="stHorizontalBlock"] {
  flex-wrap: wrap;
}

button:focus-visible,
input:focus-visible,
textarea:focus-visible,
a:focus-visible,
[role="combobox"]:focus-visible {
  outline: 3px solid rgba(88, 214, 200, 0.65) !important;
  outline-offset: 3px;
}

.st-key-atlas_shell_nav [data-testid="stPageLink"] a:focus-visible {
  color: var(--atlas-ink) !important;
  background: var(--atlas-raised) !important;
  outline: 2px solid var(--atlas-cyan) !important;
  outline-offset: 2px !important;
  box-shadow: inset 0 -2px 0 var(--atlas-cyan), 0 0 12px rgba(88, 214, 200, 0.25);
}

button[kind="primary"]:focus-visible {
  outline: 3px solid rgba(94, 233, 196, 0.8) !important;
  outline-offset: 2px !important;
  box-shadow: 0 0 0 3px rgba(94, 233, 196, 0.3) !important;
}

@media (max-width: 430px) {
  .st-key-atlas_home_hero {
    min-height: 0;
    padding: 1.2rem 0.9rem;
  }

  .st-key-atlas_home_hero h2 {
    font-size: 1.85rem;
    line-height: 1.1;
  }

  .st-key-atlas_home_hero [data-testid="stMarkdownContainer"] p {
    font-size: 0.95rem;
    line-height: 1.45;
  }

  .st-key-atlas_home_trust {
    gap: 0.3rem;
    margin-top: 0.6rem;
  }

  .st-key-atlas_home_action {
    margin: 0.6rem 0;
  }
}

@media (max-width: 640px) {
  .st-key-atlas_lab_onboarding_section [data-testid="stHorizontalBlock"] {
    flex-direction: column !important;
  }

  .st-key-atlas_lab_onboarding_section [data-testid="stColumn"] {
    width: 100% !important;
    min-width: 100% !important;
  }
}

/* A 1440x800 laptop is the most common reviewer viewport. At full hero size the first screen
   holds only the headline, so nothing that demonstrates the tool is visible before scrolling.
   Shortening the hero on low-height viewports pulls the causal chain and the fault line up,
   while taller displays keep the full-scale hero. */
@media (max-height: 900px) {
  .st-key-atlas_home_hero {
    min-height: 0;
    padding: 1.7rem 2.1rem 1.9rem;
  }

  .st-key-atlas_home_hero h2 {
    max-width: 26ch;
    margin: 0.2rem 0 0.7rem;
    font-size: clamp(2rem, 3.3vw, 2.85rem);
  }

  .st-key-atlas_home_hero [data-testid="stMarkdownContainer"] p {
    font-size: 0.98rem;
  }

  .st-key-atlas_home_hero::after {
    display: none;
  }

  .st-key-atlas_home_chain {
    margin: 0.8rem 0;
    padding: 0.7rem 0.95rem;
  }
}

@media (max-width: 840px) {
  [data-testid="stAppViewBlockContainer"] {
    padding: 0.7rem 0.75rem 3rem;
  }

  .st-key-atlas_shell_brand {
    min-height: auto;
  }

  .st-key-atlas_home_hero {
    min-height: 0;
    padding: 2rem 1.2rem;
  }

  .st-key-atlas_home_hero h2 {
    font-size: 3rem;
  }

  [class*="st-key-atlas_"][class*="_intro"] {
    padding: 1.45rem 1.2rem;
  }

  [class*="st-key-atlas_"][class*="_intro"] h1 {
    font-size: 2.45rem;
  }

  [class*="st-key-atlas_"][class*="_faultline"]::before {
    display: none;
  }
}

@media (max-width: 360px) {
  [class*="st-key-atlas_"][class*="_faultline"] {
    padding: 0.75rem 0.6rem;
  }

  [class*="st-key-atlas_"][class*="_sequence"] {
    gap: 0.5rem;
  }

  [class*="st-key-atlas_"][class*="_factors"],
  [class*="st-key-atlas_"][class*="_metrics"],
  [class*="st-key-atlas_"][class*="_actors"] {
    flex-wrap: wrap !important;
  }

  [class*="st-key-atlas_"][class*="_factors"] [data-testid="stBadge"],
  [class*="st-key-atlas_"][class*="_actors"] [data-testid="stBadge"],
  [class*="st-key-atlas_"][class*="_metrics"] [data-testid="stMetricLabel"],
  [class*="st-key-atlas_"][class*="_metrics"] [data-testid="stMetricValue"] {
    overflow-wrap: anywhere;
    word-break: break-word;
  }

  [class*="st-key-atlas_"][class*="_faultline"] [data-testid="stMetric"] {
    min-height: auto;
    padding: 0.5rem 0.6rem;
  }
}

/* Metric tiles and the run spinner pick up the accent. Motion is opt-in only, so the lift is
   removed for anyone who has asked their system to reduce motion. */
[data-testid="stMetric"] {
  transition: box-shadow 0.2s ease, transform 0.2s ease;
}

@media (prefers-reduced-motion: no-preference) {
  [data-testid="stMetric"]:hover {
    box-shadow: 0 4px 16px rgba(94, 233, 196, 0.15);
    transform: translateY(-1px);
  }
}

[data-testid="stStatusWidget"] svg {
  stroke: #5ee9c4;
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
