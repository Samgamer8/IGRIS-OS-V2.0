' IGRIS OS V2.0 — launcher windowed (sin consola)
' Usa pyw.exe (variante windowed de py.exe) -> pythonw.exe -> main.py
Option Explicit

Dim fso, shell, root, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

root = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = root

cmd = """C:\Windows\pyw.exe"" -3.14 """ & root & "\main.py"""
shell.Run cmd, 0, False
