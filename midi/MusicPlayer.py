import midi.mp3play as mp3play

clip = mp3play.load(r'C:\Users\sakuya\Music\AGA - Wonderful U.mp3')

clip.play()

# Let it play for up to 30 seconds, then stop it.
import time
time.sleep(min(5, clip.seconds()))
clip.pause()
time.sleep(5)
clip.unpause()
time.sleep(5)
clip.stop()
print('a')