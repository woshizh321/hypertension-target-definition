"""Filesystem configuration only; no scientific transformations."""
from pathlib import Path
import os,json
REPOSITORY_ROOT=Path(__file__).resolve().parents[2]
PROJECT_ROOT=Path(os.environ.get('PROJECT_ROOT',str(REPOSITORY_ROOT/'output'/'project'))).expanduser().resolve()
DATA_ROOT=Path(os.environ.get('DATA_ROOT',str(REPOSITORY_ROOT/'private_data'))).expanduser().resolve()
CONFIG_PATH=Path(os.environ.get('SOURCE_CONFIG',str(REPOSITORY_ROOT/'documentation'/'source_paths.example.json')))
def source_path(key):
 values=json.loads(CONFIG_PATH.read_text())
 value=Path(values[key]).expanduser()
 return value if value.is_absolute() else DATA_ROOT/value
