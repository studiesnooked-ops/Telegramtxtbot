import asyncio

def get_ffmpeg_cmd(input_file, output_file, fast_mode=True):
    if fast_mode:
        return [
            "ffmpeg", "-y",
            "-i", input_file,
            "-preset", "ultrafast",
            "-threads", "0",
            "-loglevel", "error",
            "-c:v", "libx264",
            "-crf", "30",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            output_file
        ]
    else:
        return [
            "ffmpeg", "-y",
            "-i", input_file,
            "-preset", "fast",
            "-threads", "0",
            "-loglevel", "error",
            "-c:v", "libx264",
            "-crf", "24",
            "-c:a", "aac",
            "-b:a", "192k",
            output_file
        ]


async def run_ffmpeg(cmd):
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await process.communicate()
    return process.returncode
