[Setup]
AppName=FH6 Mod Manager
AppVersion=1.0.0
DefaultDirName={pf}\FH6 Mod Manager
DefaultGroupName=FH6 Mod Manager
OutputBaseFilename=FH6MM-Setup
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\\FH6MM\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\\FH6 Mod Manager"; Filename: "{app}\\FH6MM.exe"
Name: "{group}\\Uninstall FH6 Mod Manager"; Filename: "{uninstallexe}"
