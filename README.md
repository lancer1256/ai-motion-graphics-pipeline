# Autonomous Motion Graphics Editor Agent

An early autonomous video editor that does full motion graphics editing given an audio file. It uses Grok to chunk the script and plan the graphic for each scene, then creates the images, reflects on and improves them, writes the prompts for the animated graphic, and feeds them into Hailuo to generate the video.

I used Mirage for avatar generation and MiniMax for TTS generation.

This repository was extracted from the August 3, 2025 Fantas codebase at commit `b67e45a47`, immediately before the product pivoted toward avatar video.

## Generated examples

These three complete videos were produced by the pipeline:

- [`DM075lqA_8j.mp4`](demo/instagram/DM075lqA_8j.mp4)
- [`DM07Z3KApB-.mp4`](demo/instagram/DM07Z3KApB-.mp4)
- [`DM08A8CAlQv.mp4`](demo/instagram/DM08A8CAlQv.mp4)

## Pipeline

1. The orchestration layer split a transcript into timed lines and maintained the scene-level generation context.
2. Versioned prompts guided the LLM from literal visual ideas through first-frame and motion instructions.
3. The video-generation service sent an image and motion prompt to `fal-ai/minimax/hailuo-02/standard/image-to-video`.
4. The transition-video service rendered word-timed connective scenes through a small Remotion HTTP renderer.
5. The backtest processor assembled scene outputs and kept provenance for each experiment.

## Repository map

- `backend/app/features/backtest/` — historical orchestration and assembly slice
- `backend/app/features/video_generation/` — optional Hailuo/fal.ai generation stage
- `backend/app/features/transition_video/` — deterministic word-timed Remotion renderer
- `prompt-history/` — the selected historical prompt stack
- `demo/instagram/` — three generated public examples and cover frames

## Run the deterministic renderer

Requirements: Node.js 20+, npm, Chrome/Chromium, and FFmpeg.

```bash
cd backend/app/features/transition_video/renderer
npm install
npm run render
```

The sample render is written to `out/sample-transition.mp4`. Edit `test_props.json` to change words and timings. The renderer itself does not need an API key.

## Optional model stage

The historical Python service is included as an architectural reference and expects the surrounding application models/configuration. To adapt it, supply your own `FAL_KEY` and install `fal-client`; no credentials are included here. Paid model calls are never made by the sample render.

## Security and provenance

- This is a clean export with no original Git history, environment files, keys, provider responses, debug dumps, or customer data.
- Downloaded Instagram metadata was discarded; only the creator's three public video files and thumbnails are included.
- The code is a historical snapshot, not the current Rayloom production system.

## License

MIT. Generated demo media is provided for portfolio and educational viewing.
