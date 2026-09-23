from pathlib import Path

from aegissat.protocol.ax25 import build_ui_frame
from aegissat.protocol.kiss import encode_kiss_frame
from aegissat.protocol.satellite_command import encode_command


class UplinkService:
    def __init__(self, output_path="outputs/uplink_commands.kiss"):
        self.output_path = Path(output_path)
        self.sequence = 0

    def queue_command(self, command_id, parameters=b""):
        self.sequence = (self.sequence + 1) % 65536
        command = encode_command(command_id, self.sequence, parameters)
        ax25 = build_ui_frame("AEGIS", "GROUND", command, include_fcs=False)
        kiss = encode_kiss_frame(ax25)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("ab") as output:
            output.write(kiss)
        return {
            "status": "queued",
            "command_id": command_id,
            "sequence": self.sequence,
            "output": str(self.output_path),
        }
