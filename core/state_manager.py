import uuid
from datetime import datetime, timezone
import numpy as np

class MarketState:
    def __init__(self):
        self.underlying = {"history": [], "tick": {}, "signals": []}
        self.ceOption = {"history": [], "tick": {}, "signals": []}
        self.peOption = {"history": [], "tick": {}, "signals": []}
        self.oiData = []
        self.pcr = 1.0
        self.pcrChange = 0.0

        # Internal tracking
        self.last_oi = {} # symbol -> last_oi
        self.last_price = {} # symbol -> last_price
        self.session_start_oi = {} # symbol -> first oi of session
        self.candle_start_vtt = {} # symbol -> vtt at start of current candle
        self.instrument_keys = {} # sym -> key
        self.rev_instrument_keys = {} # key -> sym

    def to_dict(self):
        return {
            "underlying": self.underlying,
            "ceOption": self.ceOption,
            "peOption": self.peOption,
            "oiData": self.oiData,
            "pcr": self.pcr,
            "pcrChange": self.pcrChange
        }

def clean_json(obj):
    if isinstance(obj, dict): return {k: clean_json(v) for k, v in obj.items()}
    elif isinstance(obj, list): return [clean_json(i) for i in obj]
    elif isinstance(obj, (np.float64, float)): return float(obj) if not np.isnan(obj) else None
    elif isinstance(obj, (np.int64, int)): return int(obj)
    return obj
