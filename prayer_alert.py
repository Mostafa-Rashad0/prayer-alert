import requests
import datetime
import time
import threading
import sys
import ctypes
import subprocess
import os
import logging
from plyer import notification
import pygame
from datetime import datetime, timedelta
import socket  # For single instance check
from PIL import Image  # For system tray icon
import pystray  # For system tray functionality

# Configure logging
logging.basicConfig(
    filename='prayer_alert.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Initialize pygame for audio
pygame.init()
pygame.mixer.init()

# Global variables
stop_sound_event = threading.Event()
sound_playing = False
sound_thread = None
exit_event = threading.Event()  # To signal the application to exit
tray_icon = None  # Will hold the system tray icon

# Constants
DETACHED_PROCESS = 0x00000008
DEFAULT_METHOD = 5  # Method 5 is Egyptian General Authority of Survey
SOCKET_PORT = 47890  # Arbitrary port for single instance check

# Get the directory the executable is in (for PyInstaller)
def get_base_dir():
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return os.path.dirname(sys.executable)
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))

# Define paths
base_dir = get_base_dir()
REMINDER_SOUND = os.path.join(base_dir, "resources", "alert_sound.mp3")
ADHAN_SOUND = os.path.join(base_dir, "resources", "athan_alafasy.mp3")
ICON_PATH = os.path.join(base_dir, "resources", "prayer_icon.png")

# For development environment - use absolute paths if files exist
DEV_REMINDER_SOUND = r"D:\python VC\my_projects\prayer_alert\resources\alert_sound.mp3"
DEV_ADHAN_SOUND = r"D:\python VC\my_projects\prayer_alert\resources\athan_alafasy.mp3"
DEV_ICON_PATH = r"D:\python VC\my_projects\prayer_alert\resources\prayer_icon.png"

# First try the packaged resources
if not os.path.exists(REMINDER_SOUND) and os.path.exists(DEV_REMINDER_SOUND):
    REMINDER_SOUND = DEV_REMINDER_SOUND
if not os.path.exists(ADHAN_SOUND) and os.path.exists(DEV_ADHAN_SOUND):
    ADHAN_SOUND = DEV_ADHAN_SOUND
if not os.path.exists(ICON_PATH) and os.path.exists(DEV_ICON_PATH):
    ICON_PATH = DEV_ICON_PATH

# If icon still doesn't exist, we'll create a basic one
if not os.path.exists(ICON_PATH):
    from PIL import Image, ImageDraw
    
    # Create a simple icon - a green circle
    img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((5, 5, 59, 59), fill=(0, 128, 0))
    
    # Ensure resources directory exists
    os.makedirs(os.path.join(base_dir, "resources"), exist_ok=True)
    
    # Save the icon
    img.save(ICON_PATH)
    logging.info(f"Created default icon at {ICON_PATH}")

def is_already_running():
    """Check if application is already running by trying to bind to a specific port"""
    try:
        # Create a socket and try to bind to port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('localhost', SOCKET_PORT))
        sock.listen(5)
        # If we get here, no other instance is running
        return False
    except socket.error:
        # If we can't bind to the port, another instance is already running
        return True

def show_already_running_notification():
    """Show notification that app is already running"""
    try:
        notification.notify(
            title="Prayer Times Alert App",
            message="The application is already running in the background. Check system tray for details.",
            app_name="Prayer Times Alert",
            timeout=10
        )
        logging.info("Showed 'already running' notification")
    except Exception as e:
        logging.error(f"Error displaying notification: {e}")

def show_started_notification():
    """Show notification that app has started successfully"""
    try:
        notification.notify(
            title="Prayer Times Alert App Started",
            message="The application is now running in the system tray and will alert you before prayer times.",
            app_name="Prayer Times Alert",
            timeout=10
        )
        logging.info("Showed 'app started' notification")
    except Exception as e:
        logging.error(f"Error displaying notification: {e}")

