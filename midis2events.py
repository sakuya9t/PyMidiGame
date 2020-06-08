# adapted from
# http://www.pygame.org/docs/ref/midi.html#comment_pygame_midi_midis2events

import pygame

# Incomplete listing:
from constants import EVENT_KEY_UP, EVENT_KEY_DOWN
from KeyMapper import get_key_name

NOTE_OFF = "NOTE_OFF"
NOTE_ON = "NOTE_ON"
KEY_AFTER_TOUCH = "KEY_AFTER_TOUCH"
CONTROLLER_CHANGE = "CONTROLLER_CHANGE"
PROGRAM_CHANGE = "PROGRAM_CHANGE"
CHANNEL_AFTER_TOUCH = "CHANNEL_AFTER_TOUCH"
PITCH_BEND = "PITCH_BEND"

COMMANDS = {
    0: NOTE_OFF,
    1: NOTE_ON,
    2: KEY_AFTER_TOUCH,
    3: CONTROLLER_CHANGE,
    4: PROGRAM_CHANGE,
    5: CHANNEL_AFTER_TOUCH,
    6: PITCH_BEND,
}

MOD_WHEEL = "MOD_WHEEL"
BREATH = "BREATH"
FOOT = "FOOT"
PORTAMENTO = "PORTAMENTO"
DATA = "DATA"
VOLUME = "VOLUME"
PAN = "PAN"

# Incomplete listing: this is the key to CONTROLLER_CHANGE events data1
CONTROLLER_CHANGES = {
    1: MOD_WHEEL,
    2: BREATH,
    4: FOOT,
    5: PORTAMENTO,
    6: DATA,
    7: VOLUME,
    10: PAN,
}


def midis2events(midis, device_id):
    """ Takes a sequence of midi events and returns list of pygame events."""
    evs = []
    for midi in midis:

        ((status, data1, data2, data3), timestamp) = midi

        if status == 0xFF:
            # pygame doesn't seem to get these, so I didn't decode
            command = "META"
            channel = None
        else:
            try:
                command = COMMANDS[ (status & 0x70) >> 4]
            except:
                command = status & 0x70
            channel = status & 0x0F

        e = pygame.event.Event(pygame.midi.MIDIIN,
                               status=status,
                               command=command,
                               channel=channel,
                               data1=data1,
                               data2=data2,
                               timestamp=timestamp,
                               vice_id=device_id)
        evs.append(e)
    return evs


def simplify_midi_event(event):
    key_id = get_key_name(event.dict['data1'])
    velocity = event.dict['data2']
    return {'id': key_id, 'event': EVENT_KEY_DOWN if velocity > 0 else EVENT_KEY_UP}