Set WshShell = CreateObject("WScript.Shell")
' Get the directory of the current script
ScriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
' Run the python script from the same directory
WshShell.Run "python """ & ScriptDir & "\check_mail.py"" --listen", 0
Set WshShell = Nothing
