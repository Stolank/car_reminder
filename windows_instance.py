"""Coordinate Windows launches that use the same data file."""

import ctypes
from ctypes import wintypes
import hashlib
import os


class WindowsInstance:
    def __init__(self, data_file):
        path = os.path.normcase(os.path.realpath(data_file))
        name = "Local\\CarReminder-" + hashlib.sha256(os.fsencode(path)).hexdigest()
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateEventW": ([ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE),
            "CreateMutexW": ([ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE),
            "SetEvent": ([wintypes.HANDLE], wintypes.BOOL),
            "WaitForSingleObject": ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
        }
        for function, (args, result) in signatures.items():
            method = getattr(kernel, function)
            method.argtypes, method.restype = args, result
        self.kernel = kernel
        self.event = kernel.CreateEventW(None, False, False, name + "-activate")
        if not self.event:
            raise ctypes.WinError(ctypes.get_last_error())
        self.mutex = None
        try:
            ctypes.set_last_error(0)
            self.mutex = kernel.CreateMutexW(None, False, name)
            error = ctypes.get_last_error()
            if not self.mutex:
                raise ctypes.WinError(error)
            self.primary = error != 183  # ERROR_ALREADY_EXISTS
            if not self.primary and not kernel.SetEvent(self.event):
                raise ctypes.WinError(ctypes.get_last_error())
        except OSError:
            self.close()
            raise

    def activation_requested(self):
        return self.kernel.WaitForSingleObject(self.event, 0) == 0

    def close(self):
        for handle in (self.mutex, self.event):
            if handle:
                self.kernel.CloseHandle(handle)
        self.mutex = self.event = None
