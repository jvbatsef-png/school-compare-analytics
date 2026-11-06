"""Generate the GTM container import file from the tracking spec and the public IDs."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
IDS_PATH = ROOT / "tracking" / "gtm" / "ids.yaml"


def load_ids(path: Path = IDS_PATH) -> dict[str, str]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))
