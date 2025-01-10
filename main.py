#!/usr/bin/env python3
import pygame
import pyaudio
import wave
import numpy as np
import os
import requests
import json
from datetime import datetime
from io import BytesIO

# Initialize Pygame
pygame.init()
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
width, height = screen.get_size()

# LCARS Colors
ORANGE = (255, 153, 0)
PINK = (255, 153, 204)
PURPLE = (204, 153, 204)
BLUE = (153, 153, 255)
BROWN = (204, 153, 102)
RED = (204, 102, 102)
BLACK = (0, 0, 0)

# Audio setup
audio = pyaudio.PyAudio()
CHANNELS = 1
RATE = 16000
CHUNK = 1024
FORMAT = pyaudio.paFloat32

# Server settings
SERVER_URL = "https://10.250.10.148:8000"
VERIFY_SSL = False

class Button:
    def __init__(self, x, y, width, height, color, text=''):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
        self.text = text
        self.font = pygame.font.Font(None, 36)
        self.active = False

    def draw(self, surface):
        # Draw basic rectangle
        pygame.draw.rect(surface, self.color, self.rect)
        # Draw rounded corners with small circles
        radius = 10
        pygame.draw.circle(surface, self.color, (self.rect.left + radius, self.rect.top + radius), radius)
        pygame.draw.circle(surface, self.color, (self.rect.right - radius, self.rect.top + radius), radius)
        pygame.draw.circle(surface, self.color, (self.rect.left + radius, self.rect.bottom - radius), radius)
        pygame.draw.circle(surface, self.color, (self.rect.right - radius, self.rect.bottom - radius), radius)
        
        if self.text:
            text_surface = self.font.render(self.text, True, BLACK)
            text_rect = text_surface.get_rect(center=self.rect.center)
            surface.blit(text_surface, text_rect)

def draw_lcars_frame():
    # Background
    screen.fill(BLACK)
    
    # Left side elbow - drawn as separate rectangles with a circle for corner
    pygame.draw.rect(screen, ORANGE, (0, 100, 80, height-100))  # Vertical bar
    pygame.draw.rect(screen, ORANGE, (0, 0, 200, 80))  # Horizontal bar
    pygame.draw.circle(screen, ORANGE, (80, 100), 20)  # Corner
    
    # Top bars
    colors = [PINK, PURPLE, BLUE, BROWN]
    for i, color in enumerate(colors):
        pygame.draw.rect(screen, color, (220 + i*90, 0, 80, 60))

def audio_callback(in_data, frame_count, time_info, status):
    if status:
        print(status)
    chunks.append(in_data)
    return (in_data, pyaudio.paContinue)

# Create buttons and state
record_button = Button(width//2-100, height//2-50, 200, 100, RED, "RECORD")
messages = []
chunks = []
font = pygame.font.Font(None, 32)

def send_audio_to_server():
    try:
        # Prepare audio data
        audio_data = np.concatenate([np.frombuffer(chunk, dtype=np.float32) 
                                   for chunk in chunks])
        
        # Convert to WAV format
        wav_buffer = BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(4)  # 32-bit float
            wf.setframerate(RATE)
            wf.writeframes(audio_data.tobytes())
            
        # Send to server
        files = {'audio': ('audio.wav', wav_buffer.getvalue(), 'audio/wav')}
        response = requests.post(
            f"{SERVER_URL}/api/transcribe",
            files=files,
            verify=VERIFY_SSL
        )
        
        if response.ok:
            result = response.json()
            text = result.get('text', '').strip()
            if text:
                messages.append(('You: ' + text, BLUE))
                # Get AI response
                chat_response = requests.post(
                    f"{SERVER_URL}/api/chat",
                    json={'text': text},
                    verify=VERIFY_SSL
                )
                if chat_response.ok:
                    ai_text = chat_response.json().get('response', '').strip()
                    messages.append(('AI: ' + ai_text, PURPLE))
                    # Request speech
                    requests.post(
                        f"{SERVER_URL}/api/speak",
                        json={'text': ai_text},
                        verify=VERIFY_SSL
                    )
    except Exception as e:
        messages.append(('Error: ' + str(e), RED))

def draw_messages():
    y = height - 200
    for msg, color in messages[-3:]:  # Show last 3 messages
        text = font.render(msg[:50], True, color)  # Truncate long messages
        screen.blit(text, (220, y))
        y += 40

# Main loop
running = True
recording = False
stream = None

while running:
    draw_lcars_frame()
    record_button.color = PINK if recording else RED
    record_button.draw(screen)
    draw_messages()
    
    pygame.display.flip()
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            running = False
            
        elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
            pos = event.pos if event.type == pygame.MOUSEBUTTONDOWN else (event.x * width, event.y * height)
            if record_button.rect.collidepoint(pos):
                if not recording:
                    chunks.clear()
                    stream = audio.open(
                        format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK,
                        stream_callback=audio_callback
                    )
                    stream.start_stream()
                    recording = True
                    messages.append(('Recording...', ORANGE))
                
        elif event.type in (pygame.MOUSEBUTTONUP, pygame.FINGERUP):
            if recording:
                recording = False
                if stream:
                    stream.stop_stream()
                    stream.close()
                    stream = None
                    messages.append(('Processing...', BROWN))
                    send_audio_to_server()

# Cleanup
if stream:
    stream.stop_stream()
    stream.close()
audio.terminate()
pygame.quit()
