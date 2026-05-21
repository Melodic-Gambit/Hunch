; Hunch — Inno Setup Script
; Сборка установщика: iscc Hunch.iss  (Inno Setup 6+)

#define MyAppName      "Hunch"
#define MyAppVersion   "3.1.1"
#define MyAppPublisher "Hunch"
#define MyAppExeName   "Hunch.exe"
#define MyAppDir       "dist\Hunch"

[Setup]
; GUID установки — не изменять после первого релиза
AppId={{F3A7C2E1-8D45-4B9F-A123-456789ABCDEF}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=LICENSE.txt
InfoAfterFile=CHANGELOG.md
OutputDir=dist
OutputBaseFilename=Hunch_v{#MyAppVersion}_installer
SetupIconFile=support_system.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Требуем 64-бит Windows
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
; Минимальная версия ОС — Windows 10
MinVersion=10.0

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Все файлы из папки dist\Hunch\
Source: "{#MyAppDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Ярлык в меню «Пуск»
Name: "{group}\{#MyAppName}";                            Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}";      Filename: "{uninstallexe}"
; Ярлык на рабочем столе (необязательно, задаётся в Tasks)
Name: "{commondesktop}\{#MyAppName}";                    Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Dirs]
; Папка настроек в %APPDATA% — создаётся при установке, удаляется при деинсталляции
Name: "{userappdata}\{#MyAppName}"; Flags: uninsalwaysuninstall

[Run]
; Запустить приложение после установки (опционально)
Filename: "{app}\{#MyAppExeName}"; \
  Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
  Flags: nowait postinstall skipifsilent

[UninstallRun]
; Ничего дополнительного при удалении не требуется

[Code]
// Дополнительный Pascal-код при необходимости можно добавить здесь.
