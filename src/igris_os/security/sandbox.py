# -*- coding: utf-8 -*-
"""Ejecucion endurecida de subprocesos con Job Objects de Windows.

Anade limites reales al taller de ejecucion (mas alla de la lista negra de
comandos):

- limite de memoria por proceso y por trabajo;
- limite de tiempo de CPU por proceso y por trabajo;
- ``KILL_ON_JOB_CLOSE``: al cerrar el trabajo, el proceso y sus hijos mueren;
- ventana sin consola (``CREATE_NO_WINDOW``).

En sistemas no Windows cae a un ``subprocess.run`` con timeout (sin los limites
de memoria/CPU, que son especificos del SO).
"""

from __future__ import annotations

import ctypes
import os
import subprocess
from ctypes import wintypes
from dataclasses import dataclass

JOB_OBJECT_LIMIT_PROCESS_TIME = 0x00000002
JOB_OBJECT_LIMIT_JOB_TIME = 0x00000004
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

JobObjectExtendedLimitInformation = 9

CREATE_SUSPENDED = 0x00000004
THREAD_SUSPEND_RESUME = 0x0002
TH32CS_SNAPTHREAD = 0x00000004

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


@dataclass(frozen=True, slots=True)
class SandboxRun:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    sandboxed: bool = False


class THREADENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ThreadID", wintypes.DWORD),
        ("th32OwnerProcessID", wintypes.DWORD),
        ("tpBasePri", ctypes.c_long),
        ("tpDeltaPri", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
    ]


class JobObjectSandbox:
    """Ejecuta un comando confinado en un Job Object de Windows.

    El proceso hijo se crea SUSPENDIDO, se asigna al job y luego se reanuda:
    asi no hay ventana de carrera en la que el proceso pueda escapar del
    confinamiento.
    """

    def __init__(self, memory_limit_mb: int = 1024,
                 cpu_seconds: int = 60,
                 max_processes: int = 4) -> None:
        self.memory_limit_mb = max(64, memory_limit_mb)
        self.cpu_seconds = max(1, cpu_seconds)
        self.max_processes = max(1, max_processes)
        self._windows = os.name == "nt"

    def run(self, command: list[str], *, timeout: int = 30,
            cwd: str | None = None,
            env: dict[str, str] | None = None) -> SandboxRun:
        if not self._windows:
            return self._plain_run(command, timeout, cwd, env)
        job = self._create_job()
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | CREATE_SUSPENDED
        try:
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True, cwd=cwd, env=env, creationflags=creationflags)
        except OSError as exc:
            if job:
                self._close(job)
            return SandboxRun(-1, "", str(exc))
        sandboxed = self._assign(job, process) if job else False
        self._resume(process.pid)
        try:
            out, err = process.communicate(timeout=timeout)
            return SandboxRun(process.returncode, out or "", err or "",
                              False, sandboxed)
        except subprocess.TimeoutExpired:
            if job:
                self._terminate(job)
            process.kill()
            try:
                out, err = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                out, err = "", ""
            return SandboxRun(process.returncode, out or "", err or "",
                              True, sandboxed)
        finally:
            if job:
                self._close(job)

    @staticmethod
    def _plain_run(command, timeout, cwd, env) -> SandboxRun:
        try:
            run = subprocess.run(command, capture_output=True, text=True,
                                 stdin=subprocess.DEVNULL,
                                 timeout=timeout, cwd=cwd, env=env)
            return SandboxRun(run.returncode, run.stdout or "",
                              run.stderr or "")
        except subprocess.TimeoutExpired:
            return SandboxRun(-1, "", "agoto el tiempo", True)

    def _create_job(self):
        kernel32 = _kernel32
        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            return None
        info = _ExtendedLimitInformation()
        info.BasicLimitInformation.LimitFlags = (
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE |
            JOB_OBJECT_LIMIT_PROCESS_MEMORY |
            JOB_OBJECT_LIMIT_JOB_MEMORY |
            JOB_OBJECT_LIMIT_PROCESS_TIME |
            JOB_OBJECT_LIMIT_JOB_TIME |
            JOB_OBJECT_LIMIT_ACTIVE_PROCESS)
        info.BasicLimitInformation.PerProcessUserTimeLimit = \
            10_000_000 * self.cpu_seconds
        info.BasicLimitInformation.PerJobUserTimeLimit = \
            10_000_000 * self.cpu_seconds * 4
        info.BasicLimitInformation.ActiveProcessLimit = self.max_processes
        info.ProcessMemoryLimit = self.memory_limit_mb * 1024 * 1024
        info.JobMemoryLimit = self.memory_limit_mb * 1024 * 1024 * 4
        ok = kernel32.SetInformationJobObject(
            wintypes.HANDLE(handle), JobObjectExtendedLimitInformation,
            ctypes.byref(info), ctypes.sizeof(info))
        if not ok:
            kernel32.CloseHandle(wintypes.HANDLE(handle))
            return None
        return handle

    @staticmethod
    def _assign(job, process) -> bool:
        kernel32 = _kernel32
        return bool(kernel32.AssignProcessToJobObject(
            wintypes.HANDLE(job), wintypes.HANDLE(process._handle)))

    @staticmethod
    def _resume(pid: int) -> None:
        kernel32 = _kernel32
        tid = JobObjectSandbox._primary_thread_id(kernel32, pid)
        if not tid:
            return
        thread = kernel32.OpenThread(THREAD_SUSPEND_RESUME, False, tid)
        if thread:
            kernel32.ResumeThread(thread)
            kernel32.CloseHandle(wintypes.HANDLE(thread))

    @staticmethod
    def _primary_thread_id(kernel32, pid: int) -> int | None:
        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, pid)
        if snap == -1:
            return None
        try:
            entry = THREADENTRY32()
            entry.dwSize = ctypes.sizeof(THREADENTRY32)
            if not kernel32.Thread32First(snap, ctypes.byref(entry)):
                return None
            tids = []
            while True:
                if entry.th32OwnerProcessID == pid:
                    tids.append(int(entry.th32ThreadID))
                if not kernel32.Thread32Next(snap, ctypes.byref(entry)):
                    break
            return min(tids) if tids else None
        finally:
            kernel32.CloseHandle(wintypes.HANDLE(snap))

    @staticmethod
    def _terminate(job) -> None:
        kernel32 = _kernel32
        kernel32.TerminateJobObject(wintypes.HANDLE(job), 1)

    @staticmethod
    def _close(job) -> None:
        kernel32 = _kernel32
        kernel32.CloseHandle(wintypes.HANDLE(job))


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong)]


class _BasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _ExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimitInformation),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]
