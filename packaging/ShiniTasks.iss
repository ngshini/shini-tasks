; Shini Tasks — bo cai Windows (Inno Setup 6)
; Cau truc thu muc cai: ShiniTasks.exe + _internal\ (app GTK) va
; ShiniTasksEngine.exe (1 file) nam CANH nhau — app tu bat engine khi can,
; engine giu phim Alt+E va tu chay cung Windows qua muc Startup o duoi.
; DU LIEU nguoi dung nam o %APPDATA%\Shini Tasks — go cai KHONG xoa du lieu.

[Setup]
AppId={{9D4F2A71-3C8E-4B5A-A6D1-2E7F8B0C4D55}
AppName=Shini Tasks
AppVersion=1.2.0
AppPublisher=Shini Web
DefaultDirName={autopf}\Shini Tasks
DefaultGroupName=Shini Tasks
OutputDir=..\build\installer
OutputBaseFilename=ShiniTasks-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Languages]
; File ngon ngu kem theo repo (ban Inno tren may build khong co san tieng Viet)
Name: "vi"; MessagesFile: "Vietnamese.isl"

[Tasks]
Name: "desktopicon"; Description: "Tao bieu tuong ngoai man hinh Desktop"; GroupDescription: "Tuy chon them:"

[Files]
Source: "..\build\dist\ShiniTasks\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Shini Tasks"; Filename: "{app}\ShiniTasks.exe"; Comment: "Mo Shini Tasks"
Name: "{group}\Go cai dat Shini Tasks"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Shini Tasks"; Filename: "{app}\ShiniTasks.exe"; Tasks: desktopicon
Name: "{userstartup}\Shini Tasks Engine"; Filename: "{app}\ShiniTasksEngine.exe"; Comment: "Engine nhac viec — tu chay khi dang nhap Windows"

[Run]
Filename: "{app}\ShiniTasksEngine.exe"; Description: "Chay engine Shini Tasks ngay bay gio"; Flags: nowait postinstall skipifsilent
