"""
MidiMania launcher.

Usage:
    python mania.py                      # song-select menu over songs/
    python mania.py --songs DIR          # menu over a custom library directory
    python mania.py SONG.mid [--audio SONG.ogg] [--mode midi|pc] [--play]

With no positional MIDI, the song-selection menu opens over the songs/ library:
↑↓ pick a song, ←→ choose PC Keyboard or Demo (MIDI Keyboard is shown but needs
a device), Enter plays, Esc quits; after a song, Enter returns to the menu and R
retries.

With a SONG.mid, the single song plays directly. Audio precedence: --audio if
given, else a produced track paired with the MIDI by name (SONG.mid ->
SONG.ogg/.mp3/.wav/.flac in the same folder), else a temporary WAV preview
synthesized from the MIDI. The song auto-plays in demo mode (no MIDI device
needed); pass --play to take control with the PC keyboard. Space pauses; Esc quits.
"""
import argparse

from src.app import run, App


def main() -> None:
    parser = argparse.ArgumentParser(description='MidiMania — a MIDI rhythm game.')
    parser.add_argument('midi', nargs='?', default=None,
                        help='Path to a .mid chart to play directly. Omit to open '
                             'the song-selection menu.')
    parser.add_argument('--songs', default='songs',
                        help='Song library directory for the menu (default: songs).')
    parser.add_argument('--audio', default=None,
                        help='Produced audio track (mp3/ogg/wav) to play. '
                             'Overrides the paired-file / MIDI preview fallback.')
    parser.add_argument('--mode', default='midi', choices=['midi', 'pc'],
                        help='Lane mode: "midi" (1:1) or "pc" (9 lanes). Default midi.')
    parser.add_argument('--play', action='store_true',
                        help='Play with the PC keyboard instead of demo auto-play.')
    args = parser.parse_args()

    if args.midi is None:
        App(songs_dir=args.songs).run()
    else:
        run(args.midi, audio_path=args.audio, demo=not args.play, mode=args.mode)


if __name__ == '__main__':
    main()
