; Inno Setup script for the UEBench Windows installer (ECQ-RS05).
;
; MyAppVersion is NOT declared here: it comes from version.iss, which
; tools/release_version.py generates from the authoritative version in
; pyproject.toml.  Editing a version number in this file by hand is forbidden
; and `python tools/release_version.py --check` enforces it.
#include "version.iss"

#define MyAppName "单位产品能耗对标软件"
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
; No code-signing certificate is available for this Candidate.  Declared
; explicitly so the Windows "Unknown publisher"/SmartScreen behaviour is a
; known, recorded property of the artifact rather than a surprise.
SignedUninstaller=no

[Languages]
; 软件仅面向中文用户，安装向导、取消确认和安装完成页面统一使用简体中文。
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"

[InstallDelete]
; ECQ-RS05: an upgrade installs into the SAME {autopf}\UEBench directory, and
; every [Files] entry below uses "ignoreversion", so Inno only overwrites files
; whose names still exist in the new build.  Anything left over from the
; previous version survives -- most importantly the whole PyInstaller payload
; under {app}\_internal, including {app}\_internal\migrations.  A stale
; _internal\migrations would make the NEW executable run OLD revision scripts,
; which is worse than a cosmetic mismatch.  So the application payload is
; removed before the new one is laid down.
;
; Scope is strictly {app}.  The user's data directory
; (%LOCALAPPDATA%\UEBench: SQLite database, WAL/SHM, standards, backups, logs,
; imports) is never referenced here, so it survives upgrade and uninstall.
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{app}\{#MyAppExeName}"
Type: filesandordirs; Name: "{app}\文档"
Type: filesandordirs; Name: "{app}\模板"

[Files]
Source: "..\dist\UEBench\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "uebench.ico"; DestDir: "{app}"; Flags: ignoreversion
; The GB 29446 import template is generated headlessly by
; tools/build_release_templates.py through the real WorkbookTemplateService, so
; producing a release never requires opening the GUI and saving by hand.
Source: "..\dist\release\GB29446选煤电力消耗限额导入模板.xlsx"; DestDir: "{app}\模板"; Flags: ignoreversion
Source: "..\docs\用户手册.md"; DestDir: "{app}\文档"; Flags: ignoreversion
Source: "..\docs\安装与发布说明-0.2.0.md"; DestDir: "{app}\文档"; Flags: ignoreversion
Source: "..\docs\交付清单-0.2.0.md"; DestDir: "{app}\文档"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}\文档"; Flags: ignoreversion
; Helper scripts come straight from scripts/ so building the installer does not
; depend on the release directory having been assembled first.
Source: "..\scripts\验收助手.ps1"; DestDir: "{app}\文档"; Flags: ignoreversion
Source: "..\scripts\验收助手.cmd"; DestDir: "{app}\文档"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\uebench.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\uebench.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标："

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动{#MyAppName}"; Flags: nowait postinstall skipifsilent
