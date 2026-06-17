' ZCBS LEDSS Session Logger — silent launcher (no terminal window)
Dim sh, dir
Set sh = CreateObject("WScript.Shell")
dir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
sh.Run "pythonw.exe """ & dir & "sun_logger.py""", 0, False
Set sh = Nothing
