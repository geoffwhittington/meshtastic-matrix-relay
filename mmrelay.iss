[Code]
var
  YamlPage: TWizardPage;
  Memo: TMemo;

procedure InitializeWizard();
begin
  // Create the wizard page
  YamlPage := CreateCustomPage(wpWelcome, 'YAML Configuration', 'Enter the YAML configuration for your application:');
  
  // Add a memo control to the page
  Memo := TMemo.Create(WizardForm);
  Memo.Parent := YamlPage.Surface;
  Memo.Align := alClient;
  Memo.ScrollBars := ssBoth;
  Memo.WordWrap := False;
end;

procedure SaveYamlConfig();
var
  YamlText: string;
  ConfigFile: string;
  FileStream: TFileStream;
begin
  // Get the YAML text from the memo control
  YamlText := Memo.Text;
  
  // Save the YAML text to a file
  ConfigFile := ExpandConstant('{app}\config.yaml');
  FileStream := TFileStream.Create(ConfigFile, fmCreate);
  try
    FileStream.WriteBuffer(YamlText[1], Length(YamlText) * SizeOf(Char));
  finally
    FileStream.Free;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  // Save the YAML configuration when the user clicks Next
  if CurPageID = YamlPage.ID then
  begin
    SaveYamlConfig();
  end;
  Result := True;
end;

[Setup]
// Add the custom wizard page to the installation
//WizardImageFile=wizard.bmp
//WizardSmallImageFile=smallwiz.bmp

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
