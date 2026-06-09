#!/bin/sh
# Point this repo at versioned hooks under .githooks/ (run once per clone).
cd "$(dirname "$0")/.." || exit 1
git config core.hooksPath .githooks
echo "git config core.hooksPath=.githooks"
