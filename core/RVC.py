# RVC.py

import os
import subprocess
import uuid

TEMP_DIR = "temp"


class RVCService:

    def __init__(self):
        self.rvc_model = "rvc_models/amora/model.pth"
        self.rvc_index = "rvc_models/amora/model.index"

    async def convert_voice(
        self,
        input_mp3: str,
        pitch: int = 0
    ) -> str:

        output_path = os.path.join(
            TEMP_DIR,
            f"{uuid.uuid4()}.mp3"
        )

        cmd = [
            "python",
            "rvc_infer.py",

            "--input",
            input_mp3,

            "--output",
            output_path,

            "--model",
            self.rvc_model,

            "--index",
            self.rvc_index,

            "--pitch",
            str(pitch)
        ]

        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        if process.returncode != 0:
            raise Exception(process.stderr)

        return output_path