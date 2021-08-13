# SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
#
# SPDX-License-Identifier: GPL-3.0-or-later

import tempfile
import os

import pytest

from drmock import commandline
from drmock import generator
from drmock import utils


def test_snapshot(script_runner):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "example_mock.h")
        ret = script_runner.run(
            "drmock-generator",
            "--input-class",
            "Derived",
            "--output-class",
            "DerivedMock",
            "resources/example.h",
            str(path),
            "-n",
            "ns",
            "-c",
            "ctrl",
            "-f --std=c++17",
        )
        with open(path, "r") as f:
            result = f.read()
        with open("resources/example_mock.h") as f:
            expected = f.read()
    assert ret.success
    assert result == expected


def test_success(monkeypatch, mocker, script_runner):
    flags = [" --std=c++17", "-fPIC"]
    args = mocker.Mock(flags=flags)
    monkeypatch.setattr(commandline, "parse_args", mocker.Mock(return_value=args))
    monkeypatch.setattr(generator, "main", mocker.Mock())
    ret = script_runner.run("drmock-generator")
    assert ret.success
    assert generator.main.called_once_with(args, args.flags)


def test_parser_fails(monkeypatch, mocker, script_runner):
    # Cause a parser error by not providing required args.
    ret = script_runner.run("drmock-generator")
    assert not ret.success
    assert ret.returncode == 2


def test_failure(monkeypatch, mocker, script_runner):
    flags = [" --std=c++17", "-fPIC"]
    args = mocker.Mock(flags=flags)
    monkeypatch.setattr(commandline, "parse_args", mocker.Mock(return_value=args))
    monkeypatch.setattr(
        generator, "main", mocker.Mock(side_effect=utils.DrMockRuntimeError())
    )
    ret = script_runner.run("drmock-generator")
    assert not ret.success
    assert ret.returncode == 1
    assert ret.stderr.startswith("drmock-generator: error:")
    assert generator.main.called_once_with(args, args.flags)


@pytest.mark.parametrize(
    "error", [AttributeError(), IOError(), RuntimeError(), ValueError()]
)
def test_panic(error, monkeypatch, mocker, script_runner):
    flags = [" --std=c++17", "-fPIC"]
    args = mocker.Mock(flags=flags)
    monkeypatch.setattr(commandline, "parse_args", mocker.Mock(return_value=args))
    monkeypatch.setattr(generator, "main", mocker.Mock(side_effect=error))
    ret = script_runner.run("drmock-generator", print_result=False)
    assert not ret.success
    assert ret.stderr.startswith("Traceback")
    assert generator.main.called_once_with(args)
