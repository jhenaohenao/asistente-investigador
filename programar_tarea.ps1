# Registra la busqueda diaria en el Programador de tareas de Windows.
# StartWhenAvailable: si el PC estaba apagado a la hora, corre apenas se encienda.
$raiz = $PSScriptRoot
$accion = New-ScheduledTaskAction -Execute (Join-Path $raiz ".venv\Scripts\pythonw.exe") `
          -Argument ('"' + (Join-Path $raiz "buscar_diario.py") + '"') -WorkingDirectory $raiz
$disparador = New-ScheduledTaskTrigger -Daily -At 7am
$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "InvestigadorLocal_BusquedaDiaria" -Action $accion `
    -Trigger $disparador -Settings $ajustes -Force | Out-Null
