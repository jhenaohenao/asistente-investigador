@echo off
schtasks /Delete /F /TN "InvestigadorLocal_BusquedaDiaria"
echo Busqueda diaria desactivada. Tus datos (datos.sqlite y biblioteca) no se borraron.
pause
