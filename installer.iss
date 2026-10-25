
#define MyAppName "CerePhyte"
#define MyAppVersion "5.0.0"
#define MyPublisher "ISLERI"

[Setup]
AppId={{8D923A5E-1C46-4B7D-9A2F-63E5C1A7B840}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyPublisher}
DefaultDirName={localappdata}\Programs\ISLERI\CerePhyte
DefaultGroupName=CerePhyte
PrivilegesRequired=lowest
OutputDir=build\installer
OutputBaseFilename=CerePhyte-Setup-5.0.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
Uninstallable=yes
CloseApplications=force
SetupIconFile=images\isleri.ico

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "build\package\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\CerePhyte"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\desktop.py"""; WorkingDir: "{app}"; IconFilename: "{app}\images\isleri.ico"

Name: "{autodesktop}\CerePhyte"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\desktop.py"""; WorkingDir: "{app}"; IconFilename: "{app}\images\isleri.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\python\python.exe"; Parameters: """{app}\desktop.py"""; WorkingDir: "{app}"; Description: "Launch CerePhyte"; Flags: postinstall nowait skipifsilent
