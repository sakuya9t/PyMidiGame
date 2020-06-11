import time

import pygame

pygame.mixer.pre_init(44100)  # setup mixer to avoid sound lag
pygame.init()
pygame.mixer.init()
pygame.mixer.music.load('../resources/chords.mid')
pygame.mixer.music.play()
time.sleep(60)