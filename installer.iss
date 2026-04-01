; ============================================================
;  Juice - Render Manager for Blender - Inno Setup Script
;  Compatible con Inno Setup 6
; ============================================================

#define AppName      "Juice - Render Manager for Blender"
#define AppDirName   "Juice Render Manager"
#define AppVersion   "1.1.0"
#define AppPublisher "Franco Basualdo - Tryhard VFX"
#define AppExeName   "Juice.exe"
#define AppID        "{{A3F2C1D4-8B7E-4F9A-B2C3-D4E5F6A7B8C9}"
#define BuildDir     "dist\Juice"

[Setup]
AppId={#AppID}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} v{#AppVersion}
AppPublisher={#AppPublisher}
AppCopyright=Copyright (C) 2024 {#AppPublisher}

DefaultDirName={autopf}\{#AppDirName}
DefaultGroupName={#AppName}
AllowNoIcons=yes

SetupIconFile=logo.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

OutputDir=dist
OutputBaseFilename=Juice_Setup_v{#AppVersion}

Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

WizardStyle=modern
WizardSizePercent=120
DisableWelcomePage=no

PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
MinVersion=10.0

VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Installer
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el &Escritorio"; GroupDescription: "Accesos directos adicionales:"; Flags: unchecked

[Files]
; Copiar salida completa de PyInstaller onedir
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";             Filename: "{app}\{#AppExeName}"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";       Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; Lanzar app al finalizar (sin shellexec para evitar ShellExecuteEx code 2)
Filename: "{app}\{#AppExeName}"; Description: "Iniciar {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\Juice"

[Registry]
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppID}_is1"; ValueType: string; ValueName: "DisplayVersion"; ValueData: "{#AppVersion}"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppID}_is1"; ValueType: string; ValueName: "Publisher"; ValueData: "{#AppPublisher}"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppID}_is1"; ValueType: string; ValueName: "DisplayIcon"; ValueData: "{app}\{#AppExeName}"; Flags: uninsdeletevalue

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if not FileExists(ExpandConstant('{app}\{#AppExeName}')) then
    begin
      MsgBox('Instalación incompleta: no se encontró "{#AppExeName}" en la carpeta de instalación.' + #13#10 +
             'Recompila con build.bat y vuelve a instalar.',
             mbCriticalError, MB_OK);
    end;
  end;
end;
