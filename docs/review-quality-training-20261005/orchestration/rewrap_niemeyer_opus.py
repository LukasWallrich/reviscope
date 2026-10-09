"""Offline-only wrap of the available valid Opus cache; leave Sol primary missing."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;CODE=Path(json.loads((ROOT/'assessment-method-v2.json').read_text())['offline_rewrap']['code']);sys.path[:0]=[str(CODE/'src'),str(CODE/'eval')]
import assess_criticisms as m
m.ROOT=ROOT;m.LAUNCH=json.loads((ROOT/'launch.json').read_text())
m.assess('niemeyer','claude-opus-5-5',m.packet('niemeyer'),offline=True)
