from ..controls.listbox import *
from ..themes import *

LISTBOX_BG_COLOR = 0xf0f0f0
LISTBOX_BG_BRUSH = gdi32.CreateSolidBrush(LISTBOX_BG_COLOR)

LISTBOX_DARK_BG_COLOR = 0x2C2C2C
LISTBOX_DARK_BG_BRUSH = gdi32.CreateSolidBrush(LISTBOX_DARK_BG_COLOR)


########################################
# Wrapper Class
########################################
class ListBox(ListBox):

    ########################################
    #
    ########################################
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent_window.register_message_callback(WM_CTLCOLORLISTBOX, self._on_WM_CTLCOLORLISTBOX)

    ########################################
    #
    ########################################
    def destroy_window(self):
        self.parent_window.unregister_message_callback(WM_CTLCOLORLISTBOX, self._on_WM_CTLCOLORLISTBOX)
        super().destroy_window()

    ########################################
    #
    ########################################
    def apply_theme(self, is_dark):
        super().apply_theme(is_dark)
        uxtheme.SetWindowTheme(self.hwnd, 'DarkMode_Explorer' if is_dark else 'Explorer', None)

    # #######################################
    #
    # #######################################
    def _on_WM_CTLCOLORLISTBOX(self, hwnd, wparam, lparam):
        if self.is_dark:
            gdi32.SetTextColor(wparam, DARK_TEXT_COLOR)
            gdi32.SetBkColor(wparam, LISTBOX_DARK_BG_COLOR)
            return LISTBOX_DARK_BG_BRUSH
        else:
            gdi32.SetBkColor(wparam, LISTBOX_BG_COLOR)
            gdi32.SetDCBrushColor(wparam, LISTBOX_BG_COLOR)
            return LISTBOX_BG_BRUSH
