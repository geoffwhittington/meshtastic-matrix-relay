[Setup]
// Add the custom wizard page to the installation
//WizardImageFile=wizard.bmp
//WizardSmallImageFile=smallwiz.bmp

AppName=Matrix <> Meshtastic Relay
AppVersion=1.0
DefaultDirName={userpf}\MM Relay
DefaultGroupName=MM Relay
UninstallFilesDir={app}
OutputDir=.
OutputBaseFilename=MMRelay_setup
PrivilegesRequiredOverridesAllowed=dialog commandline

[Files]
Source: "dist\mmrelay.exe"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs; AfterInstall: AfterInstall(ExpandConstant('{app}'));

[Icons]
Name: "{group}\MM Relay"; Filename: "{app}\mmrelay.bat"

[Run]
Filename: "{app}\mmrelay.bat"; Description: "Launch MM Relay"; Flags: nowait postinstall

[Code]
var
  MatrixPage : TInputQueryWizardPage;
  OverwriteConfig: TInputOptionWizardPage;
  MatrixMeshtasticPage : TInputQueryWizardPage;
  MeshtasticConnectionPage: TInputOptionWizardPage;
  MeshtasticPage : TInputQueryWizardPage;
  OptionsPage : TInputOptionWizardPage;
  Connection: string;

procedure InitializeWizard;
begin
  OverwriteConfig := CreateInputOptionPage(wpWelcome,
    'Configure the relay', 'Create new configuration',
    '', False, False);
  MatrixPage := CreateInputQueryPage(OverwriteConfig.ID, 
      'Matrix Setup', 'Configure Matrix Settings',
      'Enter the settings for your Matrix server.');
  MeshtasticConnectionPage := CreateInputOptionPage(MatrixPage.ID, 
      'Meshtastic Setup', 'Meshtastic Connection',
      'Connect to Meshtastic Radio using Network or Serial connection.', False, True);
  MeshtasticPage := CreateInputQueryPage(MeshtasticConnectionPage.ID, 
      'Meshtastic Setup', 'Configure Meshtastic Settings',
      'Enter the settings for connecting with your Meshtastic radio.');
  MatrixMeshtasticPage := CreateInputQueryPage(MeshtasticPage.ID, 
      'Matrix <> Meshtastic Setup', 'Configure Matrix <> Meshtastic Settings',
      'Connect a Matrix room with a Meshtastic radio channel.');
  OptionsPage := CreateInputOptionPage(MatrixMeshtasticPage.ID, 
      'Additional Options', 'Provide additional optios',
      'Set logging and broadcast options, you can keep the defaults.', False, False);
  
  OverwriteConfig.Add('Generate configuration (overwrite any current config files)');
  OverwriteConfig.Values[0] := True;

  MatrixPage.Add('Homeserver', False);
  MatrixPage.Add('Access token', False);
  MatrixPage.Add('Bot User ID', False);
  MatrixPage.Edits[0].Hint := 'https://example.matrix.org';
  MatrixPage.Edits[1].Hint := 'reaalllllyloooooongsecretttttcodeeeeeeforrrrbot';
  MatrixPage.Edits[2].Hint := '@botuser:example.matrix.org';

  MeshtasticConnectionPage.Add('Serial');
  MeshtasticConnectionPage.Add('Network');

  MeshtasticPage.Add('Network host/Serial port', False);
  MeshtasticPage.Add('Meshnet Name', False);
  MeshtasticPage.Edits[0].Hint := 'serial port or TCP host'
  MeshtasticPage.Edits[1].Hint := 'Name for radio Meshnet'

  MatrixMeshtasticPage.Add('Matrix Room ID', False);
  MatrixMeshtasticPage.Add('Meshtastic Channel', False);
  MatrixMeshtasticPage.Edits[0].Hint := '!someroomid:example.matrix.org';
  MatrixMeshtasticPage.Edits[1].Hint := '0-10 (default 0)';

  OptionsPage.Add('Detailed logging');
  OptionsPage.Add('Radio broadcasts enabled');
  OptionsPage.Values[0] := True
  OptionsPage.Values[1] := False
end;

function BoolToStr(Value : Boolean): String;
begin
  if Value then
    result := 'true'
  else
    result := 'false';
end;

{ Skips config setup pages if needed}
function ShouldSkipPage(PageID: Integer): Boolean;
begin
  if PageID = OverwriteConfig.ID then
      Result := False
  else
      Result := Not OverwriteConfig.Values[0];
end;

procedure AfterInstall(sAppDir: string);
var
    config: string;
    connection_type: string;
    serial_port: string;
    host: string;
    log_level: string;
    batch_file: string;
begin
    If Not OverwriteConfig.Values[0] then
      Exit;

    if (FileExists(sAppDir+'/config.yaml')) then
    begin
        RenameFile(sAppDir+'/config.yaml', sAppDir+'/config-old.yaml');
    end;

    if MeshtasticConnectionPage.Values[0] then
    begin
        connection_type := 'serial';
        serial_port := MeshtasticPage.Values[0]
    end
    else
    begin
        connection_type := 'network';
        host := MeshtasticPage.Values[0]
    end;

    if OptionsPage.Values[1] then
    begin
        log_level := 'debug';
    end
    else
    begin
        log_level := 'info';
    end;

    config := 'matrix:' + #13#10 +
              '  homeserver: "' + MatrixPage.Values[0] + '"' +  #13#10 +
              '  access_token: "' + MatrixPage.Values[1] + '"' +  #13#10 +
              '  bot_user_id: "' + MatrixPage.Values[2] + '"' + #13#10 +
              'matrix_rooms:' + #13#10 +
              '  - id: "' + MatrixMeshtasticPage.Values[0] + '"' + #13#10 +
              '    meshtastic_channel: ' + MatrixMeshtasticPage.Values[1] + #13#10 +
              'meshtastic:' + #13#10 +
              '  connection_type: "' + connection_type + '"' + #13#10 +
              '  serial_port: "' + serial_port + '"' + #13#10 +
              '  host: "' + host + '"' + #13#10 +
              '  meshnet_name: "' + MeshtasticPage.Values[1] + '"' + #13#10 +
              '  broadcast_enabled: ' + BoolToStr(OptionsPage.Values[1]) + #13#10 +
              'logging:' + #13#10 +
              '  level: "' + log_level + '"' + #13#10;

    if Not SaveStringToFile(sAppDir+'/config.yaml', config, false) then
    begin
        MsgBox('Could not create config file "config.yaml". Close any applications that may have it open and re-run setup', mbInformation, MB_OK);
    end;


    batch_file := '"' + sAppDir+ '\mmrelay.exe" config.yaml ' + #13#10 +
                  'pause'

    if Not SaveStringToFile(sAppDir+'/mmrelay.bat', batch_file, false) then
    begin
        MsgBox('Could not create batch file "relay.bat". Close any applications that may have it open and re-run setup', mbInformation, MB_OK);
    end;
end;
