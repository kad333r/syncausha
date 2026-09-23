#define AppName "SyncAusha"
#define AppVersion "1.0.0"
#define AppExe "SyncAusha.exe"
; Créé par l'application tant qu'elle tourne (voir syncausha/app.py).
#define AppMutex "SyncAushaRunning"

[Setup]
AppId={{8F3C2A51-6B7D-4E2A-9C1F-3D5B7A9E4C21}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Silicon
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=SyncAusha-Setup
SetupIconFile=..\syncausha\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
AppMutex={#AppMutex}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "autostart"; Description: "Lancer SyncAusha au démarrage de Windows"; GroupDescription: "Options :"
Name: "desktopicon"; Description: "Créer un raccourci sur le bureau"; GroupDescription: "Options :"; Flags: unchecked

[Files]
Source: "..\dist\SyncAusha\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; ValueData: """{app}\{#AppExe}"" --minimized"; Tasks: autostart

[Run]
Filename: "{app}\{#AppExe}"; Description: "Lancer SyncAusha maintenant"; Flags: nowait postinstall skipifsilent

[Code]
const
  UninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{8F3C2A51-6B7D-4E2A-9C1F-3D5B7A9E4C21}_is1';

var
  DeleteUserData: Boolean;

{ Demande à SyncAusha de se fermer (un envoi en cours est interrompu proprement et reprendra
  au prochain lancement), puis attend jusqu'à 20 s que le mutex de l'application disparaisse. }
procedure CloseRunningApp(const Exe: String);
var
  ResultCode, Waited: Integer;
begin
  if not CheckForMutexes('{#AppMutex}') then
    Exit;
  if FileExists(Exe) then
    Exec(Exe, '--quit', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Waited := 0;
  while CheckForMutexes('{#AppMutex}') and (Waited < 20000) do
  begin
    Sleep(250);
    Waited := Waited + 250;
  end;
end;

{ Mise à jour : Setup vérifie AppMutex juste après InitializeSetup, avant l'assistant. Le dossier
  d'installation n'est pas encore connu : celui de l'installation précédente est lu dans le registre. }
function InitializeSetup(): Boolean;
var
  PreviousDir: String;
begin
  if RegQueryStringValue(HKCU, UninstallKey, 'Inno Setup: App Path', PreviousDir) then
    CloseRunningApp(AddBackslash(PreviousDir) + '{#AppExe}');
  Result := True;
end;

{ SyncAusha relancé pendant l'assistant. }
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  CloseRunningApp(ExpandConstant('{app}\{#AppExe}'));
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  case CurUninstallStep of
    usAppMutexCheck:
      CloseRunningApp(ExpandConstant('{app}\{#AppExe}'));
    usUninstall:
      begin
        RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', '{#AppName}');
        { Question posée avant la suppression des fichiers : SyncAusha.exe doit encore
          exister pour retirer le jeton du Gestionnaire d'identifiants Windows. }
        DeleteUserData := SuppressibleMsgBox('Supprimer aussi vos réglages et l''historique SyncAusha ?',
                                             mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES;
        if DeleteUserData then
          Exec(ExpandConstant('{app}\{#AppExe}'), '--forget-token', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      end;
    usPostUninstall:
      if DeleteUserData then
        DelTree(ExpandConstant('{userappdata}\{#AppName}'), True, True, True);
  end;
end;
