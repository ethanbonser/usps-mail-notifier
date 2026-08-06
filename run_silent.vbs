Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonScript = scriptDir & "\scripts\check_mail.py"
WshShell.Run "python """ & pythonScript & """ --listen", 0, False
