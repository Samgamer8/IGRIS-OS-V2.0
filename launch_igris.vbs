' IGRIS OS - launcher sin consola
Option Explicit

Dim fso, shell, root, pythonw, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

root = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = root
pythonw = root & "\.venv\Scripts\pythonw.exe"
cmd = Chr(34) & pythonw & Chr(34) & " " & Chr(34) & root & "\main.py" & Chr(34)
shell.Run cmd, 0, False
