"""Compare QGIS PDF export modes from one frozen report payload.

Run with the Python interpreter bundled with QGIS. The input has the same
records/filters/summary/warnings keys as the report worker's JSON payload.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from time import perf_counter

os.environ.setdefault("QT_QPA_PLATFORM", "windows" if sys.platform == "win32" else "offscreen")
os.environ.setdefault("SIG_PRESTATIONS_PERF", "1")
os.environ["SIG_PRESTATIONS_PERF_WORKER"] = "1"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qgis.core import QgsApplication, Qgis, QgsLayoutExporter  # noqa: E402
from gemapi_app.report_pdf import export_report  # noqa: E402


MODES = (("reference_200dpi", 200, "standard"),
         ("standard_100dpi", 100, "standard"),
         ("rasterise_100dpi", 100, "rasterized"),
         ("hybride_100dpi", 100, "hybrid"),
         ("standard_80dpi", 80, "standard"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON figé du rapport")
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--only", action="append",
                        choices=[f"{fond}_{name}" for fond in ("epure", "ortho")
                                 for name, _, _ in MODES])
    args = parser.parse_args()
    source = args.input.read_bytes()
    payload = json.loads(source)
    if len(payload["records"]) != 13:
        raise ValueError("La comparaison requiert exactement 13 prestations figées.")
    if not all(hasattr(QgsLayoutExporter.PdfExportSettings(), name)
               for name in ("dpi", "rasterizeWholeImage", "textRenderFormat")):
        raise RuntimeError("Cette version de QGIS ne fournit pas les paramètres PDF requis.")
    app = QgsApplication([], True)
    app.initQgis()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(json.dumps({"qgis": Qgis.QGIS_VERSION, "input_sha256": hashlib.sha256(source).hexdigest(),
                      "records": len(payload["records"])}), flush=True)
    try:
        for fond in ("epure", "ortho"):
            for name, dpi, mode in MODES:
                variant = f"{fond}_{name}"
                if args.only and variant not in args.only:
                    continue
                destination = args.output_dir / f"{variant}.pdf"
                started = perf_counter()
                pages = export_report(
                    payload["records"], payload["filters"], payload["summary"],
                    payload["warnings"], str(destination),
                    include_photos=payload.get("include_photos", False),
                    include_maps=True, map_background=fond, export_dpi=dpi,
                    export_mode=mode, require_basemap=True)
                print(json.dumps({"variant": variant, "pages": pages,
                                  "size_bytes": destination.stat().st_size,
                                  "total_ms": round((perf_counter() - started) * 1000, 2)}),
                      flush=True)
    finally:
        app.exitQgis()


if __name__ == "__main__":
    main()
