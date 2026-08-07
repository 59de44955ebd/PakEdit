# https://learn.microsoft.com/en-us/windows/win32/controls/list-boxes
from ..window import *

class DRAGLISTINFO(Structure):
    _fields_ = [
        ('uNotification', UINT),
        ('hWnd', HWND),
        ('ptCursor', POINT),
    ]


########################################
# Wrapper Class
########################################
class ListBox(Window):

    ########################################
    #
    ########################################
    def __init__(
        self,
        parent_window = None,
        style = WS_CHILD | WS_VISIBLE,
        ex_style = 0,
        left = 0, top = 0, width = 0, height = 0,
        window_title = None,
        wrap_hwnd = None,
        h_font = H_FONT_SHELL,
    ):
        super().__init__(
            WC_LISTBOX,
            parent_window = parent_window,
            style = style,
            ex_style = ex_style,
            left = left, top = top, width = width, height = height,
            window_title = window_title,
            wrap_hwnd = wrap_hwnd,
            h_font = h_font,
        )
