# create-bhav

One-command scaffold for [Bhav](https://github.com/rajmaurya0904/bhav), an open-source NSE options backtesting engine.

```
npx create-bhav [directory]
```

Defaults to `./bhav` if no directory is given. This:

1. Clones the Bhav repo (shallow) into that directory
2. Installs the Python package (`pip install -e .`) — needs Python 3.11+ on PATH
3. Installs frontend dependencies (`npm install` in `frontend/`)
4. Prints next steps to get a Upstox token and run the CLI or web UI

Requires `git`, `python`/`python3`/`py`, and `npm` on PATH. Nothing is published to npm registries beyond this thin wrapper — the actual clone always pulls the latest `main` from GitHub.

## License

MIT.
