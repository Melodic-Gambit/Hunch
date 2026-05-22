; Hunch — Inno Setup Script
; Сборка установщика: iscc Hunch.iss  (Inno Setup 6+)

#define MyAppName      "Hunch"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
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
InfoAfterFile=LATEST_CHANGES.txt
OutputDir=dist
OutputBaseFilename=Hunch_v{#MyAppVersion}_installer
SetupIconFile=Hunch.ico
WizardImageFile=installer_banner.bmp
WizardSmallImageFile=installer_small.bmp
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
; Папка настроек в %APPDATA% — создаётся при установке
Name: "{userappdata}\{#MyAppName}"

[UninstallDelete]
; Полностью удаляет %APPDATA%\Hunch при деинсталляции (настройки, логи, кэш)
Type: filesandordirs; Name: "{userappdata}\{#MyAppName}"

[Run]
; Запустить приложение после установки (опционально)
Filename: "{app}\{#MyAppExeName}"; \
  Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
  Flags: nowait postinstall skipifsilent

[UninstallRun]
; Ничего дополнительного при удалении не требуется

[Code]

// ── Windows API ───────────────────────────────────────────────────────────────
function SetWindowTheme(Hwnd: HWND; pszSubAppName: String; pszSubIdList: String): HRESULT;
  external 'SetWindowTheme@uxtheme.dll stdcall';
function SendMessage(hWnd: HWND; Msg: Cardinal; wParam: LongWord; lParam: LongInt): LongInt;
  external 'SendMessageA@user32.dll stdcall';

// ── Brand colours — Windows BGR notation ─────────────────────────────────────
// RGB #1C1C1E → BGR $1E1C1C   RGB #0D9488 → BGR $88940D
const
  CLR_BG    = $1E1C1C;   // #1C1C1E  dark background
  CLR_PANEL = $2D2D2D;   // #2D2D2D  content panels
  CLR_TEAL  = $88940D;   // #0D9488  teal accent
  CLR_WHITE = $F0F0F0;   // near-white text
  CLR_DIM   = $909090;   // dimmed / disabled text

  PBM_SETBARCOLOR = $0409;
  PBM_SETBKCOLOR  = $040A;

// ── Fake button panels ────────────────────────────────────────────────────────
var
  FakeNext, FakeBack, FakeCancel: TPanel;

procedure OnNextClick(Sender: TObject);
begin
  if WizardForm.NextButton.Enabled then WizardForm.NextButton.Click;
end;

procedure OnBackClick(Sender: TObject);
begin
  if WizardForm.BackButton.Enabled then WizardForm.BackButton.Click;
end;

procedure OnCancelClick(Sender: TObject);
begin
  if WizardForm.CancelButton.Enabled then WizardForm.CancelButton.Click;
end;

// Strip accelerator & prefix chars from button captions (e.g. "&Далее >" → "Далее >")
function BtnCaption(Btn: TButton): String;
begin
  Result := StringReplace(Btn.Caption, '&', '', [rfReplaceAll]);
end;

procedure MakeBtn(var P: TPanel; RealBtn: TButton; BgColor: Integer;
  Handler: TNotifyEvent);
begin
  P            := TPanel.Create(WizardForm);
  P.Parent     := WizardForm.BottomPanel;
  P.Left       := RealBtn.Left;
  P.Top        := RealBtn.Top;
  P.Width      := RealBtn.Width;
  P.Height     := RealBtn.Height;
  P.BevelOuter := bvNone;
  P.BevelInner := bvNone;
  P.Color      := BgColor;
  P.Caption    := BtnCaption(RealBtn);
  P.Font.Color := CLR_WHITE;
  P.Font.Size  := 9;
  P.Cursor     := crHandPoint;
  P.OnClick    := Handler;
end;

// Sync captions and enabled-state colours after each page change
procedure SyncBtns;
begin
  FakeNext.Caption := BtnCaption(WizardForm.NextButton);
  if WizardForm.NextButton.Enabled then
  begin
    FakeNext.Color      := CLR_TEAL;
    FakeNext.Font.Color := CLR_WHITE;
  end else begin
    FakeNext.Color      := CLR_PANEL;
    FakeNext.Font.Color := CLR_DIM;
  end;

  if WizardForm.BackButton.Enabled then
    FakeBack.Font.Color := CLR_WHITE
  else
    FakeBack.Font.Color := CLR_DIM;

  if WizardForm.CancelButton.Enabled then
    FakeCancel.Font.Color := CLR_WHITE
  else
    FakeCancel.Font.Color := CLR_DIM;
end;

// ── Theme setup ───────────────────────────────────────────────────────────────
procedure InitializeWizard;
begin
  // Form shell
  WizardForm.Color             := CLR_BG;
  WizardForm.BottomPanel.Color := CLR_BG;
  WizardForm.Bevel.Visible     := False;

  // Teal top header
  WizardForm.MainPanel.Color                 := CLR_TEAL;
  WizardForm.PageNameLabel.Font.Color        := CLR_WHITE;
  WizardForm.PageDescriptionLabel.Font.Color := CLR_WHITE;

  // Inner content area
  WizardForm.InnerPage.Color := CLR_PANEL;

  // Welcome / Finish labels
  WizardForm.WelcomeLabel1.Font.Color := CLR_WHITE;
  WizardForm.WelcomeLabel2.Font.Color := CLR_DIM;
  WizardForm.FinishedLabel.Font.Color := CLR_WHITE;

  // Scrollable text areas
  WizardForm.LicenseMemo.Color        := CLR_PANEL;
  WizardForm.LicenseMemo.Font.Color   := CLR_WHITE;
  WizardForm.InfoAfterMemo.Color      := CLR_PANEL;
  WizardForm.InfoAfterMemo.Font.Color := CLR_WHITE;
  WizardForm.ReadyMemo.Color          := CLR_PANEL;
  WizardForm.ReadyMemo.Font.Color     := CLR_WHITE;

  // Path / group inputs
  WizardForm.DirEdit.Color        := CLR_PANEL;
  WizardForm.DirEdit.Font.Color   := CLR_WHITE;
  WizardForm.GroupEdit.Color      := CLR_PANEL;
  WizardForm.GroupEdit.Font.Color := CLR_WHITE;

  // Task checkboxes
  WizardForm.TasksList.Color      := CLR_PANEL;
  WizardForm.TasksList.Font.Color := CLR_WHITE;

  // Install progress labels
  WizardForm.StatusLabel.Font.Color   := CLR_WHITE;
  WizardForm.FilenameLabel.Font.Color := CLR_DIM;

  // Strip visual themes from system buttons then hide them
  SetWindowTheme(WizardForm.NextButton.Handle,   '', '');
  SetWindowTheme(WizardForm.BackButton.Handle,   '', '');
  SetWindowTheme(WizardForm.CancelButton.Handle, '', '');
  WizardForm.NextButton.Visible   := False;
  WizardForm.BackButton.Visible   := False;
  WizardForm.CancelButton.Visible := False;

  // Coloured replacement panels
  MakeBtn(FakeNext,   WizardForm.NextButton,   CLR_TEAL,  @OnNextClick);
  MakeBtn(FakeBack,   WizardForm.BackButton,   CLR_PANEL, @OnBackClick);
  MakeBtn(FakeCancel, WizardForm.CancelButton, CLR_PANEL, @OnCancelClick);
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  SyncBtns;
  if CurPageID = wpInstalling then
  begin
    SendMessage(WizardForm.ProgressGauge.Handle, PBM_SETBARCOLOR, 0, CLR_TEAL);
    SendMessage(WizardForm.ProgressGauge.Handle, PBM_SETBKCOLOR,  0, CLR_PANEL);
  end;
end;
