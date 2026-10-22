# analysis/

First-pass error hunt (exploratory scripts, kept for the record). Each reads
`../data/okafor_lindqvist_2025_packet.json` by default, or a path given as the first argument:

    python analysis/check4.py

The production versions of these checks live in `workpaper/checks/` and run via `run_checks.py`.
