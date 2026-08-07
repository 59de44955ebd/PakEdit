import base64
import brotli
from contextlib import contextmanager
import gzip
import os
import random
import shutil
import sys
import traceback

APP_NAME = 'PakEdit'
APP_VERSION = '0.1'
APP_DIR = os.path.dirname(__file__)
IS_FROZEN = getattr(sys, 'frozen', False)

if not IS_FROZEN:
    # Force local imports
    sys.path.append(APP_DIR)

from webview2 import *
from webview2.winapp.const import *
from webview2.winapp.controls_themed.listbox import *
from webview2.winapp.controls_themed.statusbar import *
from webview2.winapp.dialogs import *
from webview2.winapp.dlls import *
from webview2.winapp.mainwin_themed import *

from resources import *
from command import *
from pak import *

if IS_FROZEN:
    HMOD_RESOURCES = kernel32.GetModuleHandleW(None)
else:
    HMOD_RESOURCES = kernel32.LoadLibraryW(os.path.join(APP_DIR, '..', 'resources.dll'))

HCURSOR_ARROW = user32.LoadCursorW(None, IDC_ARROW)
HCURSOR_WAIT = user32.LoadCursorW(None, IDC_WAIT)

@contextmanager
def wait_cursor():
    user32.SetCursor(HCURSOR_WAIT)
    try:
        yield
    finally:
        user32.SetCursor(HCURSOR_ARROW)

# CONFIG
LISTBOX_WIDTH = 140
HEX_BLOCK_WIDTH = 16
HEX_MAX_BLOCKS = 400

# File types that might exist without additional brotli/gzip compression and can therefor
# be identified directly by examining the first few bytes of a chunk.
# 'lottie' chunks are special, they can be identified by magic LOTTIE, but are nevertheless
# either brotli or gzip compressed, which is encoded in the bytes after the magic.
KNOWN_BINARY_EXTENSIONS = ('.avif', '.jpg', '.lottie_json', '.mp4', '.png', '.webp', '.woff', '.zip')

#TMP_DIR = os.path.join(APP_DIR, 'tmp')
TMP_DIR = os.environ['TMP']

MEDIA_MIMETYPES = {
    '.avif': 'image/avif',
    '.jpg': 'image/jpeg',
    '.mp4': 'video/mp4',
    '.png': 'image/png',
    '.svg': 'image/svg+xml',
    '.webp': 'image/webp',
}

EDITABLE_MIMETYPES = {
    '.css': 'text/plain',
    '.htm': 'text/plain',
    '.js': 'text/javascript',
    '.json': 'application/json',
}

LOTTIE_HTML = '''<!DOCTYPE html>
<html>
<head>
<title>LottieView</title>
<meta name="color-scheme" content="light dark">
<link rel="stylesheet" href="https://app/lottie.css">
</head>
<body>
<div></div>
<script src="https://app/lottie.min.js"></script>
<script>
bodymovin.loadAnimation({{
    container: document.querySelector('div'),
    animationData: {},
    renderer: 'svg',
    loop: window.loopAll,
    autoplay: true,
}});
</script>
</body>
</html>'''

EDIT_JS = '''const el=document.body.firstElementChild;
el.contentEditable="plaintext-only";
el.spellcheck=false;
el.addEventListener("input", () => chrome.webview.api.edit(el.textContent), false);'''

SETTINGS.ALLOW_HOST_INPUT_PROCESSING = True  # Forward key events

# Use a local profile folder
if IS_FROZEN:
    SETTINGS.USER_DATA_FOLDER = os.path.join(APP_DIR, 'profile')


