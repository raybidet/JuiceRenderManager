; ============================================================
;  Juice | Render Manager for Blender - Inno Setup Script
;  Compilar con Inno Setup 6: https://jrsoftware.org/isinfo.php
;
;  REQUISITO PREVIO: ejecutar build.bat primero para generar
;  la carpeta dist\Juice\
; ============================================================

#define AppName      "Juice | Render Manager for Blender"
#define AppDirName   "Juice Render Manager"
#define AppVersion   "1.0.0"
#define AppPublisher "Franco Basualdo - Tryhard VFX"
#define AppExeName   "Juice.exe"
#define AppID        "{{A3F2C1D4-8B7E-4F9A-B2C3-D4E5F6A7B8C9}"

[Setup]
AppId={#AppID}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} v{#AppVersion}
AppPublisher={#AppPublisher}
AppCopyright=Copyright (C) 2024 {#AppPublisher}

; Directorio de instalacion por defecto
; NOTE: AppName contains '|' which is invalid in Windows paths, so we use
; AppDirName (without the pipe) for the actual install directory.
DefaultDirName={autopf}\{#AppDirName}
DefaultGroupName={#AppName}
AllowNoIcons=yes

; Icono del instalador y del desinstalador
SetupIconFile=logo.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

; Archivo de salida del instalador
OutputDir=dist
OutputBaseFilename=Juice_Setup_v{#AppVersion}

; Compresion
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Apariencia
WizardStyle=modern
WizardSizePercent=120
DisableWelcomePage=no

; Privilegios: intentar instalar para todos los usuarios, caer a usuario actual si no hay permisos
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Minimo Windows 10
MinVersion=10.0

; Informacion de version para el .exe del instalador
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Installer
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}

[Languages]
Name: "spanish";  MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english";  MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";    Description: "Crear acceso directo en el &Escritorio";    GroupDescription: "Accesos directos adicionales:"; Flags: unchecked
Name: "quicklaunchicon"; Description: "Crear acceso directo en la barra de &tareas"; GroupDescription: "Accesos directos adicionales:"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; Todos los archivos del build de PyInstaller
Source: "dist\Juice\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Acceso directo en el Menu Inicio
Name: "{group}\{#AppName}";                    Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"
Name: "{group}\Desinstalar {#AppName}";        Filename: "{uninstallexe}"

; Acceso directo en el Escritorio (opcional)
Name: "{autodesktop}\{#AppName}";              Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

; Acceso directo en la barra de tareas (opcional, solo Windows XP/Vista/7)
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: quicklaunchicon

[Run]
; Ofrecer iniciar la app al terminar la instalacion
Filename: "{app}\{#AppExeName}"; Description: "Iniciar {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Limpiar archivos generados por la app en AppData al desinstalar
Type: filesandordirs; Name: "{userappdata}\Juice"

[Registry]
; Registrar en "Agregar o quitar programas" con informacion extra
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppID}_is1"; ValueType: string; ValueName: "DisplayVersion";  ValueData: "{#AppVersion}"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppID}_is1"; ValueType: string; ValueName: "Publisher";       ValueData: "{#AppPublisher}"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppID}_is1"; ValueType: string; ValueName: "DisplayIcon";     ValueData: "{app}\{#AppExeName}"; Flags: uninsdeletevalue

[Code]
// Verificar si ya hay una version instalada y ofrecer desinstalarla primero
function InitializeSetup(): Boolean;
var
  OldVersion: String;
  UninstallString: String;
  ResultCode: Integer;
begin
  Result := True;
  if RegQueryStringValue(HKA,
    'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppID}_is1',
    'DisplayVersion', OldVersion) then
  begin
    if OldVersion <> '{#AppVersion}' then
    begin
      if MsgBox('Se encontro una version anterior (' + OldVersion + ') instalada.' + #13#10 +
                'Se desinstalara antes de continuar. ¿Desea continuar?',
                mbConfirmation, MB_YESNO) = IDYES then
      begin
        if RegQueryStringValue(HKA,
          'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppID}_is1',
          'UninstallString', UninstallString) then
        begin
          Exec(RemoveQuotes(UninstallString), '/SILENT', '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
        end;
      end else
        Result := False;
    end;
  end;
end;

