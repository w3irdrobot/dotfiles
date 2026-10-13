---
name: youtube-transcript
description: Fetch YouTube captions or transcripts using yt-dlp and convert WebVTT captions to readable text. Use when asked for a transcript, captions, subtitles, or transcription of a YouTube video. A YouTube URL alone does not request downloading media.
---

# YouTube transcripts

Use existing captions first. Keep timestamped source captions and produce plain
text when requested. Audio transcription is a separate fallback when captions
are unavailable, not a response to every download error.

## Resolve inputs and tools

- Resolve the video URL, destination, and desired language/format from the task.
  Prefer the video's original language unless the user requests another one.
- Check `yt-dlp --version`. If unavailable, report the missing tool and an
  appropriate installation command. Use the user's existing package workflow.
- Use `--no-playlist` for a single-video request. Quote URLs and paths as shell
  arguments; pass paths to Python as arguments rather than interpolating titles
  into source code.
- Try public captions without browser cookies by default. If authentication is
  necessary, use a browser/cookie source selected by the user. Do not assume
  Brave, export raw cookies, or treat a sandbox denial as missing subtitles.

## Inspect and fetch captions

First inspect the available manual and automatic subtitle tracks:

```bash
yt-dlp --no-playlist --list-subs "VIDEO_URL"
```

Choose the actual language code shown in the listing. Prefer manual captions
where available, otherwise use automatic captions. For example, when a manual
English track exists:

```bash
yt-dlp --no-playlist --skip-download --write-subs \
  --sub-langs en --sub-format vtt \
  --paths "/absolute/destination" \
  --output "%(title)s [%(id)s].%(ext)s" \
  "VIDEO_URL"
```

For an automatic track, replace `--write-subs` with `--write-auto-subs` and use
its actual language code. Check destination conflicts before downloading and
use yt-dlp's `--no-overwrites` where appropriate.

Confirm that the expected nonempty subtitle file exists. yt-dlp can exit
successfully without writing subtitles; exit status alone does not establish
success. Preserve visible error output and distinguish missing captions from
rate limits, authentication problems, unavailable videos, and network failures.
Do not disable certificate verification as a retry strategy.

## Convert to text

For WebVTT, use the bundled converter with absolute paths:

```bash
python3 /absolute/path/to/this-skill/scripts/vtt_to_text.py \
  "/absolute/path/to/captions.vtt" \
  --output "/absolute/path/to/transcript.txt"
```

The script parses cue bodies, strips WebVTT markup, decodes HTML entities, and
removes shared rolling text only between overlapping cues. It preserves repeated
speech in later, non-overlapping cues rather than globally deleting duplicates.
It refuses to overwrite an existing output. Omit `--output` to print to stdout.
If another subtitle format is available instead, convert it deliberately rather
than treating it as VTT. Preserve the source captions unless cleanup is requested.

## If captions are unavailable

If the user requested only captions/transcript retrieval, ask before downloading
audio and running a transcription model. If audio transcription was explicitly
requested, proceed within that scope. Check the selected transcription tool,
model, available dependencies such as ffmpeg, and approximate media size/duration.
Discuss any necessary large installation/model download before starting it.

Use an audio-only download and a supported local transcription tool when chosen.
Do not install Whisper or choose a model solely because this skill mentions it.
Report the transcript path, language, and whether it came from manual captions,
automatic captions, or audio transcription. State any blocker concretely.
