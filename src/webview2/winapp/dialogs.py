from ctypes import *
from ctypes.wintypes import *
from .const import *
from .dlls import *

class OPENFILENAMEW(Structure):
    def __init__(self, *args, **kwargs):
        super(OPENFILENAMEW, self).__init__(*args, **kwargs)
        self.lStructSize = sizeof(self)
    _fields_ = (
        ('lStructSize', DWORD),
        ('hwndOwner', HWND),
        ('hInstance', HINSTANCE),
        ('lpstrFilter', LPWSTR),
        ('lpstrCustomFilter', LPWSTR),
        ('nMaxCustFilter', DWORD),
        ('nFilterIndex', DWORD),
        ('lpstrFile', LPWSTR),
        ('nMaxFile', DWORD),
        ('lpstrFileTitle', LPWSTR),
        ('nMaxFileTitle', DWORD),
        ('lpstrInitialDir', LPCWSTR),
        ('lpstrTitle', LPCWSTR),
        ('Flags', DWORD),
        ('nFileOffset', WORD),
        ('nFileExtension', WORD),
        ('lpstrDefExt', LPCWSTR),
        ('lCustData', LPARAM),
        ('lpfnHook', LPVOID),  # DLGHOOKPROC
        ('lpTemplateName', LPCWSTR),
        ('pvReserved', LPVOID),
        ('dwReserved', DWORD),
        ('FlagsEx', DWORD),
    )

class FINDREPLACEW(Structure):
    def __init__(self, *args, **kwargs):
        super(FINDREPLACEW, self).__init__(*args, **kwargs)
        self.lStructSize = sizeof(self)
    _fields_ = [
        ('lStructSize',                 DWORD),
        ('hwndOwner',                   HWND),
        ('hInstance',                   HINSTANCE),
        ('Flags',                       DWORD),
        ('lpstrFindWhat',               LPWSTR),
        ('lpstrReplaceWith',            LPWSTR),
        ('wFindWhatLen',                WORD),
        ('wReplaceWithLen',             WORD),
        ('lCustData',                   LPARAM),
        ('lpfnHook',                    DLGHOOKPROC),
        ('lpTemplateName',              LPCWSTR),
    ]

comdlg32.FindTextW.argtypes = (POINTER(FINDREPLACEW),)
comdlg32.FindTextW.restype = HWND

########################################
# Classic MessageBox, but themed
########################################
def show_message_box(hwnd = None, text = '', window_title = '', utype = MB_ICONINFORMATION | MB_OK):
    return user32.MessageBoxW(hwnd, text, window_title, utype)

########################################
# Modern UWP MessageBox - if content contains \n\n, the text before is used as instruction
########################################
#    def show_message_box(hwnd = None, text = '', window_title = '', common_buttons = TDCBF_OK_BUTTON, icon = TD_INFORMATION_ICON):
#        parts = text.split('\n\n', 1)
#        if len(parts) > 1:
#            instruction, text = parts
#        else:
#            instruction = None
#        button_pressed = INT(0)
#        comctl32.TaskDialog(
#            hwnd,
#            None,
#            window_title,
#            instruction,
#            text,
#            common_buttons,
#            cast(c_void_p(icon & 0xFFFF), LPCWSTR),
#            byref(button_pressed)
#        )
#        return button_pressed.value

########################################
#
########################################
def show_open_file_dialog(
    hwnd = None,
    title = 'Open...',
    default_extension = '',
    filter_string = 'All Files (*.*)\0*.*\0\0',
    initial_path = ''
):
    file_buffer = create_unicode_buffer(initial_path, MAX_PATH)
    ofn = OPENFILENAMEW()
    ofn.hwndOwner = hwnd
    ofn.lpstrTitle = title
    ofn.lpstrFile = cast(file_buffer, LPWSTR)
    ofn.nMaxFile = MAX_PATH
    ofn.lpstrDefExt = default_extension
    ofn.lpstrFilter = cast(create_unicode_buffer(filter_string), c_wchar_p)
    ofn.Flags = OFN_ENABLESIZING | OFN_PATHMUSTEXIST
    ok = comdlg32.GetOpenFileNameW(byref(ofn))
    return file_buffer[:].split('\0', 1)[0] if ok else None

########################################
#
########################################
def show_save_file_dialog(
    hwnd = None,
    title = 'Save...',
    default_extension = '',
    filter_string = 'All Files (*.*)\0*.*\0\0',
    initial_path = '',
    flags = OFN_ENABLESIZING | OFN_OVERWRITEPROMPT,
    filter_index = 0,
):
    file_buffer = create_unicode_buffer(initial_path, MAX_PATH)
    ofn = OPENFILENAMEW()
    ofn.hwndOwner = hwnd
    ofn.lpstrTitle = title
    ofn.lpstrFile = cast(file_buffer, LPWSTR)
    ofn.nMaxFile = MAX_PATH
    ofn.lpstrDefExt = default_extension
    ofn.lpstrFilter = cast(create_unicode_buffer(filter_string), c_wchar_p)
    ofn.Flags = flags
    ofn.nFilterIndex = filter_index
    ok = comdlg32.GetSaveFileNameW(byref(ofn))
    return file_buffer[:].split('\0', 1)[0] if ok else None

########################################
# Returned fr *must* be saved to prevent garbage collection
########################################
def show_find_dialog(parent_window, dialog_proc, find_what = ''):
    MAX_SEARCH_REPLACE_LEN = MAX_PATH
    fr = FINDREPLACEW()
    fr.hwndOwner = parent_window.hwnd
    fr.Flags = FR_DOWN | FR_FINDNEXT| FR_ENABLEHOOK
    fr.lpstrFindWhat = cast(create_unicode_buffer(find_what, MAX_SEARCH_REPLACE_LEN), c_wchar_p)
    fr.wFindWhatLen = MAX_SEARCH_REPLACE_LEN
    fr.lpfnHook = dialog_proc  # LPFRHOOKPROC
    hdlg = comdlg32.FindTextW(fr)
    return fr, hdlg
