' IGRIS OS - launcher robusto y compatible con el escritorio
Option Explicit

Dim fso, shell, root, exe, pythonw, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

root = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = root

exe = root & "\dist\IGRIS OS\IGRIS OS.exe"
If fso.FileExists(exe) Then
    shell.Run Chr(34) & exe & Chr(34), 0, False
    WScript.Quit 0
End If

exe = root & "\dist\IGRIS OS.exe"
If fso.FileExists(exe) Then
    shell.Run Chr(34) & exe & Chr(34), 0, False
    WScript.Quit 0
End If

pythonw = "C:\Python314\pythonw.exe"
If Not fso.FileExists(pythonw) Then pythonw = "C:\Windows\pyw.exe"
If Not fso.FileExists(pythonw) Then pythonw = "C:\Python314\python.exe"

cmd = Chr(34) & pythonw & Chr(34) & " " & Chr(34) & root & "\main.py" & Chr(34)
shell.Environment("Process")("PYTHONPATH") = root & "\src"
shell.Environment("Process")("QT_QPA_PLATFORM") = "windows"
' La ejecucion de fondo elimina bloqueos con accesos directos del escritorio.
shell.Run cmd, 0, False