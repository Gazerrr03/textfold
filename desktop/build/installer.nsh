; The Windows installer (electron-builder's NSIS, which includes this file from build/). It asks where to install;
; it installs for this user alone, as the one-click installer before it did: no administrator, and the app's updates
; install without asking for one.
!macro customInstallMode
  StrCpy $isForceCurrentInstall "1"
!macroend

; The app registers textfold:// links for itself when it runs (main.js, setAsDefaultProtocolClient): removed with it,
; but not when an update replaces it.
!macro customUnInstall
  ${ifNot} ${isUpdated}
    DeleteRegKey HKCU "Software\Classes\textfold"
  ${endIf}
!macroend
