[Setup]
AppName=MM Relay
AppVersion=1.0
DefaultDirName={pf}\MM Relay
DefaultGroupName=MM Relay
UninstallFilesDir={app}
OutputDir=.
OutputBaseFilename=MMRelay_setup

[Files]
Source: "dist\mmrelay.exe"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\MM Relay"; Filename: "{app}\mmrelay.exe"

[Run]
Filename: "{app}\mmrelay.exe"; Description: "Launch MM Relay"; Flags: nowait postinstall
