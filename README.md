# PakEdit

PakEdit is a simple viewer and editor for PAK resource files of Chromium-based browsers (Chrome/Chromium/Edge/WebView2/Brave).

It is based on [Microsoft Edge WebView2](https://developer.microsoft.com/en-us/microsoft-edge/webview2) and native [Windows controls](https://learn.microsoft.com/en-us/windows/win32/controls/individual-control-info) and written in Python. It's a showcase app for WebView2 Python binding [WebView2-for-Python](https://github.com/59de44955ebd/webview2-for-python).

## Usage

After loading a PAK file all resources are displayed in a listbox on the left. When selecting a resource, it in a webvie on the right, either as media preview (for images, videos and animations), as editable text (for `.css`, `.html`, `.js`, `.json` and string resources) or as hex view (for unidentified binary resources).

Editable text resources can be edited directly inside the application. Binary resources can be exported (via context menu "Export and reveal" or double-click) to a temporary directory and then edited with some external media editor or replaced with a different file but the same filename.

After some resources were edited a new `.pak` file can be saved (menu `File` -> `Save as...`). All resources in the new file will use the same compression as in the original file.

## Supported media types for preview

* avif
* jpeg
* lottie (JSON)
* mp4
* png
* svg
* webp

*PakEdit running in Windows 11 (dark mode)*
![](screenshots/pakedit-win11-dark.png)
