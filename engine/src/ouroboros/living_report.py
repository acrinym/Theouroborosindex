from __future__ import annotations

from pathlib import Path

from .anatomy import anatomy_fingerprint, spatial_map_html
from .model import Category
from .report import CATEGORY_LABELS, build_report_html


def _fingerprint_html(baseline, semantic) -> str:
    fingerprint = anatomy_fingerprint(baseline, semantic)
    rows = []
    shares = fingerprint["category_shares"]
    for category in (
        Category.CORE_PRODUCT,
        Category.USER_SURFACE,
        Category.ESSENTIAL_SUPPORT,
        Category.TESTING,
        Category.DEVELOPER_TOOLING,
        Category.OBSERVABILITY,
        Category.VERIFICATION,
        Category.AUDIT_PROVENANCE,
        Category.PROCESS_MACHINERY,
        Category.META_MACHINERY,
    ):
        share = float(shares.get(category.value, 0.0))
        width = max(0.0, min(100.0, share * 100))
        rows.append(
            f'<div class="living-fp-row"><span>{CATEGORY_LABELS.get(category, category.value)}</span>'
            f'<div class="living-fp-track"><i class="cat-{category.value}" style="width:{width:.5f}%"></i></div>'
            f'<strong>{width:.1f}%</strong></div>'
        )
    far = float(fingerprint.get("far_from_value_share") or 0.0)
    rows.append(
        f'<div class="living-fp-row"><span>Far from value</span>'
        f'<div class="living-fp-track"><i class="living-far" style="width:{far*100:.5f}%"></i></div>'
        f'<strong>{far*100:.1f}%</strong></div>'
    )
    return (
        '<div class="living-fingerprint">' + "".join(rows) + '</div>'
        '<div class="living-fp-meta">'
        f'<span>Exact recursive depth <strong>{int(fingerprint.get("recursive_depth") or 0)}</strong></span>'
        f'<span>Semantic Index <strong>{float(fingerprint.get("semantic_index") or 0):.1f}</strong></span>'
        '</div>'
    )


def _living_css() -> str:
    return """
.repo-map-layout { display:grid; grid-template-columns:minmax(0,2fr) minmax(260px,1fr); gap:16px; }
.repo-map-wrap { min-height:420px; overflow:auto; border:1px solid var(--line); border-radius:12px; background:#090d12; }
.repo-map { display:block; width:100%; min-width:650px; min-height:420px; }
.map-dir > rect { fill:none; stroke:#ffffff28; stroke-width:1.1px; }
.map-dir > text { fill:#d7e0e8; font-size:10px; pointer-events:none; text-shadow:0 1px 2px #000; }
.map-dir { cursor:pointer; }
.map-dir:hover > rect, .map-dir:focus > rect { stroke:var(--accent); stroke-width:2px; }
.map-inversion > rect { stroke:var(--warn); stroke-dasharray:7 4; stroke-width:2px; }
.map-file { cursor:pointer; }
.map-file > rect { stroke:#0a0e13; vector-effect:non-scaling-stroke; opacity:.94; }
.repo-map .cat-core-product > rect { fill:#2f8f72; }
.repo-map .cat-user-surface > rect { fill:#57b894; }
.repo-map .cat-essential-support > rect { fill:#4f7fab; }
.repo-map .cat-testing > rect { fill:#a987db; }
.repo-map .cat-developer-tooling > rect { fill:#d59a55; }
.repo-map .cat-observability > rect { fill:#d0709c; }
.repo-map .cat-verification > rect { fill:#c9ad54; }
.repo-map .cat-audit-provenance > rect { fill:#d26969; }
.repo-map .cat-process-machinery > rect { fill:#b85f7b; }
.repo-map .cat-meta-machinery > rect { fill:#a54f4f; }
.repo-map .cat-documentation > rect { fill:#6f7b87; }
.repo-map .cat-unknown > rect { fill:#4a5058; }
.map-file:hover > rect, .map-file:focus > rect { stroke:#fff; opacity:1; }
.map-chain > rect { stroke:var(--accent-2); stroke-dasharray:4 3; }
.repo-map-detail { border:1px solid var(--line); border-radius:12px; padding:14px; min-height:420px; overflow:auto; }
.repo-map-detail h3 { margin-bottom:8px; }
.map-files,.map-symbols { display:grid; gap:6px; margin:10px 0; }
.map-file-link,.map-symbol-link,.map-open-evidence,.map-filter-directory { text-align:left; border:1px solid var(--line); border-radius:8px; background:var(--panel-2); color:var(--text); padding:8px 9px; cursor:pointer; }
.map-file-link span { float:right; color:var(--muted); font-size:12px; }
.map-file-link:hover,.map-symbol-link:hover,.map-open-evidence:hover,.map-filter-directory:hover { border-color:var(--accent); }
.living-map-legend { display:flex; gap:14px; flex-wrap:wrap; color:var(--muted); margin:10px 0 14px; }
.living-map-legend span::before { content:""; display:inline-block; width:18px; height:10px; margin-right:6px; border:2px solid var(--line); vertical-align:-1px; }
.living-map-legend .inv::before { border-color:var(--warn); border-style:dashed; }
.living-map-legend .chain::before { border-color:var(--accent-2); border-style:dashed; }
.living-map-legend .distance::before { border-width:4px; border-color:#d9e7f2; }
.living-fingerprint { display:grid; gap:7px; }
.living-fp-row { display:grid; grid-template-columns:170px 1fr 58px; gap:9px; align-items:center; }
.living-fp-track { height:13px; border-radius:999px; border:1px solid var(--line); background:#090d12; overflow:hidden; }
.living-fp-track i { display:block; height:100%; min-width:0; }
.living-far { background:var(--accent-2); }
.living-fp-meta { display:flex; gap:20px; flex-wrap:wrap; margin-top:14px; color:var(--muted); }
@media (max-width:900px) { .repo-map-layout { grid-template-columns:1fr; } .repo-map-detail { min-height:auto; } }
@media (max-width:560px) { .living-fp-row { grid-template-columns:120px 1fr 48px; font-size:12px; } }
"""


