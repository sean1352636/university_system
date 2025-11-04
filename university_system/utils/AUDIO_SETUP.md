# Audio System Setup Guide

## Overview

The university system uses PyAudio for audio-related features. This guide explains how to work with audio without annoying ALSA/JACK warnings.

## Quick Start

### Option 1: Use the Utility (Recommended)

```python
from utils.audio_utils import init_pyaudio_quietly

# Initialize PyAudio cleanly (no warnings)
p = init_pyaudio_quietly()

# Use it normally
device_count = p.get_device_count()
default_input = p.get_default_input_device_info()

# Clean up when done
p.terminate()
```

### Option 2: Manual Suppression

```python
from utils.audio_utils import suppress_alsa_warnings

# Suppress warnings during import and initialization only
with suppress_alsa_warnings():
    import pyaudio
    p = pyaudio.PyAudio()

# Use p normally here (warnings won't appear)
```

### Option 3: System-Wide (Not Recommended)

If you want to suppress warnings globally (affects all Python processes):

```bash
export ALSA_CARD=default
```

## Understanding the Warnings

### What You See

```
ALSA lib pcm.c:2666:(snd_pcm_open_noupdate) Unknown PCM cards.pcm.front
ALSA lib pcm.c:2666:(snd_pcm_open_noupdate) Unknown PCM cards.pcm.surround51
Cannot connect to server socket err = No such file or directory
jack server is not running or cannot be started
```

### What It Means

- **ALSA warnings**: The audio system is checking for fancy audio setups (5.1 surround sound, HDMI audio, etc.) that don't exist on your server
- **JACK warnings**: Professional audio server (JACK) isn't running - you don't need it for basic audio

### Why It's Safe to Ignore

✅ PyAudio is working correctly
✅ Audio devices are detected properly
✅ The warnings are purely informational
✅ No functionality is affected

## System Dependencies

### Required Packages (Already Installed)

```bash
# Debian/Ubuntu
sudo apt-get install portaudio19-dev python3-pyaudio

# Python package
pip install pyaudio
```

## Available Audio Devices

Run this to see your audio devices:

```python
from utils.audio_utils import init_pyaudio_quietly

p = init_pyaudio_quietly()

for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    print(f"Device {i}: {info['name']}")
    print(f"  Max Input Channels: {info['maxInputChannels']}")
    print(f"  Max Output Channels: {info['maxOutputChannels']}")
    print()

p.terminate()
```

## Troubleshooting

### "ImportError: No module named 'pyaudio'"

```bash
source venv/bin/activate
pip install pyaudio
```

### "Permission denied" during installation

```bash
sudo chown -R $USER:$USER venv/
pip install pyaudio
```

### "Failed to build wheel for pyaudio"

```bash
sudo apt-get install portaudio19-dev
pip install pyaudio
```

### Still seeing warnings?

Make sure you're using the `audio_utils` module:

```python
# ❌ Wrong - will show warnings
import pyaudio
p = pyaudio.PyAudio()

# ✅ Correct - no warnings
from utils.audio_utils import init_pyaudio_quietly
p = init_pyaudio_quietly()
```

## Best Practices

1. **Always use `audio_utils.init_pyaudio_quietly()`** instead of direct PyAudio initialization
2. **Always call `p.terminate()`** when done to free resources
3. **Use context managers** for automatic cleanup:

```python
class AudioManager:
    def __init__(self):
        self.p = init_pyaudio_quietly()

    def __enter__(self):
        return self.p

    def __exit__(self, *args):
        self.p.terminate()

# Usage
with AudioManager() as p:
    # Use p here
    pass
# Automatically cleaned up
```

## Future Features

Audio-related features in the system may include:
- Voice-to-text for lecture transcription
- Audio announcements in campus events
- Voice commands in accessibility features
- Audio notifications for alerts

All of these will use the `audio_utils` module for clean initialization.

## Support

If you encounter audio issues not covered here:
1. Check PyAudio version: `pip show pyaudio`
2. Verify system dependencies: `dpkg -l | grep portaudio`
3. Test basic functionality: `python -c "from utils.audio_utils import init_pyaudio_quietly; p = init_pyaudio_quietly(); print('OK'); p.terminate()"`
