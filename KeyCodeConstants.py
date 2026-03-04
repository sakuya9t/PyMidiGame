import pygame

pygame_keys = [pygame.K_a, pygame.K_b, pygame.K_c, pygame.K_d, pygame.K_e, pygame.K_f, pygame.K_g,
               pygame.K_h, pygame.K_i, pygame.K_j, pygame.K_k, pygame.K_l, pygame.K_m, pygame.K_n,
               pygame.K_o, pygame.K_p, pygame.K_q, pygame.K_r, pygame.K_s, pygame.K_t, pygame.K_u,
               pygame.K_v, pygame.K_w, pygame.K_x, pygame.K_y, pygame.K_z, pygame.K_0, pygame.K_1,
               pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6, pygame.K_7, pygame.K_8,
               pygame.K_9, pygame.K_MINUS, pygame.K_EQUALS, pygame.K_COMMA, pygame.K_PERIOD,
               pygame.K_SEMICOLON, pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET, pygame.K_QUOTE,
               pygame.K_BACKSLASH, pygame.K_SLASH, pygame.K_BACKQUOTE, pygame.K_SPACE, pygame.K_RETURN,
               pygame.K_TAB, pygame.K_BACKSPACE, pygame.K_ESCAPE, pygame.K_CAPSLOCK, pygame.K_LSHIFT,
               pygame.K_RSHIFT, pygame.K_LALT, pygame.K_RALT, pygame.K_LCTRL, pygame.K_RCTRL, pygame.K_F1,
               pygame.K_F2, pygame.K_F3, pygame.K_F4, pygame.K_F5, pygame.K_F6, pygame.K_F7, pygame.K_F8,
               pygame.K_F9, pygame.K_F10, pygame.K_F11, pygame.K_F12, pygame.K_F13, pygame.K_F14, pygame.K_F15,
               pygame.K_PAGEUP, pygame.K_PAGEDOWN, pygame.K_DELETE, pygame.K_END, pygame.K_LEFT, pygame.K_RIGHT,
               pygame.K_DOWN, pygame.K_UP]

pygame_keys_code = {pygame.key.name(x): x for x in pygame_keys}

# Maps key names (stored in config, formerly pyautogui convention) to pygame key codes.
keyboardMapping = {
    'a': pygame.K_a,
    'b': pygame.K_b,
    'c': pygame.K_c,
    'd': pygame.K_d,
    'e': pygame.K_e,
    'f': pygame.K_f,
    'g': pygame.K_g,
    'h': pygame.K_h,
    'i': pygame.K_i,
    'j': pygame.K_j,
    'k': pygame.K_k,
    'l': pygame.K_l,
    'm': pygame.K_m,
    'n': pygame.K_n,
    'o': pygame.K_o,
    'p': pygame.K_p,
    'q': pygame.K_q,
    'r': pygame.K_r,
    's': pygame.K_s,
    't': pygame.K_t,
    'u': pygame.K_u,
    'v': pygame.K_v,
    'w': pygame.K_w,
    'x': pygame.K_x,
    'y': pygame.K_y,
    'z': pygame.K_z,
    '0': pygame.K_0,
    '1': pygame.K_1,
    '2': pygame.K_2,
    '3': pygame.K_3,
    '4': pygame.K_4,
    '5': pygame.K_5,
    '6': pygame.K_6,
    '7': pygame.K_7,
    '8': pygame.K_8,
    '9': pygame.K_9,
    '-': pygame.K_MINUS,
    '=': pygame.K_EQUALS,
    ',': pygame.K_COMMA,
    '.': pygame.K_PERIOD,
    ';': pygame.K_SEMICOLON,
    '[': pygame.K_LEFTBRACKET,
    ']': pygame.K_RIGHTBRACKET,
    "'": pygame.K_QUOTE,
    '\\': pygame.K_BACKSLASH,
    '/': pygame.K_SLASH,
    '`': pygame.K_BACKQUOTE,
    'space': pygame.K_SPACE,
    'enter': pygame.K_RETURN,
    'tab': pygame.K_TAB,
    'backspace': pygame.K_BACKSPACE,
    'escape': pygame.K_ESCAPE,
    'capslock': pygame.K_CAPSLOCK,
    'shiftleft': pygame.K_LSHIFT,
    'shiftright': pygame.K_RSHIFT,
    'altleft': pygame.K_LALT,
    'altright': pygame.K_RALT,
    'ctrlleft': pygame.K_LCTRL,
    'ctrlright': pygame.K_RCTRL,
    'f1': pygame.K_F1,
    'f2': pygame.K_F2,
    'f3': pygame.K_F3,
    'f4': pygame.K_F4,
    'f5': pygame.K_F5,
    'f6': pygame.K_F6,
    'f7': pygame.K_F7,
    'f8': pygame.K_F8,
    'f9': pygame.K_F9,
    'f10': pygame.K_F10,
    'f11': pygame.K_F11,
    'f12': pygame.K_F12,
    'f13': pygame.K_F13,
    'f14': pygame.K_F14,
    'f15': pygame.K_F15,
    'pageup': pygame.K_PAGEUP,
    'pagedown': pygame.K_PAGEDOWN,
    'delete': pygame.K_DELETE,
    'end': pygame.K_END,
    'left': pygame.K_LEFT,
    'right': pygame.K_RIGHT,
    'down': pygame.K_DOWN,
    'up': pygame.K_UP,
}

key_code_reverse_map = {value: key for key, value in keyboardMapping.items()}


def get_key_code(key_name):
    return keyboardMapping.get(key_name)


def get_pyautogui_key_name(code):
    return key_code_reverse_map[code]


def pygame_key_code(key_name):
    if key_name not in pygame_keys_code.keys():
        raise Exception('Unsupported key {}'.format(key_name))
    return pygame_keys_code[key_name]
