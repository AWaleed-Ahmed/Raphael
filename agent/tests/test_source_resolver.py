from pathlib import Path

from raphael_agent.localization.anchors import RuntimeAnchor
from raphael_agent.localization.source_resolver import required_oci_labels, resolve_anchor


def test_source_map_and_oci_provenance(tmp_path: Path):
    config = tmp_path / ".raphael"
    config.mkdir()
    (config / "source-map.json").write_text('{"dist/app.js":{"source_file":"src/app.ts","source_line":22,"source_symbol":"handler"}}', encoding="utf-8")
    anchor = RuntimeAnchor("exception", "dist/app.js", 1, "main", 0.8, "ev")
    resolved = resolve_anchor(anchor, tmp_path)
    assert resolved.file_path == "src/app.ts"
    assert resolved.line_number == 22
    assert required_oci_labels({"org.opencontainers.image.revision":"abc"}) == ["org.opencontainers.image.source"]