def _living_script() -> str:
    return r"""
<script>
(() => {
  function showOnly(selector, attribute, value) {
    document.querySelectorAll(selector).forEach((record) => record.classList.toggle("hidden", record.getAttribute(attribute) !== value));
  }
  function openDirectory(path) {
    document.querySelectorAll("[data-map-record]").forEach((record) => record.classList.add("hidden"));
    showOnly("[data-map-directory-record]", "data-map-directory-record", path);
  }
  function openFile(path) {
    document.querySelectorAll("[data-map-directory-record]").forEach((record) => record.classList.add("hidden"));
    showOnly("[data-map-record]", "data-map-record", path);
  }
  function keyboardActivate(element, callback) {
    element.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); callback(); }
    });
  }
  document.querySelectorAll("[data-map-dir]").forEach((element) => {
    const action = () => openDirectory(element.dataset.mapDir);
    element.addEventListener("click", action); keyboardActivate(element, action);
  });
  document.querySelectorAll("[data-map-file]").forEach((element) => {
    const action = () => openFile(element.dataset.mapFile);
    element.addEventListener("click", action); keyboardActivate(element, action);
  });
  document.querySelectorAll("[data-map-file-link]").forEach((button) => button.addEventListener("click", () => openFile(button.dataset.mapFileLink)));

  function filterExisting(inputId, value, containerId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    input.value = value;
    input.dispatchEvent(new Event("input", {bubbles:true}));
    const container = document.getElementById(containerId);
    if (container) container.scrollIntoView({behavior:"smooth", block:"start"});
  }
  document.querySelectorAll("[data-map-filter-directory]").forEach((button) => button.addEventListener("click", () => {
    filterExisting("file-search", button.dataset.mapFilterDirectory, "file-evidence");
  }));
  document.querySelectorAll("[data-map-evidence]").forEach((button) => button.addEventListener("click", () => {
    const value = button.dataset.mapEvidence;
    filterExisting("file-search", value, "file-evidence");
    requestAnimationFrame(() => {
      const first = [...document.querySelectorAll("#file-evidence details.searchable")].find((item) => !item.classList.contains("hidden"));
      if (first) first.open = true;
    });
  }));
  document.querySelectorAll("[data-map-symbol]").forEach((button) => button.addEventListener("click", () => {
    filterExisting("symbol-search", button.dataset.mapSymbol, "symbol-evidence");
    requestAnimationFrame(() => {
      const first = [...document.querySelectorAll("#symbol-evidence details.searchable")].find((item) => !item.classList.contains("hidden"));
      if (first) first.open = true;
    });
  }));
})();
</script>
"""


def build_living_report_html(repository: str | Path, baseline, semantic) -> str:
    base = build_report_html(repository, baseline, semantic)
    anchor = '<section class="panel">\n  <h2>Where did the product go?</h2>'
    if anchor not in base:
        raise ValueError("Repository Anatomy report structure changed; Living Anatomy insertion point was not found")
    living = f"""
<section class="panel">
  <h2>Living repository map</h2>
  <p class="section-note">Directories are spatial regions and file area follows code-line mass. This map drills into the same classifications, symbols, value distance, inversion evidence, and exact chains used elsewhere in this report; it is not a second analyzer.</p>
  <div class="living-map-legend"><span class="inv">Inversion directory</span><span class="chain">Deepest exact chain</span><span class="distance">Thicker border = farther from value</span></div>
  {spatial_map_html(baseline, semantic)}
</section>
<section class="panel">
  <h2>Anatomy fingerprint</h2>
  <p class="section-note">A deterministic multidimensional fingerprint for this scan. It is designed for before/after and structural-peer comparison, not as a ranking badge.</p>
  {_fingerprint_html(baseline, semantic)}
</section>
"""
    result = base.replace(anchor, living + "\n" + anchor, 1)
    result = result.replace("</style>", _living_css() + "\n</style>", 1)
    result = result.replace("</body>", _living_script() + "\n</body>", 1)
    return result


def write_living_report(repository: str | Path, baseline, semantic, target: str | Path) -> Path:
    destination = Path(target).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(build_living_report_html(repository, baseline, semantic), encoding="utf-8")
    return destination.resolve()
