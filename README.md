# Prayer Times Alert

A desktop application that provides timely notifications for Islamic prayer times, running silently in your system tray.

## Overview

Prayer Times Alert is a Windows application that fetches Islamic prayer times and provides notifications before and at prayer times. The app runs in the system tray, providing a non-intrusive way to receive prayer time alerts with sound notifications.

## Features

- **Automated Prayer Time Fetching**: Automatically retrieves prayer times for Cairo, Egypt using the Aladhan API
- **Customized Notifications**: 
  - Reminder notifications 15 and 5 minutes before each prayer
  - Adhan (call to prayer) notification at the exact prayer time
- **Audio Alerts**: 
  - Different sounds for reminders and adhan
  - Ability to stop sounds from the system tray
- **System Tray Integration**:
  - Runs silently in the background
  - Displays next prayer information in tray tooltip
  - Provides quick access to today's prayer times
- **Single Instance**: Prevents multiple instances of the application from running
- **Automatic Startup**: Can be configured to run on system startup

## Technical Details

- **Language**: Python
- **Dependencies**:
  - requests - For API calls
  - pygame - For audio playback
  - plyer - For desktop notifications
  - pystray - For system tray functionality
  - PIL (Pillow) - For image processing
- **API**: Aladhan API for prayer times


After launching the application:

1. The app will run in your system tray (look for the prayer icon in the taskbar)
2. Right-click the icon to:
   - View today's prayer times
   - Stop any currently playing sound
   - Exit the application
3. The app will automatically show notifications:
   - 15 minutes before prayer time
   - 5 minutes before prayer time
   - At the exact prayer time (with adhan)

## Project Structure

- `prayer_alert.py` - Main application code
- `resources/` - Directory containing audio and image resources:
  - `alert_sound.mp3` - Sound for reminders
  - `athan_alafasy.mp3` - Adhan sound for prayer times
  - `prayer_icon.png` - System tray icon

## Configuration

Currently, the application is configured for Cairo, Egypt. To modify for other locations, you'll need to update the coordinates in the `get_prayer_times()` function.

## Admin Privileges

The application requires admin privileges to ensure proper notification functionality on Windows.

## Logging

The application logs activity to `prayer_alert.log` in the same directory as the executable.


## Acknowledgments

- Aladhan API for providing accurate prayer times
- Sheikh Mishary Rashid Alafasy for the adhan recitation

---

May this application help you maintain consistent prayer practices throughout your day.
