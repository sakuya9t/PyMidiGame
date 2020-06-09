import pyautogui

import pygame

keyboardMapping = dict([(key, None) for key in pyautogui.KEY_NAMES])
keyboardMapping.update({
    'a': pygame.K_a,  # kVK_ANSI_A
    'b': pygame.K_b,  # kVK_ANSI_B
    'c': pygame.K_c,  # kVK_ANSI_C
    'd': pygame.K_d,  # kVK_ANSI_D
    'e': pygame.K_e,  # kVK_ANSI_E
    'f': pygame.K_f,  # kVK_ANSI_F
    'g': pygame.K_g,  # kVK_ANSI_G
    'h': pygame.K_h,  # kVK_ANSI_H
    'i': pygame.K_i,  # kVK_ANSI_I
    'j': pygame.K_j,  # kVK_ANSI_J
    'k': pygame.K_k,  # kVK_ANSI_K
    'l': pygame.K_l,  # kVK_ANSI_L
    'm': pygame.K_m,  # kVK_ANSI_M
    'n': pygame.K_n,  # kVK_ANSI_N
    'o': pygame.K_o,  # kVK_ANSI_O
    'p': pygame.K_p,  # kVK_ANSI_P
    'q': pygame.K_q,  # kVK_ANSI_Q
    'r': pygame.K_r,  # kVK_ANSI_R
    's': pygame.K_s,  # kVK_ANSI_S
    't': pygame.K_t,  # kVK_ANSI_T
    'u': pygame.K_u,  # kVK_ANSI_U
    'v': pygame.K_v,  # kVK_ANSI_V
    'w': pygame.K_w,  # kVK_ANSI_W
    'x': pygame.K_x,  # kVK_ANSI_X
    'y': pygame.K_y,  # kVK_ANSI_Y
    'z': pygame.K_z,  # kVK_ANSI_Z
    '0': pygame.K_0,  # kVK_ANSI_0
    '1': pygame.K_1,  # kVK_ANSI_1
    '2': pygame.K_2,  # kVK_ANSI_2
    '3': pygame.K_3,  # kVK_ANSI_3
    '4': pygame.K_4,  # kVK_ANSI_4
    '5': pygame.K_5,  # kVK_ANSI_5
    '6': pygame.K_6,  # kVK_ANSI_6
    '7': pygame.K_7,  # kVK_ANSI_7
    '8': pygame.K_8,  # kVK_ANSI_8
    '9': pygame.K_9,  # kVK_ANSI_9
    '-': pygame.K_MINUS,  # kVK_ANSI_Minus
    '=': pygame.K_EQUALS,  # kVK_ANSI_Equal
    ',': pygame.K_COMMA,  # kVK_ANSI_Comma
    '.': pygame.K_PERIOD,  # kVK_ANSI_Period
    ';': pygame.K_SEMICOLON,  # kVK_ANSI_Semicolon
    '[': pygame.K_LEFTBRACKET,  # kVK_ANSI_LeftBracket
    ']': pygame.K_RIGHTBRACKET,  # kVK_ANSI_RightBracket
    "'": pygame.K_QUOTE,  # kVK_ANSI_Quote
    '\\': pygame.K_BACKSLASH,  # kVK_ANSI_Backslash
    '/': pygame.K_SLASH,  # kVK_ANSI_Slash
    '`': pygame.K_BACKQUOTE,  # kVK_ANSI_Grave
    'space': pygame.K_SPACE,
    'enter': pygame.K_RETURN,  # kVK_Return
    'tab': pygame.K_TAB,  # kVK_Tab
    'backspace': pygame.K_BACKSPACE,  # kVK_Delete, which is "Backspace" on OS X.
    'escape': pygame.K_ESCAPE,  # kVK_Escape
    'capslock': pygame.K_CAPSLOCK,  # kVK_CapsLock
    'shiftleft': pygame.K_LSHIFT,  # kVK_Shift
    'shiftright': pygame.K_RSHIFT,  # kVK_RightShift
    'altleft': pygame.K_LALT,  # kVK_Option
    'altright': pygame.K_RALT,
    'ctrlleft': pygame.K_LCTRL,  # kVK_Control
    'ctrlright': pygame.K_RCTRL,  # kVK_RightControl
    'f1': pygame.K_F1,  # kVK_F1
    'f2': pygame.K_F2,  # kVK_F2
    'f3': pygame.K_F3,  # kVK_F3
    'f4': pygame.K_F4,  # kVK_F4
    'f5': pygame.K_F5,  # kVK_F5
    'f6': pygame.K_F6,  # kVK_F6
    'f7': pygame.K_F7,  # kVK_F7
    'f8': pygame.K_F8,  # kVK_F8
    'f9': pygame.K_F9,  # kVK_F9
    'f10': pygame.K_F10,  # kVK_F10
    'f11': pygame.K_F11,  # kVK_F11
    'f12': pygame.K_F12,  # kVK_F12
    'f13': pygame.K_F13,  # kVK_F13
    'f14': pygame.K_F14,  # kVK_F14
    'f15': pygame.K_F15,  # kVK_F15
    'pageup': pygame.K_PAGEUP,  # kVK_PageUp
    'pagedown': pygame.K_PAGEDOWN,  # kVK_PageDown
    'delete': pygame.K_DELETE,  # kVK_ForwardDelete
    'end': pygame.K_END,  # kVK_End
    'left': pygame.K_LEFT,  # kVK_LeftArrow
    'right': pygame.K_RIGHT,  # kVK_RightArrow
    'down': pygame.K_DOWN,  # kVK_DownArrow
    'up': pygame.K_UP,  # kVK_UpArrow
})

key_code_reverse_map = {value: key for key, value in keyboardMapping.items()}


def get_key_code(pyautogui_name):
    return keyboardMapping[pyautogui_name]


def get_pyautogui_key_name(code):
    return key_code_reverse_map[code]
