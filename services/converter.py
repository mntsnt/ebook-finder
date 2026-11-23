import asyncio
import shutil
from pathlib import Path
from typing import Optional
import config

class EbookConverter:
    @staticmethod
    def is_calibre_available() -> bool:
        """Checks if ebook-convert CLI is installed and discoverable."""
        return shutil.which(config.CALIBRE_CONVERT_PATH) is not None

    @classmethod
    async def convert(cls, input_file: Path, target_ext: str) -> Optional[Path]:
        """
        Converts input ebook to target format using Calibre's ebook-convert.
        Supported target formats include: epub, pdf, mobi, azw3, txt, etc.
        """
        target_ext = target_ext.lstrip(".").lower()
        output_file = input_file.with_suffix(f".{target_ext}")

        if input_file.suffix.lower() == f".{target_ext}":
            return input_file

        if not cls.is_calibre_available():
            print(f"[Converter] Calibre CLI '{config.CALIBRE_CONVERT_PATH}' is not installed or not in PATH.")
            return None

        cmd = [
            config.CALIBRE_CONVERT_PATH,
            str(input_file),
            str(output_file)
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0 and output_file.exists():
                return output_file
            else:
                print(f"[Converter] Failed conversion: {stderr.decode(errors='ignore')}")
                return None
        except Exception as e:
            print(f"[Converter] Error executing conversion: {e}")
            return None
