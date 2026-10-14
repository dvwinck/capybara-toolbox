#!/usr/bin/env python3
# tidy-board 0.1.0 - cards para limpar branches, worktrees e stashes; o apply reconfere e apaga (somente stdlib e git)
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Diogo Winck
#
# Uso:
#   tidy_board.py scan    [REPO] [--base REF] [--gh auto|off] [--out DIR]   # le o git e escreve batch.json + scan.json
#   tidy_board.py check   DIR                                              # valida batch.json + scan.json
#   tidy_board.py apply   DIR [--dry-run]                                  # reconfere cada item aprovado e apaga
#   tidy_board.py restore DIR ID                                           # recria o que foi apagado (backup ou sha)
import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import namedtuple
from pathlib import Path

VERSION = "0.1.0"


def main(argv=None):
    print(f"tidy-board {VERSION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
