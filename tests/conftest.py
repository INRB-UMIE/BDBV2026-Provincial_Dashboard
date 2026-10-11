"""Point the build at the small fixture build/ before any Scripts module is imported."""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ["BUILD_DIR"] = str(HERE / "fixtures" / "build")
os.environ["GEO_SOURCE"] = str(HERE / "fixtures" / "geo" / "DRC_Health_zones.shp")
os.environ["QA_LOG"] = str(HERE / "fixtures" / "qa" / "qa_log.csv")
os.environ["EXTRACTION_DIR"] = str(HERE / "fixtures" / "presentations")
sys.path.insert(0, str(HERE.parent / "Scripts"))
sys.path.insert(0, str(HERE.parent))  # tests.shapefile_writer
