"""Read-only root-confined file handles; no scans, writes or link traversal."""
from __future__ import annotations

from contextlib import ExitStack
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys

from .models import ContractError


class IntakeError(ContractError):
    def __init__(self, code: str, *, name: str | None = None):
        self.code = code
        self.name = name
        super().__init__(code + (': ' + name if name else ''))


def relative_parts(name: str) -> tuple[str, ...]:
    if not isinstance(name, str) or not 1 <= len(name) <= 512:
        raise IntakeError('INVALID_PATH')
    try:
        name.encode('utf-8')
    except UnicodeError as exc:
        raise IntakeError('INVALID_PATH') from exc
    path = PurePosixPath(name)
    if (path.is_absolute() or path.as_posix() != name or name in {'.', '..'}
        or len(path.parts) > 20 or any(ord(c) < 32 for c in name)
        or '\\' in name or ':' in name or '..' in path.parts):
        raise IntakeError('INVALID_PATH')
    for part in path.parts:
        if (part.endswith((' ', '.')) or part.casefold().startswith('.env')
            or re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', part)
            or Path(part).suffix.lower() in {'.pem', '.key', '.token', '.pfx', '.p12'}):
            raise IntakeError('FORBIDDEN_PATH')
    return path.parts


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_nlink)


class FileRoot:
    """Own all ancestor handles until both byte passes are complete."""
    def __init__(self, root):
        try:
            value=os.fspath(root)
            if not isinstance(value,str) or not value.strip() or '\x00' in value:
                raise ValueError('invalid root')
            self.root = Path(os.path.abspath(value))
        except (ValueError,TypeError,UnicodeError) as exc:
            raise IntakeError('INVALID_ROOT') from exc
        if self.root.anchor.startswith('\\\\') or len(self.root.parts) > 64:
            raise IntakeError('UNSUPPORTED_ROOT')
        self.stack = ExitStack()
        self.directories = []
        self.windows = None

    def __enter__(self):
        try:
            if os.name == 'nt':
                self.windows = _WindowsReader(self.stack)
                for path in [Path(self.root.anchor), *list(reversed(self.root.parents))[1:], self.root]:
                    if path in [p for p, _ in self.directories]: continue
                    handle = self.windows.open(path, directory=True)
                    self.directories.append((path, handle))
            elif os.name == 'posix' and hasattr(os, 'O_NOFOLLOW'):
                flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
                fd = os.open(self.root.anchor, flags)
                self.stack.callback(os.close, fd)
                self.directories.append((None, self.root.anchor, fd, os.fstat(fd)))
                for part in self.root.parts[1:]:
                    child = os.open(part, flags, dir_fd=fd)
                    self.stack.callback(os.close, child)
                    self.directories.append((fd, part, child, os.fstat(child)))
                    fd = child
                self.fd = fd
            else:
                raise IntakeError('UNSUPPORTED_SECURE_READ')
            return self
        except (OSError, IntakeError) as exc:
            self.stack.close()
            if isinstance(exc, IntakeError): raise
            raise IntakeError('ROOT_UNAVAILABLE_OR_UNSAFE') from exc

    def __exit__(self, *args):
        self.stack.close()

    def _check_directories(self):
        if self.windows:
            # Windows handles deny WRITE/DELETE sharing; a rename/reparse replacement
            # cannot redirect any parent while these handles remain open.
            for _, handle in self.directories:
                self.windows.info(handle, directory=True)
            return
        for parent, name, fd, expected in self.directories:
            current = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if (not stat.S_ISDIR(current.st_mode)
                or (current.st_dev, current.st_ino) != (expected.st_dev, expected.st_ino)
                or (os.fstat(fd).st_dev, os.fstat(fd).st_ino) != (expected.st_dev, expected.st_ino)):
                raise IntakeError('SOURCE_CHANGED')

    def read(self, name: str, maximum: int):
        parts = relative_parts(name)
        try:
            with ExitStack() as files:
                if self.windows:
                    parent = self.root
                    for part in parts[:-1]:
                        parent = parent / part
                        handle = self.windows.open(parent, directory=True)
                        self.directories.append((parent, handle))
                    handle = self.windows.open(self.root.joinpath(*parts), directory=False, stack=files)
                    before = self.windows.info(handle, directory=False)
                    if before['size'] > maximum:
                        raise IntakeError('FILE_BYTE_LIMIT', name=name)
                    self._check_directories()
                    data = self.windows.read(handle, maximum)
                    after = self.windows.info(handle, directory=False)
                    identity = before['identity']
                    if after != before: raise IntakeError('SOURCE_CHANGED', name=name)
                else:
                    parent = self.fd
                    for part in parts[:-1]:
                        child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
                        self.stack.callback(os.close, child)
                        self.directories.append((parent, part, child, os.fstat(child)))
                        parent = child
                    fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parent)
                    files.callback(os.close, fd)
                    before = os.fstat(fd)
                    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                        raise IntakeError('NON_REGULAR_OR_LINKED', name=name)
                    if before.st_size > maximum: raise IntakeError('FILE_BYTE_LIMIT', name=name)
                    self._check_directories()
                    chunks = []; remaining = maximum + 1
                    while remaining:
                        block = os.read(fd, min(65536, remaining))
                        if not block: break
                        chunks.append(block); remaining -= len(block)
                    data = b''.join(chunks)
                    if _identity(os.fstat(fd)) != _identity(before):
                        raise IntakeError('SOURCE_CHANGED', name=name)
                    current = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
                    if _identity(current) != _identity(before): raise IntakeError('SOURCE_CHANGED', name=name)
                    identity = _identity(before)
                if len(data) > maximum: raise IntakeError('FILE_BYTE_LIMIT', name=name)
                self._check_directories()
                return data, identity
        except FileNotFoundError as exc:
            raise IntakeError('FILE_MISSING', name=name) from exc
        except OSError as exc:
            raise IntakeError('FILE_UNAVAILABLE_OR_UNSAFE', name=name) from exc


