import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GMSKConfig:
    profile: str
    center_frequency_hz: float
    symbol_rate: float
    samples_per_symbol: int
    bt: float
    frequency_deviation_hz: float
    rtl_gain_db: float

    @property
    def sample_rate(self):
        return self.symbol_rate * self.samples_per_symbol


def load_gmsk_config():
    symbol_rate = float(os.getenv("AEGIS_GMSK_SYMBOL_RATE", "9600"))
    return GMSKConfig(
        profile=os.getenv("AEGIS_GMSK_PROFILE", "laboratory_default"),
        center_frequency_hz=float(
            os.getenv("AEGIS_GMSK_CENTER_FREQUENCY_HZ", "437500000")
        ),
        symbol_rate=symbol_rate,
        samples_per_symbol=int(os.getenv("AEGIS_GMSK_SAMPLES_PER_SYMBOL", "4")),
        bt=float(os.getenv("AEGIS_GMSK_BT", "0.5")),
        frequency_deviation_hz=float(
            os.getenv("AEGIS_GMSK_FREQUENCY_DEVIATION_HZ", str(symbol_rate / 4))
        ),
        rtl_gain_db=float(os.getenv("AEGIS_RTL_GAIN_DB", "30")),
    )


def validate_gmsk_config(config):
    if config.profile == "aegissat_final":
        return
    if config.profile != "laboratory_default":
        raise ValueError("Unknown GMSK profile")
    if config.symbol_rate <= 0:
        raise ValueError("Symbol rate must be positive")
    if config.samples_per_symbol < 2:
        raise ValueError("At least two samples per symbol are required")
    if not 0 < config.bt <= 1:
        raise ValueError("GMSK BT must be between 0 and 1")
