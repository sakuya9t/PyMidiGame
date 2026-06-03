"""
MidiMania launcher.

Usage:
    python mania.py SONG.mid [--audio SONG.ogg] [--mode midi|pc] [--play]

Audio precedence: --audio if given, else a produced track paired with the MIDI
by name (SONG.mid -> SONG.ogg/.mp3/.wav/.flac in the same folder), else a simple
temporary WAV preview synthesized from the MIDI. The song auto-plays in demo mode (no
MIDI device needed); pass --play to take control with the PC keyboard (lanes
A S D F J K L ; for up to 8 lanes). Space pauses/resumes; Esc quits.
"""
import argparse

from src.app import run


def main() -> None:
    parser = argparse.ArgumentParser(description='MidiMania — a MIDI rhythm game.')
    parser.add_argument('midi', help='Path to the .mid chart file.')
    parser.add_argument('--audio', default=None,
                        help='Produced audio track (mp3/ogg/wav) to play. '
                             'Overrides the paired-file / MIDI preview fallback.')
    parser.add_argument('--mode', default='midi', choices=['midi', 'pc'],
                        help='Lane mode: "midi" (1:1) or "pc" (8 lanes). Default midi.')
    parser.add_argument('--play', action='store_true',
                        help='Play with the PC keyboard instead of demo auto-play.')
    args = parser.parse_args()

    run(args.midi, audio_path=args.audio, demo=not args.play, mode=args.mode)


if __name__ == '__main__':
    main()
