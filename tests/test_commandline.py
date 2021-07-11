# SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
# 
# SPDX-License-Identifier: GPL-3.0-or-later

import tempfile
import os

import pytest

from drmock import commandline
from drmock import generator
from drmock import utils


def test_example(script_runner):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, 'example_mock.h')
        ret = script_runner.run('drmock-gen', '--input-class', 'Derived', '--output-class', 'DerivedMock', 'resources/example.h', str(path), '--std=c++17')
    assert ret.success


def test_success(monkeypatch, mocker, script_runner):
    args, compiler_flags = object(), object()
    monkeypatch.setattr(commandline, 'parse_args', mocker.Mock(return_value=(args, compiler_flags)))
    monkeypatch.setattr(generator, 'main', mocker.Mock())
    ret = script_runner.run('drmock-gen')
    assert ret.success
    assert generator.main.called_once_with(args, compiler_flags)


def test_parser_fails(monkeypatch, mocker, script_runner):
    # Cause a parser error by not providing required args.
    ret = script_runner.run('drmock-gen')
    assert not ret.success
    assert ret.returncode == 2


def test_failure(monkeypatch, mocker, script_runner):
    args, compiler_flags = object(), object()
    monkeypatch.setattr(commandline, 'parse_args', mocker.Mock(return_value=(args, compiler_flags)))
    monkeypatch.setattr(generator, 'main', mocker.Mock(side_effect=utils.DrMockRuntimeError()))
    ret = script_runner.run('drmock-gen', print_result=False)
    assert not ret.success
    assert ret.returncode == 1
    assert ret.stderr.startswith('drmock-gen: error:')
    assert generator.main.called_once_with(args, compiler_flags)


@pytest.mark.parametrize('error', [AttributeError(), IOError(), RuntimeError(), ValueError()])
def test_panic(error, monkeypatch, mocker, script_runner):
    args, compiler_flags = object(), object()
    monkeypatch.setattr(commandline, 'parse_args', mocker.Mock(return_value=(args, compiler_flags)))
    monkeypatch.setattr(generator, 'main', mocker.Mock(side_effect=error))
    ret = script_runner.run('drmock-gen', print_result=False)
    assert not ret.success
    assert ret.stderr.startswith('Traceback')
    assert generator.main.called_once_with(args, compiler_flags)