def run_as_admin():
    """Restart the script with admin privileges if not already running as admin"""
    if ctypes.windll.shell32.IsUserAnAdmin():
        return True
    
    script = sys.argv[0]
    params = ' '.join(sys.argv[1:])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
    sys.exit()

def get_prayer_times(city="Cairo", country="Egypt", method=DEFAULT_METHOD):
    """Fetch prayer times from Aladhan API"""
    try:
        # Cairo coordinates
        url = "http://api.aladhan.com/v1/timings?latitude=30.0444&longitude=31.2357&method=5"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 200 and data.get('status') == 'OK':
                return data.get('data', {}).get('timings', {})
            else:
                logging.error(f"API Error: {data.get('data')}")
                return None
        else:
            logging.error(f"Failed to fetch prayer times. Status code: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"Error fetching prayer times: {e}")
        return None

def parse_time(time_str):
    """Convert time string to datetime object"""
    try:
        current_date = datetime.now().strftime("%Y-%m-%d")
        time_obj = datetime.strptime(f"{current_date} {time_str}", "%Y-%m-%d %H:%M")
        return time_obj
    except Exception as e:
        logging.error(f"Error parsing time: {e}")
        return None

def calculate_alert_times(prayer_time, prayer_name):
    """Calculate alert times for reminders"""
    alerts = []
    
    # Add reminders before prayer time
    for minutes in [15, 5]:
        reminder_time = prayer_time - timedelta(minutes=minutes)
        # Only add future reminders
        if reminder_time > datetime.now():
            alerts.append({
                'time': reminder_time,
                'prayer': prayer_name,
                'type': 'reminder',
                'minutes': minutes
            })
    
    # Add the exact prayer time alert
    if prayer_time > datetime.now():
        alerts.append({
            'time': prayer_time,
            'prayer': prayer_name,
            'type': 'adhan',
            'minutes': 0
        })
        
    return alerts

def get_all_alerts(prayer_times):
    """Get all alerts for all prayers"""
    alerts = []
    prayers = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']
    
    for prayer in prayers:
        if prayer in prayer_times:
            prayer_time = parse_time(prayer_times[prayer])
            if prayer_time:
                prayer_alerts = calculate_alert_times(prayer_time, prayer)
                alerts.extend(prayer_alerts)
    
    # Sort alerts by time
    alerts.sort(key=lambda x: x['time'])
    return alerts

def play_sound(file_path):
    """Play sound using pygame"""
    global sound_playing
    
    try:
        sound_playing = True
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        
        # Wait for the sound to finish or for stop event
        while pygame.mixer.music.get_busy() and not stop_sound_event.is_set():
            time.sleep(0.1)
            
        # Stop the sound if it's still playing
        pygame.mixer.music.stop()
        sound_playing = False
    except Exception as e:
        logging.error(f"Error playing sound: {e}")
        sound_playing = False

def stop_sound():
    """Stop the currently playing sound"""
    global sound_playing
    
    if sound_playing:
        stop_sound_event.set()
        time.sleep(0.2)  # Give time for the sound thread to respond
        stop_sound_event.clear()
        logging.info("Sound stopped by user")
        
        # Update tray icon title
        if tray_icon:
            update_tray_title()

def handle_alert(alert):
    """Handle displaying notifications and playing sounds for an alert"""
    global sound_thread
    
    prayer = alert['prayer']
    alert_type = alert['type']
    
    # Create the notification message
    if alert_type == 'reminder':
        title = f"{prayer} Prayer Reminder"
        message = f"{prayer} prayer will be in {alert['minutes']} minutes at {alert['time'].strftime('%H:%M')}"
        sound_file = REMINDER_SOUND
    else:  # adhan
        title = f"{prayer} Prayer Time"
        message = f"It's time for {prayer} prayer"
        sound_file = ADHAN_SOUND
    
    # Display notification
    try:
        notification.notify(
            title=title,
            message=message,
            app_name="Prayer Times Alert",
            timeout=10
        )
        logging.info(f"Notification displayed: {title} - {message}")
        
        # Update tray icon title
        if tray_icon:
            if alert_type == 'adhan':
                tray_icon.title = f"Prayer Alert - {prayer} Prayer Time"
            else:
                tray_icon.title = f"Prayer Alert - {prayer} in {alert['minutes']} min"
    except Exception as e:
        logging.error(f"Error displaying notification: {e}")

    # Play sound in a separate thread
    if not sound_playing:
        # Ensure previous sound thread is not active
        if sound_thread and sound_thread.is_alive():
            stop_sound()
            sound_thread.join(1)
        
        sound_thread = threading.Thread(target=play_sound, args=(sound_file,))
        sound_thread.daemon = True
        sound_thread.start()
        logging.info(f"Started playing {alert_type} sound for {prayer} prayer")
    else:
        logging.info("Another sound is already playing, skipping")

def update_tray_title(next_prayer_info=None):
    """Update the tray icon title with next prayer information"""
    if tray_icon:
        if sound_playing:
            tray_icon.title = "Prayer Alert - Sound Playing (Right-click to stop)"
        elif next_prayer_info:
            prayer, time_str = next_prayer_info
            tray_icon.title = f"Prayer Alert - Next: {prayer} at {time_str}"
        else:
            tray_icon.title = "Prayer Times Alert"

def on_exit(icon):
    """Handle exit from system tray"""
    global exit_event
    icon.stop()
    exit_event.set()
    logging.info("Application exit requested from system tray")

def on_stop_sound(icon):
    """Stop currently playing sound from system tray menu"""
    stop_sound()
    
def is_sound_playing(*args):
    """Check if sound is currently playing - used for menu item enabled state"""
    return sound_playing
    
def main_tray_loop():
    """Main function for the system tray application"""
    global tray_icon
    
    # Fetch initial prayer times
    prayer_times = get_prayer_times()
    
    # Load icon
    icon_image = Image.open(ICON_PATH)
    
    # Create menu for system tray icon
    def create_menu():
        prayers = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']
        prayer_items = []
        
        if prayer_times:
            for prayer in prayers:
                if prayer in prayer_times:
                    prayer_items.append(
                        pystray.MenuItem(f"{prayer}: {prayer_times[prayer]}", lambda _: None)
                    )
        else:
            prayer_items.append(pystray.MenuItem("No prayer times available", lambda _: None))
        
        prayer_times_menu = pystray.Menu(*prayer_items)
        
        return pystray.Menu(
            pystray.MenuItem("Today's Prayer Times", pystray.Menu(*prayer_items)),
            pystray.MenuItem("Stop Sound", on_stop_sound, enabled=is_sound_playing),
            pystray.MenuItem("Exit", on_exit)
        )
    
    # Create system tray icon
    tray_icon = pystray.Icon(
        "prayer_alert",
        icon_image,
        "Prayer Times Alert"
    )
    
    # Set the menu
    tray_icon.menu = create_menu()
    
    # Start the icon in a separate thread
    icon_thread = threading.Thread(target=tray_icon.run)
    icon_thread.daemon = True
    icon_thread.start()
    
    # Show notification that app has started
    show_started_notification()
    
    # Main application loop
    while not exit_event.is_set():
        try:
            # Fetch prayer times
            prayer_times = get_prayer_times()
            
            if prayer_times:
                logging.info(f"Fetched prayer times: {prayer_times}")
                
                # Calculate all alerts
                alerts = get_all_alerts(prayer_times)
                
                # Update tray icon menu to reflect current prayer times
                tray_icon.menu = create_menu()
                
                if not alerts:
                    logging.info("No upcoming prayers for today.")
                    # Update tray icon title
                    update_tray_title()
                    # Sleep until next day
                    tomorrow = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
                    seconds_to_tomorrow = (tomorrow - datetime.now()).total_seconds()
                    logging.info(f"Sleeping until tomorrow ({seconds_to_tomorrow/60:.1f} minutes)...")
                    
                    # Sleep in small intervals to check for exit event
                    sleep_interval = 300  # 5 minutes
                    for _ in range(int(seconds_to_tomorrow / sleep_interval) + 1):
                        if exit_event.is_set():
                            break
                        time.sleep(min(sleep_interval, seconds_to_tomorrow))
                    continue
                
                # Get next prayer info
                next_prayer = alerts[0]['prayer']
                next_time = alerts[0]['time'].strftime('%H:%M')
                logging.info(f"Next prayer: {next_prayer} at {next_time}")
                
                # Update tray icon title with next prayer
                update_tray_title((next_prayer, next_time))
                
                # Process each alert
                for alert in alerts:
                    # Calculate seconds until the alert
                    seconds_until_alert = (alert['time'] - datetime.now()).total_seconds()
                    
                    if seconds_until_alert > 0:
                        logging.info(f"Waiting for {alert['prayer']} {alert['type']} alert in {seconds_until_alert/60:.1f} minutes...")
                        
                        # Wait until alert time (check every 15 seconds for exit event)
                        wait_interval = 15
                        while (alert['time'] - datetime.now()).total_seconds() > wait_interval:
                            if exit_event.is_set():
                                return
                            time.sleep(wait_interval)
                        
                        # Final wait for exact timing
                        remaining_seconds = (alert['time'] - datetime.now()).total_seconds()
                        if remaining_seconds > 0:
                            if exit_event.wait(timeout=remaining_seconds):
                                return
                        
                        # Trigger the alert if we haven't been asked to exit
                        if not exit_event.is_set():
                            handle_alert(alert)
                    
                # After processing all alerts, wait for next hour to refresh prayer times
                next_hour = datetime.now().replace(minute=0, second=0) + timedelta(hours=1)
                seconds_to_next_hour = (next_hour - datetime.now()).total_seconds()
                logging.info(f"All alerts processed. Refreshing prayer times in {seconds_to_next_hour/60:.1f} minutes...")
                
                # Sleep in small intervals to check for exit event
                sleep_interval = 300  # 5 minutes
                for _ in range(int(seconds_to_next_hour / sleep_interval) + 1):
                    if exit_event.is_set():
                        break
                    time.sleep(min(sleep_interval, seconds_to_next_hour))
            else:
                # If API call failed, wait 5 minutes and try again
                logging.warning("Failed to fetch prayer times. Retrying in 5 minutes...")
                if exit_event.wait(timeout=300):  # Wait 5 minutes or until exit
                    break
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            # Wait 1 minute before retry
            if exit_event.wait(timeout=60):  # Wait 1 minute or until exit
                break
    
    logging.info("Exiting application")
    pygame.quit()

def hide_console_window():
    """Hide the console window"""
    if sys.platform == "win32":
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd != 0:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE = 0

def main():
    """Main entry point for the application"""
    # Hide console window
    hide_console_window()
    
    # Check if application is already running
    if is_already_running():
        print("Application is already running!")
        show_already_running_notification()
        return
    
    # Check for admin privileges and restart if needed
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print("Restarting with admin privileges...")
        run_as_admin()
        return
    
    # Start the system tray application
    try:
        # Create socket server to keep the port occupied (for single instance check)
        socket_thread = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socket_thread.bind(('localhost', SOCKET_PORT))
        socket_thread.listen(5)
        
        # Run the main tray loop
        main_tray_loop()
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        # Make sure to display an error if it happens during startup
        try:
            notification.notify(
                title="Prayer Times Alert - Error",
                message=f"Application encountered an error: {str(e)}",
                app_name="Prayer Times Alert",
                timeout=10
            )
        except:
            pass

if __name__ == "__main__":
    main()