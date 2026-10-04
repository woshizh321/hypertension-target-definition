"""Figure 4 presentation entry point. Common compositor creates Figures 1–5 from frozen outputs; no model fitting. Use --source and --output. Optional --private-charls-oof requires controlled CHARLS access; omit for aggregate-only display."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('build_figures.py')),run_name='__main__')
