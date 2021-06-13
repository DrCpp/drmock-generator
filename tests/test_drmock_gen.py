# SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
# 
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from drmock import frontend
from drmock import generator
from drmock import utils


@pytest.mark.script_launch_mode('subprocess')
def test_success(monkeypatch, mocker, script_runner):
    args, compiler_flags = object(), object()
    monkeypatch.setattr(frontend, 'parse_args', mocker.Mock(return_value=(args, compiler_flags)))
    monkeypatch.setattr(generator, 'main', mocker.Mock())
    ret = script_runner.run('drmock-gen', print_result=False)
    assert ret.success
    assert generator.main.called_once_with(args, compiler_flags)


@pytest.mark.script_launch_mode('subprocess')
def test_parser_fails(monkeypatch, mocker, script_runner):
    # Cause a parser error by not providing required args.
    ret = script_runner.run('drmock-gen', print_result=False)
    assert not ret.success
    assert ret.returncode == 2


@pytest.mark.script_launch_mode('subprocess')
def test_failure(monkeypatch, mocker, script_runner):
    args, compiler_flags = object(), object()
    monkeypatch.setattr(frontend, 'parse_args', mocker.Mock(return_value=(args, compiler_flags)))
    monkeypatch.setattr(generator, 'main', mocker.Mock(side_effect=utils.DrMockRuntimeError()))
    ret = script_runner.run('drmock-gen', print_result=False)
    assert not ret.success
    assert ret.returncode == 1
    assert ret.stderr.startswith('drmock-gen: error:')
    assert generator.main.called_once_with(args, compiler_flags)


@pytest.mark.script_launch_mode('subprocess')
@pytest.mark.parametrize('error', [AttributeError(), IOError(), RuntimeError(), ValueError()])
def test_panic(error, monkeypatch, mocker, script_runner):
    args, compiler_flags = object(), object()
    monkeypatch.setattr(frontend, 'parse_args', mocker.Mock(return_value=(args, compiler_flags)))
    monkeypatch.setattr(generator, 'main', mocker.Mock(side_effect=error))
    ret = script_runner.run('drmock-gen', print_result=False)
    assert not ret.success
    assert ret.stderr.startswith('Traceback')
    assert generator.main.called_once_with(args, compiler_flags)
