from dataclasses import dataclass
from typing import Optional

from dataclasses_json import dataclass_json
from models.batch_auction_model import SettledBatchAuction


@dataclass_json
@dataclass
class SimulationResult:
    solution: str
    passed: bool
    reason: Optional[str] = ''
    error: Optional[str] = ''
    gas: Optional[int] = None


@dataclass_json
@dataclass
class SimulationRequest:
    solution: SettledBatchAuction
    estimate_block: Optional[bool] = False