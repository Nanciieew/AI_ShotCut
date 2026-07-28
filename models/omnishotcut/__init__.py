"""OmniShotCut Adapter — Shot Boundary Detection.

OmniShotCut detects natural shot boundaries (hard cuts, dissolves,
wipes) in video. This module wraps the third-party model via the
project's BaseModelAdapter interface.

Status: SPIKE — model installed and verified, Adapter pending.
"""

from models.omnishotcut.adapter import OmniShotCutAdapter
from models.omnishotcut.converter import ShotConverter
from models.omnishotcut.validation import validate_shot_output

__all__ = [
    "OmniShotCutAdapter",
    "ShotConverter",
    "validate_shot_output",
]
