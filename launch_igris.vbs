' IGRIS OS v4.0 - launcher sin consola
Option Explicit

Dim fso, shell, root, pythonw, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

root = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = root
pythonw = "C:\Python314\pythonw.exe"
If Not fso.FileExists(pythonw) Then pythonw = "C:\Windows\pyw.exe"
cmd = Chr(34) & pythonw & Chr(34) & " " & Chr(34) & root & "\main.py" & Chr(34)
shell.Run cmd, 0, False