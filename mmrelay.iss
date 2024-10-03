; Inno Setup Script for MMRelay Installer
; This script builds the installer for the MMRelay application,
; incorporating the version number from the GitHub tag.

[Setup]
; Application Information
AppName=Matrix <> Meshtastic Relay
AppVersion={#AppVersion}  ; Use the version passed from GitHub Actions
DefaultDirName={userpf}\MM Relay
DefaultGroupName=MM Relay
UninstallFilesDir={app}

; Output Configuration
OutputDir=.
OutputBaseFilename=MMRelay_setup_{#AppVersion}  ; Include version in installer filename

; Privileges
PrivilegesRequiredOverridesAllowed=dialog commandline

; Uncomment the following lines to add custom wizard images
; WizardImageFile=wizard.bmp
; WizardSmallImageFile=smallwiz.bmp

[Files]
; Source Executable with Version Number
Source: "dist\mmrelay_{#AppVersion}.exe"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs; AfterInstall: AfterInstall(ExpandConstant('{app}'));

[Icons]
; Application Icons
Name: "{group}\MM Relay"; Filename: "{app}\mmrelay.bat"
Name: "{group}\MM Relay Config"; Filename: "{app}\config.yaml"; IconFilename: "{sys}\notepad.exe"; WorkingDir: "{app}"; Parameters: "config.yaml"

[Run]
; Launch the MMRelay application after installation
Filename: "{app}\mmrelay.bat"; Description: "Launch MM Relay"; Flags: nowait postinstall

[Code]
; Pascal Script for Custom Installation Logic

var
  TokenInfoLabel: TLabel;
  TokenInfoLink: TNewStaticText;
  MatrixPage: TInputQueryWizardPage;
  OverwriteConfig: TInputOptionWizardPage;
  MatrixMeshtasticPage: TInputQueryWizardPage;
  MeshtasticPage: TInputQueryWizardPage;
  OptionsPage: TInputOptionWizardPage;
  Connection: string;

procedure TokenInfoLinkClick(Sender: TObject);
var
  ErrorCode: Integer;
begin
  if not ShellExec('', 'open', TNewStaticText(Sender).Caption, '', SW_SHOWNORMAL, ewNoWait, ErrorCode) then
  begin
    // Handle failure if necessary
  end;
end;

procedure InitializeWizard;
begin
  ; Create configuration option page
  OverwriteConfig := CreateInputOptionPage(wpWelcome,
    'Configure the relay', 'Create new configuration',
    '', False, False);
  
  ; Create Matrix Setup page
  MatrixPage := CreateInputQueryPage(OverwriteConfig.ID, 
      'Matrix Setup', 'Configure Matrix Settings',
      'Enter the settings for your Matrix server.');
  
  ; Create Meshtastic Setup page
  MeshtasticPage := CreateInputQueryPage(MatrixPage.ID, 
      'Meshtastic Setup', 'Configure Meshtastic Settings',
      'Enter the settings for connecting with your Meshtastic radio.');
  
  ; Create Matrix <> Meshtastic Setup page
  MatrixMeshtasticPage := CreateInputQueryPage(MeshtasticPage.ID, 
      'Matrix <> Meshtastic Setup', 'Configure Matrix <> Meshtastic Settings',
      'Connect a Matrix room with a Meshtastic radio channel.');
  
  ; Create Additional Options page
  OptionsPage := CreateInputOptionPage(MatrixMeshtasticPage.ID, 
      'Additional Options', 'Provide additional options',
      'Set logging and broadcast options, you can keep the defaults.', False, False);

  ; Increase wizard form height for better layout
  WizardForm.ClientHeight := WizardForm.ClientHeight + 50;
  
  ; Add options to OverwriteConfig page
  OverwriteConfig.Add('Generate configuration (overwrite any current config files)');
  OverwriteConfig.Values[0] := False;

  ; Add input fields to MatrixPage
  MatrixPage.Add('Homeserver (example: https://matrix.org):', False);
  MatrixPage.Add('Bot user ID (example: @mybotuser:matrix.org):', False);
  MatrixPage.Add('Access token (example: syt_bWvzaGjvdD1_PwsXoZgGItImVxBIZbBK_1XZVW8):', False);

  ; Add informational label and link for access token
  TokenInfoLabel := TLabel.Create(WizardForm);
  TokenInfoLabel.Caption := 'For instructions on where to find your access token, visit:';
  TokenInfoLabel.Parent := MatrixPage.Surface;
  TokenInfoLabel.Left := 0;
  TokenInfoLabel.Top := MatrixPage.Edits[2].Top + MatrixPage.Edits[2].Height + 8;

  TokenInfoLink := TNewStaticText.Create(WizardForm);
  TokenInfoLink.Caption := 'https://t2bot.io/docs/access_tokens/';
  TokenInfoLink.Cursor := crHand;
  TokenInfoLink.Font.Color := clBlue;
  TokenInfoLink.Font.Style := [fsUnderline];
  TokenInfoLink.OnClick := @TokenInfoLinkClick;
  TokenInfoLink.Parent := MatrixPage.Surface;
  TokenInfoLink.Left := TokenInfoLabel.Left;
  TokenInfoLink.Top := TokenInfoLabel.Top + TokenInfoLabel.Height;

  ; Set hints for MatrixPage input fields
  MatrixPage.Edits[0].Hint := 'https://example.matrix.org';
  MatrixPage.Edits[1].Hint := '@botuser:example.matrix.org';
  MatrixPage.Edits[2].Hint := 'reaalllllyloooooongsecretttttcodeeeeeeforrrrbot';

  ; Add input fields to MeshtasticPage
  MeshtasticPage.Add('Connection type (network, serial, or ble):', False);
  MeshtasticPage.Add('Serial port (if serial):', False);
  MeshtasticPage.Add('Hostname/IP (if network):', False);
  MeshtasticPage.Add('BLE address/name (if ble):', False);
  MeshtasticPage.Add('Meshnet name:', False);

  ; Set hints for MeshtasticPage input fields
  MeshtasticPage.Edits[0].Hint := 'network, serial, or ble';
  MeshtasticPage.Edits[1].Hint := 'serial port (if serial)';
  MeshtasticPage.Edits[2].Hint := 'hostname/IP (if network)';
  MeshtasticPage.Edits[3].Hint := 'BLE address or name (if ble)';
  MeshtasticPage.Edits[4].Hint := 'Name for radio Meshnet';

  ; Add input fields to MatrixMeshtasticPage
  MatrixMeshtasticPage.Add('Matrix room ID/alias (example: #someroom:example.matrix.org):', False);
  MatrixMeshtasticPage.Add('Meshtastic channel # (0 is primary, 1-7 secondary):', False);

  ; Set hints for MatrixMeshtasticPage input fields
  MatrixMeshtasticPage.Edits[0].Hint := '!someroomid:example.matrix.org';
  MatrixMeshtasticPage.Edits[1].Hint := '0-7 (default 0)';

  ; Add options to OptionsPage
  OptionsPage.Add('Detailed logging');
  OptionsPage.Add('Radio broadcasts enabled');
  OptionsPage.Values[0] := True;
  OptionsPage.Values[1] := True;
end;

; Helper function to convert Boolean to String
function BoolToStr(Value: Boolean): String;
begin
  if Value then
    result := 'true'
  else
    result := 'false';
end;

; Determines whether to skip a wizard page based on user input
function ShouldSkipPage(PageID: Integer): Boolean;
begin
  if PageID = OverwriteConfig.ID then
    Result := False
  else
    Result := Not OverwriteConfig.Values[0];
end;

; Procedure to handle actions after installation
procedure AfterInstall(sAppDir: string);
var
  config: string;
  connection_type: string;
  serial_port: string;
  host: string;
  ble_address: string;
  log_level: string;
  batch_file: string;
begin
  ; Exit if user chose not to overwrite existing config
  If Not OverwriteConfig.Values[0] then
    Exit;

  ; Backup existing config if it exists
  if (FileExists(sAppDir + '\config.yaml')) then
  begin
    RenameFile(sAppDir + '\config.yaml', sAppDir + '\config-old.yaml');
  end;

  ; Retrieve user inputs from MeshtasticPage
  connection_type := MeshtasticPage.Values[0];
  serial_port := MeshtasticPage.Values[1];
  host := MeshtasticPage.Values[2];
  ble_address := MeshtasticPage.Values[3];

  ; Determine logging level based on user input
  if OptionsPage.Values[0] then
  begin
    log_level := 'debug';
  end
  else
  begin
    log_level := 'info';
  end;

  ; Construct the configuration content
  config := 'matrix:' + #13#10 +
            '  homeserver: "' + MatrixPage.Values[0] + '"' + #13#10 +
            '  bot_user_id: "' + MatrixPage.Values[1] + '"' + #13#10 +
            '  access_token: "' + MatrixPage.Values[2] + '"' + #13#10 +
            'matrix_rooms:' + #13#10 +
            '  - id: "' + MatrixMeshtasticPage.Values[0] + '"' + #13#10 +
            '    meshtastic_channel: ' + MatrixMeshtasticPage.Values[1] + #13#10 +
            'meshtastic:' + #13#10 +
            '  connection_type: "' + connection_type + '"' + #13#10;

  ; Append connection-specific settings
  if connection_type = 'serial' then
    config := config + '  serial_port: "' + serial_port + '"' + #13#10
  else if connection_type = 'network' then
    config := config + '  host: "' + host + '"' + #13#10
  else if connection_type = 'ble' then
    config := config + '  ble_address: "' + ble_address + '"' + #13#10;

  ; Continue constructing the configuration
  config := config + '  meshnet_name: "' + MeshtasticPage.Values[4] + '"' + #13#10 +
            '  broadcast_enabled: ' + BoolToStr(OptionsPage.Values[1]) + #13#10 +
            'logging:' + #13#10 +
            '  level: "' + log_level + '"' + #13#10 +
            'plugins:' + #13#10;

  ; Save the configuration to config.yaml
  if Not SaveStringToFile(sAppDir + '\config.yaml', config, false) then
  begin
    MsgBox('Could not create config file "config.yaml". Close any applications that may have it open and re-run setup', mbInformation, MB_OK);
  end;

  ; Create the batch file to launch the application with the versioned executable
  batch_file := '"' + sAppDir + '\mmrelay_' + '{#AppVersion}' + '.exe" config.yaml ' + #13#10 +
                'pause';

  ; Save the batch file as mmrelay.bat
  if Not SaveStringToFile(sAppDir + '\mmrelay.bat', batch_file, false) then
  begin
    MsgBox('Could not create batch file "mmrelay.bat". Close any applications that may have it open and re-run setup', mbInformation, MB_OK);
  end;
end;