########################################
#
########################################
class App(MainWin):

    ########################################
    #
    ########################################
    def __init__(self):
        self.tmp_dir = None
        self.pak_file = None
        self.pak_infos = None
        self.is_dirty = False
        self.hwnd_find = None

        self.COMMAND_MESSAGE_MAP = {
            IDM_OPEN:                   self.open_pak_file,
            IDM_SAVE:                   self.save_pak_file,
            IDM_CLOSE:                  self.reset_ui,
            IDM_EXIT:                   self.quit,
            IDM_FIND:                   self.find_string,
            IDM_ABOUT:                  self.about,
            IDM_DEV_TOOLS:              self.open_dev_tools,
        }

        super().__init__(
            window_title = APP_NAME,
            h_accel = user32.LoadAcceleratorsW(HMOD_RESOURCES, MAKEINTRESOURCEW(1)),
            h_icon = user32.LoadIconW(HMOD_RESOURCES, MAKEINTRESOURCEW(1)),
            h_menu = user32.LoadMenuW(HMOD_RESOURCES, MAKEINTRESOURCEW(1)),
            h_cursor = 0,
            h_brush = COLOR_3DFACE,
        )

        user32.SetCursor(HCURSOR_ARROW)

        self.h_menu_listbox = user32.GetSubMenu(user32.LoadMenuW(HMOD_RESOURCES, MAKEINTRESOURCEW(ID_POPUP_MENU_SHOW_FOLDER)), 0)

        self.listbox = ListBox(
            self,
            left = 5,
            width = LISTBOX_WIDTH,
            style = WS_CHILD | WS_VISIBLE | WS_VSCROLL | LBS_NOINTEGRALHEIGHT | LBS_NOTIFY| LBS_HASSTRINGS,
        )

        self.listbox.set_font('Segoe UI', -13)
        self.listbox.hide_focus_rects()

        ########################################
        #
        ########################################
        def _on_WM_CONTEXTMENU(hwnd, wparam, lparam):
            x, y = lparam & 0xFFFF, (lparam >> 16) & 0xFFFF
            pt = POINT(x, y)
            user32.MapWindowPoints(None, self.listbox.hwnd, byref(pt), 1)
            idx = SHORT(self.listbox.send_message(LB_ITEMFROMPOINT, 0, MAKELPARAM(pt.x, pt.y))).value
            if idx < 0:
                return
            user32.SendMessageW(self.listbox.hwnd, LB_SETCURSEL, idx, 0)
            self.load_chunk(idx)
            res = user32.TrackPopupMenuEx(self.h_menu_listbox, TPM_LEFTBUTTON | TPM_RETURNCMD, x, y, self.hwnd, 0)

            if res == IDM_EXPORT:
                self.export_chunk(idx)

        self.listbox.register_message_callback(WM_CONTEXTMENU, _on_WM_CONTEXTMENU)

        self.webview = WebView2(
            self.hwnd,
            left = LISTBOX_WIDTH + 5,
        )
        self.webview.set_virtual_host_name_to_folder_mapping('app', APP_DIR)

        ########################################
        #
        ########################################
        def _on_files_dropped(webview, files, target_id):
            if os.path.isfile(files[0]) and files[0].lower().endswith('.pak'):
                self.load_pak_file(files[0])

        self.webview.connect(EVENT.FILES_DROPPED, _on_files_dropped)

        self.statusbar = StatusBar(self)

        ########################################
        #
        ########################################
        def _on_WM_SIZE(hwnd, wparam, lparam):
            width, height = lparam & 0xFFFF, (lparam >> 16) & 0xFFFF
            self.statusbar.update_size()
            height -= self.statusbar.height
            self.listbox.set_window_pos(
                width = LISTBOX_WIDTH,
                height = height,
                flags = SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE
            )
            self.webview.put_bounds(RECT(LISTBOX_WIDTH + 5, 0, width, height))

        self.register_message_callback(WM_SIZE, _on_WM_SIZE)

        if reg_should_use_dark_mode():
            self.apply_theme(True)

        self.show()

        ########################################
        #
        ########################################
        def _on_WM_COMMAND(hwnd, wparam, lparam):
            if lparam == 0:
                command_id = LOWORD(wparam)
                if command_id in self.COMMAND_MESSAGE_MAP:
                    self.COMMAND_MESSAGE_MAP[command_id]()

            elif lparam == self.listbox.hwnd:
                code = HIWORD(wparam)

                if code == LBN_SELCHANGE:
                    idx = user32.SendMessageW(self.listbox.hwnd, LB_GETCURSEL, 0, 0)
                    self.load_chunk(idx)

                elif code == LBN_DBLCLK:
                    idx = user32.SendMessageW(self.listbox.hwnd, LB_GETCURSEL, 0, 0)
                    self.export_chunk(idx)

        self.register_message_callback(WM_COMMAND, _on_WM_COMMAND)

        ########################################
        #
        ########################################
        def _on_WM_DROPFILES(hwnd, wparam, lparam):
            dropped_items = self.get_dropped_items(wparam)
            if os.path.isfile(dropped_items[0]) and dropped_items[0].lower().endswith('.pak'):
                self.load_pak_file(dropped_items[0])

        self.register_message_callback(WM_DROPFILES, _on_WM_DROPFILES)

        shell32.DragAcceptFiles(self.hwnd, TRUE)

        ########################################
        #
        ########################################
        def _on_WM_SETTINGCHANGE(hwnd, wparam, lparam):
            if lparam and cast(lparam, LPCWSTR).value == 'ImmersiveColorSet':
                self.apply_theme(reg_should_use_dark_mode())

        self.register_message_callback(WM_SETTINGCHANGE, _on_WM_SETTINGCHANGE)

        if len(sys.argv) > 1 and sys.argv[1].lower().endswith('.pak'):
            self.load_pak_file(sys.argv[1])

    ########################################
    #
    ########################################
    def get_chunk_text(self, idx):
        buf = create_unicode_buffer(MAX_PATH)
        user32.SendMessageW(self.listbox.hwnd, LB_GETTEXT, idx, buf)
        resource_id, ext = os.path.splitext(buf.value)
        entry = self.pak_infos.resource_table[int(resource_id)]
        with open(self.pak_file, 'rb') as f:
            f.seek(entry['offset'])
            data = f.read(entry['size'])
        if entry['type'] == '.br':
            data = brotli.decompress(data[8:])
        elif entry['type'] == '.gz':
            data = gzip.decompress(data)
        return data.decode('utf-8')

    ########################################
    #
    ########################################
    def load_chunk(self, idx):
        buf = create_unicode_buffer(MAX_PATH)
        user32.SendMessageW(self.listbox.hwnd, LB_GETTEXT, idx, buf)
        resource_id, ext = os.path.splitext(buf.value)
        resource_id = int(resource_id)
        entry = self.pak_infos.resource_table[resource_id]

        with wait_cursor():
            compr = ''
            tmp_file = os.path.join(self.tmp_dir, buf.value)
            if os.path.isfile(tmp_file):
                with open(tmp_file, 'rb') as f:
                    data = f.read()
                if entry['type'] == '.br':
                    compr = ' (brotli-compressed)'
                elif entry['type'] == '.gz':
                    compr = ' (gzip-compressed)'
            else:
                with open(self.pak_file, 'rb') as f:
                    f.seek(entry['offset'])
                    data = f.read(entry['size'])

                if entry['type'] == '.br':
                    data = brotli.decompress(data[8:])
                    compr = ' (brotli-compressed)'

                elif entry['type'] == '.gz':
                    data = gzip.decompress(data)
                    compr = ' (gzip-compressed)'

                elif entry['type'] == '.lottie_json':
                    if entry['lottie_compression'] == 'brotli':
                        data = brotli.decompress(data[14:])
                        compr = ' (brotli-compressed)'
                    elif entry['lottie_compression'] == 'gzip':
                        data = gzip.decompress(data[6:])
                        compr = ' (gzip-compressed)'

            self.show_data(resource_id, ext, data)

        user32.SetWindowTextW(self.statusbar.hwnd, f"  Size: {entry['size']:,} bytes{compr}")

    ########################################
    #
    ########################################
    def export_chunk(self, idx):
        buf = create_unicode_buffer(MAX_PATH)
        user32.SendMessageW(self.listbox.hwnd, LB_GETTEXT, idx, buf)
        resource_id, ext = os.path.splitext(buf.value)

        filename = os.path.join(self.tmp_dir, buf.value)
        if not os.path.isfile(filename):
            entry = self.pak_infos.resource_table[int(resource_id)]
            with open(self.pak_file, 'rb') as f:
                f.seek(entry['offset'])

                if entry['type'] == '.br':
                    f.seek(8, os.SEEK_CUR)
                    data = brotli.decompress(f.read(entry['size'] - 8))

                elif entry['type'] == '.gz':
                    data = gzip.decompress(f.read(entry['size']))

                elif ext == '.lottie_json':
                    data = f.read(entry['size'])
                    if data[6:8] == BROTLI_MAGIC:
                        data = brotli.decompress(data[14:])
                    elif data[6:8] == GZIP_MAGIC:
                        data = gzip.decompress(data[6:])

                else:
                    data = f.read(entry['size'])

            with open(filename, 'wb') as f:
                f.write(data)

        sei = SHELLEXECUTEINFOW()
        sei.nShow = SW_SHOWNORMAL
        sei.lpFile = 'explorer.exe'
        sei.lpParameters = f'/select,"{filename}"'
        shell32.ShellExecuteExW(byref(sei))

    ########################################
    #
    ########################################
    def detect_file_type(self, data):
        has_utf8_bom = data.startswith(b'\xef\xbb\xbf')
        if has_utf8_bom:
            data = data[3:]
        if data.startswith(b'<svg'):  # lstrip().
            return '.svg'
        elif data.startswith(b'<!doctype') or data.startswith(b'<!DOCTYPE') or data.startswith(b'<!--') or data.startswith(b'<html'):
            return '.htm'
        elif data.startswith(ZIP_MAGIC):
            return '.zip'
        elif data.startswith(b'{"') or data.startswith(b'{\n') or data.startswith(b'[\n'):
            return '.json'
        elif data.startswith(b'import') or data.startswith(b'export') or data.startswith(b'// ')  or data.startswith(b'\n// ') or data.startswith(b'const ') or data.startswith(b'var ') or data.startswith(b'"use strict"') or data.startswith(b'(()=>') or data.startswith(b'!') or data.startswith(b'(function'):
            return '.js'
        elif data.startswith(b'/*'):
            return '.css'
        elif data[4:11] == MP4_MAGIC:
            return '.mp4'
        elif has_utf8_bom:
            return '.txt'
        return ''

    ########################################
    #
    ########################################
    def open_pak_file(self):
        pak_file = show_open_file_dialog(
            hwnd = self.hwnd,
            filter_string = 'PAK Files (*.pak)\0*.pak\0\0',
            initial_path = 'resources.pak'
        )
        if pak_file:
            self.load_pak_file(pak_file)

    ########################################
    #
    ########################################
    def load_pak_file(self, pak_file):
        self.reset_ui()

        self.tmp_dir = os.path.join(TMP_DIR, f'{APP_NAME}{random.randint(10000000, 99999999)}')
        if os.path.isdir(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)
        os.mkdir(self.tmp_dir)

        with wait_cursor():
            pak_infos = self.pak_parse(pak_file)
            if pak_infos:
                self.pak_file = pak_file
                self.pak_infos = pak_infos

                self.editable_chunk_indexes = []

                user32.SendMessageW(self.listbox.hwnd, WM_SETREDRAW, FALSE, 0)

                with open(self.pak_file, 'rb') as f:

                    for resource_id, entry in self.pak_infos.resource_table.items():

                        if entry['type'] in KNOWN_BINARY_EXTENSIONS:
                            ext = entry['type']

                        else:
                            if entry['type'] == '.br':
                                f.seek(entry['offset'] + 8)
                                data = brotli.decompress(f.read(entry['size'] - 8))
                            else:
                                f.seek(entry['offset'])
                                data = f.read(entry['size'])
                                if entry['type'] == '.gz':
                                    data = gzip.decompress(data)

                            ext = self.detect_file_type(data)

                        idx = user32.SendMessageW(self.listbox.hwnd, LB_ADDSTRING, 0, f'{resource_id}{ext}')
                        if ext in EDITABLE_MIMETYPES:
                            self.editable_chunk_indexes.append(idx)

                user32.SendMessageW(self.listbox.hwnd, WM_SETREDRAW, TRUE, 0)

                user32.EnableMenuItem(self.h_menu, IDM_CLOSE, MF_ENABLED)
                user32.EnableMenuItem(self.h_menu, IDM_SAVE, MF_ENABLED)
                user32.EnableMenuItem(self.h_menu, IDM_FIND, MF_ENABLED)
                user32.SetWindowTextW(self.hwnd, f'{pak_file} - {APP_NAME}')

    ########################################
    #
    ########################################
    def save_pak_file(self):
        while True:
            pak_file_new = show_save_file_dialog(
                hwnd = self.hwnd,
                filter_string = 'PAK Files\0*.pak\0\0',
                initial_path = 'resources.pak'
            )
            if not pak_file_new:
                return
            if pak_file_new.lower() != self.pak_file.lower():
                break
            show_message_box(
                self.hwnd,
                'The currently loaded .pak file can not be overwritten.\nPlease save under a different filename.',
                'Can not overwrite',
                MB_ICONWARNING | MB_OK
            )

        user32.SetWindowTextW(self.statusbar.hwnd, '  Creating new PAK file...')

        with wait_cursor():
            chunk_files = os.listdir(self.tmp_dir)
            replaced_resources = {}
            for chunk_name in chunk_files:

                with open(os.path.join(self.tmp_dir, chunk_name), 'rb') as f:
                    data = f.read()

                resource_id, ext = os.path.splitext(chunk_name)
                resource_id = int(resource_id)
                entry = self.pak_infos.resource_table[resource_id]

                if entry['type'] == '.br':
                    data = BROTLI_MAGIC + bytes(c_ulonglong(len(data)))[:6] + brotli.compress(data, quality = 6)

                elif entry['type'] == '.gz':
                    data = gzip.compress(data)

                elif entry['type'] == '.lottie_json':
                    if entry['lottie_compression'] == 'brotli':
                        data = LOTTIE_MAGIC + BROTLI_MAGIC + bytes(c_ulonglong(len(data)))[:6] + brotli.compress(data, quality = 6)
                    elif entry['lottie_compression'] == 'gzip':
                        data = LOTTIE_MAGIC + gzip.compress(data)
                    else:
                        data = LOTTIE_MAGIC + data  # Most likely never occurs

                replaced_resources[resource_id] = data

            try:
                self.pak_replace(pak_file_new, replaced_resources)
                user32.SetWindowTextW(self.statusbar.hwnd, '')
            except Exception as e:
                user32.SetWindowTextW(self.statusbar.hwnd, f'  Error: {e}')

    ########################################
    #
    ########################################
    def reset_ui(self):

        if self.tmp_dir and os.path.isdir(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)
            self.tmp_dir = None

        self.pak_file = None
        self.pak_infos = None
        self.is_dirty = False

        user32.SetWindowTextW(self.hwnd, APP_NAME)
        user32.SendMessageW(self.listbox.hwnd, LB_RESETCONTENT, 0, 0)
        self.webview.load_url('about:blank')
        user32.EnableMenuItem(self.h_menu, IDM_CLOSE, MF_GRAYED)
        user32.EnableMenuItem(self.h_menu, IDM_SAVE, MF_GRAYED)
        user32.EnableMenuItem(self.h_menu, IDM_FIND, MF_GRAYED)

        user32.SetWindowTextW(self.statusbar.hwnd, '')

    ########################################
    #
    ########################################
    def show_data(self, resource_id, ext, data):

        ########################################
        #
        ########################################
        def _on_edit(text):
            with open(os.path.join(self.tmp_dir, f'{resource_id}{ext}'), 'w', encoding='utf-8', newline='\n') as f:
                f.write(text)
            if not self.is_dirty:
                self.is_dirty = True
                user32.SetWindowTextW(self.hwnd, f'*{self.pak_file} - {APP_NAME}')

        if ext in MEDIA_MIMETYPES:
            base64_bytes = base64.b64encode(data)
            self.webview.load_url('data:' + MEDIA_MIMETYPES[ext] + ';base64,' + base64_bytes.decode("ascii"))

        elif ext in EDITABLE_MIMETYPES:
            base64_bytes = base64.b64encode(data)
            self.webview.load_url('data:' + EDITABLE_MIMETYPES[ext] + ';base64,' + base64_bytes.decode("ascii"))
            self.webview.expose('edit', _on_edit)
            self.webview.execute_js(EDIT_JS)

        elif ext == '.lottie_json':
            self.webview.load_html(LOTTIE_HTML.format(data.decode()))

        else:
            try:
                text = data.decode('utf-8')
                base64_bytes = base64.b64encode(data)
                self.webview.load_url('data:text/plain;charset=UTF-8;base64,' + base64_bytes.decode("ascii"))
                self.webview.expose('edit', _on_edit)
                self.webview.execute_js(EDIT_JS)
            except:
                self.show_data_hex(data)

    ########################################
    #
    ########################################
    def show_data_hex(self, data):
        data_show = data[:HEX_MAX_BLOCKS * HEX_BLOCK_WIDTH]
        rows = [data_show[i:i + HEX_BLOCK_WIDTH] for i in range(0, len(data_show), HEX_BLOCK_WIDTH)]
        lines = [self.hex_line(lineno, row).encode() for lineno, row in enumerate(rows)]
        missing = len(data) - len(data_show)
        if missing:
            lines.append(f'\r\n--> Data display truncated, {missing} more bytes.'.encode())
        base64_bytes = base64.b64encode(b'\r\n'.join(lines))
        self.webview.load_url('data:text/plain;base64,' + base64_bytes.decode("ascii"))

    ########################################
    #
    ########################################
    def hex_line(self, lineno, row):
        return (
            hex(lineno * HEX_BLOCK_WIDTH)[2:].zfill(8) +
            'h: ' +
            ''.join(f'{byte:02X} ' for byte in row) +
            '   ' * (HEX_BLOCK_WIDTH - len(row)) +
            '; ' +
            ''.join(chr(byte) if 0x20 <= byte < 0x7F else '.' for byte in row)
        )

    ########################################
    #
    ########################################
    def find_string(self):

        ########################################
        #
        ########################################
        def _dialog_proc_find(hwnd, msg, wparam, lparam):

            if msg == WM_INITDIALOG:
                for idc in (IDC_FIND_MATCH_WHOLE_WORD_ONLY, IDC_FIND_MATCH_CASE, IDC_FIND_WRAP_AROUND, IDC_FIND_DIRECTION, IDC_FIND_UP, IDC_FIND_DOWN):
                    user32.ShowWindow(user32.GetDlgItem(hwnd, idc), SW_HIDE)

            elif msg == WM_COMMAND:
                control_id = LOWORD(wparam)
                command = HIWORD(wparam)

                if control_id == IDC_FIND_EDIT:
                    if command == EN_UPDATE:
                        text_len = user32.SendMessageW(user32.GetDlgItem(hwnd, IDC_FIND_EDIT), WM_GETTEXTLENGTH, 0, 0)
                        user32.EnableWindow(user32.GetDlgItem(hwnd, IDOK), int(text_len > 0))
                        self.find_chunk_idx = -1

                elif command == BN_CLICKED:

                    if control_id == IDOK:
                        hwnd_edit = user32.GetDlgItem(hwnd, IDC_FIND_EDIT)
                        text_len = user32.SendMessageW(hwnd_edit, WM_GETTEXTLENGTH, 0, 0) + 1
                        text_buf = create_unicode_buffer(text_len)
                        user32.SendMessageW(hwnd_edit, WM_GETTEXT, text_len, text_buf)
                        self.find_next(text_buf.value)

                    elif control_id == IDCANCEL:
                        user32.ShowWindow(hwnd, SW_HIDE)
                        return TRUE

            elif msg == WM_CLOSE:
                user32.ShowWindow(hwnd, SW_HIDE)
                return TRUE

            return FALSE

        if self.hwnd_find is None:
            self.fr_find, self.hwnd_find = show_find_dialog(self, DLGHOOKPROC(_dialog_proc_find))

        user32.ShowWindow(self.hwnd_find, SW_SHOW)

    ########################################
    #
    ########################################
    def find_next(self, find_term):
        user32.SetWindowTextW(self.statusbar.hwnd, '')

        ########################################
        #
        ########################################
        def _on_dom_content_loaded(webview):
            self.webview.disconnect(EVENT.DOM_CONTENT_LOADED, _on_dom_content_loaded)
            opts = WebView2.environment.CreateFindOptions()
            opts.put_FindTerm(find_term)
            opts.put_ShouldHighlightAllMatches(TRUE)
            self.webview.get_find().Start(opts, None)

        for i in range(self.find_chunk_idx + 1, len(self.editable_chunk_indexes)):
            idx = self.editable_chunk_indexes[i]
            text = self.get_chunk_text(idx)
            pos = text.find(find_term)
            if pos >= 0:
                user32.SendMessageW(self.listbox.hwnd, LB_SETCURSEL, idx, 0)
                self.find_chunk_idx = i
                self.webview.connect(EVENT.DOM_CONTENT_LOADED, _on_dom_content_loaded)
                self.load_chunk(idx)
                return

        user32.SetWindowTextW(self.statusbar.hwnd, '  No more results.')

    ########################################
    #
    ########################################
    def about(self):
        show_message_box(
            self.hwnd,
            (
                f'{APP_NAME} v{APP_VERSION}\n\n'
                'A simple tool for editing resources in .pak files of Chromium-based browsers.\n\n'
            ),
            'About'
        )

    ########################################
    #
    ########################################
    def open_dev_tools(self):
        self.webview.open_dev_tools()

    ########################################
    #
    ########################################
    def quit(self, *_):
        self.webview.close()
        if self.tmp_dir and os.path.isdir(self.tmp_dir):
            try:
                shutil.rmtree(self.tmp_dir)
            except:
                pass
        super().quit()

    ########################################
    #
    ########################################
    def pak_parse(self, pak_file: str, is_32_bit: bool = None) -> dict:
        with open(pak_file, 'rb') as f:

            if is_32_bit is None:
                # Tries to heuristically detect if the file uses 32 (Edge) or 16 (Chrome) bit resource_ids.
                cnt = 0
                for i in range(0, 153, 8):
                    f.seek(19 + i)
                    if f.read(1) == b'\0':
                        cnt += 1
                is_32_bit = cnt > 10
                f.seek(0)

            if is_32_bit:
                header_class = HEADER_V5_32
                resource_entry_class = RESOURCE_ENTRY_32
                alias_entry_class = ALIAS_ENTRY_32
            else:
                header_class = HEADER_V5_16
                resource_entry_class = RESOURCE_ENTRY_16
                alias_entry_class = ALIAS_ENTRY_16

            header = header_class.from_buffer_copy(f.read(sizeof(header_class)))

            pak_infos = PakInfos(header)

            resource_table = pak_infos.resource_table
            entry_size = sizeof(resource_entry_class)
            last_item = {'offset': 0}  # dummy
            for i in range(header.resource_count):
                entry = resource_entry_class.from_buffer_copy(f.read(entry_size))
                last_item['size'] = entry.offset - last_item['offset']
                last_item = {'offset': entry.offset}
                resource_table[entry.resource_id] = last_item

            entry = resource_entry_class.from_buffer_copy(f.read(entry_size))
            last_item['size'] = entry.offset - last_item['offset']

            alias_table = pak_infos.alias_table
            entry_size = sizeof(alias_entry_class)
            for i in range(header.alias_count):
                entry = alias_entry_class.from_buffer_copy(f.read(entry_size))
                alias_table[entry.resource_id] = entry.index

            for resource_id, entry in resource_table.items():
                f.seek(entry['offset'])
                magic = f.read(12)
                if magic[:2] == BROTLI_MAGIC:
                    entry['type'] = '.br'

                elif magic[:2] == GZIP_MAGIC:
                    entry['type'] = '.gz'

                elif magic[AVIF_OFFSET:AVIF_OFFSET + 8] == AVIF_MAGIC:
                    entry['type'] = '.avif'

                elif magic[:2] == JPEG_MAGIC:
                    entry['type'] = '.jpg'

                elif magic[:6] == LOTTIE_MAGIC:
                    entry['type'] = '.lottie_json'
                    if magic[6:8] == BROTLI_MAGIC:
                        entry['lottie_compression'] = 'brotli'
                    elif magic[6:8] == GZIP_MAGIC:
                        entry['lottie_compression'] = 'gzip'
                    else:
                        entry['lottie_compression'] = ''  # Most likely never occurs

                elif magic[MP4_OFFSET:MP4_OFFSET + 7] == MP4_MAGIC:
                    entry['type'] = '.mp4'

                elif magic[:4] == PNG_MAGIC:
                    entry['type'] = '.png'

                elif magic[WEBP_OFFSET:WEBP_OFFSET + 4] == WEBP_MAGIC:
                    entry['type'] = '.webp'

                elif magic[:4] == WOFF_MAGIC:
                    entry['type'] = '.woff'

                elif magic[:4] == ZIP_MAGIC:
                    entry['type'] = '.zip'

                else:
                    entry['type'] = ''

            return pak_infos

    ########################################
    #
    ########################################
    def pak_replace(self, pak_file_new: str, replaced_resources: dict):

        if self.pak_infos.is_32bit:
            resource_entry_class = RESOURCE_ENTRY_32
            alias_entry_class = ALIAS_ENTRY_32
        else:
            resource_entry_class = RESOURCE_ENTRY_16
            alias_entry_class = ALIAS_ENTRY_16

        with open(self.pak_file, 'rb') as f_org:
            with open(pak_file_new, 'wb') as f_new:

                # Header
                f_new.write(bytes(self.pak_infos.header))

                # Resource table
                offset = sizeof(self.pak_infos.header) + (self.pak_infos.header.resource_count + 1) * sizeof(resource_entry_class) + self.pak_infos.header.alias_count * sizeof(alias_entry_class)
                for resource_id, entry in self.pak_infos.resource_table.items():
                    f_new.write(bytes(resource_entry_class(resource_id, offset)))
                    if resource_id in replaced_resources:
                        offset += len(replaced_resources[resource_id])
                    else:
                        offset += entry['size']

                f_new.write(bytes(resource_entry_class(0, offset)))

                # Alias table
                for resource_id, index in self.pak_infos.alias_table.items():
                    f_new.write(bytes(alias_entry_class(resource_id, int(index))))

                # Data
                for resource_id, entry in self.pak_infos.resource_table.items():
                    if resource_id in replaced_resources:
                        f_new.write(replaced_resources[resource_id])
                    else:
                        f_org.seek(entry['offset'])
                        f_new.write(f_org.read(entry['size']))


if __name__ == '__main__':
    sys.excepthook = traceback.print_exception
    sys.exit(App().run())
