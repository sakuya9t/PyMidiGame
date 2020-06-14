import Mp3Player
clip = Mp3Player.load(r'C:\Users\sakuya\Music\Vicetone - Nevada (Original Mix).mp3')

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