class _WindowsReader:
    """Win32 read-only handles, reparse refusal and no write/delete sharing."""
    def __init__(self, stack):
        import ctypes
        from ctypes import wintypes
        self.c = ctypes; self.w = wintypes; self.stack = stack
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        class Info(ctypes.Structure):
            _fields_ = [('attributes', wintypes.DWORD), ('created', wintypes.FILETIME),
                        ('accessed', wintypes.FILETIME), ('written', wintypes.FILETIME),
                        ('volume', wintypes.DWORD), ('size_high', wintypes.DWORD),
                        ('size_low', wintypes.DWORD), ('links', wintypes.DWORD),
                        ('index_high', wintypes.DWORD), ('index_low', wintypes.DWORD)]
        self.Info = Info
        self.kernel.CreateFileW.argtypes = [wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        self.kernel.CreateFileW.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]; self.kernel.CloseHandle.restype = wintypes.BOOL
        self.kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE,ctypes.POINTER(Info)]
        self.kernel.GetFileInformationByHandle.restype = wintypes.BOOL
        self.kernel.GetFileType.argtypes = [wintypes.HANDLE]; self.kernel.GetFileType.restype = wintypes.DWORD
        self.kernel.ReadFile.argtypes = [wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),ctypes.c_void_p]
        self.kernel.ReadFile.restype = wintypes.BOOL

    def open(self, path, *, directory, stack=None):
        sys.audit('rag_lab.intake_open', str(path), directory)
        # OPEN_EXISTING, OPEN_REPARSE_POINT; only READ sharing on files AND
        # directories. Denying WRITE also prevents a parent from being changed
        # into a reparse point between checks. No file is created or modified.
        flags = 0x00200000 | (0x02000000 if directory else 0x08000000)
        handle = self.kernel.CreateFileW(str(path), 0x80000000, 1, None, 3, flags, None)
        if handle == self.w.HANDLE(-1).value:
            error = self.c.get_last_error()
            if error in (2,3): raise FileNotFoundError(error, 'intake file missing')
            raise OSError(error, 'intake handle refused')
        (stack or self.stack).callback(self.kernel.CloseHandle, handle)
        self.info(handle, directory=directory)
        return handle

    def info(self, handle, *, directory):
        value = self.Info()
        if not self.kernel.GetFileInformationByHandle(handle, self.c.byref(value)):
            raise OSError(self.c.get_last_error(), 'intake metadata unavailable')
        if (value.attributes & 0x400 or bool(value.attributes & 0x10) != directory
            or self.kernel.GetFileType(handle) != 1 or (not directory and value.links != 1)):
            raise IntakeError('NON_REGULAR_OR_LINKED')
        size = (value.size_high << 32) | value.size_low
        return {'size':size,'identity':(value.volume,value.index_high,value.index_low,size,
                                        value.written.dwHighDateTime,value.written.dwLowDateTime,
                                        value.created.dwHighDateTime,value.created.dwLowDateTime,value.links,value.attributes)}

    def read(self, handle, maximum):
        chunks=[]; remaining=maximum+1
        while remaining:
            size=min(65536,remaining);buffer=self.c.create_string_buffer(size);count=self.w.DWORD()
            if not self.kernel.ReadFile(handle,buffer,size,self.c.byref(count),None):
                raise OSError(self.c.get_last_error(),'intake read failed')
            if not count.value:break
            chunks.append(buffer.raw[:count.value]);remaining-=count.value
        return b''.join(chunks)
