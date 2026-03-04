from constants import EVENT_KEY_UP, EVENT_KEY_DOWN
from KeyMapper import get_midi_key_name

NOTE_OFF = "NOTE_OFF"
NOTE_ON = "NOTE_ON"
KEY_AFTER_TOUCH = "KEY_AFTER_TOUCH"
CONTROLLER_CHANGE = "CONTROLLER_CHANGE"
PROGRAM_CHANGE = "PROGRAM_CHANGE"
CHANNEL_AFTER_TOUCH = "CHANNEL_AFTER_TOUCH"
PITCH_BEND = "PITCH_BEND"

# Maps upper nibble of status byte to command name
COMMANDS = {
    0x08: NOTE_OFF,
    0x09: NOTE_ON,
    0x0A: KEY_AFTER_TOUCH,
    0x0B: CONTROLLER_CHANGE,
    0x0C: PROGRAM_CHANGE,
    0x0D: CHANNEL_AFTER_TOUCH,
    0x0E: PITCH_BEND,
}

MOD_WHEEL = "MOD_WHEEL"
BREATH = "BREATH"
FOOT = "FOOT"
PORTAMENTO = "PORTAMENTO"
DATA = "DATA"
VOLUME = "VOLUME"
PAN = "PAN"

CONTROLLER_CHANGES = {
    1: MOD_WHEEL,
    2: BREATH,
    4: FOOT,
    5: PORTAMENTO,
    6: DATA,
    7: VOLUME,
    10: PAN,
}


def rtmidi_msg_to_event(msg_bytes):
    """Parse an rtmidi message (list of ints) into an event dict."""
    status = msg_bytes[0]
    data1 = msg_bytes[1] if len(msg_bytes) > 1 else 0
    data2 = msg_bytes[2] if len(msg_bytes) > 2 else 0
    msg_type = (status & 0xF0) >> 4
    channel = status & 0x0F
    command = COMMANDS.get(msg_type, status & 0xF0)
    return {
        'status': status,
        'command': command,
        'channel': channel,
        'data1': data1,
        'data2': data2,
    }


def simplify_midi_event(event):
    key_id = get_midi_key_name(event['data1'])
    velocity = event['data2']
    return {'id': key_id, 'event': EVENT_KEY_DOWN if velocity > 0 else EVENT_KEY_UP}
