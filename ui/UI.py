import pygame
from pygame_gui.elements import UIPanel, UIButton, UILabel, UIDropDownMenu, UIScrollingContainer, UIVerticalScrollBar
from pygame_gui.windows import UIMessageWindow

from config.Config import Config
from constants import UI_CONSTANT, STORE_KEYS


class UI:
    def __init__(self, ui_manager, store, ui_control):
        self.config = Config('ui/ui_layout.json')
        self.manager = ui_manager
        self.store = store
        self.controller = ui_control

    def render(self):
        if not self.store.get(STORE_KEYS.CONFIGURING_KEY_MAP):
            return
        self.__render__(self.config.get('mainframe'))
        if UI_CONSTANT.KEY_POPUP in self.controller.keys() and self.controller[UI_CONSTANT.KEY_POPUP]:
            self.__render__(self.config.get('keymap_dialog'))

    def __render__(self, element, parent=None):
        ele_type = element['type']
        if ele_type == 'panel':
            panel = UIPanel(relative_rect=__get_rect__(element),
                            manager=self.manager,
                            starting_layer_height=element['z-index'])
            for child in element['children']:
                self.__render__(child, panel)
        elif ele_type == 'scrollable-container':
            container = UIScrollingContainer(relative_rect=__get_rect__(element),
                                             manager=self.manager,
                                             container=parent)
            scrollbar_left = element['left'] + element['width'] - 20
            scroll = UIVerticalScrollBar(relative_rect=pygame.Rect(scrollbar_left, 0, 20, 250),
                                         manager=self.manager,
                                         visible_percentage=0.5,
                                         container=container)
            container.vert_scroll_bar = scroll
            for child in element['children']:
                self.__render__(child, container)
        elif ele_type == 'button':
            UIButton(relative_rect=__get_rect__(element),
                     text=element['text'],
                     manager=self.manager,
                     container=parent,
                     object_id=element['id'])
        elif ele_type == 'label':
            text = self.get_changeable_item(element['text'])
            UILabel(relative_rect=__get_rect__(element),
                    text=text,
                    manager=self.manager,
                    container=parent)
        elif ele_type == 'dropdown':
            options = self.get_changeable_item(element['options'])
            selected = '' if len(options) == 0 else options[element['default']]
            UIDropDownMenu(options_list=options,
                           starting_option=selected,
                           relative_rect=__get_rect__(element),
                           manager=self.manager,
                           container=parent,
                           object_id=element['id'])
        elif ele_type == 'table':
            rows = self.generate_rows(element)
            for row in rows:
                self.__render__(row, parent)
        elif ele_type == 'row':
            for i, child in enumerate(element['children'], start=0):
                child['width'] = element['column-width']
                child['height'] = element['height']
                child['left'] = element['left'] + i * element['column-width']
                child['top'] = element['top']
                self.__render__(child, parent)
        elif ele_type == 'cell':
            text = self.get_changeable_item(element['text'])
            UILabel(relative_rect=__get_rect__(element),
                    text=text,
                    manager=self.manager,
                    container=parent)
        elif ele_type == 'messagewindow':
            text = self.get_changeable_item(element['text'])
            UIMessageWindow(rect=__get_rect__(element),
                            html_message=text,
                            manager=self.manager)

    def get_changeable_item(self, value):
        if value.startswith('$'):
            key = value[1:]
            return self.store.get(key)
        return value

    def generate_rows(self, table):
        key = table['children'][1:]
        line_space = 5
        rows = []
        children_data = self.store.get(key)
        for i, line_item in enumerate(children_data, start=0):
            row = {'type': 'row',
                   'left': table['left'],
                   'top': table['top'] + i * (table['line-height'] + line_space),
                   'width': table['width'],
                   'height': table['line-height'],
                   'column-width': table['column-width'],
                   'children': [{'type': 'cell',
                                 'text': item} for item in line_item]}
            rows.append(row)
        return rows


def __get_rect__(element):
    return pygame.Rect(element['left'], element['top'], element['width'], element['height'])
