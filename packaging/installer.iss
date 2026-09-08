#define MyAppName "单位产品能耗对标软件"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "UEBench"
#define MyAppExeName "UEBench.exe"

[Setup]
AppId={{6C4394C8-8A07-4AB3-A9D5-67B18623C3B0}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\UEBench
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installer
OutputBaseFilename=UEBench-Setup-{#MyAppVersion}-x64
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName={#MyAppName}
SetupLogging=yes
SetupIconFile=uebench.ico

[Languages]
; 软件仅面向中文用户，安装向导、取消确认和安装完成页面统一使用简体中文。
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"

[Files]
Source: "..\dist\UEBench\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "uebench.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\release\单位产品能耗对标导入模板.xlsx"; DestDir: "{app}\模板"; Flags: ignoreversion
Source: "..\dist\release\统一标准规则确认表.xlsx"; DestDir: "{app}\规则确认"; Flags: ignoreversion
Source: "..\docs\用户手册.md"; DestDir: "{app}\文档"; Flags: ignoreversion
Source: "..\docs\非程序员验收与AI开发教程.md"; DestDir: "{app}\文档"; Flags: ignoreversion
Source: "..\docs\安装发布说明.md"; DestDir: "{app}\文档"; Flags: ignoreversion
Source: "..\docs\验收记录.md"; DestDir: "{app}\文档"; Flags: ignoreversion
Source: "..\docs\交付清单.md"; DestDir: "{app}\文档"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}\文档"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\uebench.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\uebench.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标："

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动{#MyAppName}"; Flags: nowait postinstall skipifsilent
