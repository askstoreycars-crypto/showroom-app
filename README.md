# Showroom Photo Booth

Upload car photos, get back a precise AI cutout on a clean white
background with one soft grounding shadow — batch, automatic, no
manual tracing and no per-photo trip through an outside AI tool.

This is a real (small) application with a backend, unlike the
in-chat/browser-only versions we prototyped first — that's what makes
full automation possible: the backend can actually download and run
the AI segmentation model, which a page hosted purely in a browser
sandbox cannot do.

## What's inside

```
showroom-app/
  backend/
    main.py           FastAPI app: one endpoint, /api/process
    processing.py      The exact image pipeline we finalized
    requirements.txt
  frontend/
    index.html          Upload UI (drag/drop, batch, zip download)
  Dockerfile
  README.md (this file)
```

## Run it locally

Requires Python 3.10+.

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** in a browser. Drop in photos, download
results individually or as a zip.

The first photo you process will be slow (~20-30 seconds) while it
downloads the ~176MB segmentation model in the background; every photo
after that is fast (a few seconds each, CPU only, no GPU needed).

## Run it with Docker

```bash
docker build -t showroom-booth .
docker run -p 8000:8000 showroom-booth
```

The model is downloaded at build time, so the container is ready to go
as soon as it starts.

## Deploying so your whole team can use it

Any host that runs a Docker container or a Python web service works.
Reasonable options, roughly cheapest/simplest first:

- **Render** or **Railway**: point them at this repo, they detect the
  Dockerfile and deploy it. A small always-on instance (512MB-1GB RAM)
  is enough.
- **Fly.io**: `fly launch` in this folder, it picks up the Dockerfile.
- **Your own server / VPS**: `docker run` as above behind nginx or
  Caddy for HTTPS.

None of these require a GPU — `onnxruntime` runs the model on CPU,
just a bit slower per photo than a GPU would be (a few seconds either
way for a single car photo).

## Adjusting the look

Everything about the final image — margin, shadow strength, output
size/aspect ratio, and the alpha edge-cleanup thresholds — lives in
`backend/processing.py`, with comments explaining what each part does
and why. A few things worth knowing if you want to change the look
later:

- **Background style**: currently a flat white canvas. We tried a grey
  studio look and a "room" look (floor reflection, wall/floor seam,
  soft overhead light streaks) while dialing this in — if you want
  those back, they're straightforward to re-add in `compose_showroom`;
  ask whoever's maintaining this (or Claude) to reintroduce them.
- **Color enhancement**: intentionally left off per the final call —
  colors are exactly as shot. There's no contrast/saturation boost.
- **Edge cleanup thresholds** (`_clean_alpha`'s `low`/`high`): raise
  `low` if you still see a faint halo around any edges; lower it if
  thin details (antennas, mirrors) start getting clipped off.

## A note on cost/upkeep

This needs an actual server running somewhere (even a cheap one), and
occasional maintenance if a dependency needs updating or something
breaks — unlike a plain static webpage, there's a real running service
behind this now. That's the trade-off for genuine one-click automatic
background removal.
