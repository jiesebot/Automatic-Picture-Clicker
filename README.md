# Automatic-Picture-Clicker
Automatic Picture Clicker. IDK what else to tell you.


Does what it says

If using EXE: 
Should just open normally, if it doesn't, use the requirements installation from the Python section.

If using Python:

Install the requirements first
>python -m pip install --upgrade opencv-python pyautogui pillow numpy pynput

Then open pc2.py in PowerScript
The most recent version of Python I have installed is 3.13.9, so if it doesn't work on your version, install that one.

I use it for Smite 2 afk farming. You could probably use it for similar things, like automating Nexus Mod downloads.

### Note: You will have to manually expand the window to see every option.

<img width="918" height="1211" alt="Capture" src="https://github.com/user-attachments/assets/c111210f-328f-49d1-b5cb-9a90a936b089" />

#Features

## Pictures

Allows multiple pictures along with checkboxes to enable it to find the ones you want to click, while keeping the others stored for later (so you can upload them all at the same time).

## Settings

Match Threshold: How similar an image has to be to an enabled picture in order for the software to attempt to click it. I personally use 0.75. Use something like 0.90 or 0.95 if it is clicking the wrong things. Use something like 0.75 or 0.80 if it is missing images that are clearly visible.

Scan delay seconds: Controls how long the program waits between full-screen scans.

Delay after click (seconds): Controls how long the program waits after a click before continuing.

Loop yield delay seconds: Only matters when "Keep clicking while matching image remains visible" is turned on. It adds a tiny pause inside the repeat-click loop so the program does not completely hog the CPU while repeatedly clicking the same image.

Click every match: Changes how it handles multiple copies of the same image on-screen.
-Off means: if it finds that picture in multiple places, it clicks only the best match.
-On means: if it finds that picture in multiple places, it clicks all matching locations.

Keep clicking: Makes the program repeatedly click the same image until it disappears.

Prioritize less recently clicked: Makes the program rotate through your enabled pictures instead of obsessing over the same recently clicked one. Could possibly slow down the search if using a lot of photos.

Move cursor to top-left: Moves the mouse away after every click.
-This is useful because sometimes the mouse cursor hovering over a button changes the button’s appearance. If the button changes appearance, image matching can fail. Parking the cursor in the corner keeps it out of the way.

>Top-left park: Controls where the cursor moves to. Default is top-left of the screen, although it can be changed. Do not use 0, 0. PyAutoGUI uses the exact top-left corner as an emergency failsafe. Moving the mouse there can immediately stop the program.

Hotkey: Self-explanatory, changes what hot-key is used for enabling and disabling the tool. Default is Ctrl + Alt + S

Setting Presets: Type the name you want to give your preset and then press "Save Preset". Click the arrow, click the preset, and then press "Load Preset" to load it or "Delete Preset" to delete it. This is useful if you want different settings for different apps or tasks. It saves, loads, and deletes settings for the program, but does not do the same for pictures. Those will need to be set manually.
