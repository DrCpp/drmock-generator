# SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os

import clang.cindex
import pytest

from drmock import translator


@pytest.fixture(scope="module")
def set_library_file():
    # pytest seems to import translator only once, so we need to protect
    # clang from being configured twice.
    if clang.cindex.Config.loaded:
        return
    translator.set_library_file(os.environ["CLANG_LIBRARY_FILE"])
