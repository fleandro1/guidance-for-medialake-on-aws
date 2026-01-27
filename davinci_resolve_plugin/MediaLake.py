#!/usr/bin/env python3
"""
Media Lake - DaVinci Resolve Workflow Integration Script

This script appears in Resolve's Workspace → Workflow Integrations menu.
It launches the Media Lake browser application.

Installation:
- macOS: Copy this file to /Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins/
- Windows: Copy this file to %PROGRAMDATA%\\Blackmagic Design\\DaVinci Resolve\\Support\\Workflow Integration Plugins\\

When launched from Resolve, this script opens the Media Lake browser panel.
"""

import sys
import os
import subprocess

# Path to the Media Lake plugin installation
# Update this path to where you installed the medialake_resolve package
MEDIALAKE_PLUGIN_DIR = "/Users/fleandro/src/guidance-for-medialake-on-aws/davinci_resolve_plugin"

# Try to get Resolve context (available when launched from Resolve)
try:
    # These are provided by Resolve when the script is launched
    resolve_obj = resolve  # noqa: F821 - provided by Resolve
    project_obj = project  # noqa: F821 - provided by Resolve
    fusion_obj = fusion  # noqa: F821 - provided by Resolve
    RUNNING_IN_RESOLVE = True
except NameError:
    resolve_obj = None
    project_obj = None
    fusion_obj = None
    RUNNING_IN_RESOLVE = False


def get_python_path():
    """Get the Python interpreter path."""
    # Try to find a suitable Python with PySide6
    possible_pythons = [
        # Conda environments - most likely to have PySide6
        "/opt/conda/envs/python_resolve/bin/python",
        "/opt/conda/envs/python_3_11/bin/python",
        "/opt/conda/bin/python",
        # Homebrew Python on macOS
        "/opt/homebrew/bin/python3",
        "/usr/local/bin/python3",
        # System Python
        "/usr/bin/python3",
    ]
    
    for python_path in possible_pythons:
        if os.path.exists(python_path):
            # Check if PySide6 is available
            try:
                result = subprocess.run(
                    [python_path, "-c", "import PySide6; print('ok')"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0 and "ok" in result.stdout:
                    return python_path
            except Exception:
                continue
    
    # Last resort - return the first one that exists (even without PySide6 check)
    for python_path in possible_pythons:
        if os.path.exists(python_path):
            return python_path
    
    return "/opt/conda/envs/python_resolve/bin/python"  # Default fallback


def launch_medialake_external():
    """Launch Media Lake as an external process."""
    import datetime
    
    python_path = get_python_path()
    
    # Set environment variables
    env = os.environ.copy()
    env["MEDIALAKE_LAUNCHED_FROM_RESOLVE"] = "1"
    
    # Add the plugin directory to PYTHONPATH
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{MEDIALAKE_PLUGIN_DIR}:{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = MEDIALAKE_PLUGIN_DIR
    
    # Log to a file for debugging
    log_file = os.path.join(MEDIALAKE_PLUGIN_DIR, "launch.log")
    error_log_file = os.path.join(MEDIALAKE_PLUGIN_DIR, "medialake_error.log")
    
    with open(log_file, "w") as f:
        f.write(f"Launch time: {datetime.datetime.now().isoformat()}\n")
        f.write(f"Python path: {python_path}\n")
        f.write(f"Plugin dir: {MEDIALAKE_PLUGIN_DIR}\n")
        f.write(f"PYTHONPATH: {env.get('PYTHONPATH', 'not set')}\n")
    
    # Launch the Media Lake application with error capture
    # Redirect stderr to a log file so we can diagnose issues
    os.chdir(MEDIALAKE_PLUGIN_DIR)
    cmd = f'"{python_path}" -m medialake_resolve 2>> "{error_log_file}" &'
    os.system(cmd)


def show_resolve_dialog():
    """Show a simple dialog in Resolve using UIManager."""
    if not RUNNING_IN_RESOLVE or fusion_obj is None:
        # If not in Resolve, just launch directly
        launch_medialake_external()
        return
    
    ui = fusion_obj.UIManager
    dispatcher = bmd.UIDispatcher(ui)  # noqa: F821 - provided by Resolve
    
    # Create a simple launcher dialog
    win = dispatcher.AddWindow(
        {
            'ID': 'MediaLakeLauncher',
            'WindowTitle': 'Media Lake',
            'Geometry': [400, 300, 400, 200],
        },
        ui.VGroup([
            ui.VGap(10),
            ui.Label({
                'ID': 'TitleLabel',
                'Text': '<h2>AWS Media Lake</h2>',
                'Alignment': {'AlignHCenter': True},
            }),
            ui.VGap(5),
            ui.Label({
                'ID': 'DescLabel',
                'Text': 'Browse, search, and import assets from AWS Media Lake into DaVinci Resolve.',
                'WordWrap': True,
                'Alignment': {'AlignHCenter': True},
            }),
            ui.VGap(20),
            ui.HGroup([
                ui.HGap(0, 1),
                ui.Button({
                    'ID': 'LaunchButton',
                    'Text': 'Open Media Lake Browser',
                    'MinimumSize': [200, 40],
                }),
                ui.HGap(0, 1),
            ]),
            ui.VGap(10),
            ui.Label({
                'ID': 'StatusLabel',
                'Text': '',
                'Alignment': {'AlignHCenter': True},
            }),
            ui.VGap(0, 1),
        ])
    )
    
    items = win.GetItems()
    
    def on_launch_clicked(ev):
        """Handle launch button click."""
        items['StatusLabel'].Text = 'Launching Media Lake...'
        win.Update()  # Force UI update
        try:
            launch_medialake_external()
            items['StatusLabel'].Text = 'Media Lake launched! You can close this dialog.'
        except Exception as e:
            # Log error to file
            log_file = os.path.join(MEDIALAKE_PLUGIN_DIR, "error.log")
            with open(log_file, "w") as f:
                import traceback
                f.write(traceback.format_exc())
            items['StatusLabel'].Text = f'Error: {str(e)}'
    
    def on_close(ev):
        """Handle window close."""
        dispatcher.ExitLoop()
    
    # Connect event handlers
    win.On.LaunchButton.Clicked = on_launch_clicked
    win.On.MediaLakeLauncher.Close = on_close
    
    # Show window and run event loop
    win.Show()
    dispatcher.RunLoop()
    win.Hide()


def main():
    """Main entry point."""
    # Always try to launch directly first for simplicity
    # The dialog approach has event handling issues in some Resolve versions
    try:
        launch_medialake_external()
    except Exception as e:
        # If direct launch fails and we're in Resolve, show a dialog with error
        if RUNNING_IN_RESOLVE and fusion_obj is not None:
            ui = fusion_obj.UIManager
            dispatcher = bmd.UIDispatcher(ui)  # noqa: F821
            
            win = dispatcher.AddWindow(
                {'ID': 'ErrorDialog', 'WindowTitle': 'Media Lake Error', 'Geometry': [400, 300, 400, 150]},
                ui.VGroup([
                    ui.Label({'Text': f'Failed to launch Media Lake:\n{str(e)}', 'WordWrap': True}),
                    ui.Button({'ID': 'OKBtn', 'Text': 'OK'}),
                ])
            )
            
            def on_ok(ev):
                dispatcher.ExitLoop()
            
            win.On.OKBtn.Clicked = on_ok
            win.On.ErrorDialog.Close = on_ok
            win.Show()
            dispatcher.RunLoop()
            win.Hide()


if __name__ == "__main__":
    main()
